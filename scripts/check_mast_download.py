"""Verify MAST products and one public file (at most 20 MiB)."""
import json
from astrobridge.core import Bridge
from astrobridge.config import Settings

bridge = Bridge(Settings(workspace="workspace/live", timeout=30, retries=0))
observation_run = next(m for m in bridge.history() if m["status"] == "success" and m["request"]["operation"] == "mast.cone")
observations = bridge.table(observation_run["run_id"])
obsid = str(observations["obsid"][0])
result = bridge.run({"service": "mast", "operation": "mast.products", "params": {"obsid": obsid}, "limit": 30})
print(json.dumps({"step": "products", "status": result["status"], "run_id": result["run_id"], "rows": result.get("row_count"), "error": result.get("error")}), flush=True)
if result["status"] == "success":
    products = bridge.table(result["run_id"])
    for row in products:
        try:
            size = int(row["size"])
        except (ValueError, TypeError):
            continue
        if 0 < size < 20 * 1024 * 1024:
            manifest = bridge.run({"service": "mast", "operation": "download", "params": {"url": str(row["dataURI"]), "filename": str(row["productFilename"]), "max_mb": 20}})
            print(json.dumps({"step": "download", "status": manifest["status"], "run_id": manifest["run_id"], "metadata": manifest.get("metadata"), "error": manifest.get("error")}), flush=True)
            if manifest["status"] == "success" and str(row["productFilename"]).endswith(".fits"):
                from pathlib import Path
                from astropy.io import fits
                header = fits.getheader(Path(manifest["directory"]) / manifest["metadata"]["download"])
                print(json.dumps({"fits_SIMPLE": bool(header.get("SIMPLE")), "fits_NAXIS": header.get("NAXIS")}), flush=True)
            break
    else:
        print("No product below 20 MiB found; no download attempted.")
