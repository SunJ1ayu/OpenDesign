#!/usr/bin/env python3
"""判据:存 key 之后「网关在跑就不碰它,没在跑才起它」+ 子进程不共用管家的输入(track opendesign-key-restart)。

    /root/.venvs/design-studio/bin/python tests/test_key_restart.py

主 agent 亲写,判据先单独 commit。真网关用上新 key 那件事在 test_key_live.py;这里问接在它两头的零件:

- S(外壳 Supervisor):S1 子进程的 stdin 是空设备 —— Windows 探针 probe-3/probe-4:新网关继承了管家正同步读着的
  stdin 管道就卡死(240s 没进 Python),只改 stdin=DEVNULL 的两组 1.5s 起来(evidence/20260925-windows-probe-*.txt)。
  Linux 复现不了那种卡死 ⇒ 这里问的是「子进程拿到的到底是什么」;S2 `ensure` 不碰活着的腿、补起没有的 / 死了的腿。
- W(工作台 ds_web):W1 网关端口在听 ⇒ `live` 且**一个帧都不发**;W2 不在听 ⇒ 帧送到 ⇒ `requested`;W3 没外壳 ⇒ `manual`。
- K(存 key 当场对齐配置):K1 设置页存第二家 ⇒ 配置当场有这家的条目(只含 ${VAR})、这一行 live 不 pending;
  K2 引导页那条(switch=True)⇒ 当场换过去;K3 自定义供应商带 key 同理。
- R(外壳接线,真跑 start_backend、只换掉开进程):R1 锁帧回调走 ensure 不走 restart;R2 网关用启动器起,不再 `-m nanobot`。
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
sys.path.insert(0, HERE)

import ds_credential  # noqa: E402
import ds_shell as shell  # noqa: E402
import ds_shell_core as core  # noqa: E402
import test_ds_web_credential as wc  # noqa: E402
import test_ds_shell_startup as st  # noqa: E402
from test_ds_shell_core import BIND_AND_WAIT, free_port  # noqa: E402

def setUpModule():
    wc.setUpModule()        # W 组借的 Rig 要它的模块级假家(HOME/USERPROFILE 不许指到真家)


def tearDownModule():
    wc.tearDownModule()


# 子进程报告自己的 stdin 是什么:和空设备是不是同一个文件
REPORT_STDIN = (
    "import os,socket,sys,time\n"
    "same = os.path.samestat(os.fstat(0), os.stat(os.devnull))\n"
    "open(sys.argv[2], 'w').write('devnull' if same else 'other')\n"
    "s=socket.socket();s.bind(('127.0.0.1',int(sys.argv[1])));s.listen(4)\n"
    "time.sleep(300)\n"
)


class SupervisorStdinAndEnsure(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.sup = core.Supervisor()
        self.addCleanup(self.sup.shutdown)

    def svc(self, name, code, port, *extra):
        return core.Service(name=name, argv=[sys.executable, "-c", code, str(port), *extra],
                            env=dict(os.environ), ready_port=port,
                            log_path=self.dir / f"{name}.log", ready_timeout=20)

    def test_s1_children_do_not_inherit_the_hosts_stdin(self):
        """🔴 让本进程的 stdin 此刻是一根管道(管家的真实形状:Electron 往里写命令)。
        判据若在 `< /dev/null` 下跑(CI / run-all),子进程继承来的本来就是空设备 —— 不换这一下,这条永远绿。"""
        r, w = os.pipe()
        saved = os.dup(0)
        os.dup2(r, 0)
        try:
            report = self.dir / "stdin.txt"
            self.sup.start([self.svc("网关", REPORT_STDIN, free_port(), str(report))])
        finally:
            os.dup2(saved, 0)
            os.close(saved)
            os.close(r)
            os.close(w)
        self.assertEqual(report.read_text(), "devnull",
                         "子进程拿到的是管家的输入管道 —— Windows 上新网关就卡在这里(probe-3/4)")

    def test_s1b_the_restart_path_too(self):
        """重启(ensure 补起)走的是同一个 _spawn,也要问一次:业主真机卡死的正是这一条路。"""
        port = free_port()
        report = self.dir / "stdin-restart.txt"
        r, w = os.pipe()
        saved = os.dup(0)
        os.dup2(r, 0)
        try:
            self.sup.restart([self.svc("网关", REPORT_STDIN, port, str(report))])
        finally:
            os.dup2(saved, 0)
            os.close(saved)
            os.close(r)
            os.close(w)
        self.assertEqual(report.read_text(), "devnull")

    def pid_of(self, name):
        return next(c.proc.pid for c in self.sup._children if c.service.name == name)

    def test_s2_ensure_leaves_a_live_gateway_alone(self):
        """存 key 时网关在跑 ⇒ 不许碰它:碰了就是今天的病(杀掉正在用的那个、新的起不来)。"""
        port = free_port()
        self.sup.start([self.svc("网关", BIND_AND_WAIT, port)])
        pid = self.pid_of("网关")
        self.sup.ensure([self.svc("网关", BIND_AND_WAIT, port)])
        self.assertEqual(self.pid_of("网关"), pid, "网关活着,ensure 却换了一个新进程")
        self.assertEqual([c.service.name for c in self.sup._children], ["网关"], "名册里多出一条")
        self.assertTrue(core.port_listening(port))

    def test_s2b_ensure_starts_a_gateway_that_was_never_started(self):
        """全新装机没 key ⇒ 开机只起了工作台;第一次存 key ⇒ 这里把网关起起来(Grok 4c 挑战抓到的那条)。"""
        web = free_port()
        self.sup.start([self.svc("工作台", BIND_AND_WAIT, web)])
        web_pid = self.pid_of("工作台")
        gw = free_port()
        self.sup.ensure([self.svc("网关", BIND_AND_WAIT, gw)])
        self.assertTrue(core.port_listening(gw), "没在跑的网关没被起起来")
        self.assertEqual(self.pid_of("工作台"), web_pid, "工作台被连坐换掉了 —— 业主正看着的页面会断")

    def test_s2c_ensure_replaces_a_gateway_that_died(self):
        port = free_port()
        self.sup.start([self.svc("网关", BIND_AND_WAIT, port)])
        old = next(c for c in self.sup._children if c.service.name == "网关")
        old.proc.kill()
        old.proc.wait(10)
        self.sup.ensure([self.svc("网关", BIND_AND_WAIT, port)])
        self.assertNotEqual(self.pid_of("网关"), old.proc.pid, "死掉的网关没被补起")
        self.assertTrue(core.port_listening(port))


class WorkbenchVerdict(wc.Rig):
    """ds_web 存完 key 之后怎么说。`live` = 网关在跑、下一句就用;不许为此去碰外壳。"""

    def bridge_port(self, port):
        os.environ["DS_SHELL_LOCK_PORT"] = str(port)
        self.addCleanup(os.environ.pop, "DS_SHELL_LOCK_PORT", None)

    def save(self, port):
        _, d, _ = self.req(port, "POST", "/api/llm/credential", {"provider": "mimo", "key": wc.FAKE_KEY})
        return d

    def save_in_settings(self, port):
        _, d, _ = self.req(port, "POST", "/api/llm/providers/key", {"provider": "mimo", "key": wc.FAKE_KEY})
        return d

    def test_w1_gateway_listening_means_live_and_no_frame(self):
        gw = socket.socket()
        gw.bind(("127.0.0.1", 0))
        gw.listen(8)
        self.addCleanup(gw.close)
        with wc._fake_shell() as (lp, got):
            self.bridge_port(lp)
            with self.serve(nanobot_port=gw.getsockname()[1]) as port:
                self.assertEqual(self.save(port).get("restart"), "live")
                self.assertEqual(self.save_in_settings(port).get("restart"), "live")
            time.sleep(0.2)
            self.assertEqual(got, [], f"网关在跑,却还是往外壳发了帧:{got!r}")

    def test_w2_gateway_not_listening_asks_the_shell_to_start_it(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            dead = probe.getsockname()[1]
        with wc._fake_shell() as (lp, got):
            self.bridge_port(lp)
            with self.serve(nanobot_port=dead) as port:
                self.assertEqual(self.save(port).get("restart"), "requested")
            self.assertTrue(got, "网关没在跑,却没请外壳把它起起来 —— 全新装机填完第一把 key 会一直连不上")

    def test_w3_no_shell_is_still_manual_even_if_something_listens(self):
        """git-pull / Linux 启动器的网关没有启动器钩子 ⇒ 不许说 live。"""
        gw = socket.socket()
        gw.bind(("127.0.0.1", 0))
        gw.listen(8)
        self.addCleanup(gw.close)
        os.environ.pop("DS_SHELL_LOCK_PORT", None)
        with self.serve(nanobot_port=gw.getsockname()[1]) as port:
            self.assertEqual(self.save(port).get("restart"), "manual")


class KeyFilesAndConfigTogether(unittest.TestCase):
    """网关现读 key 文件之后,「条目在 = 网关拿得到」要在**存的那一刻**成立,不再等起网关。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ds-key-restart-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = os.path.join(self.tmp, "UserData")
        os.makedirs(os.path.join(self.home, ".nanobot"))
        os.makedirs(os.path.join(self.home, ".openDesign"))
        self.cfg_path = os.path.join(self.home, ".nanobot", "config.json")
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            json.dump(ds_credential.load_jsonc(ds_credential.WINDOWS_TEMPLATE), fh, ensure_ascii=False, indent=2)
        with open(os.path.join(self.home, ".openDesign", "key.txt"), "w", encoding="utf-8") as fh:
            fh.write("tp-key-restart-oracle-main-0123456\n")

    def cfg(self):
        with open(self.cfg_path, encoding="utf-8") as fh:
            return json.load(fh)

    def row(self, vendor):
        view = ds_credential.providers_view(self.home, self.cfg_path, multi=True)
        return next(p for p in view["providers"] if p["id"] == vendor)

    def test_k1_saving_a_second_vendor_in_settings_adds_its_entry_right_away(self):
        key = "sk-key-restart-oracle-deepseek-01234"
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="deepseek", key=key,
                           multi=True, switch=False)
        entry = (self.cfg().get("providers") or {}).get("od_deepseek")
        self.assertIsInstance(entry, dict, "存完 DeepSeek,配置里还没有它的条目 —— 运行中的网关用不上它")
        self.assertEqual(entry.get("apiKey"), "${DS_LLM_KEY_DEEPSEEK}")
        self.assertNotIn(key, open(self.cfg_path, encoding="utf-8").read(), "key 原文进了配置")
        r = self.row("deepseek")
        self.assertTrue(r["live"], r)
        self.assertFalse(r["pending"], f"存完还挂着「等重启」:{r}")
        cur = ds_credential.providers_view(self.home, self.cfg_path, multi=True)["current"]
        self.assertEqual(cur.get("provider"), "mimo", f"设置页存 key 把当前模型换掉了(D4:存 key 不换当前模型):{cur}")

    def test_k2_the_onboarding_switch_happens_right_away(self):
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="deepseek",
                           key="sk-key-restart-oracle-deepseek-56789", multi=True, switch=True)
        cur = self.cfg()["agents"]["defaults"].get("modelPreset")
        preset = self.cfg()["model_presets"].get(cur) or {}
        self.assertEqual(preset.get("provider"), "od_deepseek",
                         f"「存了想换过去」没当场兑现(不会再有起网关那一下替它兑现):当前 {cur}")
        self.assertFalse(os.path.exists(os.path.join(self.home, ".openDesign", "keys", "switch-to")),
                         "兑现了却留着标记")

    def test_k3_a_custom_provider_with_a_key_is_usable_right_away(self):
        pid = ds_credential.add_custom_provider(self.home, self.cfg_path, label="中转",
                                                api_base="http://127.0.0.1:9/v1", models=["relay-1"],
                                                key="sk-key-restart-oracle-relay-0123")
        entry = (self.cfg().get("providers") or {}).get(f"od_{pid}")
        self.assertIsInstance(entry, dict, "带 key 添加的自定义供应商,配置里没有条目")
        self.assertTrue(self.row(pid)["live"])


class ShellWiresEnsureAndLauncher(unittest.TestCase):
    """真跑 start_backend,只把开进程换成替身(test_ds_shell_startup 同款)。
    借它的夹具,**不继承那个类**:继承会把那边的 test_s* 在这里再跑一遍。"""

    setUp = st.StartBackend.setUp
    tearDown = st.StartBackend.tearDown
    write_key = st.StartBackend.write_key
    start = st.StartBackend.start

    def test_r1_the_lock_callback_ensures_instead_of_restarting(self):
        self.write_key("sk-yezhu-de-key")
        ensured: list = []
        with mock.patch.object(st.FakeSupervisor, "ensure", lambda s, svcs: ensured.extend(svcs), create=True):
            sup, _web, on_key_saved = self.start()
            on_key_saved()
        self.assertEqual([s.name for s in ensured], ["网关"], "锁帧回调没走 ensure")
        self.assertEqual(sup.restarted, [], "网关在跑时存 key 还是走了重启 —— 这正是业主 09-25 的病")

    def test_r2_the_gateway_is_started_through_the_live_key_launcher(self):
        self.write_key("sk-yezhu-de-key")
        sup, _web, _cb = self.start()
        gw = next(s for s in sup.started if s.name == "网关")
        argv = [str(a) for a in gw.argv]
        self.assertEqual(argv, core.gateway_argv(str(shell.python_exe()), str(self.install / "ds")))
        self.assertTrue(argv[-1].endswith(os.path.join("bin", "ds_gateway.py")), argv)
        self.assertNotIn("-m", argv, "网关还是 `-m nanobot` 直接起 —— 没有钩子,存 key 不生效")


if __name__ == "__main__":
    unittest.main(verbosity=2)
