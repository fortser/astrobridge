"""Export previously fetched TAP table inventories; makes no network requests."""
from pathlib import Path
import json

from astrobridge.config import Settings
from astrobridge.core import Bridge

bridge = Bridge(Settings(workspace="workspace/data_catalog"))
directory = Path("docs/catalog_inventory")
directory.mkdir(parents=True, exist_ok=True)
seen, index = set(), []
for result in bridge.history(limit=None):
    service = result["request"]["service"]
    if result["request"]["operation"] != "tap.tables" or service in seen:
        continue
    seen.add(service)
    entry = {"service": service, "status": result["status"], "run_id": result["run_id"],
             "retrieved_at": result["finished_at"], "rows": result.get("row_count"),
             "truncated": result.get("truncated"), "limit_reached": result.get("limit_reached"),
             "endpoint": result["provider"]["url"], "error": result.get("error")}
    if result["status"] == "success":
        target = directory / (service + ".csv")
        if not target.exists():
            bridge.export(result["run_id"], target, "csv")
        entry["file"] = target.name
    index.append(entry)
path = directory / "index.json"
if path.exists():
    raise SystemExit("index.json already exists; use a new output directory for a new snapshot.")
path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(index, ensure_ascii=True, indent=2))
