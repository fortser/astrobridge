"""Adapters return Result and never open network connections outside Transport."""
from dataclasses import replace
from io import StringIO
import csv
import json
import os
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlencode, urlsplit

from astropy.table import Table
from defusedxml import ElementTree
import pyvo

from .errors import BridgeError, Cancelled
from .network import VOSession
from .tables import Result, from_rows, from_votable


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def identifier(value):
    if not re.fullmatch(r'(?:[A-Za-z_][\w]*|"[^"\r\n]+")(?:(?:\.)(?:[A-Za-z_][\w]*|"[^"\r\n]+"))*', value):
        raise BridgeError("validation", "Некорректный ADQL identifier. Для сложного запроса используйте tap.query.")
    return value


def adql(service, operation, p, limit):
    if operation == "tap.query":
        query = p["query"]
        clean = re.sub(r"--[^\n]*|/\*.*?\*/", " ", query, flags=re.S).strip()
        if not re.match(r"SELECT\b", clean, re.I):
            raise BridgeError("validation", "Допускается только ADQL SELECT.")
        return query
    if operation == "tap.tables":
        query = f"SELECT TOP {limit} schema_name,table_name,description FROM TAP_SCHEMA.tables"
        if p.get("contains"):
            term = literal("%" + p["contains"] + "%")
            query += f" WHERE table_name LIKE {term} OR description LIKE {term}"
        return query + " ORDER BY table_name"
    if operation == "tap.columns":
        return f"SELECT TOP {limit} column_name,datatype,unit,ucd,description FROM TAP_SCHEMA.columns WHERE table_name={literal(p['table'])}"
    if operation == "simbad.resolve":
        return f"SELECT TOP {limit} b.main_id,b.ra,b.dec,b.otype FROM basic AS b JOIN ident AS i ON b.oid=i.oidref WHERE i.id={literal(p['name'])}"
    table = p.get("table", service.get("table"))
    if not table:
        raise BridgeError("validation", "Укажите table; сначала используйте tap.tables и tap.columns.")
    ra = identifier(p.get("ra_column", service.get("ra_column", "ra")))
    dec = identifier(p.get("dec_column", service.get("dec_column", "dec")))
    names = p.get("columns", service.get("columns", "*"))
    names = "*" if names == "*" else ",".join(identifier(x.strip()) for x in names.split(","))
    return (f"SELECT TOP {limit} {names} FROM {identifier(table)} WHERE 1=CONTAINS("
            f"POINT('ICRS',{ra},{dec}),CIRCLE('ICRS',{p['ra']},{p['dec']},{p['radius']}))")


def tap(service, operation, params, limit, transport):
    query = adql(service, operation, params, limit)
    (transport.run_dir / "query.adql").write_text(query, encoding="utf-8")
    session = VOSession(transport)
    client = pyvo.dal.TAPService(service["url"], session=session)
    job = None
    complete = False
    job_info = {}
    try:
        if params.get("async", False):
            job = client.submit_job(query, maxrec=limit)
            job_info["job_url"] = job.url
            (transport.run_dir / "remote-job.json").write_text(json.dumps(job_info), encoding="utf-8")
            job.run()
            deadline = time.monotonic() + transport.settings.job_timeout
            while True:
                transport.check()
                phase = job.phase
                transport.progress(f"TAP async: {phase}")
                if phase == "COMPLETED":
                    break
                if phase in {"ERROR", "ABORTED"}:
                    raise BridgeError("query", f"TAP job: {phase}. См. remote-job.json и исходные ответы.")
                if time.monotonic() >= deadline:
                    raise BridgeError("timeout", "Превышен бюджет ожидания TAP job.", retryable=True)
                transport.wait(2)
            job.fetch_result()
        else:
            client.run_sync(query, maxrec=limit)
        # Parsing ourselves preserves QUERY_STATUS and explicit overflow semantics.
        content = (transport.run_dir / transport.records[-1]["file"]).read_bytes()
        result = from_votable(content, limit)
        result.metadata.update({"query": query, "release": service.get("release", "unspecified"), **job_info})
        complete = True
        return result
    except (BridgeError, KeyboardInterrupt):
        raise
    except Exception as exc:
        cause = getattr(exc, "cause", None)
        if isinstance(cause, BridgeError):
            raise cause
        # Do not interpolate pyvo/requests exceptions: URLs can contain credentials.
        raise BridgeError("vo", f"Ошибка VO ({type(exc).__name__}). Проверьте ADQL и raw-ответы; сервис мог быть недоступен.") from None
    finally:
        if job is not None and not complete:
            # Best effort abort of this invocation's own job, with a short timeout.
            original_cancel, original_settings = transport.cancel, transport.settings
            try:
                transport.cancel = threading.Event()
                transport.settings = replace(original_settings, timeout=5, retries=0, job_timeout=10)
                job.abort()
                job_info["abort_requested"] = True
            except Exception:
                job_info["abort_requested"] = False
            finally:
                transport.cancel, transport.settings = original_cancel, original_settings
                (transport.run_dir / "remote-job.json").write_text(json.dumps(job_info), encoding="utf-8")


def mast(service, operation, p, limit, transport):
    limit = min(limit, 10000)
    if operation == "mast.cone":
        name, args = "Mast.Caom.Cone", {key: p[key] for key in ("ra", "dec", "radius")}
    elif operation == "mast.products":
        name, args = "Mast.Caom.Products", {"obsid": p["obsid"]}
    else:
        name, args = "Mast.Caom.Filtered", {"columns": "*", "filters": p["filters"]}
    request = {"service": name, "params": args, "format": "json", "pagesize": limit, "page": p.get("page", 1)}
    deadline = time.monotonic() + transport.settings.job_timeout
    while True:
        response = transport.request("POST", service["url"], data={"request": json.dumps(request)}, retry_read=True)
        data = response.json()
        status = data.get("status", "").upper()
        if status == "EXECUTING":
            if time.monotonic() > deadline:
                raise BridgeError("timeout", "MAST не завершил запрос за отведённое время.", retryable=True)
            transport.wait(2)
            continue
        if status != "COMPLETE":
            raise BridgeError("query", "MAST отклонил запрос. Подробности в raw-ответе.")
        result = from_rows(data.get("data", []), data.get("fields"), limit)
        paging = data.get("paging", {})
        result.metadata.update({"paging": paging, "request": request})
        result.truncated |= int(paging.get("pagesFiltered", 1)) > int(request["page"])
        if result.truncated or len(result.table) == limit:
            result.warnings.append("MAST: возможны следующие страницы; увеличьте params.page, не считайте эту страницу полной выборкой.")
        return result


def horizons(service, operation, p, limit, transport):
    modes = {"vectors": "VECTORS", "ephemerides": "OBSERVER", "elements": "ELEMENTS"}
    valid_scales = {"vectors": {"UT", "TDB"}, "ephemerides": {"UT", "TT"}, "elements": {"TDB"}}
    if p["time_scale"] not in valid_scales[p["kind"]]:
        raise BridgeError("validation", "Шкала времени несовместима с выбранным режимом Horizons.")
    params = {"COMMAND": p["target"], "CENTER": p["center"], "START_TIME": p["start"], "STOP_TIME": p["stop"],
              "STEP_SIZE": p["step"], "EPHEM_TYPE": modes[p["kind"]], "TIME_TYPE": p["time_scale"],
              "CSV_FORMAT": "YES", "OBJ_DATA": "YES", "MAKE_EPHEM": "YES", "REF_SYSTEM": "ICRF"}
    if p["kind"] != "ephemerides":
        params.update(REF_PLANE=p.get("ref_plane", "FRAME"), OUT_UNITS="AU-D")
    if p["kind"] == "vectors":
        params["VEC_CORR"] = p.get("corrections", "NONE")
    if p["kind"] == "ephemerides":
        params["QUANTITIES"] = p.get("quantities", "1,9,20,23")
    if any("'" in v or "\n" in v or "\r" in v for v in params.values()):
        raise BridgeError("validation", "Кавычки и переводы строк в параметрах Horizons не допускаются.")
    response = transport.request("GET", service["url"], params={"format": "json", **{k: f"'{v}'" for k, v in params.items()}})
    data = response.json()
    text = data.get("result", "")
    if data.get("error") or "$$SOE" not in text or "$$EOE" not in text:
        raise BridgeError("query", "Horizons не вернул эфемериды. Проверьте target/center/время; ответ сохранён.")
    (transport.run_dir / "horizons.txt").write_text(text, encoding="utf-8")
    before, body = text.split("$$SOE", 1)
    body = body.split("$$EOE", 1)[0].strip()
    lines = list(csv.reader(StringIO(body), skipinitialspace=True))
    # Retain strings rather than guessing physical types/units from variable output.
    width = len(lines[0]) if lines else 0
    headings = next((next(csv.reader([line], skipinitialspace=True)) for line in reversed(before.splitlines())
                     if "," in line and ("JD" in line or "Date__(" in line)), [])
    names, used = [], set()
    for i in range(width):
        name = headings[i].strip() if i < len(headings) else ""
        name = name or f"column_{i + 1}"
        if name in used:
            name = f"{name}_{i + 1}"
        used.add(name)
        names.append(name)
    result = from_rows([dict(zip(names, [x.strip() for x in row])) for row in lines], limit=limit)
    result.metadata.update({"horizons_parameters": params, "signature": data.get("signature"), "raw_text": "horizons.txt", "column_values": "strings; consult the original Horizons header for units"})
    result.warnings.append("Horizons: единицы и определения колонок смотрите в horizons.txt; значения не преобразованы автоматически.")
    return result


def literature(service, operation, p, limit, transport):
    kind = service["kind"]
    offset = p.get("offset", 0)
    limit = min(limit, 200 if kind == "ads" else 1000)
    if kind == "ads":
        token = os.environ.get(service.get("auth_env", "ADS_TOKEN"))
        if not token:
            raise BridgeError("authentication", "Для ADS задайте ADS_TOKEN в окружении.")
        if urlsplit(service["url"]).hostname != "api.adsabs.harvard.edu":
            raise BridgeError("authentication", "ADS token отправляется только на api.adsabs.harvard.edu.")
        response = transport.request("GET", service["url"], params={"q": p["query"], "rows": limit, "start": offset,
                                       "fl": "bibcode,title,author,year,doi,abstract,citation_count"}, headers={"Authorization": f"Bearer {token}"})
        payload = response.json()["response"]
        rows, total = payload["docs"], payload["numFound"]
    elif kind == "crossref":
        response = transport.request("GET", service["url"], params={"query": p["query"], "rows": limit, "offset": offset})
        payload = response.json()["message"]
        rows, total = payload["items"], payload["total-results"]
    else:
        response = transport.request("GET", service["url"], params={"search_query": p["query"], "start": offset, "max_results": limit})
        root = ElementTree.fromstring(response.content)
        ns = {"a": "http://www.w3.org/2005/Atom", "o": "http://a9.com/-/spec/opensearch/1.1/"}
        rows = []
        for entry in root.findall("a:entry", ns):
            if "/api/errors" in entry.findtext("a:id", "", namespaces=ns):
                raise BridgeError("query", "arXiv отклонил поисковый запрос; подробности в raw-ответе.")
            rows.append({"id": entry.findtext("a:id", namespaces=ns), "title": entry.findtext("a:title", namespaces=ns),
                         "abstract": entry.findtext("a:summary", namespaces=ns), "published": entry.findtext("a:published", namespaces=ns),
                         "authors": [node.findtext("a:name", namespaces=ns) for node in entry.findall("a:author", ns)]})
        total = int(root.findtext("o:totalResults", str(len(rows)), namespaces=ns))
    result = from_rows(rows, limit=limit)
    result.metadata.update({"total": total, "offset": offset, "next_offset": offset + len(rows) if offset + len(rows) < total else None})
    result.truncated = offset + len(rows) < total
    if result.truncated:
        result.warnings.append("Показана страница поиска; используйте next_offset для продолжения.")
    return result


def vo_search(service, operation, p, limit, transport):
    session = VOSession(transport)
    if operation == "vo.sia":
        client = pyvo.dal.SIAService(service["url"], session=session)
        client.search(pos=(p["ra"], p["dec"]), size=p["size"])
    else:
        client = pyvo.dal.SSAService(service["url"], session=session)
        client.search(pos=(p["ra"], p["dec"]), diameter=p["diameter"])
    return from_votable((transport.run_dir / transport.records[-1]["file"]).read_bytes(), limit)


def download(service, operation, p, limit, transport):
    url = p["url"]
    if url.startswith("mast:"):
        url = "https://mast.stsci.edu/api/v0.1/Download/file?" + urlencode({"uri": url})
    filename = p.get("filename") or Path(urlsplit(url).path).name or "download.bin"
    reserved = {".", "..", "request.json", "manifest.json", "manifest.tmp", "table.ecsv", "remote-job.json", "query.adql", "horizons.txt"}
    windows_device = re.match(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", filename, re.I)
    if filename in reserved or windows_device or not re.fullmatch(r"[\w. -]+", filename) or filename.startswith("raw-") or filename.endswith((".", " ")):
        raise BridgeError("validation", "filename должен быть простым именем файла без пути и служебных имён.")
    max_mb = min(p.get("max_mb", transport.settings.max_download_mb), transport.settings.max_download_mb)
    path = transport.download(url, filename, max_mb)
    return Result(metadata={"download": path.name, "bytes": path.stat().st_size})


HANDLERS = {"tap": tap, "mast": mast, "horizons": horizons, "ads": literature, "crossref": literature, "arxiv": literature, "sia": vo_search, "ssa": vo_search}


def register_handler(kind, handler):
    """Python extension hook: callable(service, operation, params, limit, transport)."""
    HANDLERS[kind] = handler
