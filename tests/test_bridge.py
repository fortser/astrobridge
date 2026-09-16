import json
from pathlib import Path
import subprocess
import sys
import threading

import pytest
from astropy.table import Table

from astrobridge.config import Settings
from astrobridge.core import Bridge, HANDLERS
from astrobridge.errors import BridgeError
from astrobridge.network import Transport
from astrobridge.tables import from_votable
from conftest import VOTABLE


def request(**params):
    return {"service": "test", "operation": "tap.query", "params": {"query": "SELECT TOP 2 * FROM sample", **params}, "limit": 2}


def test_tap_scientific_data_cache_and_exports(bridge, server, tmp_path):
    manifest = bridge.run(request())
    assert manifest["status"] == "success", manifest
    assert manifest["row_count"] == 2
    assert manifest["columns"][1]["unit"] == "deg"
    assert manifest["columns"][1]["ucd"] == "pos.eq.ra"
    rows = bridge.response(manifest)["rows"]
    assert rows[0]["source_id"] == "9007199254740993"  # no JS/LLM integer rounding
    assert rows[1]["ra"] is None
    assert (Path(manifest["directory"]) / "raw-0001.bin").read_bytes() == VOTABLE
    calls = len(server[1])
    assert bridge.run(request())["cache_hit"]
    assert len(server[1]) == calls
    for fmt in ("ecsv", "fits", "votable", "json", "csv"):
        output = tmp_path / ("export." + fmt)
        exported = bridge.export(manifest["run_id"], output, fmt)
        assert output.exists() and len(exported["sha256"]) == 64
    table = Table.read(tmp_path / "export.ecsv", format="ascii.ecsv")
    assert int(table["source_id"][0]) == 9007199254740993
    with pytest.raises(BridgeError):
        bridge.export(manifest["run_id"], tmp_path / "export.ecsv", "ecsv")


def test_cache_detects_modified_artifact(bridge, server):
    manifest = bridge.run(request())
    (Path(manifest["directory"]) / "raw-0001.bin").write_bytes(b"changed")
    second = bridge.run(request())
    assert not second["cache_hit"]
    assert second["run_id"] != manifest["run_id"]


def test_unicode_tables_survive_locale_and_text_exports(bridge, tmp_path, monkeypatch):
    import builtins
    import io
    from astrobridge.tables import Result

    # Model Windows cp1251 even when tests run in Python UTF-8 mode or on Linux.
    def locale_open(original):
        def open_file(file, mode="r", buffering=-1, encoding=None, *args, **kwargs):
            if "b" not in mode and encoding is None:
                encoding = "cp1251"
            return original(file, mode, buffering, encoding, *args, **kwargs)
        return open_file

    monkeypatch.setattr(builtins, "open", locale_open(builtins.open))
    monkeypatch.setattr(io, "open", locale_open(io.open))
    value = "Ångström — звезда 星"
    monkeypatch.setitem(HANDLERS, "tap", lambda *args: Result(Table({"title": [value]})))
    manifest = bridge.run(request())
    assert manifest["status"] == "success", manifest
    assert bridge.response(manifest)["rows"][0]["title"] == value
    assert bridge.run(request())["cache_hit"]
    for fmt in ("csv", "ecsv"):
        output = tmp_path / ("unicode." + fmt)
        bridge.export(manifest["run_id"], output, fmt)
        assert value in output.read_text(encoding="utf-8")
        restored = Table.read(output, format="ascii." + fmt, encoding="utf-8", fast_reader=False)
        assert restored["title"][0] == value
        with pytest.raises(BridgeError, match="уже существует"):
            bridge.export(manifest["run_id"], output, fmt)


@pytest.mark.parametrize("status,retryable", [(400, False), (429, True)])
def test_tap_http_error_is_preserved_in_manifest(bridge, server, status, retryable):
    server[2]["http_error"] = status
    manifest = bridge.run(request())
    assert manifest["status"] == "error"
    assert manifest["error"]["code"] == "http"
    assert manifest["error"]["retryable"] is retryable
    assert manifest["http"][0]["status"] == status
    assert bridge.result(manifest["run_id"])["http"] == manifest["http"]
    assert not (Path(manifest["directory"]) / "table.ecsv").exists()


def test_async_uses_same_transport(bridge, server):
    manifest = bridge.run(request(**{"async": True}))
    assert manifest["status"] == "success", manifest
    assert manifest["row_count"] == 2
    assert manifest["metadata"]["job_url"].endswith("/tap/async/1")
    assert any("/phase" in call[1] for call in server[1])
    assert len(manifest["http"]) >= 4


def test_overflow_is_not_silent(bridge, server):
    server[2]["overflow"] = True
    result = bridge.run(request())
    assert result["status"] == "success", result
    assert result["truncated"]
    assert result["warnings"]


@pytest.mark.parametrize("change", [{"limit": 0}, {"unknown": 1}, {"service": "nonexistent"}, {"params": {"query": "SELECT 1", "password": "secret"}}, {"params": {"query": "DROP TABLE sample"}}])
def test_invalid_requests_never_reach_network(bridge, server, change):
    try:
        result = bridge.run({**request(), **change})
        assert result["status"] == "error"
    except BridgeError:
        pass
    assert not server[1]


def test_error_and_cancel_do_not_fake_data(bridge, server):
    server[2]["fail"] = True
    result = bridge.run(request())
    assert result["status"] == "error"
    assert not (Path(result["directory"]) / "table.ecsv").exists()
    event = threading.Event()
    event.set()
    result = bridge.run(request(), cancel=event)
    assert result["status"] == "cancelled"


def test_xml_entities_rejected():
    evil = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e "EXPANSION">]><VOTABLE>&e;</VOTABLE>'
    with pytest.raises(BridgeError):
        from_votable(evil, 10)


def test_download_limits_and_no_overwrite(bridge, server, tmp_path):
    base = server[0]
    result = bridge.run({"service": "test", "operation": "download", "params": {"url": base + "/file", "filename": "test.fits"}})
    assert result["status"] == "success"
    assert (Path(result["directory"]) / "test.fits").read_bytes() == b"FITS-like-test-content"
    capped = bridge.run({"service": "test", "operation": "download", "params": {"url": base + "/large", "max_mb": 0.001}})
    assert capped["error"]["code"] == "size_limit"
    assert not (Path(capped["directory"]) / "large").exists()
    existing = tmp_path / "existing"
    existing.write_bytes(b"keep me")
    with Transport(bridge.settings, tmp_path).session as session:
        response = session.get(base + "/file", stream=True)
        with pytest.raises(FileExistsError):
            Transport(bridge.settings, tmp_path)._receive(response, existing, 1)
        response.close()
    assert existing.read_bytes() == b"keep me"


def test_mast_download_uses_uri_basename(bridge, monkeypatch):
    def fake_download(transport, url, filename, max_mb):
        path = transport.run_dir / filename
        path.write_bytes(b"fixture")
        return path

    monkeypatch.setattr(Transport, "download", fake_download)
    result = bridge.run({"service": "mast", "operation": "download",
                         "params": {"url": "mast:JWST/product/example_cal.fits"}})
    assert result["status"] == "success", result
    assert result["metadata"]["download"] == "example_cal.fits"
    assert (Path(result["directory"]) / "example_cal.fits").read_bytes() == b"fixture"


@pytest.mark.parametrize("name", ["../oops", "CON", "manifest.json", "raw-0001.bin", "C:\\data.txt"])
def test_download_rejects_unsafe_names(bridge, server, name):
    result = bridge.run({"service": "test", "operation": "download", "params": {"url": server[0] + "/file", "filename": name}})
    assert result["status"] == "error"
    assert not server[1]


def test_mast_pagination_and_nested_literature(tmp_path, server):
    base = server[0]
    bridge = Bridge(Settings(workspace=str(tmp_path), proxy_mode="direct", min_interval=0, services={
        "mast": {"url": base + "/mast"}, "crossref": {"url": base + "/crossref"}, "horizons": {"url": base + "/horizons"}}))
    result = bridge.run({"service": "mast", "operation": "mast.products", "params": {"obsid": "123"}, "limit": 1})
    assert result["status"] == "success", result
    assert result["truncated"]
    result = bridge.run({"service": "crossref", "operation": "literature.search", "params": {"query": "test"}, "limit": 1})
    assert result["status"] == "success", result
    assert result["metadata"]["next_offset"] == 1
    assert json.loads(bridge.response(result)["rows"][0]["title"]) == ["A title"]
    result = bridge.run({"service": "horizons", "operation": "horizons.query", "params": {
        "target": "499", "center": "500@399", "start": "2026-01-01", "stop": "2026-01-02", "step": "1d", "time_scale": "TDB", "kind": "vectors"}})
    assert result["status"] == "success", result
    assert result["metadata"]["horizons_parameters"]["VEC_CORR"] == "NONE"
    assert bridge.response(result)["rows"][0]["X"] == "1.0"


def test_cli_stdout_is_json_and_invalid_args_are_json(tmp_path):
    proc = subprocess.run([sys.executable, "-m", "astrobridge", "schema"], capture_output=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["type"] == "object"
    proc = subprocess.run([sys.executable, "-m", "astrobridge", "resolve"], capture_output=True, encoding="utf-8")
    assert proc.returncode == 2
    assert json.loads(proc.stdout)["error"]["code"] == "usage"


def test_ads_missing_token_is_actionable(bridge, monkeypatch):
    monkeypatch.delenv("ADS_TOKEN", raising=False)
    result = bridge.run({"service": "ads", "operation": "literature.search", "params": {"query": "star"}})
    assert result["error"]["code"] == "authentication"


def test_async_cancel_sends_abort(bridge, server):
    server[2]["hold"] = True
    event = threading.Event()
    def progress(message):
        if "EXECUTING" in message:
            event.set()
    result = bridge.run(request(**{"async": True}), cancel=event, progress=progress)
    assert result["status"] == "cancelled", result
    assert server[2]["phase"] == "ABORTED"
    job = json.loads((Path(result["directory"]) / "remote-job.json").read_text())
    assert job["abort_requested"]


def test_arxiv_and_generic_vo_adapters(tmp_path, server):
    base = server[0]
    bridge = Bridge(Settings(workspace=str(tmp_path), proxy_mode="direct", min_interval=0, services={
        "arxiv": {"url": base + "/arxiv"}, "images": {"kind": "sia", "url": base + "/sia"}, "spectra": {"kind": "ssa", "url": base + "/ssa"}}))
    response = bridge.run({"service": "arxiv", "operation": "literature.search", "params": {"query": "fixture"}})
    assert response["status"] == "success", response
    assert response["metadata"]["total"] == 1
    assert json.loads(bridge.response(response)["rows"][0]["authors"]) == ["Fixture Author"]
    for service, op, parameter in [("images", "vo.sia", "size"), ("spectra", "vo.ssa", "diameter")]:
        response = bridge.run({"service": service, "operation": op, "params": {"ra": 10, "dec": 20, parameter: 0.1}})
        assert response["status"] == "success", response


def test_cli_stdin_unicode_and_batch(bridge, tmp_path):
    config = tmp_path / "config.json"
    bridge.settings.save(config)
    req = request()
    req["release"] = "Проверка кириллицы"
    command = [sys.executable, "-m", "astrobridge", "--config", str(config), "--quiet"]
    proc = subprocess.run(command + ["run", "-", "--preview", "1"], input=json.dumps(req, ensure_ascii=False), text=True, encoding="utf-8", capture_output=True)
    assert proc.returncode == 0, proc.stdout
    response = json.loads(proc.stdout)
    assert response["release"] == "Проверка кириллицы"
    assert response["page"]["next_offset"] == 1
    proc = subprocess.run(command + ["batch", "-", "--preview", "0"], input=json.dumps(req) + "\nnot-json\n" + json.dumps(req), text=True, encoding="utf-8", capture_output=True)
    assert proc.returncode == 1
    assert [json.loads(line)["status"] for line in proc.stdout.splitlines()] == ["success", "error", "success"]


def test_nonfinite_coordinates_are_rejected(bridge, server):
    with pytest.raises(BridgeError):
        bridge.run({"service": "gaia", "operation": "tap.cone", "params": {"ra": float("nan"), "dec": 0, "radius": 1}})
    assert not server[1]


def test_explicit_missing_config_does_not_fall_back(tmp_path):
    from astrobridge.config import load_settings
    with pytest.raises(BridgeError, match="не найден"):
        load_settings(tmp_path / "missing-config.json")


def test_corrupted_stored_table_detected(bridge):
    result = bridge.run(request())
    (Path(result["directory"]) / "table.ecsv").write_bytes(b"corrupted")
    with pytest.raises(BridgeError) as exc:
        bridge.table(result["run_id"])
    assert exc.value.code == "integrity"
