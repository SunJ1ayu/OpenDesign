"""业主同意卡:工具停下来等业主点 —— track opendesign-consent-dock。

跑法:  python3 tests/test_consent_wait.py

以前 `set_workspace_tool` / `bind_project_tool` 排完队立刻回 {"pending": true},
这一轮对话随即结束,业主点完同意助手也不知道。现在照 ZCode:工具**停在那里等**
业主点完,再把执行后的结果交给助手(ds_tools_server.await_owner)。

这份判据只管"等"这件事本身;同意闸的安全性质(不落盘、不许绕过、卡片内容来自
落盘记录……)仍由 tests/test_ds_consent.py 全权负责,本单一条都没动它们。

考的东西:
  W1 没开等待(env 未设)⇒ 行为和以前逐字一样:立刻回 pending,不落盘。
  W2 等待中业主点「同意」⇒ 工具回执行后的结果(folder_count),配置真的改了。
  W3 等待中业主点「拒绝」⇒ 工具回 owner_rejected,配置逐字节未变。
  W4 等不到 ⇒ 回 pending + owner_decision=waiting,并且清掉"在等"标记。
  W5 「在等」标记:等待中 resolve 报 waiter=true;等完 / 被取消之后报 false
     (前端靠它决定要不要在对话里替业主补一句)。
  W6 **走真 MCP 入口**:工具在等的时候,同一个 server 上的别的工具照常响应
     (同步 sleep 会把整个 server 卡死 —— 这条是 async 的承重墙)。
  W7 外壳写进配置的两个数:等待 < nanobot 的工具超时,且只写在 design-studio 上。
  W8 (PR #2 三审)同意之后 resolve 回执带落盘结果(前端补话要说"已生效、认出几个");
     已经是这个状态时再调一遍不弹卡、直接回当前事实;换成新根照样要卡(闸没松)。

纯 stdlib + mcp、离线,不烧 LLM。
"""
import asyncio
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
sys.path.insert(0, HERE)
import ds_consent  # noqa: E402
import ds_tools    # noqa: E402
from test_ds_consent import PROJ_IN, _flatten, _mkfixture, _ws_bytes  # noqa: E402


def _mcp_missing() -> bool:
    try:
        import mcp  # noqa: F401
        return False
    except ImportError:
        return True


def _resolve_later(ds_root: str, approve: bool, delay: float = 0.3) -> dict:
    """在另一个线程里,等到有一条待确认出现,再替"业主"点下去(走 ds_web 用的同一个核心函数)。"""
    box: dict = {}

    def run():
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            pend = ds_consent.list_pending(ds_root)
            if pend:
                time.sleep(delay)
                box["r"] = ds_consent.resolve_pending(
                    ds_root, pend[0]["pending_id"], approve,
                    apply_fn=ds_tools.apply_pending)
                return
            time.sleep(0.05)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    box["thread"] = t
    return box


def _await(coro):
    return asyncio.run(coro)


@unittest.skipIf(_mcp_missing(), "未装 mcp 包")
class W_工具等业主(unittest.TestCase):
    def setUp(self):
        self.ds, self.old, self.new = _mkfixture()
        import ds_tools_server
        self.srv = ds_tools_server

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    def _staged(self):
        return ds_tools.set_workspace(self.new, ds_root=self.ds)

    def test_w1_没开等待时行为和以前一样(self):
        os.environ.pop("DS_CONSENT_WAIT_S", None)
        before = _ws_bytes(self.ds)
        t0 = time.monotonic()
        r = _await(self.srv.await_owner(self._staged(), self.ds))
        self.assertLess(time.monotonic() - t0, 1.0, "没开等待却停下来等了")
        self.assertTrue(r.get("pending"))
        self.assertNotIn("owner_decision", r, "没开等待时返回值不许变样")
        self.assertEqual(_ws_bytes(self.ds), before)

    def test_w2_等待中点同意_回执行后的结果(self):
        box = _resolve_later(self.ds, True)
        r = _await(self.srv.await_owner(self._staged(), self.ds, wait_s=8))
        box["thread"].join(5)
        self.assertEqual(r.get("owner_decision"), "approved", r)
        self.assertTrue(r.get("ok"), r)
        self.assertIn("folder_count", r, "助手要拿到执行后的事实,不是一句'大概同意了'")
        cfg = json.loads(_ws_bytes(self.ds))
        self.assertEqual(os.path.realpath(cfg["root"]), os.path.realpath(self.new))
        self.assertTrue(box["r"].get("waiter"), "等待中点下去,resolve 应该报 waiter=true")

    def test_w3_等待中点拒绝_什么都没改(self):
        before = _ws_bytes(self.ds)
        box = _resolve_later(self.ds, False)
        r = _await(self.srv.await_owner(self._staged(), self.ds, wait_s=8))
        box["thread"].join(5)
        self.assertEqual(r.get("owner_decision"), "rejected", r)
        self.assertEqual(r.get("error"), "owner_rejected")
        self.assertEqual(_ws_bytes(self.ds), before, "拒绝之后配置必须逐字节未变")

    def test_w4_等不到_回pending并清掉在等标记(self):
        before = _ws_bytes(self.ds)
        r = _await(self.srv.await_owner(self._staged(), self.ds, wait_s=0.6))
        self.assertTrue(r.get("pending"), r)
        self.assertEqual(r.get("owner_decision"), "waiting")
        self.assertIn("note", r)
        self.assertEqual(_ws_bytes(self.ds), before)
        # 之后业主再点:没有人在等了 ⇒ 前端要在对话里补一句
        res = ds_consent.resolve_pending(self.ds, r["pending_id"], True,
                                         apply_fn=ds_tools.apply_pending)
        self.assertTrue(res.get("ok"), res)
        self.assertFalse(res.get("waiter"), "等超时之后还报'在等',前端就不会告诉助手结果")

    def test_w5_被取消_比如业主点了停止_也要清掉在等标记(self):
        staged = self._staged()

        async def run():
            task = asyncio.create_task(self.srv.await_owner(staged, self.ds, wait_s=30))
            await asyncio.sleep(0.4)
            rec = ds_consent.get_pending(self.ds, staged["pending_id"])
            self.assertTrue(ds_consent._waiter_alive(rec), "等待中必须标着'在等'")
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        _await(run())
        res = ds_consent.resolve_pending(self.ds, staged["pending_id"], False)
        self.assertTrue(res.get("ok"), res)
        self.assertFalse(res.get("waiter"), "取消之后还报'在等'")

    def test_w5b_进程被直接杀掉_标记也会自己过期(self):
        """finally 跑不到时(进程被杀),靠截止时刻自然失效,不会永远'在等'。"""
        staged = self._staged()
        ds_consent.mark_waiter(self.ds, staged["pending_id"], "2000-01-01T00:00:00")
        res = ds_consent.resolve_pending(self.ds, staged["pending_id"], False)
        self.assertFalse(res.get("waiter"))

    def test_w6_真MCP入口_等待期间同一server的别的工具照常响应(self):
        import ds_mcp
        saved = {k: os.environ.get(k) for k in ("DS_ROOT", "DS_CONSENT_WAIT_S")}
        os.environ["DS_ROOT"] = self.ds
        os.environ["DS_CONSENT_WAIT_S"] = "8"
        try:
            server = ds_mcp.build("tools")

            async def run():
                waiting = asyncio.create_task(
                    server.call_tool("set_workspace_tool", {"root": self.new}))
                await asyncio.sleep(0.5)
                self.assertFalse(waiting.done(), "工具没有停下来等业主")
                t0 = time.monotonic()
                other = await asyncio.wait_for(
                    server.call_tool("list_projects_tool", {}), timeout=5)
                self.assertLess(time.monotonic() - t0, 2.0,
                                "等待把同一个 server 上的其它工具卡住了(同步 sleep?)")
                self.assertIn(PROJ_IN, _flatten(other))
                box = _resolve_later(self.ds, True, delay=0)
                r = json.loads(_flatten(await asyncio.wait_for(waiting, timeout=10)))
                box["thread"].join(5)
                return r

            r = asyncio.run(run())
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        self.assertEqual(r.get("owner_decision"), "approved", r)
        self.assertIn("folder_count", r)


class W7_外壳写进配置的两个数(unittest.TestCase):
    def test_w7_等待短于nanobot超时_且只写在design_studio上(self):
        import ds_shell_core as core
        self.assertGreater(core.CONSENT_TOOL_TIMEOUT_S, core.CONSENT_WAIT_S + 10,
                           "nanobot 的超时必须明显长于等待,否则助手只收到一句 timed out")
        d = tempfile.mkdtemp(prefix="consent_wait_cfg_")
        try:
            path = os.path.join(d, "config.json")
            servers = {n: {"command": "x", "args": [], "env": {}} for n in core.OUR_MCP}
            servers["别人家的"] = {"command": "npx", "args": []}
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"channels": {"websocket": {"enabled": True, "token": "abc"}},
                           "tools": {"mcpServers": servers}}, fh)
            core.patch_config(path, gateway_port=1, ws_port=2, python_exe="py")
            with open(path, encoding="utf-8") as fh:
                got = json.load(fh)["tools"]["mcpServers"]
        finally:
            shutil.rmtree(d, ignore_errors=True)
        ds = got["design-studio"]
        self.assertEqual(ds["env"]["DS_CONSENT_WAIT_S"], str(core.CONSENT_WAIT_S))
        self.assertEqual(ds["toolTimeout"], core.CONSENT_TOOL_TIMEOUT_S)
        for n in ("design-studio-organize", "design-studio-refs", "别人家的"):
            self.assertNotIn("toolTimeout", got[n], f"{n} 不该被改超时")
            self.assertNotIn("DS_CONSENT_WAIT_S", got[n].get("env", {}))


class W8_点完之后助手别再重复申请(unittest.TestCase):
    def setUp(self):
        self.ds, self.old, self.new = _mkfixture()

    def tearDown(self):
        shutil.rmtree(self.ds, ignore_errors=True)

    def test_w8a_同意的回执带落盘结果_拒绝的不带(self):
        pid = ds_tools.set_workspace(self.new, ds_root=self.ds)["pending_id"]
        r = ds_consent.resolve_pending(self.ds, pid, True, apply_fn=ds_tools.apply_pending)
        self.assertTrue(r.get("ok"), r)
        self.assertIsInstance(r.get("result"), dict, "回执里没有执行结果,前端没法告诉助手认出了几个")
        self.assertIn("folder_count", r["result"])
        pid2 = ds_tools.set_workspace(self.old, ds_root=self.ds)["pending_id"]
        r2 = ds_consent.resolve_pending(self.ds, pid2, False)
        self.assertNotIn("result", r2)

    def test_w8b_已经是这个根了再调一遍_不弹卡直接回当前事实(self):
        before = _ws_bytes(self.ds)
        r = ds_tools.set_workspace(self.old, ds_root=self.ds)
        self.assertTrue(r.get("ok") and r.get("unchanged"), r)
        self.assertFalse(r.get("pending"), "什么都不会变,却又弹了一张卡")
        self.assertIn("folder_count", r)
        self.assertEqual(ds_consent.list_pending(self.ds), [])
        self.assertEqual(_ws_bytes(self.ds), before)

    def test_w8c_换成新根照样要卡_闸没松(self):
        r = ds_tools.set_workspace(self.new, ds_root=self.ds)
        self.assertTrue(r.get("pending"), "新根必须走同意卡")
        # 同一个根、但换了项目夹子目录:也算改动,照样要卡
        r2 = ds_tools.set_workspace(self.old, projects_dir=".", ds_root=self.ds)
        self.assertTrue(r2.get("pending"), r2)

    def test_w8d_已经这么关联着再绑一遍_不弹卡(self):
        cfg = json.loads(_ws_bytes(self.ds))
        cfg["projects"] = {PROJ_IN: f"01-项目/{PROJ_IN}"}
        with open(os.path.join(self.ds, "config", "workspace.json"), "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False)
        r = ds_tools.bind_project(PROJ_IN, PROJ_IN, ds_root=self.ds)
        self.assertTrue(r.get("ok") and r.get("unchanged"), r)
        self.assertEqual(ds_consent.list_pending(self.ds), [])


if __name__ == "__main__":
    unittest.main()
