"""Small real-network smoke queries. No credentials, no bulk downloads."""
import json
from pathlib import Path
import sys

from astrobridge.config import Settings
from astrobridge.core import Bridge


def main():
    bridge = Bridge(Settings(workspace="workspace/live", timeout=20, job_timeout=90, retries=0))
    queries = [
        {"service": "gaia", "operation": "tap.cone", "params": {"ra": 56.75, "dec": 24.12, "radius": 0.005}},
        {"service": "simbad", "operation": "simbad.resolve", "params": {"name": "M31"}},
        {"service": "exoplanet", "operation": "tap.query", "params": {"query": "SELECT TOP 2 pl_name,pl_orbper FROM pscomppars"}},
        {"service": "vizier", "operation": "tap.query", "params": {"query": 'SELECT TOP 2 Source,RA_ICRS,DE_ICRS FROM "I/355/gaiadr3"'}},
        {"service": "mast", "operation": "mast.cone", "params": {"ra": 10.6847, "dec": 41.269, "radius": 0.005}},
        {"service": "crossref", "operation": "literature.search", "params": {"query": "exoplanet atmosphere"}},
        json.loads(Path("examples/mars_vectors.json").read_text()),
        json.loads(Path("examples/arxiv.json").read_text()),
        json.loads(Path("examples/registry_tap.json").read_text()),
        *[{"service": name, "operation": "tap.query", "params": {"query": "SELECT TOP 2 table_name FROM TAP_SCHEMA.tables"}} for name in ("heasarc", "irsa", "cadc")],
    ]
    # Optional service selection makes repeat verification small and targeted.
    selected = set(sys.argv[1:])
    report = []
    for req in queries:
        if selected and req["service"] not in selected:
            continue
        req.update(limit=2, cache=False)
        result = bridge.run(req)
        item = {"service": req["service"], "status": result["status"], "rows": result.get("row_count"), "error": result.get("error"), "run_id": result["run_id"], "time": result["finished_at"]}
        report.append(item)
        print(json.dumps(item, ensure_ascii=True), flush=True)
    return 0 if all(item["status"] == "success" for item in report) else 1


if __name__ == "__main__":
    raise SystemExit(main())
