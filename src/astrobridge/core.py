"""Execution, provenance, reusable cache, and local result paging."""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version, PackageNotFoundError
import json
import os
from pathlib import Path
import re
import threading
import uuid

from astropy.table import Table
from jsonschema import Draft202012Validator

from . import __version__
from .catalog import schema, services, supports
from .config import Settings
from .errors import BridgeError
from .network import Transport
from .providers import HANDLERS, download
from .tables import columns, table_rows
from .util import dumps, reject_secrets, safe_url, sha256_file, utcnow


class Bridge:
    def __init__(self, settings=None):
        self.settings = (settings or Settings()).validate()
        self.services = services(self.settings)
        self.root = Path(self.settings.workspace).resolve()
        (self.root / "runs").mkdir(parents=True, exist_ok=True)

    def validate(self, request):
        errors = sorted(Draft202012Validator(schema()).iter_errors(request), key=lambda e: str(e.path))
        if errors:
            error = errors[0]
            # Do not echo invalid values: a misplaced proxy password may be present.
            path = ".".join(str(x) for x in error.path) or "request"
            raise BridgeError("validation", f"Некорректный {path} (правило {error.validator}); смотрите команду schema.")
        reject_secrets(request)
        if request["service"] not in self.services:
            raise BridgeError("validation", "Неизвестный service; смотрите providers.")
        service = self.services[request["service"]]
        if not supports(service, request["operation"]):
            raise BridgeError("validation", "Операция не поддерживается выбранным сервисом.")
        request = {"limit": 1000, "cache": True, **request}
        if request["operation"] == "download":
            request["cache"] = False
        return request

    def _key(self, request, service):
        value = {"version": __version__, "request": {k: v for k, v in request.items() if k != "cache"}, "provider": service}
        return hashlib.sha256(dumps(value, sort_keys=True).encode()).hexdigest()

    def run(self, request, cancel=None, progress=None):
        request = self.validate(request)
        service = self.services[request["service"]]
        key = self._key(request, service)
        # Never reuse authenticated results across changing credentials.
        use_cache = request["cache"] and service["kind"] != "ads" and not service.get("auth_env")
        if use_cache:
            cached = self._cached(key)
            if cached:
                return {**cached, "cache_hit": True}
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:12]
        folder = self.root / "runs" / run_id
        folder.mkdir()
        (folder / "request.json").write_text(dumps(request, indent=2), encoding="utf-8")
        manifest = {"schema_version": "1.0", "app_version": __version__, "run_id": run_id, "status": "running",
                    "started_at": utcnow(), "request": request, "provider": {**service, "url": safe_url(service["url"])},
                    "cache_key": key, "cache_hit": False, "directory": str(folder), "warnings": [],
                    "network": {"proxy_mode": self.settings.proxy_mode, "tls_verified": True}, "environment": {}}
        for package in ("astropy", "pyvo", "requests", "astrobridge"):
            try:
                manifest["environment"][package] = version(package)
            except PackageNotFoundError:
                pass
        self._write_manifest(folder, manifest)
        transport = None
        try:
            transport = Transport(self.settings, folder, cancel, progress)
            handler = download if request["operation"] == "download" else HANDLERS.get(service["kind"])
            if handler is None:
                raise BridgeError("validation", "Для kind сервиса не зарегистрирован адаптер.")
            result = handler(service, request["operation"], request["params"], request["limit"], transport)
            transport.check()
            if result.table is not None:
                result.table.write(folder / "table.ecsv", format="ascii.ecsv")
            manifest.update(status="success", row_count=len(result.table) if result.table is not None else 0,
                            columns=columns(result.table), truncated=result.truncated, warnings=result.warnings,
                            metadata=result.metadata, release=request.get("release", service.get("release", "unspecified")))
            manifest["limit_reached"] = result.table is not None and len(result.table) >= request["limit"]
        except (KeyboardInterrupt, Exception) as exc:
            if isinstance(exc, KeyboardInterrupt):
                error = BridgeError("cancelled", "Операция прервана пользователем.")
            elif isinstance(exc, BridgeError):
                error = exc
            else:
                error = BridgeError("internal", f"Ошибка адаптера ({type(exc).__name__}); исходные ответы сохранены. Проверьте формат ответа сервиса.")
            manifest.update(status="cancelled" if error.code == "cancelled" else "error", error=error.as_dict())
        finally:
            if transport:
                manifest["http"] = transport.records
                transport.close()
            manifest["finished_at"] = utcnow()
            manifest["artifacts"] = [{"name": p.name, "bytes": p.stat().st_size, "sha256": sha256_file(p)}
                                     for p in sorted(folder.iterdir()) if p.is_file() and p.name != "manifest.json"]
            self._write_manifest(folder, manifest)
        return manifest

    @staticmethod
    def _write_manifest(folder, data):
        temp = folder / "manifest.tmp"
        temp.write_text(dumps(data, indent=2), encoding="utf-8")
        temp.replace(folder / "manifest.json")

    def _cached(self, key):
        for item in self.history(limit=None):
            if item.get("cache_key") != key or item.get("status") != "success":
                continue
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(item["finished_at"])).total_seconds()
            if age > self.settings.cache_ttl_hours * 3600:
                continue
            folder = self.root / "runs" / item["run_id"]
            if all((folder / a["name"]).is_file() and sha256_file(folder / a["name"]) == a["sha256"] for a in item.get("artifacts", [])):
                return item
        return None

    def history(self, limit=50):
        items = []
        for path in sorted((self.root / "runs").glob("*/manifest.json"), reverse=True):
            try:
                items.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
            if limit is not None and len(items) >= limit:
                break
        return items

    def result(self, run_id):
        if not re.fullmatch(r"[0-9]{8}T[0-9]{6}-[0-9a-f]{12}", run_id):
            raise BridgeError("validation", "Некорректный run_id.")
        path = self.root / "runs" / run_id / "manifest.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise BridgeError("not_found", "Результат не найден в выбранном workspace.") from None

    def table(self, run_id):
        manifest = self.result(run_id)
        if manifest["status"] != "success":
            return None
        path = self.root / "runs" / run_id / "table.ecsv"
        artifact = next((a for a in manifest.get("artifacts", []) if a["name"] == "table.ecsv"), None)
        if artifact and (not path.is_file() or sha256_file(path) != artifact["sha256"]):
            raise BridgeError("integrity", "Сохранённая таблица отсутствует или её SHA-256 изменился.")
        if not path.exists():
            return None
        try:
            return Table.read(path, format="ascii.ecsv")
        except Exception:
            raise BridgeError("parse", "Сохранённая ECSV-таблица не читается.") from None

    def response(self, manifest, offset=0, limit=100):
        table = self.table(manifest["run_id"])
        return {**manifest, "rows": table_rows(table, offset, limit), "page": {"offset": offset, "limit": limit,
                "next_offset": offset + limit if table is not None and offset + limit < len(table) else None}}

    def export(self, run_id, output, fmt):
        table = self.table(run_id)
        if table is None:
            raise BridgeError("validation", "В этом запуске нет таблицы для экспорта.")
        output = Path(output)
        if output.exists():
            raise BridgeError("exists", "Файл экспорта уже существует. Укажите новое имя.")
        output.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "json":
            output.write_text(dumps({"columns": columns(table), "rows": table_rows(table, limit=len(table))}, indent=2), encoding="utf-8")
        else:
            formats = {"csv": "ascii.csv", "ecsv": "ascii.ecsv", "fits": "fits", "votable": "votable"}
            if fmt not in formats:
                raise BridgeError("validation", "Форматы: csv, ecsv, fits, votable, json.")
            table.write(output, format=formats[fmt])
        return {"path": str(output.resolve()), "sha256": sha256_file(output), "format": fmt}
