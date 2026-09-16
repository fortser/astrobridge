from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from urllib.parse import parse_qs, urlsplit

import pytest


VOTABLE = b'''<?xml version="1.0"?>
<VOTABLE version="1.3" xmlns="http://www.ivoa.net/xml/VOTable/v1.3"><RESOURCE type="results">
<INFO name="QUERY_STATUS" value="OK"/>
<TABLE><FIELD name="source_id" datatype="long"/><FIELD name="ra" datatype="double" unit="deg" ucd="pos.eq.ra"/>
<FIELD name="name" datatype="char" arraysize="*"/>
<DATA><TABLEDATA><TR><TD>9007199254740993</TD><TD>10.5</TD><TD>test star</TD></TR>
<TR><TD>2</TD><TD></TD><TD>second</TD></TR></TABLEDATA></DATA></TABLE>
</RESOURCE></VOTABLE>'''


@pytest.fixture
def server():
    calls = []
    state = {"phase": "PENDING", "overflow": False, "fail": False, "polls": 0}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, content, code=200, content_type="application/xml", headers=None):
            if isinstance(content, str):
                content = content.encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(content)

        def uws(self):
            return f'''<?xml version="1.0"?><uws:job xmlns:uws="http://www.ivoa.net/xml/UWS/v1.0" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.0">
            <uws:jobId>1</uws:jobId><uws:phase>{state['phase']}</uws:phase>
            <uws:executionDuration>600</uws:executionDuration><uws:destruction>2026-12-01T00:00:00Z</uws:destruction>
            <uws:parameters><uws:parameter id="QUERY">SELECT TOP 2 * FROM sample</uws:parameter></uws:parameters>
            <uws:results><uws:result id="result" xlink:href="{base}/tap/async/1/results/result"/></uws:results></uws:job>'''

        def do_GET(self):
            calls.append(("GET", self.path, None, dict(self.headers)))
            path = urlsplit(self.path).path
            if path == "/tap/async/1":
                self.reply(self.uws())
            elif path.endswith("/results/result") or path == "/tap/sync":
                self.reply(VOTABLE)
            elif path == "/file":
                self.reply(b"FITS-like-test-content", content_type="application/octet-stream")
            elif path == "/large":
                self.reply(b"x" * 4096, content_type="application/octet-stream")
            elif path == "/redirect":
                self.reply(b"", 302, headers={"Location": base + "/file"})
            elif path == "/retry":
                state["polls"] += 1
                self.reply(b"busy" if state["polls"] == 1 else b"ok", 429 if state["polls"] == 1 else 200, headers={"Retry-After": "0"})
            elif path == "/crossref":
                self.reply(json.dumps({"message": {"items": [{"DOI": "10.1/example", "title": ["A title"], "author": [{"family": "Test"}]}], "total-results": 4}}), content_type="application/json")
            elif path == "/arxiv":
                self.reply('''<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom" xmlns:o="http://a9.com/-/spec/opensearch/1.1/">
                <o:totalResults>1</o:totalResults><entry><id>https://arxiv.org/abs/0000.00000</id><title>Fixture only</title><summary>Test abstract</summary><published>2026-01-01</published><author><name>Fixture Author</name></author></entry></feed>''')
            elif path in {"/sia", "/ssa"}:
                self.reply(VOTABLE)
            elif path == "/horizons":
                self.reply(json.dumps({"signature": {"version": "test"}, "result": "Header AU-D\nJDTDB,Calendar Date (TDB),X,Y,Z,\n********\n$$SOE\n2461041.5,A.D. 2026-Jan-01,1.0,2.0,3.0,\n$$EOE\nUnits AU-D"}), content_type="application/json")
            else:
                self.reply(b"not found", 404)

        def do_POST(self):
            data = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
            calls.append(("POST", self.path, data, dict(self.headers)))
            path = urlsplit(self.path).path
            if path == "/tap/sync":
                if state.get("http_error"):
                    self.reply(b"invalid query", state["http_error"])
                    return
                vot = VOTABLE
                if state["overflow"]:
                    vot = vot.replace(b"</RESOURCE>", b'<INFO name="QUERY_STATUS" value="OVERFLOW"/></RESOURCE>')
                if state["fail"]:
                    vot = vot.replace(b'value="OK"', b'value="ERROR"').replace(b'<TABLE>', b'<TABLE>')
                self.reply(vot)
            elif path == "/tap/async":
                self.reply(b"", 303, headers={"Location": base + "/tap/async/1"})
            elif path == "/tap/async/1/phase":
                state["phase"] = "ABORTED" if "ABORT" in data else "EXECUTING" if state.get("hold") else "COMPLETED"
                self.reply(b"", 303, headers={"Location": base + "/tap/async/1"})
            elif path == "/mast":
                req = json.loads(parse_qs(data)["request"][0])
                self.reply(json.dumps({"status": "COMPLETE", "data": [{"obsid": 123, "dataURI": "mast:test/file.fits"}], "fields": [{"name": "obsid", "type": "int"}, {"name": "dataURI", "type": "string"}], "paging": {"pagesFiltered": 2, "page": req.get("page", 1)}}), content_type="application/json")
            else:
                self.reply(b"not found", 404)

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    base = f"http://127.0.0.1:{httpd.server_port}"
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield base, calls, state
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=3)


@pytest.fixture
def bridge(tmp_path, server):
    from astrobridge.config import Settings
    from astrobridge.core import Bridge
    base, _, _ = server
    return Bridge(Settings(workspace=str(tmp_path / "data"), min_interval=0, proxy_mode="direct", timeout=3,
                           services={"test": {"kind": "tap", "url": base + "/tap"}}))
