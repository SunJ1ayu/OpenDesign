"""probe-5 = QA 执行(track opendesign-key-restart):**修好的包**在真 Windows 上走业主的两条路,全程记录。

  live :聊天连着 → 发一句(MiMo,K1)→ 设置页存 DeepSeek 的 key → 聊天框切到 DeepSeek 发一句 →
         设置页把 MiMo 换成 K2 → 切回 MiMo 发一句。要看的:同一条 websocket 没断、网关监听进程 PID 没换、
         每句打到对的那家、带的是刚存的那把 key、存 key 的回包是 live。
  fresh:全新装机、一把 key 都没有 → 设置页存第一把 MiMo key → 回包 requested → 网关被起起来 → 发一句。

两家厂商都是本机假服务:sitecustomize 在管家 / 工作台进程里把目录端点改到本机(PROBE_VENDOR_BASES),网关只读配置。
零外网:代理变量指向没人听的本机端口。**探针只记录,判断在主 agent**(结论行是给人看的摘要,不是判卷)。

用法:<包里的 python.exe> drive5.py <pkg 目录> <live|fresh> <输出目录>
"""
import json, os, socket, subprocess, sys, threading, time, urllib.error, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PKG, ARM, OUT = Path(sys.argv[1]).resolve(), sys.argv[2], Path(sys.argv[3]).resolve() / sys.argv[2]
PY = PKG / "python" / "python.exe"
sys.path.insert(0, str(PKG / "ds" / "bin"))
import ds_credential  # noqa: E402

K1, K2 = "tp-probe5-mimo-one-0123456789", "tp-probe5-mimo-two-9876543210"
DS_KEY = "sk-probe5-deepseek-0123456789ab"
t0 = time.monotonic()
events, checks = [], []


def say(msg):
    line = f"[{ARM} +{time.monotonic() - t0:6.1f}s] {msg}"
    print(line, flush=True)
    events.append(line)


def check(ok, what):
    checks.append((bool(ok), what))
    say(f"{'ok  ' if ok else 'FAIL'} {what}")


class FakeVendor:
    def __init__(self, name):
        self.name, self.hits = name, []
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
                outer.hits.append({"auth": self.headers.get("Authorization") or "", "model": body.get("model")})
                text, now = f"我是{outer.name}", int(time.time())
                if body.get("stream"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    for delta, fin in (({"role": "assistant", "content": text}, None), ({}, "stop")):
                        chunk = {"id": "x", "object": "chat.completion.chunk", "created": now, "model": body.get("model"),
                                 "choices": [{"index": 0, "delta": delta, "finish_reason": fin}]}
                        self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode())
                    self.wfile.write(b"data: [DONE]\n\n")
                    return
                out = json.dumps({"id": "x", "object": "chat.completion", "created": now, "model": body.get("model"),
                                  "choices": [{"index": 0, "finish_reason": "stop",
                                               "message": {"role": "assistant", "content": text}}],
                                  "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}},
                                 ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}/v1"


mimo, ds = FakeVendor("MiMo"), FakeVendor("DeepSeek")
vendors = (mimo, ds)

app = OUT / "appdata"
home = app / "OpenDesign" / "UserData"
logs = app / "OpenDesign" / "Logs"
(home / ".nanobot").mkdir(parents=True, exist_ok=True)
(home / ".openDesign").mkdir(parents=True, exist_ok=True)
cfg = ds_credential.load_jsonc(str(PKG / "ds" / "config" / "nanobot.config.windows.jsonc"))
cfg["providers"]["custom"]["apiBase"] = mimo.base
ws_cfg = cfg.setdefault("channels", {}).setdefault("websocket", {})
ws_cfg.update(enabled=True, host="127.0.0.1", token="probe-kouling", websocketRequiresToken=True, allowFrom=["*"])
(home / ".nanobot" / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
if ARM == "live":
    (home / ".openDesign" / "key.txt").write_text(K1 + "\n", encoding="utf-8")

dead = "http://127.0.0.1:9"
env = dict(os.environ, LOCALAPPDATA=str(app), PROBE_FAULT="1", PYTHONIOENCODING="utf-8",
           PROBE_VENDOR_BASES=json.dumps({"mimo": mimo.base, "deepseek": ds.base}),
           HTTP_PROXY=dead, HTTPS_PROXY=dead, http_proxy=dead, https_proxy=dead,
           NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost")
op = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def listening(port):
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def call(port, path, body=None, timeout=60):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with op.open(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {"raw": e.read()[:300].decode("utf-8", "replace")}
    except Exception as e:
        return repr(e)[:80], {}


def listener_pid(port):
    if os.name != "nt":            # 只为在 Linux 上先空跑一遍(probe-1/2 都死在没在本机先跑)
        out = subprocess.run(["ss", "-ltnpH", f"sport = :{port}"], capture_output=True, text=True, timeout=30).stdout
        return out.split("pid=")[1].split(",")[0] if "pid=" in out else None
    ns = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, timeout=30).stdout
    for line in ns.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[1].endswith(f":{port}") and parts[3] == "LISTENING":
            return parts[4]
    return None


host = subprocess.Popen([str(PY), str(PKG / "ds" / "bin" / "ds_host.py")], env=env,
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE)
first = {}
threading.Thread(target=lambda: first.setdefault("line", host.stdout.readline()), daemon=True).start()
while "line" not in first and time.monotonic() - t0 < 420:
    time.sleep(0.2)
say(f"host 第一帧: {first.get('line', b'(timeout)')[:300]!r}")
web = json.loads(first["line"])["web_port"]
wsport = json.loads((home / ".nanobot" / "config.json").read_text(encoding="utf-8"))["channels"]["websocket"]["port"]
say(f"web={web} ws={wsport} ws在听={listening(wsport)}")

if ARM == "fresh":
    check(not listening(wsport), "全新装机没 key:开机只起工作台,网关没在听")
    code, d = call(web, "/api/llm/providers/key", {"provider": "mimo", "key": K1})
    say(f"存第一把 key = {code} restart={d.get('restart')}")
    check(code == 200 and d.get("restart") == "requested", "存第一把 key ⇒ 回包 requested(请外壳把网关起起来)")
    up = None
    for _ in range(150):
        if listening(wsport) and call(web, "/api/chat/bootstrap", timeout=5)[0] == 200:
            up = time.monotonic() - t0
            break
        time.sleep(2)
    check(up is not None, f"网关被起起来了{'(@+%.1fs)' % up if up else '(300s 内没有)'}")

live = {"closed_at": None}
ws = None
if listening(wsport):
    code, info = call(web, "/api/chat/bootstrap")
    from websockets.sync.client import connect
    path = info.get("ws_path") if str(info.get("ws_path", "")).startswith("/") else "/"
    ws = connect(f"ws://127.0.0.1:{wsport}{path}?client_id=probe-5&token={info.get('token')}", open_timeout=30)
    say("活 websocket 已连上(= 聊天页连着)")

    def pump():
        try:
            while True:
                ws.recv()
        except Exception as e:
            live["closed_at"] = time.monotonic() - t0
            live["why"] = repr(e)[:120]
    threading.Thread(target=pump, daemon=True).start()


def say_expect(text, vendor, key, model=None):
    before = [len(v.hits) for v in vendors]
    try:
        ws.send(text)
    except Exception as e:
        check(False, f"「{text}」发不出去:{e!r}")
        return
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline and not any(len(v.hits) > b for v, b in zip(vendors, before)):
        time.sleep(0.5)
    time.sleep(1.0)
    new = {v.name: v.hits[b:] for v, b in zip(vendors, before)}
    got = new[vendor.name]
    say(f"「{text}」→ " + "; ".join(f"{n}:{[(h['auth'][-6:], h['model']) for h in hs]}" for n, hs in new.items()))
    check(got and all(h["auth"] == f"Bearer {key}" for h in got)
          and not any(hs for n, hs in new.items() if n != vendor.name)
          and (model is None or all(h["model"] == model for h in got)),
          f"「{text}」只打到 {vendor.name}、带的是 …{key[-6:]}")


if ws is not None and ARM == "live":
    pid0 = listener_pid(wsport)
    say(f"网关监听 PID = {pid0}")
    say_expect("第一句(MiMo K1)", mimo, K1)
    code, d = call(web, "/api/llm/providers/key", {"provider": "deepseek", "key": DS_KEY})
    check(code == 200 and d.get("restart") == "live", f"设置页存 DeepSeek ⇒ 回包 live(实际 {code} {d.get('restart')})")
    code, d = call(web, "/api/llm/model", {"model": "deepseek-v4-pro", "provider": "deepseek"})
    check(code == 200, f"聊天框切到 DeepSeek(实际 {code} {str(d)[:120]})")
    say_expect("切到 DeepSeek 之后", ds, DS_KEY, "deepseek-v4-pro")
    code, d = call(web, "/api/llm/providers/key", {"provider": "mimo", "key": K2})
    check(code == 200 and d.get("restart") == "live", f"设置页换 MiMo 的 key ⇒ 回包 live(实际 {code} {d.get('restart')})")
    code, d = call(web, "/api/llm/model", {"model": "mimo-v2.5", "provider": "mimo"})
    check(code == 200, f"聊天框切回 MiMo(实际 {code})")
    say_expect("切回 MiMo(K2)", mimo, K2, "mimo-v2.5")
    check(live["closed_at"] is None, f"全程同一条 websocket 没断(断于 {live['closed_at']} {live.get('why', '')})")
    pid1 = listener_pid(wsport)
    check(pid0 is not None and pid0 == pid1, f"网关监听进程没换(之前 {pid0},之后 {pid1})")
elif ws is not None and ARM == "fresh":
    say_expect("第一句(刚起来的网关)", mimo, K1)

say("结论摘要:" + ("全部 ok" if checks and all(ok for ok, _ in checks) else
                   f"{sum(1 for ok, _ in checks if not ok)} 条 FAIL / 共 {len(checks)} 条"))
try:
    host.stdin.write(b'{"cmd":"quit"}\n')
    host.stdin.flush()
    host.wait(60)
    say(f"管家收摊 rc={host.returncode}")
except Exception as e:
    say(f"收摊异常 {e!r}")
    host.kill()
for name in ("外壳.log", "网关.log", "工作台.log"):
    p = logs / name
    txt = p.read_text(encoding="utf-8", errors="replace") if p.exists() else "(没有)"
    (OUT / name).write_text(txt, encoding="utf-8")
    print(f"\n======== {ARM} {name}(尾 4000 字)========\n{txt[-4000:]}", flush=True)
(OUT / "events.txt").write_text("\n".join(events), encoding="utf-8")
