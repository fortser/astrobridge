import socket
import socketserver
import select
import threading

import pytest

from astrobridge.config import Settings
from astrobridge.core import Bridge
from astrobridge.network import Transport
from astrobridge.errors import BridgeError
from astrobridge.util import dumps


def test_all_pyvo_requests_use_authenticated_http_proxy(tmp_path, server, monkeypatch):
    proxy_url, calls, _ = server
    proxy = proxy_url.replace("http://", "http://user:TOP-SECRET@")
    monkeypatch.setenv("ASTROBRIDGE_PROXY", proxy)
    monkeypatch.setenv("NO_PROXY", "*")  # manual selection must not be bypassed
    bridge = Bridge(Settings(workspace=str(tmp_path), proxy_mode="manual", min_interval=0,
                             services={"test": {"kind": "tap", "url": "http://no-dns.invalid/tap"}}))
    result = bridge.run({"service": "test", "operation": "tap.query", "params": {"query": "SELECT TOP 2 * FROM sample"}})
    assert result["status"] == "success", result
    assert calls[0][1] == "http://no-dns.invalid/tap/sync"
    assert calls[0][3].get("Proxy-Authorization", "").startswith("Basic ")
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert b"TOP-SECRET" not in path.read_bytes()
    assert "TOP-SECRET" not in dumps(result)


def test_broken_proxy_never_falls_back_direct(tmp_path, server, monkeypatch):
    monkeypatch.setenv("ASTROBRIDGE_PROXY", "http://secret:PRIVATE@127.0.0.1:1")
    bridge = Bridge(Settings(workspace=str(tmp_path), proxy_mode="manual", min_interval=0, timeout=1, retries=0,
                             services={"test": {"kind": "tap", "url": server[0] + "/tap"}}))
    result = bridge.run({"service": "test", "operation": "tap.query", "params": {"query": "SELECT TOP 2 * FROM sample"}})
    assert result["status"] == "error"
    assert result["error"]["code"] == "proxy"
    assert not server[1]
    assert "PRIVATE" not in dumps(result)


def test_direct_and_environment_modes(tmp_path, monkeypatch):
    for name in list(__import__("os").environ):
        if name.lower().endswith("_proxy"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9876")
    monkeypatch.setenv("HTTPS_PROXY", "socks5h://127.0.0.1:9999")
    t = Transport(Settings(proxy_mode="environment"), tmp_path)
    assert t.proxy_map["http"].endswith(":9876")
    assert t.proxy_map["https"].startswith("socks5h://")
    assert t.session.trust_env is False
    assert t.session.verify is True
    assert not Transport(Settings(proxy_mode="direct"), tmp_path).proxy_map
    with pytest.raises(BridgeError):
        Settings(proxy_url="http://name:password@localhost:1").validate()


def test_retry_after_and_redirect_use_transport(tmp_path, server):
    base = server[0]
    t = Transport(Settings(proxy_mode="direct", min_interval=0), tmp_path)
    assert t.request("GET", base + "/retry").content == b"ok"
    assert server[2]["polls"] == 2
    assert t.request("GET", base + "/redirect").content == b"FITS-like-test-content"


def test_socks5h_dns_at_proxy(tmp_path, server, monkeypatch):
    destinations = []

    def read_exact(sock, length):
        data = b""
        while len(data) < length:
            chunk = sock.recv(length - len(data))
            if not chunk:
                raise ConnectionError()
            data += chunk
        return data

    class Socks(socketserver.BaseRequestHandler):
        def handle(self):
            sock = self.request
            sock.settimeout(5)
            try:
                version, count = read_exact(sock, 2)
                methods = read_exact(sock, count)
                assert version == 5 and 0 in methods
                sock.sendall(b"\x05\x00")
                header = read_exact(sock, 4)
                assert header[1] == 1
                if header[3] == 3:
                    host = read_exact(sock, read_exact(sock, 1)[0]).decode()
                else:
                    host = socket.inet_ntoa(read_exact(sock, 4))
                port = int.from_bytes(read_exact(sock, 2), "big")
                destinations.append((host, port))
                with socket.create_connection(("127.0.0.1", port), timeout=5) as remote:
                    sock.sendall(b"\x05\x00\x00\x01\x7f\x00\x00\x01\x00\x00")
                    while True:
                        ready, _, _ = select.select([sock, remote], [], [], 5)
                        if not ready:
                            return
                        for source in ready:
                            data = source.recv(65536)
                            if not data:
                                return
                            (remote if source is sock else sock).sendall(data)
            except (OSError, ConnectionError):
                return

    proxy = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Socks)
    proxy.daemon_threads = True
    thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("ASTROBRIDGE_PROXY", f"socks5h://127.0.0.1:{proxy.server_address[1]}")
    port = int(server[0].rsplit(":", 1)[1])
    try:
        transport = Transport(Settings(proxy_mode="manual", min_interval=0), tmp_path)
        response = transport.request("GET", f"http://must-not-resolve.invalid:{port}/file")
        assert response.content == b"FITS-like-test-content"
        assert destinations == [("must-not-resolve.invalid", port)]
        transport.close()
    finally:
        proxy.shutdown()
        proxy.server_close()
        thread.join(3)

