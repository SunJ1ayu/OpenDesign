"""O2 入口契约闸:config 指向的入口必须**真的能跑**,且仓库模板与它一致。

track opendesign-mcp-registry。**主 agent 亲写,执行腿逐字节 off-limits。**

为什么单列一条:panel(subdeepseek)点出我把死线窄化了 ——
我写的是"路径不能变",但真正的死线是「**入口必须始终可直接运行**」。
路径没变而 launcher 被顺手改坏,后果一样是**用户机上助手全废**,
而且 `git pull` 救不回(他那份 config 在 `%USERPROFILE%\\.nanobot\\` 下)。

本单选的方向 R = 改一次 config、以后不用再改。所以这条闸要同时钉两件事:
① 新入口真的跑得起来;② **仓库里两份 config 模板已经指向新入口**
—— 模板不改,新用户装机拿到的还是旧路径,那才是真正的"给别人用出问题"。
"""
import json
import os
import re
import subprocess
import sys
import unittest

import mcp_surface as ms

TEMPLATES = ("config/nanobot.config.jsonc", "config/nanobot.config.windows.jsonc")
OLD_ENTRIES = ("bin/ds_tools.py", "bin/ds_organize.py", "bin/ds_refs.py")


def _mcp_missing() -> bool:
    try:
        import mcp  # noqa: F401
        return False
    except ImportError:
        return True


class EntryContract(unittest.TestCase):

    def test_01_统一入口文件存在(self):
        self.assertTrue(os.path.exists(os.path.join(ms.BIN, "ds_mcp.py")),
                        "bin/ds_mcp.py 不存在 —— 方向 R 的统一入口")

    @unittest.skipIf(_mcp_missing(), "未装 mcp 包")
    def test_02_三个key都建得出server(self):
        import ds_mcp
        for key, name in sorted(ms.SERVER_KEYS.items()):
            with self.subTest(key=key):
                self.assertEqual(ds_mcp.build(key).name, name)

    def test_03_坏key不许静默给个空server(self):
        """诚实闸:拼错 key 必须炸,不能给个没有工具的 server ——
        那会表现成"助手突然什么都不会了"却没人知道为什么。"""
        import ds_mcp
        with self.assertRaises(Exception):
            ds_mcp.build("nope")

    def test_04_入口真能当脚本跑起来(self):
        """最贴近真实风险的一条:config 就是这么调它的。

        起子进程跑 `python bin/ds_mcp.py <key> --selftest`,要求退出 0。
        (`--selftest` = 建好 server、打印工具数、**不进 stdio 循环**;
        没有它就只能真起 server 再杀,那在判据里既慢又脆。)
        """
        if _mcp_missing():
            self.skipTest("未装 mcp 包")
        env = {**os.environ, "DS_ROOT": ms.REPO, "DS_ORGANIZE_ROOTS": ms.REPO}
        for key in sorted(ms.SERVER_KEYS):
            with self.subTest(key=key):
                r = subprocess.run(
                    [sys.executable, os.path.join(ms.BIN, "ds_mcp.py"), key, "--selftest"],
                    capture_output=True, text=True, env=env, timeout=60)
                self.assertEqual(r.returncode, 0,
                                 f"`ds_mcp.py {key} --selftest` 退出码 {r.returncode}\n"
                                 f"stdout={r.stdout[-400:]}\nstderr={r.stderr[-400:]}")

    def test_05_仓库两份config模板都已指向新入口(self):
        """**这条才是"给别人用"那个问题的判据。**

        模板没改 → 新用户装机(install.ps1 Step 7 合并模板)拿到的还是旧路径
        → 他一装就坏。而这恰恰是最容易漏的一步:我这边测试全绿。
        """
        for rel in TEMPLATES:
            path = os.path.join(ms.REPO, rel)
            with self.subTest(template=rel):
                self.assertTrue(os.path.exists(path), f"{rel} 不见了")
                text = open(path, encoding="utf-8").read()
                for old in OLD_ENTRIES:
                    self.assertNotIn(
                        old, text,
                        f"{rel} 仍指向旧入口 {old} —— 新用户装机会拿到坏配置")
                self.assertIn("bin/ds_mcp.py", text,
                              f"{rel} 没有指向新入口 bin/ds_mcp.py")

    def test_06_三个server名在模板里一字未变(self):
        """server 名是 config 里的键。它变了 = 要求用户再迁移一次,本单明确不干。"""
        for rel in TEMPLATES:
            text = open(os.path.join(ms.REPO, rel), encoding="utf-8").read()
            for name in sorted(set(ms.SERVER_KEYS.values())):
                with self.subTest(template=rel, server=name):
                    self.assertIn(f'"{name}"', text)


class BusinessModulesStayMcpFree(unittest.TestCase):
    """O3:业务模块在**没装 mcp** 的环境里仍然要能 import。

    panel(subdeepseek)点出的承重墙,我没想到:
    现有代码把 `mcp` 做成函数内延迟导入,正是为了"没装 mcp 时纯 Python 核心与
    tests 照常可用"。本单如果把 import 提到模块层,而**本机恰好装了 mcp**,
    则**测试永远绿、隐患直到上线才炸**。所以要静态查,不能靠"能不能 import"。
    """

    BUSINESS = ("ds_tools", "ds_organize", "ds_refs", "ds_adopt",
                "ds_intake", "ds_lint", "ds_workspace", "ds_taxonomy")

    def test_01_业务模块里不许出现mcp的模块层import(self):
        import ast
        bad = []
        for mod in self.BUSINESS:
            path = os.path.join(ms.BIN, mod + ".py")
            if not os.path.exists(path):
                continue
            tree = ast.parse(open(path, encoding="utf-8").read())
            for node in tree.body:                      # 只看模块层
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                for n in names:
                    if n == "mcp" or n.startswith("mcp."):
                        bad.append(f"{mod}.py:{node.lineno} 模块层 import {n}")
        self.assertEqual(bad, [], "\n  " + "\n  ".join(bad))

    def test_02_业务模块不许依赖server层(self):
        """方向 R 的核心:依赖必须**单向**(入口/server → 业务),不许反过来。"""
        import ast
        bad = []
        for mod in self.BUSINESS:
            path = os.path.join(ms.BIN, mod + ".py")
            if not os.path.exists(path):
                continue
            tree = ast.parse(open(path, encoding="utf-8").read())
            for node in ast.walk(tree):                 # 全树:延迟 import 也算
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                for n in names:
                    if n == "ds_mcp" or n.endswith("_server"):
                        bad.append(f"{mod}.py:{node.lineno} → {n}")
        self.assertEqual(bad, [], "业务模块反向依赖了 server 层:\n  "
                                  + "\n  ".join(bad))


if __name__ == "__main__":
    unittest.main()
