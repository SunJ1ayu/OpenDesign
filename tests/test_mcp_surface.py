"""O1 工具表快照闸:助手看到的 29 个工具**一个字不许变**。

track opendesign-mcp-registry。**主 agent 亲写,执行腿逐字节 off-limits。**

这一单动的是助手能力的全部来源。用户不是程序员,搞砸的表现是
**他下次用的时候助手什么都不会做了**,而且是他发现、不是我发现。

基线 `mcp_surface_baseline.json` **在改造之前生成并单独 commit**
(用「FastMCP.run 换成空操作 + 截获实例」的办法取,零产品代码改动)。

改造前跑本文件必然红(`ds_mcp` 还不存在)—— **本文件就是目标契约的规格**。
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

    def test_03_工具总数仍是29(self):
        """冗余但便宜的一条:总数对不上时报出来的信息比逐 server diff 好读。"""
        actual = ms.snapshot_via_new_entry()
        self.assertEqual(sum(len(v) for v in actual.values()), 29)

    def test_04_基线自身没被改小(self):
        """护栏:防"把基线删几行让自己变绿"。29 是改造前实测的事实。"""
        base = ms.load_baseline()
        self.assertEqual(sum(len(v) for v in base.values()), 29,
                         "基线被改动过 —— 基线是改造前的事实,不是可调参数")


if __name__ == "__main__":
    unittest.main()
