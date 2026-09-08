"""本地实时演示服务。GitHub Pages 上是录制回放，本地跑这个可以实时生成。

    python3 src/serve.py     然后打开 http://127.0.0.1:8000
"""
from __future__ import annotations
import json, pathlib, sys
from http.server import SimpleHTTPRequestHandler, HTTPServer
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from generate import build

DOCS = pathlib.Path(__file__).resolve().parent.parent / "docs"


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(DOCS), **kw)

    def do_POST(self):
        if self.path != "/api/generate":
            return self.send_error(404)
        n = int(self.headers.get("Content-Length", 0))
        q = json.loads(self.rfile.read(n) or b"{}").get("question", "")
        out = build(q) if q.strip() else {"components": [], "_fallback": False}
        b = json.dumps(out, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"http://127.0.0.1:{port}  (需先在 LM Studio 中启动本地服务)")
    HTTPServer(("127.0.0.1", port), H).serve_forever()
