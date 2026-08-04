#!/usr/bin/env python3
"""nanobot WebUI 协议冒烟(gated)——基线见 docs/nanobot-ws-protocol.md。

gateway 没在跑 / websocket 通道没开 → 整体 SKIP(打印原因)。
**SKIP 不算通过**:verify 收口与升级 nanobot 前,必须见到实跑绿。
默认不烧 LLM(只验鉴权/握手/attach/HTTP API 形状);
DS_SMOKE_LLM=1 时追加完整消息链(delta→stream_end→turn_end)。

用法:python tests/test_ws_protocol_smoke.py
"""
import asyncio
import json
import os
import socket
import sys
import unittest
import urllib.error
import urllib.request
import uuid

HOST = "127.0.0.1"
PORT = int(os.environ.get("DS_NANOBOT_PORT", "8765"))
BASE = f"http://{HOST}:{PORT}"


def _gateway_token():
    """部署形状:静态口令在 ~/.nanobot/config.json websocket 段。"""
    p = os.path.expanduser("~/.nanobot/config.json")
    try:
        with open(p, encoding="utf-8") as f:
            ws = json.load(f)["channels"]["websocket"]
    except (OSError, KeyError, ValueError):
        return None
    if not ws.get("enabled") or not str(ws.get("token", "")).strip():
        return None
    return str(ws["token"]).strip()


def _port_open():
    s = socket.socket()
    s.settimeout(2)
    try:
        return s.connect_ex((HOST, PORT)) == 0
    finally:
        s.close()


def _skip_reason():
    if not _port_open():
        return f"gateway 未在 {HOST}:{PORT} 运行"
    if _gateway_token() is None:
        return "websocket 通道未开或未设 token(config.json)"
    try:
        import websockets  # noqa: F401
    except ImportError:
        return "websockets 库不可用(用 venv python 跑)"
    return None


SKIP = _skip_reason()


def _get(path, bearer=None):
    req = urllib.request.Request(BASE + path)
    if bearer is not None:
        req.add_header("Authorization", "Bearer " + bearer)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, None


@unittest.skipIf(SKIP, f"SKIP(不算通过): {SKIP}")
class TestWsProtocolSmoke(unittest.TestCase):
    """断言序与 docs/nanobot-ws-protocol.md 各节一一对应。"""

    def test_smoke(self):
        token = _gateway_token()
        import websockets

        # §1 bootstrap:无鉴权 401;Bearer 口令 200 + 必备字段
        st, _ = _get("/webui/bootstrap")
        self.assertEqual(st, 401)
        st, boot = _get("/webui/bootstrap", token)
        self.assertEqual(st, 200)
        for k in ("token", "ws_path", "ws_url", "expires_in"):
            self.assertIn(k, boot)

        # 坏口令 401
        st, _ = _get("/webui/bootstrap", "wrong-" + uuid.uuid4().hex)
        self.assertEqual(st, 401)

        async def ws_leg():
            url = (f"ws://{HOST}:{PORT}{boot['ws_path']}"
                   f"?client_id=ds-smoke&token={boot['token']}")
            # §2 握手 → ready 带全新 chat_id;attach 自身 → attached
            async with websockets.connect(url) as ws:
                ready = json.loads(await asyncio.wait_for(ws.recv(), 15))
                assert ready.get("event") == "ready", ready
                chat_id = ready["chat_id"]
                assert chat_id
                await ws.send(json.dumps({"type": "attach", "chat_id": chat_id}))
                att = json.loads(await asyncio.wait_for(ws.recv(), 15))
                assert att.get("event") == "attached", att
                assert att.get("chat_id") == chat_id

                if os.environ.get("DS_SMOKE_LLM") == "1":
                    # §2 完整消息链(烧一次 LLM):delta→stream_end→turn_end
                    await ws.send(json.dumps({
                        "type": "message", "chat_id": chat_id,
                        "content": "请只回复两个字:好的",
                        "webui": True, "turn_id": str(uuid.uuid4()),
                    }, ensure_ascii=False))
                    seen = set()
                    while "turn_end" not in seen:
                        msg = json.loads(await asyncio.wait_for(ws.recv(), 240))
                        seen.add(msg.get("event"))
                    assert {"delta", "stream_end", "turn_end"} <= seen, seen

            # §1 ws token 一次性:复用同一 token 二次握手必须被拒
            try:
                async with websockets.connect(url) as ws2:
                    await asyncio.wait_for(ws2.recv(), 10)
                raise AssertionError("token 复用未被拒——一次性语义变了")
            except AssertionError:
                raise
            except Exception:
                pass  # 预期:HTTP 401 拒绝握手
            return chat_id

        asyncio.run(ws_leg())

        # §3 HTTP API:sessions 200 形状;坏 token 401
        st, body = _get("/api/sessions", boot["token"])
        # bootstrap token TTL 内可复用于 HTTP;若恰好过期,重签一次
        if st == 401:
            st2, boot2 = _get("/webui/bootstrap", token)
            self.assertEqual(st2, 200)
            st, body = _get("/api/sessions", boot2["token"])
            boot = boot2
        self.assertEqual(st, 200)
        self.assertIn("sessions", body)
        st, _ = _get("/api/sessions", "wrong-token")
        self.assertEqual(st, 401)

        # §3 webui-thread(拿已有会话验形状;没有会话则跳过此小节)
        #
        # ⚠️ 2026-08-04 修夹具:原来直接取 sessions[0](按 updated_at 倒序 = 最新那个),
        # 于是**本脚本自己上一段 ws_leg 刚建的那条空会话**往往就是 sessions[0] ——
        # 连上但没发过消息的会话**没有 webui thread**,端点如实回 404
        # ("webui thread not found"),脚本就红在自己的夹具上。
        # 实测(08-04,活 gateway,122 条会话):前 25 条里 24 条 200 / 1 条 404,
        # 那 1 条正是最新的空会话 ⇒ **端点没坏,是取样取错了**。
        # 改成:往下找第一条真有 thread 的会话;一条都没有才跳过这一小节。
        # (顺带记下:每次 ws 连接都会产生一条会话,空连接也算 —— 这条事实对
        #  track opendesign-chat-reconnect 的自动重连有直接影响,已写进那份 design.md。)
        keys = [s["key"] for s in body["sessions"]]
        for k in keys:
            self.assertTrue(k.startswith("websocket:"))
        picked = None
        for k in keys[:25]:
            st, th = _get(f"/api/sessions/{k}/webui-thread?limit=1"
                          f"&direction=latest", boot["token"])
            if st == 200:
                picked = k
                break
        if picked:
            key = picked
            self.assertEqual(st, 200)
            self.assertIn("messages", th)
            self.assertEqual(th.get("sessionKey"), key)
            # R2-L6:schemaVersion 漂移探测器(doc §3 记为 3;零成本高信号,升级 nanobot
            # 若改了 thread schema 这里先炸)
            self.assertEqual(th.get("schemaVersion"), 3)


if __name__ == "__main__":
    r = unittest.main(exit=False, verbosity=2).result
    # R2-M3(07-13 盲评):unittest 的 wasSuccessful() 把 SKIP 计成功 → rc=0,任何按
    # 退出码判绿的脚本化(doc §5 升级流程 / 全量 oracle 循环)都会把"没跑"当成"跑绿"。
    # docstring 与 doc §5 都写死「SKIP 不算通过」——这里给它机械保证:SKIP 即 rc=3。
    if r.skipped and not (r.failures or r.errors):
        print("\n*** 冒烟被 SKIP,不算通过(rc=3)***", file=sys.stderr)
        sys.exit(3)
    sys.exit(0 if r.wasSuccessful() else 1)
