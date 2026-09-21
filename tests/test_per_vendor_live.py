#!/usr/bin/env python3
"""判据:**运行中的网关**换厂商,下一句真的换了(track opendesign-per-vendor-keys)。

    /root/.venvs/design-studio/bin/python tests/test_per_vendor_live.py

主 agent 亲写。这是整单唯一直接问「真的换了没有」的判据 —— 其余判据问的都是
"配置写得对不对",而实验 p2 证实过:配置写对了、网关照样可能**悄悄**用着旧厂商
(缺变量时每句前的重读抛错被吞)。所以这里:

- 用 `prepare_gateway` 产出的配置 + 外壳真会给网关的那份 env,起一个**真 nanobot 网关**;
- 两台**本机**假 OpenAI 服务分别扮演 MiMo / DeepSeek,记下每个请求的 Authorization 与 model;
- 走 `select_model`(界面点菜单调的就是它)切过去 → 发一句 → 断言命中另一台、带的是另一把 key;切回来同理。

🔴 零外网:两家的端点都指向 127.0.0.1;代理变量指向一个没人听的本机端口,
   万一有哪段代码想往外走,它会失败而不是真的连出去(判据不许有外网出口)。
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))

import ds_credential  # noqa: E402

TEMPLATE = os.path.join(ROOT, "config", "nanobot.config.windows.jsonc")
MIMO_KEY = "tp-live-oracle-mimo-0123456789abcdef"
DS_KEY = "sk-live-oracle-deepseek-0123456789ab"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FakeVendor:
    """假的 OpenAI 兼容服务:记下谁来过、带着哪把 key、要哪个模型;回一句带自己名字的话。"""

    def __init__(self, name: str):
        self.name, self.hits = name, []
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
                outer.hits.append({"auth": self.headers.get("Authorization"), "model": body.get("model")})
                text = f"我是{outer.name}"
                now = int(time.time())
                if body.get("stream"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    for delta, fin in (({"role": "assistant", "content": text}, None), ({}, "stop")):
                        chunk = {"id": "x", "object": "chat.completion.chunk", "created": now,
                                 "model": body.get("model"),
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

        self.port = free_port()
        self.srv = ThreadingHTTPServer(("127.0.0.1", self.port), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.port}/v1"

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


class LiveSwitch(unittest.TestCase):

    def setUp(self):
        try:
            import nanobot  # noqa: F401
            import websockets  # noqa: F401
        except ImportError as exc:      # 不许 SKIP:没跑 ≠ 绿(run-all 固定用 venv 解释器)
            self.fail(f"跑这份判据的解释器缺包:{exc}")
        self.tmp = tempfile.mkdtemp(prefix="ds-per-vendor-live-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.mimo, self.ds = FakeVendor("MiMo"), FakeVendor("DeepSeek")
        self.addCleanup(self.mimo.close)
        self.addCleanup(self.ds.close)
        # 目录里的端点指向两台假服务(只在本进程里改;网关进程只看配置文件)
        catalog = {k: dict(v) for k, v in ds_credential.PROVIDERS.items()}
        catalog["mimo"]["apiBase"] = self.mimo.base
        catalog["deepseek"]["apiBase"] = self.ds.base
        p = mock.patch.dict(ds_credential.PROVIDERS, catalog)
        p.start()
        self.addCleanup(p.stop)

        self.home = os.path.join(self.tmp, "UserData")
        os.makedirs(os.path.join(self.home, ".nanobot"))
        self.cfg_path = os.path.join(self.home, ".nanobot", "config.json")
        cfg = ds_credential.load_jsonc(TEMPLATE)
        cfg["providers"]["custom"]["apiBase"] = self.mimo.base
        cfg["tools"] = {"exec": {"enable": False}, "file": {"enable": False}, "web": {"enable": False}}
        self.gw_port, self.ws_port = free_port(), free_port()
        cfg["gateway"] = {"port": self.gw_port}
        cfg["channels"] = {"websocket": {"enabled": True, "host": "127.0.0.1", "port": self.ws_port,
                                         "token": "live-oracle", "websocketRequiresToken": True,
                                         "allowFrom": ["*"]}}
        cfg["agents"]["defaults"]["workspace"] = os.path.join(self.tmp, "ws")
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)

        # 业主的动作:先有 MiMo(主槽),再在有外壳的应用里存 DeepSeek
        os.makedirs(os.path.join(self.home, ".openDesign"))
        with open(os.path.join(self.home, ".openDesign", "key.txt"), "w") as fh:
            fh.write(MIMO_KEY + "\n")
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="deepseek", key=DS_KEY, multi=True)

        # 外壳起网关那一刻做的事:prepare_gateway + 主槽 key,只进网关
        extra = ds_credential.prepare_gateway(self.home, self.cfg_path)
        with open(self.cfg_path, encoding="utf-8") as fh:
            primary_var = ds_credential.env_var_name(json.load(fh))
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("DS_")}
        env.update(extra)
        env[primary_var] = MIMO_KEY
        env.update(HOME=self.home, USERPROFILE=self.home, PYTHONIOENCODING="utf-8",
                   HTTP_PROXY="http://127.0.0.1:9", HTTPS_PROXY="http://127.0.0.1:9",
                   http_proxy="http://127.0.0.1:9", https_proxy="http://127.0.0.1:9",
                   NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost")
        self.log = open(os.path.join(self.tmp, "gateway.log"), "w")
        self.addCleanup(self.log.close)
        self.gw = subprocess.Popen([sys.executable, "-m", "nanobot", "gateway", "--config", self.cfg_path],
                                   env=env, stdout=self.log, stderr=subprocess.STDOUT)
        self.addCleanup(self._stop_gateway)

    def _stop_gateway(self):
        if self.gw.poll() is None:
            self.gw.terminate()
            try:
                self.gw.wait(10)
            except subprocess.TimeoutExpired:
                self.gw.kill()

    def gateway_log(self) -> str:
        self.log.flush()
        with open(os.path.join(self.tmp, "gateway.log"), encoding="utf-8", errors="replace") as fh:
            return fh.read()[-3000:]

    async def _say(self, ws, text: str) -> None:
        """发一句,等到**任何一家**收到请求为止(收到的是哪家由调用方判)。"""
        n = len(self.mimo.hits) + len(self.ds.hits)
        await ws.send(text)
        t0 = time.monotonic()
        while time.monotonic() - t0 < 60:
            if len(self.mimo.hits) + len(self.ds.hits) > n:
                return
            try:
                await asyncio.wait_for(ws.recv(), timeout=0.5)
            except asyncio.TimeoutError:
                pass
        self.fail(f"「{text}」发出去 60 秒,两家都没收到请求。网关日志尾巴:\n{self.gateway_log()}")

    def test_l1_switching_vendor_in_the_menu_reaches_the_other_vendor_with_its_own_key(self):
        import websockets

        async def run():
            ws = None
            for _ in range(300):
                if self.gw.poll() is not None:
                    self.fail(f"网关起不来(rc={self.gw.returncode}):\n{self.gateway_log()}")
                try:
                    ws = await websockets.connect(f"ws://127.0.0.1:{self.ws_port}/?client_id=oracle&token=live-oracle")
                    break
                except OSError:
                    await asyncio.sleep(0.1)
            self.assertIsNotNone(ws, "网关 30 秒没开 websocket")
            async with ws:
                # prepare_gateway 已按「刚存了 DeepSeek」切到了 DeepSeek(v6);先切回 MiMo 作为起点
                for model, vendor, key in (("mimo-v2.5", self.mimo, MIMO_KEY),
                                           ("deepseek-v4-pro", self.ds, DS_KEY),
                                           ("mimo-v2.5-pro", self.mimo, MIMO_KEY)):
                    ds_credential.select_model(self.cfg_path, model)
                    before = (len(self.mimo.hits), len(self.ds.hits))
                    await self._say(ws, f"切到 {model} 之后的一句")
                    await asyncio.sleep(0.3)
                    new_m, new_d = self.mimo.hits[before[0]:], self.ds.hits[before[1]:]
                    got = new_m if vendor is self.mimo else new_d
                    wrong = new_d if vendor is self.mimo else new_m
                    self.assertTrue(got, f"选了 {model},请求却没到 {vendor.name}")
                    self.assertEqual(wrong, [], f"选了 {model},请求跑去了另一家:{wrong}")
                    self.assertTrue(all(h["auth"] == f"Bearer {key}" for h in got),
                                    f"{vendor.name} 收到的不是它自己的 key:{[h['auth'] for h in got]}")
                    self.assertTrue(all(h["model"] == model for h in got), f"模型名不对:{got}")

        asyncio.run(run())
        self.assertNotIn("Failed to refresh provider config", self.gateway_log(),
                         "网关每句前的重读失败过 —— 那正是「悄悄用着旧厂商」的形状")


if __name__ == "__main__":
    unittest.main(verbosity=2)
