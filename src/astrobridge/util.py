from datetime import datetime, timezone
import hashlib
import json
import math
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def jsonable(value):
    import numpy as np
    if value is None or value is np.ma.masked:
        return None
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [jsonable(v) for v in value]
    if isinstance(value, np.generic):
        return jsonable(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, int) and not isinstance(value, bool) and abs(value) > 2 ** 53 - 1:
        return str(value)
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def dumps(value, **kwargs):
    return json.dumps(jsonable(value), ensure_ascii=False, allow_nan=False, **kwargs)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


SECRET_KEY = re.compile(r"token|password|secret|authorization|cookie|api.?key|signature|credential", re.I)


def safe_url(url):
    p = urlsplit(url)
    host = p.netloc.rsplit("@", 1)[-1]
    query = urlencode([(k, "[REDACTED]" if SECRET_KEY.search(k) else v) for k, v in parse_qsl(p.query, keep_blank_values=True)])
    return urlunsplit((p.scheme, host, p.path, query, ""))


def reject_secrets(value):
    """Request manifests are public provenance; credentials must be out of band."""
    from .errors import BridgeError
    if isinstance(value, float) and not math.isfinite(value):
        raise BridgeError("validation", "NaN и Infinity не допускаются в запросах.")
    if isinstance(value, dict):
        for key, item in value.items():
            if SECRET_KEY.search(key):
                raise BridgeError("validation", "Секреты передаются только через переменные окружения, не в запросе.")
            reject_secrets(item)
    elif isinstance(value, list):
        for item in value:
            reject_secrets(item)
    elif isinstance(value, str) and value.startswith(("http://", "https://")):
        p = urlsplit(value)
        if p.username is not None or any(SECRET_KEY.search(k) for k, _ in parse_qsl(p.query)):
            raise BridgeError("validation", "URL с credentials/signature нельзя сохранять в манифесте запроса.")
