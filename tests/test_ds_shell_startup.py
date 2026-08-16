#!/usr/bin/env python3
"""外壳启动那条路 —— **真的跑一遍**,不是看 AST。

2026-08-16 业主真机:填完 key 之后每次打开都 `NameError: name 'env' is not defined`
(bin/ds_shell.py:202)。那一行只在**有 key**的机器上执行,而判据机上没有 key.txt。

为什么以前没有这种判据:`bin/ds_shell.py` 的文件头写着「这一层没有任何自动考卷验得了」,
理由是 pywebview / pystray / WebView2 要 Windows 桌面会话。**那句话说得太满** ——
真正碰 Windows 的只有 `main()` 里的 `import webview` 和托盘;`start_backend()` 从头到尾
只是读配置、拼 env、把两条腿交给 `Supervisor`。把 Supervisor 换成替身,它在 Linux 上
跑得好好的。这个文件就是那句话的收口。

分工(别把这里写成 test_ds_shell_core 的抄件):
  · `test_ds_shell_core.py` 验 core 的每个零件对不对;
  · `test_ds_shell_wiring.py` 静态查"接线写没写"(AST,证明不了跑得起来);
  · **这里**验那些零件被 `start_backend()` 串起来之后,**两条腿最终拿到了什么**。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bin"))

import ds_shell as shell           # noqa: E402
import ds_shell_core as core       # noqa: E402

CFG = {
    "providers": {"custom": {"apiKey": "${DS_LLM_KEY}", "apiBase": "https://example/v1"}},
    "model_presets": {"mimo-v2.5": {"label": "mimo-v2.5", "provider": "custom",
                                    "model": "mimo-v2.5"}},
    "agents": {"defaults": {"modelPreset": "mimo-v2.5"}},
    "channels": {"websocket": {"enabled": True, "token": "yezhu-de-kouling",
                               "host": "127.0.0.1", "port": 8765}},
    "gateway": {"port": 18790},
    "tools": {"mcpServers": {
        "design-studio": {"command": "py", "args": ["a.py"]},
        "design-studio-refs": {"command": "py", "args": ["b.py"]},
        "design-studio-organize": {"command": "py", "args": ["c.py"]},
    }},
}


class FakeSupervisor:
    """替身:只记下"谁被要求起来了、带着什么 env",不真的开进程。

    起真进程会把这套判据变成"要 Windows + 要 nanobot"的那一类 —— 那正是这条路
    两个月没人验的原因。这里换掉的是**开进程**,不是被测逻辑。
    """

    made: list["FakeSupervisor"] = []

    def __init__(self):
        self.started: list = []
        self.restarted: list = []
        FakeSupervisor.made.append(self)

    def start(self, services):
        self.started.extend(services)

    def restart(self, services):
        self.restarted.extend(services)

    def shutdown(self):
        pass

    def poll_dead(self):
        return []


class StartBackend(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.home = base / "UserData"
        (self.home / ".nanobot").mkdir(parents=True)
        (self.home / ".nanobot" / "config.json").write_text(
            json.dumps(CFG, ensure_ascii=False), encoding="utf-8")
        self.install = base / "install"
        (self.install / "ds" / "bin").mkdir(parents=True)

        FakeSupervisor.made.clear()
        self.env_backup = dict(os.environ)
        # 日志/数据根都关进 tmp:判据不许往业主目录(或我的 /root)写东西,
        # 而 prepare_data_root 会**改本进程的 os.environ** —— tearDown 里整个还原。
        os.environ["LOCALAPPDATA"] = str(base / "AppData")
        os.environ.pop("DS_LLM_KEY", None)

        patches = [
            mock.patch.object(shell.core, "Supervisor", FakeSupervisor),
            mock.patch.object(shell, "install_root", lambda: self.install),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.env_backup)
        self.tmp.cleanup()

    def write_key(self, key: str):
        d = self.home / ".openDesign"
        d.mkdir(parents=True, exist_ok=True)
        (d / "key.txt").write_text(key + "\n", encoding="utf-8")

    def start(self):
        return shell.start_backend(self.home, lock_port=18788)

    # ---------------------------------------------------------------- 有 key
    def test_s1_with_a_key_both_legs_come_up_and_only_the_gateway_gets_it(self):
        """**08-16 那次开不了机就死在这一条上**:有 key ⇒ 走缺变量检查那个分支。

        顺带把 service_envs 的那条边界钉在真实调用上:key 只进网关。
        ds-web 也拿到的话,`ds_credential.status()` 会把外壳自注入误判成"外部遮蔽",
        设置里改 key 那张卡片永久只读。
        """
        self.write_key("sk-yezhu-de-key")
        sup, web_port, restart = self.start()

        legs = {s.name: s for s in sup.started}
        self.assertEqual({"网关", "工作台"}, set(legs), "有 key 时两条腿都该起来")
        self.assertEqual("sk-yezhu-de-key", legs["网关"].env.get("DS_LLM_KEY"))
        self.assertNotIn("DS_LLM_KEY", legs["工作台"].env,
                         "key 不许进 ds-web —— 进了,设置里那张卡片会变成永久只读")
        self.assertEqual(str(18788), str(legs["工作台"].env.get("DS_SHELL_LOCK_PORT")),
                         "ds-web 拿不到锁端口 ⇒ 填完 key 自动重启整条空转")
        self.assertIsInstance(web_port, int)
        self.assertTrue(callable(restart))

    # ---------------------------------------------------------------- 没 key
    def test_s2_without_a_key_the_workbench_still_opens(self):
        """缺 key 不是错误,是"该去填了" —— 起工作台、不起网关、不弹窗退出。

        (没有这一条,业主永远走不到引导页:网关会死在没设的 ${DS_LLM_KEY} 上。)
        """
        sup, _web, _restart = self.start()
        self.assertEqual(["工作台"], [s.name for s in sup.started])

    # ------------------------------------------------- 装机没装全 + 有 key
    def test_s3_a_key_plus_some_other_unset_variable_stops_with_a_sentence(self):
        """配置里引用了别的没设的 ${VAR} ⇒ 现在就说人话,别让网关死在英文报错上。"""
        cfg_path = self.home / ".nanobot" / "config.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        # 变量名用 ASCII:nanobot 的解析器只认 `[A-Za-z_][A-Za-z0-9_]*`,
        # 写个中文名的 ${} 它根本不当引用 —— 那样这条判据会永远绿(第一版就这么写的)。
        cfg["tools"]["mcpServers"]["design-studio"]["args"] = ["${INSTALLER_FORGOT_THIS}"]
        cfg_path.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        self.write_key("sk-yezhu-de-key")

        said: list[str] = []
        with mock.patch.object(shell, "alert", said.append):
            with self.assertRaises(SystemExit):
                self.start()
        self.assertTrue(said, "什么都没说就退出了 —— 业主看到的是图标闪一下")
        self.assertIn("INSTALLER_FORGOT_THIS", said[0])

    # ---------------------------------------------- 填完 key,网关自己重来
    def test_s4_restart_gateway_swaps_only_the_gateway_and_reads_the_new_key(self):
        """业主在界面里填完 key ⇒ ds-web 通过锁通道叫回来。

        必须**现读**:重启时用启动那一刻缓存的 env,业主填的 key 永远不生效。
        """
        sup, _web, restart = self.start()
        self.assertEqual(["工作台"], [s.name for s in sup.started])

        self.write_key("sk-tian-jin-qu-de")
        restart()

        self.assertEqual(["网关"], [s.name for s in sup.restarted],
                         "只换网关那条腿 —— ds-web 换掉的话,业主正看的页面会断")
        self.assertEqual("sk-tian-jin-qu-de", sup.restarted[0].env.get("DS_LLM_KEY"))

    def test_s5_restart_with_an_empty_key_file_does_not_touch_anything(self):
        """key 还是空的就别动网关:重启一次要几十秒,换来的还是连不上。"""
        sup, _web, restart = self.start()
        restart()
        self.assertEqual([], sup.restarted)


class ShellIsImportableHere(unittest.TestCase):
    """这个文件成立的前提,单独钉一条。

    哪天有人往 ds_shell.py 顶上加一句 `import webview`,上面五条会**整块报错消失**
    在收集阶段(而不是红)—— 那种失效最难看见。这一条让它变成一句听得懂的红。
    """

    def test_s6_ds_shell_imports_without_a_windows_desktop(self):
        self.assertTrue(hasattr(shell, "start_backend"))
        self.assertIs(shell.core, core)


if __name__ == "__main__":
    unittest.main()
