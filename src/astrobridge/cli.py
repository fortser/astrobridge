"""Stable JSON stdout interface; diagnostics and progress go to stderr."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from . import __version__
from .catalog import OPERATIONS, schema, supports
from .config import Settings, load_settings
from .core import Bridge
from .errors import BridgeError
from .util import dumps


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise BridgeError("usage", "Некорректные аргументы команды; используйте --help.")


def parser():
    p = Parser(prog="astrobridge", description="Astronomy archive bridge. JSON on stdout; --help for command help.")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--config", help="Settings JSON path")
    p.add_argument("--workspace", help="Override result/cache directory")
    p.add_argument("--proxy", help="Manual proxy URL WITHOUT credentials; use ASTROBRIDGE_PROXY for credentials")
    p.add_argument("--direct", action="store_true", help="Ignore proxy environment and use direct connections")
    p.add_argument("--timeout", type=float, help="HTTP read timeout, seconds")
    p.add_argument("--quiet", action="store_true", help="Suppress progress on stderr")
    sub = p.add_subparsers(dest="command", required=True, parser_class=Parser)
    sub.add_parser("providers", help="List services and supported operations")
    sub.add_parser("schema", help="Print full JSON Schema for requests")
    example = sub.add_parser("example", help="Print editable request template")
    example.add_argument("operation", choices=list(OPERATIONS))
    example.add_argument("--service")
    run = sub.add_parser("run", help="Run a JSON request file, or - for stdin")
    run.add_argument("file")
    run.add_argument("--preview", type=int, default=100, help="Rows to include in stdout (all rows retained on disk)")
    run.add_argument("--no-cache", action="store_true")
    batch = sub.add_parser("batch", help="Sequential JSONL requests; one JSON response per line")
    batch.add_argument("file", help="JSONL file or - for stdin")
    batch.add_argument("--preview", type=int, default=10)
    query = sub.add_parser("query", help="Run ADQL against a TAP service")
    query.add_argument("service")
    sql = query.add_mutually_exclusive_group(required=True)
    sql.add_argument("--adql")
    sql.add_argument("--file", help="UTF-8 ADQL file")
    query.add_argument("--async", dest="asynchronous", action="store_true")
    _query_options(query)
    cone = sub.add_parser("cone", help="ICRS cone search, decimal degrees")
    cone.add_argument("service")
    cone.add_argument("--ra", type=float, required=True)
    cone.add_argument("--dec", type=float, required=True)
    cone.add_argument("--radius", type=float, required=True)
    for flag in ("table", "ra-column", "dec-column", "columns"):
        cone.add_argument("--" + flag)
    _query_options(cone)
    resolve = sub.add_parser("resolve", help="Resolve a SIMBAD identifier")
    resolve.add_argument("name")
    _query_options(resolve)
    tables = sub.add_parser("tables", help="Discover TAP tables")
    tables.add_argument("service")
    tables.add_argument("--contains", default="")
    _query_options(tables)
    cols = sub.add_parser("columns", help="Discover TAP columns, units and UCDs")
    cols.add_argument("service")
    cols.add_argument("table")
    _query_options(cols)
    dl = sub.add_parser("download", help="Download one public file with byte cap and checksum")
    dl.add_argument("url")
    dl.add_argument("--filename")
    dl.add_argument("--max-mb", type=float)
    history = sub.add_parser("history", help="Local run history")
    history.add_argument("--limit", type=int, default=50)
    result = sub.add_parser("result", help="Read stored result, with local row pagination")
    result.add_argument("run_id")
    result.add_argument("--offset", type=int, default=0)
    result.add_argument("--limit", type=int, default=100)
    export = sub.add_parser("export", help="Export a stored table without querying the archive")
    export.add_argument("run_id")
    export.add_argument("--output", required=True)
    export.add_argument("--format", required=True, choices=["csv", "ecsv", "fits", "votable", "json"])
    init = sub.add_parser("init", help="Write an example settings file")
    init.add_argument("--output", default="astrobridge.local.json")
    sub.add_parser("doctor", help="Offline environment/configuration diagnostics")
    sub.add_parser("gui", help="Launch the desktop GUI")
    return p


def _query_options(p):
    p.add_argument("--limit", type=int, default=1000)
    p.add_argument("--preview", type=int, default=100)
    p.add_argument("--no-cache", action="store_true")


def read_json(path):
    try:
        return json.loads(sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        raise BridgeError("validation", "Не удалось прочитать UTF-8 JSON-запрос.") from None


def request_for(args):
    command = args.command
    params = {}
    service = getattr(args, "service", "simbad")
    if command == "run":
        request = read_json(args.file)
        if args.no_cache and isinstance(request, dict):
            request["cache"] = False
        return request
    if command == "query":
        params = {"query": args.adql if args.adql is not None else Path(args.file).read_text(encoding="utf-8-sig"), "async": args.asynchronous}
        operation = "tap.query"
    elif command == "cone":
        operation = "mast.cone" if service == "mast" else "tap.cone"
        params = {key: getattr(args, key) for key in ("ra", "dec", "radius", "table", "ra_column", "dec_column", "columns") if getattr(args, key) is not None}
    elif command == "resolve":
        operation, params = "simbad.resolve", {"name": args.name}
    elif command == "tables":
        operation, params = "tap.tables", {"contains": args.contains}
    elif command == "columns":
        operation, params = "tap.columns", {"table": args.table}
    else:
        operation, service = "download", "mast"
        params = {key: getattr(args, key) for key in ("url", "filename", "max_mb") if getattr(args, key) is not None}
    return {"service": service, "operation": operation, "params": params, "limit": getattr(args, "limit", 1000), "cache": not getattr(args, "no_cache", False)}


def emit(data):
    print(dumps(data))


def main(argv=None):
    # Windows pipes may default to a legacy codepage; the CLI contract is UTF-8.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        args = parser().parse_args(argv)
        if args.command == "schema":
            emit(schema())
            return 0
        if args.command == "init":
            if Path(args.output).exists():
                raise BridgeError("exists", "Файл настроек уже существует.")
            Settings().save(args.output)
            emit({"status": "success", "config": str(Path(args.output).resolve())})
            return 0
        settings = load_settings(args.config)
        if args.workspace:
            settings.workspace = args.workspace
        if args.proxy and args.direct:
            raise BridgeError("usage", "Нельзя одновременно использовать --proxy и --direct.")
        if args.proxy:
            settings.proxy_mode, settings.proxy_url = "manual", args.proxy
            # CLI URL wins over default environment only when explicitly selected.
            settings.proxy_env = "ASTROBRIDGE_CLI_PROXY_UNUSED"
        if args.direct:
            settings.proxy_mode = "direct"
        if args.timeout is not None:
            settings.timeout = args.timeout
        settings.validate()
        if args.command == "gui":
            from .gui import main as gui_main
            return gui_main(settings, args.config)
        bridge = Bridge(settings)
        if args.command == "providers":
            emit({name: {**value, "operations": [op for op in OPERATIONS if supports(value, op)]} for name, value in bridge.services.items()})
        elif args.command == "example":
            op = args.operation
            service = args.service or ("gaia" if op.startswith("tap.") else "simbad" if op.startswith("simbad.") else "arxiv" if op.startswith("literature.") else "horizons" if op.startswith("horizons.") else "mast")
            emit({"service": service, "operation": op, "params": OPERATIONS[op]["example"], "limit": 100})
        elif args.command == "doctor":
            from importlib.util import find_spec
            from .network import Transport
            transport = Transport(settings, bridge.root)
            emit({"status": "success", "version": __version__, "workspace": str(bridge.root), "proxy_mode": settings.proxy_mode,
                  "proxy_configured": bool(transport.proxy_map), "gui_available": find_spec("PySide6") is not None,
                  "network_checked": False, "note": "Use resolve M31 --limit 1 --no-cache for a small live test."})
            transport.close()
        elif args.command == "history":
            if args.limit < 1:
                raise BridgeError("validation", "limit должен быть положительным.")
            emit({"runs": [{k: m.get(k) for k in ("run_id", "status", "started_at", "request", "row_count", "truncated")} for m in bridge.history(args.limit)]})
        elif args.command == "result":
            if args.offset < 0 or args.limit < 1:
                raise BridgeError("validation", "offset >= 0, limit >= 1.")
            emit(bridge.response(bridge.result(args.run_id), args.offset, args.limit))
        elif args.command == "export":
            emit(bridge.export(args.run_id, args.output, args.format))
        elif args.command == "batch":
            if args.preview < 0:
                raise BridgeError("validation", "preview >= 0.")
            stream = sys.stdin if args.file == "-" else open(args.file, encoding="utf-8-sig")
            failed = False
            try:
                for line in stream:
                    if not line.strip():
                        continue
                    try:
                        manifest = bridge.run(json.loads(line), progress=None)
                        emit(bridge.response(manifest, limit=args.preview))
                        failed |= manifest["status"] != "success"
                    except (BridgeError, ValueError) as exc:
                        failed = True
                        error = exc if isinstance(exc, BridgeError) else BridgeError("validation", "Некорректная JSONL-строка.")
                        emit({"status": "error", "error": error.as_dict()})
            finally:
                if stream is not sys.stdin:
                    stream.close()
            return 1 if failed else 0
        else:
            preview = getattr(args, "preview", 100)
            if preview < 0:
                raise BridgeError("validation", "preview >= 0.")
            manifest = bridge.run(request_for(args), progress=None if args.quiet else lambda msg: print(msg, file=sys.stderr))
            emit(bridge.response(manifest, limit=preview))
            return 0 if manifest["status"] == "success" else 130 if manifest["status"] == "cancelled" else 1
        return 0
    except BridgeError as exc:
        emit({"schema_version": "1.0", "status": "error", "error": exc.as_dict()})
        return 2 if exc.code in {"usage", "validation", "config"} else 1
    except KeyboardInterrupt:
        emit({"status": "cancelled", "error": {"code": "cancelled", "message": "Interrupted", "retryable": False}})
        return 130
    except Exception as exc:
        emit({"status": "error", "error": {"code": "internal", "message": f"Local error ({type(exc).__name__})", "retryable": False}})
        return 1
