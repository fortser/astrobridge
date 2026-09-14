"""One transport for every adapter, including redirects, polling and downloads."""
from datetime import datetime, timezone
from io import BytesIO
from email.utils import parsedate_to_datetime
import os
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit

import requests
from requests.utils import should_bypass_proxies

from .config import validate_url
from .errors import BridgeError, Cancelled
from .util import safe_url, sha256_file, utcnow

_rate_lock = threading.Lock()
_last_request = {}


class Transport:
    def __init__(self, settings, run_dir, cancel=None, progress=None):
        self.settings = settings
        self.run_dir = Path(run_dir)
        self.cancel = cancel or threading.Event()
        self.progress = progress or (lambda message: None)
        self.session = requests.Session()
        # Do not silently consult .netrc or OS proxy settings.
        self.session.trust_env = False
        self.session.headers["User-Agent"] = "AstroBridge/0.1 (astronomy research client)"
        self.session.verify = settings.ca_bundle or os.environ.get("REQUESTS_CA_BUNDLE") or True
        self.records = []
        self.proxy_map, self.no_proxy = self._proxies()

    def _proxies(self):
        s = self.settings
        if s.proxy_mode == "direct":
            return {}, ""
        proxy = os.environ.get(s.proxy_env, "") or s.proxy_url
        if s.proxy_mode == "manual":
            if not proxy:
                raise BridgeError("proxy", f"Укажите proxy_url или переменную {s.proxy_env}.")
            validate_url(proxy, proxy=True)
            return {"http": proxy, "https": proxy}, ""
        if proxy:
            validate_url(proxy, proxy=True)
            return {"http": proxy, "https": proxy}, ""
        env = {key.lower(): value for key, value in os.environ.items()}
        mapping = {scheme: env.get(f"{scheme}_proxy") or env.get("all_proxy", "") for scheme in ("http", "https")}
        mapping = {key: value for key, value in mapping.items() if value}
        for value in mapping.values():
            validate_url(value, proxy=True)
        return mapping, env.get("no_proxy", "")

    def check(self):
        if self.cancel.is_set():
            raise Cancelled()

    def wait(self, seconds):
        if self.cancel.wait(max(0, seconds)):
            raise Cancelled()

    def _throttle(self, host):
        interval = max(self.settings.min_interval, 3.1 if host == "export.arxiv.org" else 0)
        while True:
            self.check()
            with _rate_lock:
                now = time.monotonic()
                delay = _last_request.get(host, 0) + interval - now
                if delay <= 0:
                    _last_request[host] = now
                    return
            self.wait(min(delay, 0.25))

    def _open(self, method, url, *, retry_read=False, **kwargs):
        validate_url(url)
        host = urlsplit(url).hostname
        proxies = self.proxy_map
        if self.no_proxy and should_bypass_proxies(url, no_proxy=self.no_proxy):
            proxies = {}
        attempts = self.settings.retries + 1 if method == "GET" or retry_read else 1
        for attempt in range(attempts):
            self._throttle(host)
            self.progress(f"{method} {host} — попытка {attempt + 1}")
            try:
                response = self.session.request(method, url, timeout=(min(15, self.settings.timeout), self.settings.timeout),
                                                proxies=proxies, stream=True, **kwargs)
            except requests.exceptions.ProxyError:
                raise BridgeError("proxy", "Не удалось подключиться через прокси. Проверьте адрес, авторизацию и доступность. Прямое подключение не выполнялось.", retryable=True) from None
            except requests.exceptions.SSLError:
                raise BridgeError("tls", "Ошибка проверки TLS. Проверьте сертификаты или ca_bundle.") from None
            except requests.exceptions.Timeout:
                if attempt + 1 < attempts:
                    self.wait(2 ** attempt)
                    continue
                raise BridgeError("timeout", "Сетевой тайм-аут; уменьшите запрос или используйте TAP async.", retryable=True) from None
            except requests.exceptions.RequestException:
                raise BridgeError("network", "Сетевая ошибка. Проверьте доступ к сервису и настройки прокси.", retryable=True) from None
            if response.status_code in {429, 502, 503, 504} and attempt + 1 < attempts:
                retry_after = response.headers.get("Retry-After", "")
                response.close()
                try:
                    delay = float(retry_after)
                except ValueError:
                    try:
                        delay = (parsedate_to_datetime(retry_after) - datetime.now(timezone.utc)).total_seconds()
                    except (ValueError, TypeError, OverflowError):
                        delay = 2 ** attempt
                if delay > self.settings.job_timeout:
                    raise BridgeError("rate_limit", "Retry-After превышает бюджет ожидания; повторите позднее.", retryable=True)
                self.wait(max(0, delay))
                continue
            if response.status_code >= 400:
                status = response.status_code
                response.close()
                raise BridgeError("http", f"Сервис {host} вернул HTTP {status}.", retryable=status in {429, 502, 503, 504})
            return response
        raise BridgeError("network", "Исчерпаны попытки подключения.", retryable=True)

    def request(self, method, url, *, retry_read=False, **kwargs):
        """Retain decoded HTTP entity bytes, not re-serialized tables."""
        response = self._open(method, url, retry_read=retry_read, **kwargs)
        path = self.run_dir / f"raw-{len(self.records) + 1:04d}.bin"
        try:
            self._receive(response, path, self.settings.max_response_mb)
            response._content = path.read_bytes()
            response._content_consumed = True
            self._record(method, response, path, url)
            return response
        finally:
            response.close()

    def _receive(self, response, path, max_mb):
        size = 0
        limit = int(max_mb * 1024 * 1024)
        started = time.monotonic()
        last_update = started
        created = False
        try:
            with path.open("xb") as stream:
                created = True
                for chunk in response.iter_content(128 * 1024):
                    self.check()
                    if time.monotonic() - started > self.settings.job_timeout:
                        raise BridgeError("timeout", "Превышено время получения ответа.", retryable=True)
                    size += len(chunk)
                    if size > limit:
                        raise BridgeError("size_limit", f"Ответ превышает локальный лимит {max_mb} MiB.")
                    stream.write(chunk)
                    if time.monotonic() - last_update >= 0.5:
                        self.progress(f"Получено {size / 1024 / 1024:.1f} MiB / лимит {max_mb} MiB")
                        last_update = time.monotonic()
        except requests.exceptions.RequestException:
            if created:
                path.unlink(missing_ok=True)
            raise BridgeError("network", "Получение ответа прервано; неполный файл удалён.", retryable=True) from None
        except BaseException:
            if created:
                path.unlink(missing_ok=True)
            raise

    def _record(self, method, response, path, requested_url):
        self.records.append({"method": response.request.method, "url": safe_url(response.url), "status": response.status_code,
                             "requested_method": method, "requested_url": safe_url(requested_url),
                             "redirects": [{"method": item.request.method, "url": safe_url(item.url), "status": item.status_code} for item in response.history],
                             "received_at": utcnow(), "content_type": response.headers.get("Content-Type", ""),
                             "file": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)})

    def download(self, url, filename, max_mb, headers=None):
        response = self._open("GET", url, headers=headers)
        path = self.run_dir / filename
        try:
            self._receive(response, path, max_mb)
            self._record("GET", response, path, url)
            return path
        finally:
            response.close()

    def close(self):
        self.session.close()


class DecodedBody(BytesIO):
    def read(self, size=-1, **kwargs):
        # HTTP content was decoded by requests.iter_content already.
        return super().read(size)


class VOSession(requests.Session):
    """Documented pyvo session injection; no global monkey-patches."""
    def __init__(self, transport):
        super().__init__()
        self.transport = transport
        self.trust_env = False

    def request(self, method, url, **kwargs):
        kwargs.pop("stream", None)
        kwargs.pop("timeout", None)
        response = self.transport.request(method.upper(), url, **kwargs)
        if response.content.lstrip().startswith(b"<?xml") or b"<VOTABLE" in response.content[:500]:
            from defusedxml import ElementTree
            try:
                ElementTree.fromstring(response.content)
            except Exception:
                raise BridgeError("parse", "Небезопасный или повреждённый XML-ответ.") from None
        # pyvo reads response.raw even when HTTP streaming was already consumed.
        response.raw = DecodedBody(response.content)
        return response
