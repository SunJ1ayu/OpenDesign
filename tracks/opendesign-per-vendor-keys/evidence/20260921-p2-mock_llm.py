"""假的 OpenAI 兼容服务器:记下每次请求的 Authorization 与 model,回一句带自己名字的话。"""
import json, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
NAME, PORT, LOG = sys.argv[1], int(sys.argv[2]), sys.argv[3]
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        with open(LOG, "a") as f:
            f.write(json.dumps({"server": NAME, "path": self.path, "auth": self.headers.get("Authorization"),
                                "model": body.get("model"), "stream": body.get("stream")}) + "\n")
        text = f"我是{NAME}"
        if body.get("stream"):
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
            for chunk in ({"choices": [{"index": 0, "delta": {"role": "assistant", "content": text}}]},
                          {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                           "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}):
                chunk.update(id="x", object="chat.completion.chunk", created=int(time.time()), model=body.get("model"))
                self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode()); self.wfile.flush()
            self.wfile.write(b"data: [DONE]\n\n")
        else:
            out = {"id": "x", "object": "chat.completion", "created": int(time.time()), "model": body.get("model"),
                   "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
                   "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
            data = json.dumps(out, ensure_ascii=False).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
