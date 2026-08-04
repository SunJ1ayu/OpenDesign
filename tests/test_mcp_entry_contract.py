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
        ms._ensure_env()            # 单跑本文件时 bin/ 还不在 sys.path(2026-08-03 补)
        import ds_mcp
        for key, name in sorted(ms.SERVER_KEYS.items()):
            with self.subTest(key=key):
                self.assertEqual(ds_mcp.build(key).name, name)

    def test_03_坏key不许静默给个空server(self):
        """诚实闸:拼错 key 必须炸,不能给个没有工具的 server ——
        那会表现成"助手突然什么都不会了"却没人知道为什么。"""
        ms._ensure_env()
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

    def test_07_模板里每条args都带对了key(self):
        """panel(subdeepseek)补的洞:test_05 只查"文本里有 ds_mcp.py、没有旧名",
        模板写成 `args:[".../ds_mcp.py"]` **漏掉 key** 一样能绿,
        而真起进程时 argparse 立刻报错退出 —— 又是一次"我这边全绿、用户那边全废"。
        ⇒ 真解析 JSONC,逐条比对 args。"""
        sys.path.insert(0, ms.BIN)
        import ds_merge_config
        for rel in TEMPLATES:
            cfg = json.loads(ds_merge_config.strip_jsonc(
                open(os.path.join(ms.REPO, rel), encoding="utf-8").read()))
            servers = cfg["tools"]["mcpServers"]
            for key, name in sorted(ms.SERVER_KEYS.items()):
                with self.subTest(template=rel, server=name):
                    args = servers[name]["args"]
                    self.assertEqual(len(args), 2,
                                     f"{rel} 的 {name}.args 应为 [入口, key],实为 {args}")
                    self.assertTrue(args[0].endswith("bin/ds_mcp.py"),
                                    f"{rel} 的 {name} 入口不是 bin/ds_mcp.py:{args[0]}")
                    self.assertEqual(args[1], key,
                                     f"{rel} 的 {name} 少了/写错了 key")


class OldEntriesFailLoudly(unittest.TestCase):
    """存量机器上那份没更新的 config 仍指着旧入口 —— 它必须**响亮地**失败。

    2026-08-03 panel 三腿(subdeepseek/submimo/subkimi)与主 agent 独立同时命中:
    三个业务模块的 `__main__` 整块删掉之后,`python bin/ds_tools.py` 会
    **退出码 0、零输出**。机主不是程序员,他看到的只是"助手突然什么都不会做了",
    而 nanobot 那边只看到 stdio 对端干净退出,**没有任何线索指向"重跑装机脚本"**。

    这条闸钉的是:旧入口被当 MCP 入口拉起时,**必须非零退出并说人话**。
    (shim 不许 import mcp,也不许 import server 层 —— 否则承重墙/无环闸会红。)
    """

    def test_01_三个旧入口都必须非零退出并指向新入口(self):
        for mod in OLD_ENTRIES:
            with self.subTest(entry=mod):
                r = subprocess.run([sys.executable, os.path.join(ms.REPO, mod)],
                                   capture_output=True, text=True, timeout=60)
                self.assertNotEqual(r.returncode, 0,
                                    f"{mod} 被当入口跑时静默退出 0 —— "
                                    f"存量 config 会表现成'助手什么都不会了'却查不出原因")
                out = r.stdout + r.stderr
                self.assertIn("ds_mcp.py", out, f"{mod} 的报错没告诉人新入口在哪")
                self.assertIn("install", out.lower(),
                              f"{mod} 的报错没告诉人怎么修(重跑装机脚本)")


class NoStaleEntryReferences(unittest.TestCase):
    """**同一件事写在两个地方、只更新其中一个** —— 本仓反复记账的那条债。

    2026-08-03 panel(subkimi/submimo/subdeepseek)与主 agent 共命中三处:
    `docs/spec.md` 的"可抄 config 骨架"、`docs/install-windows.md` 的"更新的生效边界"、
    三个业务模块的模块头。判据原来只钉了 `config/*.jsonc` 两份模板,**没钉文档**。
    """

    def test_01_docs里不许再出现指向旧入口的启动配置(self):
        docs = os.path.join(ms.REPO, "docs")
        bad = []
        for fn in sorted(os.listdir(docs)):
            if not fn.endswith(".md"):
                continue
            for i, line in enumerate(open(os.path.join(docs, fn), encoding="utf-8"), 1):
                if "args" not in line and "command" not in line:
                    continue
                for old in OLD_ENTRIES:
                    if os.path.basename(old) in line:
                        bad.append(f"{fn}:{i} {line.strip()[:90]}")
        self.assertEqual(bad, [], "文档里的启动配置仍指向旧入口(照抄即装坏):\n  "
                                  + "\n  ".join(bad))

    def test_02_装机文档的更新边界必须提到新入口(self):
        """`docs/install-windows.md` 是**存量机器唯一会读的耐用文档**。
        本单之后"git pull + 重启"不再等于生效(config 里的 args 变了),
        它必须自己说得出 `ds_mcp.py` 与"要重跑装机脚本"。"""
        text = open(os.path.join(ms.REPO, "docs/install-windows.md"),
                    encoding="utf-8").read()
        self.assertIn("ds_mcp.py", text,
                      "装机/更新文档没提新入口 —— 存量机器按它操作会静默失去全部工具")

    def test_03_业务模块头不许再声称自己带着MCP包装(self):
        """注释撒谎是这个仓库已经记在账上的债(见 test_no_import_cycles 的同类闸)。"""
        bad = []
        for mod in OLD_ENTRIES:
            head = open(os.path.join(ms.REPO, mod), encoding="utf-8").read()[:1200]
            for claim in ("stdio MCP server 包装", "stdio FastMCP 包装"):
                if claim in head:
                    bad.append(f"{mod}: 模块头仍写着「{claim}」,但那层已搬到 *_server.py")
        self.assertEqual(bad, [], "\n  " + "\n  ".join(bad))


class EvalHarnessesFollowedTheMove(unittest.TestCase):
    """两份 eval 从 AST 抽工具表,自称"与真部署同源" —— 搬家后它们抽到的是**空表**。

    2026-08-03 submimo 与 subkimi 独立命中,**主 agent 漏了**。
    它们不进 pytest(要 key + 网络),所以搬家不会让任何测试变红:
    典型的"静默退化"。这条闸只查**抽取结果**,不跑模型,零依赖。
    """

    def _load(self, name):
        sys.path.insert(0, os.path.join(ms.REPO, "tests", "evals"))
        return __import__(name)

    # ⚠️ 2026-08-04 改判定方式(track opendesign-date-arithmetic):
    # 原来这两条把"harness 有没有扫错文件"焊成**魔数**(29 / 17)。
    # 加一个合法的新工具(resolve_date)就假红,而且失败信息还会撒谎
    # ——它会说"它还在扫旧文件",其实文件扫对了、只是多了一个工具。
    # **一条会撒谎的失败信息比没有这条闸更糟**:下一个人照着它去查文件路径,查不到东西。
    # 改成:用**另一种方法**(源码正则)数同一批文件,和 harness 的 AST 抽取对账。
    # 这比魔数强 —— 魔数只在"数目恰好变了"时响,对账在**任何**不一致时都响,
    # 而且加工具时不需要有人记得回来改数字(没人会记得)。
    def _count_tool_defs(self, *files):
        """用正则数 `def xxx_tool(` —— 故意和 harness 的 AST 路径不同源。"""
        n = 0
        for f in files:
            src = open(os.path.join(ms.REPO, "bin", f), encoding="utf-8").read()
            n += len(re.findall(r"^\s*def\s+\w+_tool\s*\(", src, re.M))
        return n

    def test_01_resolver_eval抽到的工具表与源码对得上(self):
        mod = self._load("resolver_eval")
        tools = mod.extract_tools()
        want = self._count_tool_defs("ds_tools_server.py", "ds_organize_server.py",
                                     "ds_refs_server.py")
        self.assertGreater(want, 20, "源码里的 *_tool 定义少得离谱,先查源码不是查这条闸")
        self.assertEqual(len(tools), want,
                         f"resolver_eval 抽到 {len(tools)} 个,源码里有 {want} 个 "
                         "—— 它扫的文件跟真部署对不上了")
        self.assertIn("adopt_workspace", [t[0] for t in tools])

    def test_02_due_writer_eval抽到的schema与源码对得上(self):
        mod = self._load("due_writer_eval")
        schemas = mod.tool_schemas()
        want = self._count_tool_defs("ds_tools_server.py")
        self.assertGreater(want, 10, "源码里的 *_tool 定义少得离谱,先查源码不是查这条闸")
        self.assertEqual(len(schemas), want,
                         f"due_writer_eval 抽到 {len(schemas)} 个,源码里有 {want} 个 "
                         "—— 它扫的文件跟真部署对不上了")
        names = [s["function"]["name"] for s in schemas]
        self.assertIn("set_due_date", names)
        self.assertIn("resolve_date", names)   # 助手拿不到它 = 又回去心算


class BusinessModulesStayMcpFree(unittest.TestCase):
    """O3:业务模块在**没装 mcp** 的环境里仍然要能 import。

    panel(subdeepseek)点出的承重墙,我没想到:
    现有代码把 `mcp` 做成函数内延迟导入,正是为了"没装 mcp 时纯 Python 核心与
    tests 照常可用"。本单如果把 import 提到模块层,而**本机恰好装了 mcp**,
    则**测试永远绿、隐患直到上线才炸**。所以要静态查,不能靠"能不能 import"。
    """

    # 2026-08-03 panel(subkimi)补:原名单漏了 ds_common/ds_lock/ds_todo/ds_model ——
    # 它们是所有业务模块的地基,谁在那儿把 mcp 提到模块层,承重墙一样塌。
    BUSINESS = ("ds_tools", "ds_organize", "ds_refs", "ds_adopt",
                "ds_intake", "ds_lint", "ds_workspace", "ds_taxonomy",
                "ds_common", "ds_lock", "ds_todo", "ds_model")

    # 登记层自己也不许在模块层 import mcp:`ds_tools_server` **没有任何测试无条件
    # import 它**(只经 ds_mcp.build,而那条在没装 mcp 时整块 skip),
    # ⇒ 真出了这个错,装了 mcp 的机器上永远绿、没装的机器上永远 skip。(subkimi 命中)
    SERVER_LAYER = ("ds_mcp", "ds_tools_server", "ds_organize_server", "ds_refs_server")

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

    def test_03_登记层也不许在模块层import_mcp(self):
        """`if TYPE_CHECKING:` 里的那句不算(运行期不执行,`ds_mcp.py` 就是这么写的)——
        只查真正会在 import 时执行的模块层语句。"""
        import ast
        bad = []
        for mod in self.SERVER_LAYER:
            path = os.path.join(ms.BIN, mod + ".py")
            tree = ast.parse(open(path, encoding="utf-8").read())
            for node in tree.body:                      # 只看模块层(TYPE_CHECKING 块是嵌套的)
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                for n in names:
                    if n == "mcp" or n.startswith("mcp."):
                        bad.append(f"{mod}.py:{node.lineno} 模块层 import {n}")
        self.assertEqual(bad, [], "登记层把 mcp 提到了模块层 —— 没装 mcp 的机器上"
                                  "`import ds_*_server` 会炸,而本机装了就永远绿:\n  "
                                  + "\n  ".join(bad))

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
