#!/usr/bin/env python3
"""判据:**运行中的网关**,存 key 之后下一句就用上 —— 不重启(track opendesign-key-restart)。

    /root/.venvs/design-studio/bin/python tests/test_key_live.py

主 agent 亲写,判据先单独 commit。业主 09-25:「我切换模型填入api key之后 新对话一直显示链接不上gateway」
「那就直接改成zcode那样不就好了吗」。ZCode 是存了就能用;我们以前是存 key ⇒ 重启网关,而那条重启在 Windows 上卡死。

L 组问的是业主眼里的那件事:**同一个网关进程、同一条 websocket**,存 key 之后下一句带的是新 key。
- 网关用**外壳自己的** argv(`ds_shell_core.gateway_argv`)与 env(`service_envs`)起 —— 判据不手拼,
  外壳那一跳坏了这里就和业主机器上一样红(沿用 test_per_vendor_live 第 1 轮 G4 的做法)。
- 不传 `--config`:和装好的应用一样,靠 HOME 指到 UserData 找 `~/.nanobot/config.json`。
- 三台本机假厂商(MiMo / DeepSeek / 自定义中转)记下每个请求的 Authorization 与 model。
- 全程一条 websocket:网关若被重启,这条连接会断,判据当场红。

G 组问启动器的钩子本身:文件优先、文件没有落回 env、两边都没有照 nanobot 原样抛;钩不上就拒绝开跑。

🔴 零外网:端点全是 127.0.0.1;代理变量指向没人听的本机端口。
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
sys.path.insert(0, HERE)

import ds_credential  # noqa: E402
import ds_shell_core as core  # noqa: E402
from test_per_vendor_live import FakeVendor, free_port  # noqa: E402

TEMPLATE = os.path.join(ROOT, "config", "nanobot.config.windows.jsonc")
K1 = "tp-keylive-oracle-mimo-one-0123456789"
K2 = "tp-keylive-oracle-mimo-two-9876543210"
DS_KEY = "sk-keylive-oracle-deepseek-0123456789"
RELAY_KEY = "sk-keylive-oracle-relay-0123456789ab"


class LiveKey(unittest.TestCase):

    def setUp(self):
        try:
            import nanobot  # noqa: F401
            import websockets  # noqa: F401
        except ImportError as exc:      # 不许 SKIP:没跑 ≠ 绿
            self.fail(f"跑这份判据的解释器缺包:{exc}")
        self.tmp = tempfile.mkdtemp(prefix="ds-key-live-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.mimo, self.ds, self.relay = FakeVendor("MiMo"), FakeVendor("DeepSeek"), FakeVendor("中转")
        for v in (self.mimo, self.ds, self.relay):
            self.addCleanup(v.close)
        catalog = {k: dict(v) for k, v in ds_credential.PROVIDERS.items()}
        catalog["mimo"]["apiBase"] = self.mimo.base
        catalog["deepseek"]["apiBase"] = self.ds.base
        p = mock.patch.dict(ds_credential.PROVIDERS, catalog)
        p.start()
        self.addCleanup(p.stop)

        self.home = os.path.join(self.tmp, "UserData")
        os.makedirs(os.path.join(self.home, ".nanobot"))
        os.makedirs(os.path.join(self.home, ".openDesign"))
        self.cfg_path = os.path.join(self.home, ".nanobot", "config.json")
        cfg = ds_credential.load_jsonc(TEMPLATE)
        cfg["providers"]["custom"]["apiBase"] = self.mimo.base
        cfg["tools"] = {"exec": {"enable": False}, "file": {"enable": False}, "web": {"enable": False}}
        self.ws_port = free_port()
        cfg["gateway"] = {"port": free_port()}
        cfg["channels"] = {"websocket": {"enabled": True, "host": "127.0.0.1", "port": self.ws_port,
                                         "token": "key-live", "websocketRequiresToken": True,
                                         "allowFrom": ["*"]}}
        cfg["agents"]["defaults"]["workspace"] = os.path.join(self.tmp, "ws")
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
        with open(os.path.join(self.home, ".openDesign", "key.txt"), "w", encoding="utf-8") as fh:
            fh.write(K1 + "\n")

        # 外壳起网关那一刻做的事,全用外壳自己的函数(ds_shell.build_env 同款)
        extra = ds_credential.prepare_gateway(self.home, self.cfg_path)
        with open(self.cfg_path, encoding="utf-8") as fh:
            primary_var = ds_credential.env_var_name(json.load(fh))
        env = core.service_envs(dict(os.environ), ds_root=ROOT, user_home=self.home, dsweb_port=1,
                                ws_port=self.ws_port, key=ds_credential.read_key(self.home),
                                key_var=primary_var, extra_keys=extra)["网关"]
        env.update(HOME=self.home, USERPROFILE=self.home, PYTHONIOENCODING="utf-8",
                   HTTP_PROXY="http://127.0.0.1:9", HTTPS_PROXY="http://127.0.0.1:9",
                   http_proxy="http://127.0.0.1:9", https_proxy="http://127.0.0.1:9",
                   NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost")
        self.assertEqual(env.get(primary_var), K1, "外壳注入的主槽 key 不是 key.txt 里那把 —— 起点就错了")
        self.log = open(os.path.join(self.tmp, "gateway.log"), "w")
        self.addCleanup(self.log.close)
        argv = core.gateway_argv(sys.executable, ROOT)
        self.gw = subprocess.Popen(argv, env=env, stdout=self.log, stderr=subprocess.STDOUT,
                                   stdin=subprocess.DEVNULL)
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

    def vendors(self):
        return (self.mimo, self.ds, self.relay)

    async def _connect(self):
        import websockets
        for _ in range(300):
            alive = self.gw.poll() is None
            self.assertTrue(alive, f"网关起不来(rc={self.gw.returncode}):\n{self.gateway_log() if not alive else ''}")
            try:
                return await websockets.connect(f"ws://127.0.0.1:{self.ws_port}/?client_id=oracle&token=key-live")
            except OSError:
                await asyncio.sleep(0.1)
        self.fail("网关 30 秒没开 websocket")

    async def _say_expect(self, ws, text: str, vendor: FakeVendor, key: str, model: str) -> None:
        before = [len(v.hits) for v in self.vendors()]
        await ws.send(text)
        t0 = time.monotonic()
        arrived = False
        while time.monotonic() - t0 < 60:
            if any(len(v.hits) > b for v, b in zip(self.vendors(), before)):
                arrived = True
                break
            try:
                await asyncio.wait_for(ws.recv(), timeout=0.5)
            except asyncio.TimeoutError:
                pass
        await asyncio.sleep(0.3)
        # 断言都在循环外、每次都执行(死断言闸)
        self.assertTrue(arrived, f"「{text}」发出去 60 秒,哪家都没收到请求。网关日志尾巴:\n{self.gateway_log()}")
        new = {v.name: v.hits[b:] for v, b in zip(self.vendors(), before)}
        got = new[vendor.name]
        wrong = {n: h for n, h in new.items() if n != vendor.name and h}
        self.assertTrue(got, f"「{text}」该到 {vendor.name},却到了:{wrong}")
        self.assertEqual(wrong, {}, f"「{text}」同时跑去了别家:{wrong}")
        self.assertTrue(all(h["auth"] == f"Bearer {key}" for h in got),
                        f"「{text}」{vendor.name} 收到的不是刚存的那把 key:{[h['auth'][-10:] for h in got]}")
        self.assertTrue(all(h["model"] == model for h in got), f"模型名不对:{got}")
        self.assertIsNone(self.gw.poll(), "网关进程没了 —— 存 key 不该碰它")

    def test_l1_keys_saved_in_settings_are_used_on_the_next_turn_without_restarting(self):
        pid = self.gw.pid

        async def run():
            ws = await self._connect()
            async with ws:
                await self._say_expect(ws, "起点:主槽第一把 key", self.mimo, K1, "mimo-v2.5")

                # ① 主槽换 key(填错了重填,最常见的一种)
                ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="mimo", key=K2,
                                   multi=True, switch=False)
                await self._say_expect(ws, "主槽换了 key 之后", self.mimo, K2, "mimo-v2.5")

                # ② 设置页给第二家存 key(switch=False:不换当前模型)→ 聊天框菜单切过去
                ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="deepseek", key=DS_KEY,
                                   multi=True, switch=False)
                await self._say_expect(ws, "存了 DeepSeek 但还没切", self.mimo, K2, "mimo-v2.5")
                ds_credential.select_model(self.cfg_path, "deepseek-v4-pro", provider="deepseek", home=self.home)
                await self._say_expect(ws, "切到 DeepSeek 之后", self.ds, DS_KEY, "deepseek-v4-pro")

                # ③ 添加带 key 的自定义供应商 → 切过去
                cid = ds_credential.add_custom_provider(self.home, self.cfg_path, label="我的中转",
                                                        api_base=self.relay.base, models=["relay-1"],
                                                        key=RELAY_KEY)
                ds_credential.select_model(self.cfg_path, "relay-1", provider=cid, home=self.home)
                await self._say_expect(ws, "切到自定义中转之后", self.relay, RELAY_KEY, "relay-1")

                # ④ 切回主槽:用的是换过的那把
                ds_credential.select_model(self.cfg_path, "mimo-v2.5-pro", provider="mimo", home=self.home)
                await self._say_expect(ws, "切回 MiMo", self.mimo, K2, "mimo-v2.5-pro")

        asyncio.run(run())
        self.assertEqual(self.gw.pid, pid)
        self.assertIsNone(self.gw.poll(), "网关进程没了")
        self.assertNotIn("Failed to refresh provider config", self.gateway_log(),
                         "网关每句前的重读失败过 —— 那正是「悄悄用着旧 key / 旧厂商」的形状")
        cfg_text = open(self.cfg_path, encoding="utf-8").read()
        for k in (K1, K2, DS_KEY, RELAY_KEY):
            self.assertNotIn(k, cfg_text, "key 原文进了配置 —— 「原文永不进配置」契约破了")


class LauncherHook(unittest.TestCase):
    """G 组:`bin/ds_gateway.py` 装到 nanobot 上的那个钩子。在子进程里装(钩子改的是模块全局,不污染本进程)。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ds-key-hook-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = os.path.join(self.tmp, "UserData")
        os.makedirs(os.path.join(self.home, ".nanobot"))
        os.makedirs(os.path.join(self.home, ".openDesign", "keys"))
        self.cfg_path = os.path.join(self.home, ".nanobot", "config.json")
        cfg = ds_credential.load_jsonc(TEMPLATE)
        cfg["providers"]["od_deepseek"] = {"apiKey": "${DS_LLM_KEY_DEEPSEEK}", "apiBase": "http://127.0.0.1:9/v1"}
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)

    def resolve(self, env_extra: dict, files: dict) -> subprocess.CompletedProcess:
        for rel, body in files.items():
            with open(os.path.join(self.home, ".openDesign", rel), "w", encoding="utf-8") as fh:
                fh.write(body + "\n")
        code = (
            "import json,sys\n"
            f"sys.path.insert(0, {os.path.join(ROOT, 'bin')!r})\n"
            "import ds_gateway\n"
            "ds_gateway.install_live_keys()\n"
            "from nanobot.config.loader import load_config, resolve_config_env_vars\n"
            "try:\n"
            f"    c = resolve_config_env_vars(load_config({self.cfg_path!r}))\n"
            "except ValueError as e:\n"
            "    print(json.dumps({'error': str(e)})); sys.exit(0)\n"
            "print(json.dumps({'main': c.providers.custom.api_key,"
            " 'ds': getattr(getattr(c.providers, 'od_deepseek', None), 'api_key', None)}))\n"
        )
        env = {k: v for k, v in os.environ.items() if not k.startswith("DS_")}
        env.update(HOME=self.home, USERPROFILE=self.home, DS_ROOT=ROOT, **env_extra)
        return subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)

    def out(self, r: subprocess.CompletedProcess) -> dict:
        self.assertEqual(r.returncode, 0, f"子进程出错:\n{r.stderr[-2000:]}")
        return json.loads(r.stdout.strip().splitlines()[-1])

    def test_g1_the_file_wins_over_the_start_time_env(self):
        """网关启动时 env 里注入的是旧 key;业主随后在设置页换了 ⇒ 解析出来必须是文件里的新 key。"""
        d = self.out(self.resolve({"DS_LLM_KEY": "sk-start-time-env-0000", "DS_LLM_KEY_DEEPSEEK": "sk-old-ds-env-0000"},
                                  {"key.txt": "sk-file-main-1111", "keys/deepseek.txt": "sk-file-ds-2222"}))
        self.assertEqual(d.get("main"), "sk-file-main-1111", d)
        self.assertEqual(d.get("ds"), "sk-file-ds-2222", d)

    def test_g2_a_missing_file_falls_back_to_the_env(self):
        d = self.out(self.resolve({"DS_LLM_KEY": "sk-start-time-env-0000", "DS_LLM_KEY_DEEPSEEK": "sk-old-ds-env-0000"}, {}))
        self.assertEqual(d.get("main"), "sk-start-time-env-0000", d)
        self.assertEqual(d.get("ds"), "sk-old-ds-env-0000", d)

    def test_g3_neither_file_nor_env_still_raises_like_nanobot(self):
        """两边都没有 ⇒ 照 nanobot 原样抛,不许悄悄解析成空串(空 key 会被当成「配好了」发出去)。"""
        d = self.out(self.resolve({}, {}))
        self.assertIn("error", d, d)
        self.assertRegex(d["error"], r"DS_LLM_KEY")

    def test_g4_the_launcher_refuses_to_run_when_the_hook_point_is_gone(self):
        """nanobot 升级把 `_env_replace` 改名 / 不再按全局名查 ⇒ 启动器必须当场拒绝,
        不许静默退回「只认启动时的 env」(那样存 key 不生效、界面却说下一句就用)。"""
        code = (
            "import sys\n"
            f"sys.path.insert(0, {os.path.join(ROOT, 'bin')!r})\n"
            "import nanobot.config.loader as L\n"
            "del L._env_replace\n"
            "import ds_gateway\n"
            "try:\n"
            "    ds_gateway.install_live_keys()\n"
            "except SystemExit as e:\n"
            "    print('REFUSED', e.code if isinstance(e.code, str) else ''); sys.exit(0)\n"
            "print('INSTALLED')\n"
        )
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
        self.assertIn("REFUSED", r.stdout, f"钩点不在了,启动器照样开跑:\n{r.stdout}\n{r.stderr[-1500:]}")
        self.assertTrue(re.search(r"[\u4e00-\u9fff]", r.stdout), f"拒绝时没说人话:{r.stdout!r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
