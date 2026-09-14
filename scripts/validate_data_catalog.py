"""Offline documentation/schema/link checks; no remote requests or file writes."""
import json
from pathlib import Path
import re
import shlex

from astrobridge.catalog import BUILTINS, OPERATIONS
from astrobridge.cli import parser, request_for
from astrobridge.config import Settings, load_settings
from astrobridge.core import Bridge


root = Path(__file__).resolve().parents[1]
bridge = Bridge(Settings(workspace=str(root / "workspace/catalog_validation")))
requests = 0
for path in sorted((root / "examples/catalog").glob("*.json*")):
    if path.name == "custom_tap.json":
        load_settings(str(path))
        continue
    content = path.read_text(encoding="utf-8")
    items = [json.loads(line) for line in content.splitlines() if line.strip()] if path.suffix == ".jsonl" else [json.loads(content)]
    for request in items:
        bridge.validate(request)
        requests += 1

document = (root / "DATA_CATALOG.md").read_text(encoding="utf-8")
commands = 0
for line in document.splitlines():
    if not line.startswith(".\\astrobridge.cmd "):
        continue
    argv = shlex.split(line)[1:]
    if "--help" in argv:
        continue
    args = parser().parse_args(argv)
    active = bridge
    if args.config:
        active = Bridge(load_settings(str(root / args.config)))
    if args.command in {"query", "cone", "resolve", "tables", "columns", "download"}:
        active.validate(request_for(args))
    elif args.command in {"run", "batch"}:
        assert (root / args.file).is_file(), args.file
    commands += 1

for target in re.findall(r"\]\(([^)]+)\)", document):
    if target.startswith(("https://", "http://", "#")):
        continue
    assert (root / target.split("#", 1)[0]).exists(), target
assert len(BUILTINS) == 13
assert len(OPERATIONS) == 13
for operation in OPERATIONS:
    assert f"`{operation}`" in document, operation
print(json.dumps({"status": "success", "json_requests_validated": requests,
                  "cli_examples_parsed": commands, "providers": len(BUILTINS),
                  "operations": len(OPERATIONS), "local_links": "ok",
                  "note": "Offline checks do not prove remote ADQL validity or network availability."}))
