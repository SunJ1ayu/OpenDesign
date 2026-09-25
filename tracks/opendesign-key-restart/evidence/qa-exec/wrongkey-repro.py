import asyncio, json, os, sys, subprocess, tempfile, time, shutil
sys.path.insert(0, "/root/.openclaw/workspace/projects/design-studio/bin")
sys.path.insert(0, "/root/.openclaw/workspace/projects/design-studio/tests")
import ds_credential, ds_shell_core as core
from test_per_vendor_live import FakeVendor, free_port
from unittest import mock
from http.server import BaseHTTPRequestHandler
ROOT = "/root/.openclaw/workspace/projects/design-studio"
v = FakeVendor("MiMo")
# 让假厂商对任何 key 都回 401
class H401(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); self.rfile.read(n)
        b = b'{"error":{"message":"Invalid API key","type":"invalid_request_error"}}'
        self.send_response(401); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
v.srv.RequestHandlerClass = H401
tmp = tempfile.mkdtemp(prefix="wrongkey-"); home = os.path.join(tmp, "UserData")
os.makedirs(os.path.join(home, ".nanobot")); os.makedirs(os.path.join(home, ".openDesign"))
cfgp = os.path.join(home, ".nanobot", "config.json")
cfg = ds_credential.load_jsonc(os.path.join(ROOT, "config/nanobot.config.windows.jsonc"))
cfg["providers"]["custom"]["apiBase"] = v.base
cfg["tools"] = {"exec": {"enable": False}, "file": {"enable": False}, "web": {"enable": False}}
ws_port = free_port(); cfg["gateway"] = {"port": free_port()}
cfg["channels"] = {"websocket": {"enabled": True, "host": "127.0.0.1", "port": ws_port, "token": "t", "websocketRequiresToken": True, "allowFrom": ["*"]}}
cfg["agents"]["defaults"]["workspace"] = os.path.join(tmp, "ws")
json.dump(cfg, open(cfgp, "w"))
open(os.path.join(home, ".openDesign", "key.txt"), "w").write("tp-wrong-key-0000000000\n")
env = core.service_envs(dict(os.environ), ds_root=ROOT, user_home=home, dsweb_port=1, ws_port=ws_port, key="tp-wrong-key-0000000000", key_var="DS_LLM_KEY")["网关"]
env.update(HOME=home, USERPROFILE=home, HTTP_PROXY="http://127.0.0.1:9", HTTPS_PROXY="http://127.0.0.1:9", NO_PROXY="127.0.0.1,localhost")
log = open(os.path.join(tmp, "gw.log"), "w")
gw = subprocess.Popen(core.gateway_argv(sys.executable, ROOT), env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
async def run():
    import websockets
    for _ in range(300):
        try:
            ws = await websockets.connect(f"ws://127.0.0.1:{ws_port}/?client_id=x&token=t"); break
        except OSError: await asyncio.sleep(0.1)
    async with ws:
        await ws.send("你好")
        t0 = time.monotonic()
        while time.monotonic() - t0 < 40:
            try:
                m = await asyncio.wait_for(ws.recv(), timeout=1)
                print(f"+{time.monotonic()-t0:4.1f}s", str(m)[:300])
            except asyncio.TimeoutError: pass
asyncio.run(run())
gw.terminate(); gw.wait(10); log.close()
print("---- gw log tail"); print(open(os.path.join(tmp, "gw.log")).read()[-1500:])
shutil.rmtree(tmp, ignore_errors=True)
