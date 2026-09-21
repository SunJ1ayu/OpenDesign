"""真网关切厂商实验:同一个网关进程里,只改 modelPreset,下一句是否真打到另一家、用另一把 key。"""
import asyncio, json, os, subprocess, sys, tempfile, time
from pathlib import Path
import websockets
HERE = Path(__file__).parent
PY = "/root/.venvs/design-studio/bin/python"
A, B, GW, WS = 28801, 28802, 28790, 28791
hits = HERE / "hits.jsonl"; hits.write_text("")
home = Path(tempfile.mkdtemp(prefix="live-probe-")); (home / ".nanobot").mkdir()
cfg_path = home / ".nanobot" / "config.json"
cfg = {
  "providers": {
    "custom": {"apiKey": "${DS_LLM_KEY}", "apiBase": f"http://127.0.0.1:{A}/v1"},
    "od_deepseek": {"apiKey": "${DS_LLM_KEY_DEEPSEEK}", "apiBase": f"http://127.0.0.1:{B}/v1"},
  },
  "model_presets": {
    "mimo-v2.5": {"label": "mimo-v2.5", "provider": "custom", "model": "mimo-v2.5"},
    "deepseek-v4-flash": {"label": "deepseek-v4-flash", "provider": "od_deepseek", "model": "deepseek-v4-flash"},
  },
  "agents": {"defaults": {"modelPreset": "mimo-v2.5", "workspace": str(home / "ws")}},
  "gateway": {"port": GW},
  "channels": {"websocket": {"enabled": True, "host": "127.0.0.1", "port": WS, "token": "t0k",
                             "websocketRequiresToken": True, "allowFrom": ["*"]}},
  "tools": {"web": {"enable": False}, "exec": {"enable": False}},
}
def write(preset, extra_provider=None):
    c = json.loads(json.dumps(cfg)); c["agents"]["defaults"]["modelPreset"] = preset
    if extra_provider: c["providers"].update(extra_provider)
    tmp = cfg_path.with_suffix(".tmp"); tmp.write_text(json.dumps(c)); os.replace(tmp, cfg_path)
write("mimo-v2.5")
procs = [subprocess.Popen([PY, str(HERE / "mock_llm.py"), n, str(p), str(hits)]) for n, p in (("A-mimo", A), ("B-deepseek", B))]
env = {k: v for k, v in os.environ.items() if not k.startswith("DS_")}
env.update(HOME=str(home), DS_LLM_KEY="key-A-mimo", DS_LLM_KEY_DEEPSEEK="key-B-deepseek",
           NO_PROXY="*", no_proxy="*", HTTP_PROXY="", HTTPS_PROXY="", http_proxy="", https_proxy="")
gw = subprocess.Popen([PY, "-m", "nanobot", "gateway", "--config", str(cfg_path)], env=env,
                      stdout=open(HERE / "gw.log", "w"), stderr=subprocess.STDOUT)
async def say(ws, text):
    await ws.send(text)
    t0 = time.time()
    while time.time() - t0 < 40:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=40)
        except asyncio.TimeoutError:
            break
        try: ev = json.loads(raw)
        except Exception: continue
        if ev.get("event") == "message" and ev.get("text"):
            return ev["text"]
        if ev.get("event") in ("message",) and ev.get("content"):
            return ev["content"]
    return None
def last_hit():
    lines = [json.loads(l) for l in hits.read_text().splitlines() if l.strip()]
    return lines[-1] if lines else None
async def main():
    for _ in range(100):
        try:
            ws = await websockets.connect(f"ws://127.0.0.1:{WS}/?client_id=probe&token=t0k"); break
        except Exception: await asyncio.sleep(0.2)
    else:
        print("ws never came up"); return
    async with ws:
        steps = [("mimo-v2.5", None, "第一句"), ("deepseek-v4-flash", None, "第二句"), ("mimo-v2.5", None, "第三句"),
                 # 缺变量:配置里多引用一个网关进程 env 里没有的变量,同时要求切到 deepseek
                 ("deepseek-v4-flash", {"od_other": {"apiKey": "${DS_LLM_KEY_OTHER}", "apiBase": "http://127.0.0.1:9/v1"}}, "第四句(缺变量)")]
        for preset, extra, text in steps:
            write(preset, extra)
            n_before = len(hits.read_text().splitlines())
            reply = await say(ws, text)
            new = [json.loads(l) for l in hits.read_text().splitlines()[n_before:] if l.strip()]
            print(f"config→{preset:18} | 回复={reply!r:16} | 本句打到={[(h['server'], h['auth'], h['model']) for h in new]}")
try:
    asyncio.run(main())
finally:
    gw.terminate(); [p.terminate() for p in procs]
    time.sleep(1)
