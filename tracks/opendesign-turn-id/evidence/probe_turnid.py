#!/usr/bin/env python3
"""协议探针:我们在出站信封里发的 turn_id,回放里还认得出来吗?

问的就一件事(turn_id 对账的地基):
  webui-thread 回放里那条 user 消息的 `turnId` == 我发出去时填的 `turn_id` 吗?
"""
import asyncio
import json
import os
import sys
import urllib.request
import uuid

import websockets

HOST, PORT = "127.0.0.1", 8765
BASE = f"http://{HOST}:{PORT}"
PASSWORD = json.load(open(os.path.expanduser("~/.nanobot/config.json")))[
    "channels"]["websocket"]["token"]


def http_get(path, token):
    req = urllib.request.Request(BASE + path,
                                 headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


async def main():
    boot = http_get("/webui/bootstrap", PASSWORD)
    ws_token = boot["token"]
    my_turn = str(uuid.uuid4())
    print("我发出去的 turn_id =", my_turn)

    chat_id = None
    url = f"ws://{HOST}:{PORT}{boot['ws_path']}?client_id=ds-probe&token={ws_token}"
    async with websockets.connect(url) as ws:
        while True:
            ev = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
            if ev.get("event") == "ready":
                chat_id = ev["chat_id"]
                break
        print("chat_id =", chat_id)
        await ws.send(json.dumps({
            "type": "message", "chat_id": chat_id,
            "content": "探针:请只回复「收到」两个字,不要调用任何工具",
            "webui": True, "turn_id": my_turn,
        }))
        seen_events = []
        while True:
            ev = json.loads(await asyncio.wait_for(ws.recv(), timeout=180))
            seen_events.append(ev.get("event"))
            if ev.get("event") == "turn_end":
                break
        print("事件序列:", [e for e in seen_events if e][:12], "…")

    # ws token 是一次性的(握手时被消费)⇒ 读历史要另取一枚
    thread = http_get(f"/api/sessions/websocket:{chat_id}/webui-thread",
                      http_get("/webui/bootstrap", PASSWORD)["token"])
    print("\n--- 回放 messages ---")
    for m in thread["messages"]:
        print(json.dumps({k: m.get(k) for k in
                          ("id", "role", "turnId", "turnPhase", "turnSeq", "kind")},
                         ensure_ascii=False),
              "| content:", repr(m.get("content", ""))[:40])
    users = [m for m in thread["messages"] if m.get("role") == "user"]
    ok = bool(users) and users[0].get("turnId") == my_turn
    print("\n结论:回放 user.turnId == 我发的 turn_id ?", "✅ 是" if ok else "❌ 否",
          "| 回放值 =", users[0].get("turnId") if users else "(没有 user 消息)")
    return 0 if ok else 1


sys.exit(asyncio.run(main()))
