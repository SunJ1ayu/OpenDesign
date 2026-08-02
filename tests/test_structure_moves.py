"""O1 搬运保真闸:搬过去的东西必须**逐字节不变**。

track opendesign-structure-debt。**主 agent 亲写,执行腿逐字节 off-limits。**

存在的理由:本单的 diff 是几百行纯位移 —— 这正是闸③「亲读 diff」最挡不住的形态。
几百行位移里夹一行真改动,人眼极易漏。**这条判据是唯一挡得住"搬运单夹私货"的东西。**

基线 `structure_moves_baseline.json` **在搬运之前生成并单独 commit**(见 track 规矩)。
搬完之后再生成的基线只是实现的复印件,证明不了任何事。
"""
import json
import os
import unittest

import structure_moves as sm


class MoveFidelity(unittest.TestCase):
    """搬运保真:新位置的定义与搬运前逐字节相同。"""

    @classmethod
    def setUpClass(cls):
        with open(sm.BASELINE, encoding="utf-8") as fh:
            cls.baseline = json.load(fh)

    def test_01_baseline_covers_the_move_list(self):
        """基线与搬运清单必须一一对应 —— 防"悄悄从清单里删掉一项让自己变绿"。"""
        expected = {f"{dst}.{name}" for _src, dst, name in sm.MOVES}
        self.assertEqual(set(self.baseline), expected,
                         "基线与 MOVES 清单对不上:改清单必须同步重生成基线")

    def test_02_每项都搬到新模块且逐字节不变(self):
        problems = []
        for key, meta in sorted(self.baseline.items()):
            dst_mod, name = key.rsplit(".", 1)
            text = sm.top_level_source(dst_mod, name)
            if text is None:
                problems.append(f"{key}:新模块里找不到(还没搬 / 名字被改了)")
                continue
            got = sm.digest(text)
            if got != meta["sha256"]:
                problems.append(
                    f"{key}:搬过来了但**内容被改动**"
                    f"(基线 {meta['sha256'][:12]} → 实际 {got[:12]});"
                    f"纯搬运单不许改内容,要改请单独一单")
        self.assertEqual(problems, [], "\n  " + "\n  ".join(problems))

    def test_03_原模块里不许留副本(self):
        """硬切:留一份转发/副本 = 错位没消灭,只是变隐蔽,下次引哪个全凭手感。"""
        leftovers = []
        for src_mod, dst_mod, name in sm.MOVES:
            if sm.top_level_source(src_mod, name) is not None:
                leftovers.append(f"{src_mod}.{name} 仍在原模块(应已搬去 {dst_mod})")
        self.assertEqual(leftovers, [], "\n  " + "\n  ".join(leftovers))

    def test_04_新模块确实存在(self):
        for dst in sorted({d for _s, d, _n in sm.MOVES}):
            self.assertTrue(os.path.exists(sm.module_path(dst)),
                            f"bin/{dst}.py 不存在")


if __name__ == "__main__":
    unittest.main()
