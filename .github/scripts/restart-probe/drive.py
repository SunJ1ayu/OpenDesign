"""track opendesign-key-restart 探针:真 Windows 上「聊天页连着 → 设置页存 key → 外壳自动重启网关」整条链,全程记录。

**只观察、不判卷**(不是判据):业主真机 09-25 00:32 存 key 后,新网关两分半一行日志都没写、始终没起来,
而在 Linux 上同一条路径栽在另一处(端口试探被 TIME_WAIT 挡)。这支探针回答「Windows 上新网关卡在哪」。

用法(由 windows-restart-probe.yml 调):<包里的 python.exe> drive.py <pkg 目录> <live|idle> <输出目录>
  live = 先经工作台签 token、开一条活 websocket 挂着(= 业主聊天页连着),再存 key;
  idle = 什么都不连就存 key(对照组)。
零外网:代理变量指向没人听的本机端口;不发任何聊天消息。
"""
import json, os, socket, subprocess, sys, threading, time, urllib.error, urllib.request
from pathlib import Path

PKG, ARM, OUT = Path(sys.argv[1]).resolve(), sys.argv[2], Path(sys.argv[3]).resolve() / sys.argv[2]
PY = PKG / "python" / "python.exe"
sys.path.insert(0, str(PKG / "ds" / "bin"))
import ds_credential  # noqa: E402

app = OUT / "appdata"
home = app / "OpenDesign" / "UserData"
logs = app / "OpenDesign" / "Logs"
(home / ".nanobot").mkdir(parents=True, exist_ok=True)
(home / ".openDesign").mkdir(parents=True, exist_ok=True)
cfg = ds_credential.load_jsonc(str(PKG / "ds" / "config" / "nanobot.config.windows.jsonc"))
ws_cfg = cfg.setdefault("channels", {}).setdefault("websocket", {})
ws_cfg.update(enabled=True, host="127.0.0.1", token="probe-kouling", websocketRequiresToken=True, allowFrom=["*"])
(home / ".nanobot" / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
(home / ".openDesign" / "key.txt").write_text("tp-probe-mimo-0123456789abcdef\n", encoding="utf-8")

dead = "http://127.0.0.1:9"
env = dict(os.environ, LOCALAPPDATA=str(app), PROBE_FAULT="1", PYTHONIOENCODING="utf-8",
           HTTP_PROXY=dead, HTTPS_PROXY=dead, http_proxy=dead, https_proxy=dead,
           NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost")
t0 = time.monotonic()
events = []


def say(msg):
    line = f"[{ARM} +{time.monotonic() - t0:6.1f}s] {msg}"
    print(line, flush=True)
    events.append(line)


def listening(port):
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


op = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def get(port, path, timeout=5):
    try:
        with op.open(f"http://127.0.0.1:{port}{path}", timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:
        return repr(e)[:80], b""


def snapshot(tag):
    """python 进程(pid/父 pid/命令行)+ 端口状态,写进 procs.txt。"""
    ps = subprocess.run(["powershell", "-NoProfile", "-Command",
                         "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                         "ForEach-Object { \"$($_.ProcessId) ppid=$($_.ParentProcessId) "
                         "t=$($_.CreationDate) $($_.CommandLine)\" }"],
                        capture_output=True, text=True, timeout=60).stdout
    ns = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, timeout=30).stdout
    ns = "\n".join(l for l in ns.splitlines() if f":{wsport} " in l or ":18790 " in l)
    with (OUT / "procs.txt").open("a", encoding="utf-8") as f:
        f.write(f"==== {tag} +{time.monotonic() - t0:.1f}s\n{ps}\n-- netstat\n{ns}\n")


host = subprocess.Popen([str(PY), str(PKG / "ds" / "bin" / "ds_host.py")], env=env,
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE)
first = {}
threading.Thread(target=lambda: first.setdefault("line", host.stdout.readline()), daemon=True).start()
while "line" not in first and time.monotonic() - t0 < 420:
    time.sleep(0.2)
say(f"host 第一帧: {first.get('line', b'(超时)')[:300]!r}")
ready = json.loads(first["line"])
web = ready["web_port"]
wsport = json.loads((home / ".nanobot" / "config.json").read_text(encoding="utf-8"))["channels"]["websocket"]["port"]
say(f"web={web} ws={wsport} ws在听={listening(wsport)}")
snapshot("起好之后")

live = {"open": False, "closed_at": None}
if ARM == "live":
    code, body = get(web, "/api/chat/bootstrap")
    say(f"bootstrap(经工作台)= {code}")
    info = json.loads(body)
    from websockets.sync.client import connect
    path = info.get("ws_path") if str(info.get("ws_path", "")).startswith("/") else "/"
    ws = connect(f"ws://127.0.0.1:{wsport}{path}?client_id=probe-1&token={info['token']}", open_timeout=20)
    live["open"] = True
    say("活 websocket 已连上(= 业主聊天页连着)")

    def pump():
        try:
            while True:
                ws.recv()
        except Exception as e:
            live["closed_at"] = time.monotonic() - t0
            live["why"] = repr(e)[:120]
    threading.Thread(target=pump, daemon=True).start()
    time.sleep(3)

req = urllib.request.Request(f"http://127.0.0.1:{web}/api/llm/providers/key", method="POST",
                             data=json.dumps({"provider": "deepseek", "key": "sk-probe-deepseek-0123456789ab"}).encode(),
                             headers={"Content-Type": "application/json"})
try:
    with op.open(req, timeout=60) as r:
        say(f"存 key = {r.status} restart={json.loads(r.read()).get('restart')}")
except urllib.error.HTTPError as e:
    say(f"存 key = HTTP {e.code} {e.read()[:200]!r}")

gw_log = logs / "网关.log"
base = gw_log.stat().st_size if gw_log.exists() else 0
last = None
up_at = None
for i in range(120):                                  # 最多看 240s(业主等了 155s)
    now = (listening(wsport), get(web, "/api/chat/bootstrap", timeout=3)[0], host.poll() is None,
           (gw_log.stat().st_size - base) if gw_log.exists() else -1)
    if now != last:
        say(f"ws在听={now[0]} bootstrap={now[1]} 管家活着={now[2]} 网关.log新增={now[3]}B 活ws断于={live['closed_at']}")
        last = now
    if i % 5 == 0:
        snapshot(f"存key后第{i}轮")
    if now[0] and now[1] == 200:
        up_at = time.monotonic() - t0
        break
    time.sleep(2)
say(f"结论:新网关{'起来了 @+%.1fs' % up_at if up_at else '240s 内没起来'}")
snapshot("收摊前")
try:
    host.stdin.write(b'{"cmd":"quit"}\n')
    host.stdin.flush()
    host.wait(60)
except Exception as e:
    say(f"收摊异常 {e!r}")
    host.kill()
for name in ("外壳.log", "网关.log", "工作台.log"):
    p = logs / name
    txt = p.read_text(encoding="utf-8", errors="replace") if p.exists() else "(没有)"
    (OUT / name).write_text(txt, encoding="utf-8")
    print(f"\n======== {ARM} {name}(尾 6000 字)========\n{txt[-6000:]}", flush=True)
(OUT / "events.txt").write_text("\n".join(events), encoding="utf-8")
