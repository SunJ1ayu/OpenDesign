# 探针:各种模型出错时,网关实时发什么 + 回放历史里留下什么。用法: probe.py <mode>
# mode: 401 | 429q(欠费/额度) | 429r(限流) | 500 | down(端口没人听)
import asyncio, json, os, sys, subprocess, tempfile, time, shutil, urllib.request, urllib.parse
ROOT = "/root/.openclaw/workspace/projects/design-studio"
sys.path.insert(0, ROOT + "/bin"); sys.path.insert(0, ROOT + "/tests")
import ds_credential, ds_shell_core as core
from test_per_vendor_live import FakeVendor, free_port
from http.server import BaseHTTPRequestHandler
mode = sys.argv[1]
if mode == "raw":
    pass
BODIES = {
  "401": (401, {"error": {"message": "Invalid API key", "type": "invalid_request_error"}}),
  "429q": (429, {"error": {"message": "Your account is in arrears / insufficient balance", "type": "insufficient_quota", "code": "insufficient_quota"}}),
  "429r": (429, {"error": {"message": "Rate limit reached for requests", "type": "rate_limit_error"}}),
  "500": (500, {"error": {"message": "internal server error", "type": "server_error"}}),
}
v = FakeVendor("MiMo")
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); self.rfile.read(n)
        code, body = (int(sys.argv[2]), json.loads(sys.argv[3])) if mode == "raw" else BODIES[mode]; b = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
base = v.base
if mode == "down":
    base = f"http://127.0.0.1:{free_port()}/v1"
else:
    v.srv.RequestHandlerClass = H
tmp = tempfile.mkdtemp(prefix="q1probe-"); home = os.path.join(tmp, "UserData")
os.makedirs(os.path.join(home, ".nanobot")); os.makedirs(os.path.join(home, ".openDesign"))
cfg = ds_credential.load_jsonc(os.path.join(ROOT, "config/nanobot.config.windows.jsonc"))
cfg["providers"]["custom"]["apiBase"] = base
cfg["tools"] = {"exec": {"enable": False}, "file": {"enable": False}, "web": {"enable": False}}
ws_port = free_port(); cfg["gateway"] = {"port": free_port()}
cfg["channels"] = {"websocket": {"enabled": True, "host": "127.0.0.1", "port": ws_port, "token": "t", "websocketRequiresToken": True, "allowFrom": ["*"]}}
cfg["agents"]["defaults"]["workspace"] = os.path.join(tmp, "ws")
json.dump(cfg, open(os.path.join(home, ".nanobot", "config.json"), "w"))
open(os.path.join(home, ".openDesign", "key.txt"), "w").write("tp-wrong-key-0000000000\n")
env = core.service_envs(dict(os.environ), ds_root=ROOT, user_home=home, dsweb_port=1, ws_port=ws_port, key="tp-wrong-key-0000000000", key_var="DS_LLM_KEY")["网关"]
env.update(HOME=home, USERPROFILE=home, HTTP_PROXY="http://127.0.0.1:9", HTTPS_PROXY="http://127.0.0.1:9", NO_PROXY="127.0.0.1,localhost")
log = open(os.path.join(tmp, "gw.log"), "w")
gw = subprocess.Popen(core.gateway_argv(sys.executable, ROOT), env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
chat = {}
async def run():
    import websockets
    for _ in range(300):
        try:
            ws = await websockets.connect(f"ws://127.0.0.1:{ws_port}/?client_id=x&token=t"); break
        except OSError: await asyncio.sleep(0.1)
    async with ws:
        t0 = time.monotonic()
        first = json.loads(await ws.recv()); chat["id"] = first.get("chat_id")
        await ws.send(json.dumps({"type": "message", "chat_id": chat["id"], "content": "你好", "webui": True, "turn_id": "turn-1"}))
        while time.monotonic() - t0 < 120:
            try:
                m = await asyncio.wait_for(ws.recv(), timeout=1)
                d = json.loads(m); print(f"+{time.monotonic()-t0:5.1f}s", {k: d[k] for k in d if k not in ("chat_id",)}.__repr__()[:260])
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
    for m in th.get("messages", []): print("  ", json.dumps(m, ensure_ascii=False)[:600])
except Exception as e:
    print("replay fetch failed:", repr(e))
gw.terminate(); gw.wait(10); log.close()
print("---- gw log errors:"); print("\n".join(l for l in open(os.path.join(tmp, "gw.log")).read().splitlines() if "ERROR" in l or "WARN" in l)[-1500:])
shutil.rmtree(tmp, ignore_errors=True)
