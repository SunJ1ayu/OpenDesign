"""探针替身后台:HTTP(报回收到的头/长度)+ WebSocket 回声。只绑 127.0.0.1。"""
import asyncio, json, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import websockets

HTTP_PORT, WS_PORT = int(sys.argv[1]), int(sys.argv[2])

class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def _seen(self, n=0):
        return {"path": self.path, "method": self.command, "host": self.headers.get("Host"),
                "origin": self.headers.get("Origin"), "sfs": self.headers.get("Sec-Fetch-Site"),
                "len": n}
    def do_GET(self):
        if self.path.startswith("/api/img"):
            # 1x1 png
            png = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                                "1f15c4890000000d49444154789c6360f8cfc0f01f0005000201e5d3f9"
                                "0b0000000049454e44ae426082")
            return self._send(200, png, "image/png")
        self._send(200, self._seen())
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); left = n; got = 0
        te = self.headers.get("Transfer-Encoding")
        if te == "chunked":
            while True:
                size = int(self.rfile.readline().strip(), 16)
                if size == 0: self.rfile.readline(); break
                got += len(self.rfile.read(size)); self.rfile.readline()
        else:
            while left > 0:
                c = self.rfile.read(min(65536, left)); got += len(c); left -= len(c)
        d = self._seen(got); d["te"] = te
        self._send(200, d)
    def log_message(self, *a): pass

async def echo(ws):
    async for m in ws:
        await ws.send("echo:" + m)

async def main():
    threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", HTTP_PORT), H).serve_forever, daemon=True).start()
    async with websockets.serve(echo, "127.0.0.1", WS_PORT):
        print("backend up", flush=True)
        await asyncio.Future()

asyncio.run(main())
