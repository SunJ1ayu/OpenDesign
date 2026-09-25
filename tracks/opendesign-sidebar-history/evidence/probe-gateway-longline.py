# track opendesign-sidebar-history 实现中发现:网关侧栏状态更新口把整份状态放进网址(GET ?state=),请求行上限 8192 字节。
# 跑法:/root/.venvs/design-studio/bin/python tracks/opendesign-sidebar-history/evidence/probe-gateway-longline.py(websockets 与网关同版本 16.0)
# 探针:网关(websockets 16 asyncio server + process_request)收到超长请求行会怎样
import asyncio, http.client, json, threading, urllib.parse
from websockets.asyncio.server import serve
from websockets.http11 import Response
from websockets.datastructures import Headers

def process_request(conn, req):
    body = json.dumps({"len": len(req.path)}).encode()
    return Response(200, "OK", Headers([("Content-Type", "application/json"), ("Content-Length", str(len(body)))]), body)

async def main():
    async with serve(lambda ws: None, "127.0.0.1", 0, process_request=process_request) as srv:
        port = srv.sockets[0].getsockname()[1]
        def client(n_titles, title_len):
            state = {"pinned_keys": [], "title_overrides": {f"websocket:{i:032x}": "长" * title_len for i in range(n_titles)}}
            q = urllib.parse.quote(json.dumps(state, ensure_ascii=False))
            path = "/api/webui/sidebar-state/update?state=" + q
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            try:
                c.request("GET", path); r = c.getresponse(); out = (r.status, r.read()[:60])
            except Exception as e:
                out = (type(e).__name__, str(e)[:80])
            print(f"titles={n_titles:3d} len={title_len:3d} url_bytes={len(path):6d} ->", out)
        for n, l in [(5, 10), (30, 10), (60, 10), (5, 160), (6, 160)]:
            await asyncio.to_thread(client, n, l)
asyncio.run(main())
