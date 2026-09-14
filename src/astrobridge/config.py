from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

from .errors import BridgeError


@dataclass
class Settings:
    workspace: str = "workspace"
    proxy_mode: str = "environment"
    proxy_url: str = ""
    proxy_env: str = "ASTROBRIDGE_PROXY"
    ca_bundle: str = ""
    timeout: float = 60
    job_timeout: float = 600
    min_interval: float = 1
    retries: int = 2
    max_response_mb: int = 64
    max_download_mb: int = 512
    cache_ttl_hours: float = 24
    services: dict = field(default_factory=dict)

    def validate(self):
        for name in ("workspace", "proxy_mode", "proxy_url", "proxy_env", "ca_bundle"):
            if not isinstance(getattr(self, name), str):
                raise BridgeError("config", f"{name} должен быть строкой.")
        if not self.workspace.strip():
            raise BridgeError("config", "workspace не должен быть пустым.")
        if self.proxy_mode not in {"environment", "manual", "direct"}:
            raise BridgeError("config", "proxy_mode: environment, manual или direct.")
        if self.proxy_url:
            validate_url(self.proxy_url, proxy=True)
            if urlsplit(self.proxy_url).username is not None:
                raise BridgeError("config", "Прокси с паролем задаётся через proxy_env, не в файле настроек.")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", self.proxy_env):
            raise BridgeError("config", "Некорректное имя proxy_env.")
        for name in ("timeout", "job_timeout", "max_response_mb", "max_download_mb"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value < 1e9:
                raise BridgeError("config", f"{name} должен быть положительным числом.")
        for name in ("min_interval", "cache_ttl_hours"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value < 1e9:
                raise BridgeError("config", f"Некорректный {name}.")
        if type(self.retries) is not int or not 0 <= self.retries <= 5:
            raise BridgeError("config", "retries должен быть целым числом от 0 до 5.")
        if self.ca_bundle and not Path(self.ca_bundle).is_file():
            raise BridgeError("config", "Файл CA bundle не найден.")
        if not isinstance(self.services, dict):
            raise BridgeError("config", "services должен быть объектом.")
        from .util import reject_secrets
        reject_secrets(self.services)
        return self

    def save(self, path):
        self.validate()
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")


def load_settings(path=None):
    explicit = path is not None or bool(os.environ.get("ASTROBRIDGE_CONFIG"))
    path = Path(path or os.environ.get("ASTROBRIDGE_CONFIG", "astrobridge.local.json"))
    if not path.exists():
        if explicit:
            raise BridgeError("config", "Явно указанный файл настроек не найден; настройки по умолчанию не применены.")
        return Settings().validate()
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        result = Settings(**data)
        # Relative storage and CA paths belong to the config directory.
        for name in ("workspace", "ca_bundle"):
            value = getattr(result, name)
            if value and not Path(value).is_absolute():
                setattr(result, name, str((path.parent / value).resolve()))
        return result.validate()
    except (TypeError, ValueError, OSError) as exc:
        raise BridgeError("config", "Не удалось прочитать настройки: проверьте JSON и названия полей.") from exc


def validate_url(url, proxy=False):
    try:
        parsed = urlsplit(url)
        schemes = {"http", "https", "socks5", "socks5h", "socks4", "socks4a"} if proxy else {"http", "https"}
        if parsed.scheme not in schemes or not parsed.hostname or parsed.fragment:
            raise ValueError()
        _ = parsed.port
        if not proxy and parsed.username is not None:
            raise ValueError()
    except (ValueError, TypeError):
        raise BridgeError("validation", "Неверный URL или неподдерживаемая схема; credentials в URL сервиса запрещены.") from None
    return url
