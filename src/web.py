"""Local-only demo UI; Python standard library, no installation required."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from .agent import run_agent

ROOT = Path(__file__).resolve().parents[1]


class Handler(BaseHTTPRequestHandler):
    def send(self, status, data, content_type="application/json; charset=utf-8"):
        payload = data.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/api/cases":
            cases = json.loads((ROOT / "tests/cases.json").read_text(encoding="utf-8"))
            self.send(200, json.dumps([{k:v for k,v in c.items() if k != "expected"} for c in cases], ensure_ascii=False))
        elif self.path == "/":
            self.send(200, (ROOT / "src/index.html").read_text(encoding="utf-8"), "text/html; charset=utf-8")
        else:
            self.send(404, '{"error":"not found"}')

    def do_POST(self):
        if self.path != "/api/run":
            return self.send(404, '{}')
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size < 32000:
                raise ValueError("请求长度无效")
            body = json.loads(self.rfile.read(size))
            answer = run_agent(body["request"], body.get("mode", "llm"))
            self.send(200, json.dumps(answer, ensure_ascii=False))
        except (ValueError, KeyError, RuntimeError, TypeError, json.JSONDecodeError) as exc:
            self.send(400, json.dumps({"error": str(exc)}, ensure_ascii=False))


if __name__ == "__main__":
    print("FiberScope: http://127.0.0.1:8765")
    ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
