# 探针:回复进行中发 /stop,网关实时发什么 + 回放里留下什么 + 之后还能不能正常聊。
# 用法: probe-stop.py <mode>
#   stream  —— 厂商慢慢流正文(每 0.4s 一段,共 40 段),第 2 秒发 /stop
#   think   —— 厂商 6 秒后才出第一个字(还在「思考」),第 2 秒发 /stop
#   idle    —— 没有在回复时发 /stop
import asyncio, json, os, sys, subprocess, tempfile, time, shutil, urllib.request, urllib.parse
ROOT = "/root/.openclaw/workspace/projects/design-studio"
sys.path.insert(0, ROOT + "/bin"); sys.path.insert(0, ROOT + "/tests")
import ds_credential, ds_shell_core as core
from test_per_vendor_live import FakeVendor, free_port
from http.server import BaseHTTPRequestHandler
mode = sys.argv[1]
calls = {"n": 0}
v = FakeVendor("MiMo")
class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); body = json.loads(self.rfile.read(n) or b"{}")
        calls["n"] += 1
        stream = body.get("stream")
        slow = calls["n"] == 1   # 只有第一轮慢;第二轮(验证还能聊)快速回
        def chunk(txt, finish=None):
            d = {"id": "c", "object": "chat.completion.chunk", "model": "mimo-v2.5",
                 "choices": [{"index": 0, "delta": ({"content": txt} if txt else {}), "finish_reason": finish}]}
            return ("data: " + json.dumps(d, ensure_ascii=False) + "\n\n").encode()
        if not stream:
            b = json.dumps({"id": "c", "object": "chat.completion", "model": "mimo-v2.5",
                            "choices": [{"index": 0, "message": {"role": "assistant", "content": "第二轮正常回复。"}, "finish_reason": "stop"}]}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.send_header("Transfer-Encoding", "chunked"); self.end_headers()
        def w(b):
            self.wfile.write(f"{len(b):x}\r\n".encode() + b + b"\r\n"); self.wfile.flush()
        try:
            if slow and mode == "think":
                time.sleep(6)
            parts = [f"第{i}段。" for i in range(40)] if slow else ["第二轮", "正常回复。"]
            for p in parts:
                w(chunk(p)); time.sleep(0.4 if slow else 0.05)
            w(chunk("", "stop")); w(b"data: [DONE]\n\n"); self.wfile.write(b"0\r\n\r\n"); self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            print("   [vendor] 客户端断开了流(第", calls["n"], "次调用)", flush=True)
v.srv.RequestHandlerClass = H
tmp = tempfile.mkdtemp(prefix="stopprobe-"); home = os.path.join(tmp, "UserData")
os.makedirs(os.path.join(home, ".nanobot")); os.makedirs(os.path.join(home, ".openDesign"))
cfg = ds_credential.load_jsonc(os.path.join(ROOT, "config/nanobot.config.windows.jsonc"))
cfg["providers"]["custom"]["apiBase"] = v.base
cfg["tools"] = {"exec": {"enable": False}, "file": {"enable": False}, "web": {"enable": False}}
ws_port = free_port(); cfg["gateway"] = {"port": free_port()}
cfg["channels"] = {"websocket": {"enabled": True, "host": "127.0.0.1", "port": ws_port, "token": "t", "websocketRequiresToken": True, "allowFrom": ["*"]}}
cfg["agents"]["defaults"]["workspace"] = os.path.join(tmp, "ws")
json.dump(cfg, open(os.path.join(home, ".nanobot", "config.json"), "w"))
open(os.path.join(home, ".openDesign", "key.txt"), "w").write("tp-fake-key-0000000000\n")
env = core.service_envs(dict(os.environ), ds_root=ROOT, user_home=home, dsweb_port=1, ws_port=ws_port, key="tp-fake-key-0000000000", key_var="DS_LLM_KEY")["网关"]
env.update(HOME=home, USERPROFILE=home, HTTP_PROXY="http://127.0.0.1:9", HTTPS_PROXY="http://127.0.0.1:9", NO_PROXY="127.0.0.1,localhost")
log = open(os.path.join(tmp, "gw.log"), "w")
gw = subprocess.Popen(core.gateway_argv(sys.executable, ROOT), env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
chat = {}
def show(t0, d):
    print(f"+{time.monotonic()-t0:5.1f}s", {k: d[k] for k in d if k not in ("chat_id",)}.__repr__()[:240], flush=True)
async def run():
    import websockets
    for _ in range(300):
        try:
            ws = await websockets.connect(f"ws://127.0.0.1:{ws_port}/?client_id=x&token=t", max_size=None); break
        except OSError: await asyncio.sleep(0.1)
    async with ws:
        t0 = time.monotonic()
        first = json.loads(await ws.recv()); chat["id"] = first.get("chat_id")
        if mode != "idle":
            await ws.send(json.dumps({"type": "message", "chat_id": chat["id"], "content": "讲个长故事", "webui": True, "turn_id": "turn-1"}))
        stop_sent = False; after_stop = None; deltas = 0
        while time.monotonic() - t0 < 40:
            if not stop_sent and time.monotonic() - t0 > 2.0:
                print(f"+{time.monotonic()-t0:5.1f}s >>> 发 /stop", flush=True)
                await ws.send(json.dumps({"type": "message", "chat_id": chat["id"], "content": "/stop", "webui": True, "turn_id": "turn-stop"}))
                stop_sent = True; after_stop = time.monotonic()
            try:
                d = json.loads(await asyncio.wait_for(ws.recv(), timeout=0.3))
                if d.get("event") == "delta":
                    deltas += 1
                    if deltas <= 2 or (after_stop and time.monotonic() - after_stop < 3): show(t0, d)
                else:
                    show(t0, d)
            except asyncio.TimeoutError: pass
            if after_stop and time.monotonic() - after_stop > 8: break
        print(f"   delta 总数 {deltas}", flush=True)
        print(f"+{time.monotonic()-t0:5.1f}s >>> 再发一句,看还能不能聊", flush=True)
        await ws.send(json.dumps({"type": "message", "chat_id": chat["id"], "content": "还在吗", "webui": True, "turn_id": "turn-2"}))
        t1 = time.monotonic()
        while time.monotonic() - t1 < 20:
            try:
                d = json.loads(await asyncio.wait_for(ws.recv(), timeout=1)); show(t0, d)
                if d.get("event") == "turn_end": break
            except asyncio.TimeoutError: pass
asyncio.run(run())
time.sleep(1)
try:
    boot = json.load(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{ws_port}/webui/bootstrap", headers={"Authorization": "Bearer t"}), timeout=5))
    tok = boot.get("token")
    key = urllib.parse.quote("websocket:" + chat["id"], safe="")
    th = json.load(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{ws_port}/api/sessions/{key}/webui-thread", headers={"Authorization": f"Bearer {tok}"}), timeout=5))
    print("---- replay:")
    for m in th.get("messages", []): print("  ", json.dumps(m, ensure_ascii=False)[:400])
except Exception as e:
    print("replay fetch failed:", repr(e))
print("vendor 调用次数", calls["n"])
gw.terminate(); gw.wait(10); log.close()
print("---- gw log (stop/cancel/error):"); print("\n".join(l for l in open(os.path.join(tmp, "gw.log")).read().splitlines() if any(k in l for k in ("ERROR", "WARN", "ancel", "stop", "Stop")))[-2000:])
shutil.rmtree(tmp, ignore_errors=True)
