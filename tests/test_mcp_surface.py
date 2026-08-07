"""O1 工具表快照闸:助手看到的 32 个工具**一个字不许悄悄变**。

track opendesign-mcp-registry。**主 agent 亲写,执行腿逐字节 off-limits。**

这一单动的是助手能力的全部来源。用户不是程序员,搞砸的表现是
**他下次用的时候助手什么都不会做了**,而且是他发现、不是我发现。

基线 `mcp_surface_baseline.json` **在改造之前生成并单独 commit**
(用「FastMCP.run 换成空操作 + 截获实例」的办法取,零产品代码改动)。

改造前跑本文件必然红(`ds_mcp` 还不存在)—— **本文件就是目标契约的规格**。

## 基线是"报警器",刷新它必须是**明写在某个 track 里的动作**

2026-08-05 实测:0.73/0.74 两单**故意**改了助手契约(新增 `resolve_date`、
三条 description 改写),基线没跟着刷 ⇒ 本文件从那时起一直是红的,
而收货记录里写的是"python 866/0"。为什么没人看见:那次用的是**系统 `python3`**,
它没装 `mcp` ⇒ 这 4 条整块 SKIP,汇总照印 `OK`。
**`tests/mcp-gate.sh` 08-03 就是为治这个病建的,却没有任何总跑会调它。**

所以刷新基线的规矩:
1. 只在**故意改了助手契约**的那一单里刷,和那单的 verify 一起留痕;
2. 刷之前逐条读 `git diff tests/mcp_surface_baseline.json` —— 差异必须**恰好等于**
   那单打算改的东西,多一条都是事故;
3. 刷完把下面两处数字一起改,并在这里记一句谁把它从几改到了几。

数量沿革:29(改造前基线)→ **30**(2026-08-05 补记 `resolve_date`,
出自 track opendesign-date-arithmetic / 0.74.0)
→ **32**(2026-08-07 新增 `list_project_documents` / `read_project_document`,
出自 track opendesign-anydoc —— 助手第一次能读到 `01-资料` 里的文档)。
刷新那次逐条读过 diff:**纯新增 49 行、只有这两个工具**,没有一条现有 description 被动。
同一单第二次刷新(二轮四审 M4):`read_project` 的 description 加了一句
"档案里没有那条具体事实时接着去资料夹" —— 那句引导原来只写在 AGENTS.md 散文里,
而模型选工具时看的是本表。diff **恰好 1 行改动**,工具数不变(仍是 32)。
同一单第三次刷新(闸③ 亲读 diff 时我自己读出来的):上面那次搬运,把出处
"(二轮四审 M4:…)" 也留在了 docstring 里 —— **docstring 就是模型每轮读到的话**,
评审轮次对助手毫无意义,等于每轮多塞一句噪音。删掉那一句。
diff **恰好 1 行改动**,工具数不变(仍是 32)。
"""
import unittest

import mcp_surface as ms


def _mcp_missing() -> bool:
    try:
        import mcp  # noqa: F401
        return False
    except ImportError:
        return True


@unittest.skipIf(_mcp_missing(), "未装 mcp 包(业务核心与其余 tests 不受影响)")
class McpSurfaceUnchanged(unittest.TestCase):
    """经统一入口 `ds_mcp.build(key)` 取到的工具表 == 改造前的基线。"""

    def test_01_三个server都还在且名字没变(self):
        actual = ms.snapshot_via_new_entry()
        self.assertEqual(sorted(actual), sorted(ms.load_baseline()),
                         "server 名变了 —— 那是 config 里的键,变了等于要用户再迁一次")

    def test_02_工具表逐字节不变(self):
        """name / inputSchema / **description(docstring)** 全比。

        description 就是喂给模型的规格 —— 改它 = 改产品行为,不是重构。
        """
        actual, base = ms.snapshot_via_new_entry(), ms.load_baseline()
        for name in sorted(base):
            with self.subTest(server=name):
                self.assertEqual(
                    ms.dumps(actual.get(name)), ms.dumps(base[name]),
                    f"`{name}` 的工具表变了 —— 本单是纯结构改动,"
                    f"助手看到的东西不许动一个字")

    def test_03_工具总数仍是32(self):
        """冗余但便宜的一条:总数对不上时报出来的信息比逐 server diff 好读。

        29 → 30 是 2026-08-05 补记的(0.74.0 新增 resolve_date);
        30 → 32 是 2026-08-07(anydoc 两个读文档工具)。见模块头「数量沿革」。
        """
        actual = ms.snapshot_via_new_entry()
        self.assertEqual(sum(len(v) for v in actual.values()), 32)

    def test_04_基线自身没被改小(self):
        """护栏:防"把基线删几行让自己变绿"。32 是 2026-08-07 实测的事实
        (改造前是 29 → 30,沿革见模块头)。"""
        base = ms.load_baseline()
        self.assertEqual(sum(len(v) for v in base.values()), 32,
                         "基线被改小了 —— 基线只在故意改助手契约的那一单里刷新,"
                         "而且要跟着改这里的数字(模块头「数量沿革」),不是可调参数")


if __name__ == "__main__":
    unittest.main()
