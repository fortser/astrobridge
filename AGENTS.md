# Repository Guidelines

## Project Structure & Module Organization

AstroBridge is a Python 3.10+ package for reproducible astronomy archive access. Keep application code in `src/astrobridge/`: `core.py` coordinates runs and provenance, `providers.py` implements archive adapters, `network.py` owns HTTP/proxy behavior, and `cli.py` and `gui.py` provide entry points. Put focused tests in `tests/`, using `test_<area>.py`; shared fixtures belong in `tests/conftest.py`. Store runnable request examples in `examples/`, documentation in `docs/`, and maintenance checks in `scripts/`. Runtime artifacts go under `workspace/`, which is ignored by Git.

## Build, Test, and Development Commands

On Windows, install the local environment with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

Run the CLI through `.\astrobridge.cmd doctor` or `.\astrobridge.cmd run examples\exoplanets.json`. Start the optional desktop interface with `.\start_gui.cmd`. For manual cross-platform development, use `python -m pip install -e '.[gui,dev]'`.

Run the unit suite with `.venv\Scripts\python.exe -m pytest -q`. Validate catalog examples, command snippets, and local links with `.venv\Scripts\python.exe scripts\validate_data_catalog.py`. `scripts\live_check.py simbad exoplanet mast` makes real network requests; use it only when validating an affected remote provider.

## Coding Style & Naming Conventions

Follow the existing Python style: four-space indentation, standard-library imports first, and concise module and function names in `snake_case`. Use `PascalCase` for classes, such as `Bridge` and `Settings`, and descriptive `test_<behavior>` test names. Preserve explicit request validation, provenance files, safe URL handling, and secret redaction when changing providers or transport code. No formatter or linter is configured; keep edits consistent with adjacent code.

## Testing Guidelines

Add regression coverage for behavior changes, especially validation failures, proxy handling, response parsing, and artifact integrity. Prefer isolated tests using `tmp_path`, fixtures, and local test servers; do not make the normal test suite depend on public archive availability. Run the full pytest suite before submitting.

## Commit & Pull Request Guidelines

This repository has no committed Git history, so no established commit-message convention exists. Use short imperative subjects (for example, `Validate malformed TAP responses`). Keep commits scoped to one change. Pull requests should explain the user-visible behavior, list validation performed, link relevant issues, and include screenshots for GUI changes. Do not commit `workspace/` artifacts, virtual environments, credentials, proxy URLs with passwords, or local `*.local.json` configuration.
