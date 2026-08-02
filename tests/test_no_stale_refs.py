"""O3 硬切无残留闸:搬走的东西不许在旧名字下还能引到。

track opendesign-structure-debt。**主 agent 亲写,执行腿逐字节 off-limits。**

design 决定**硬切、不留转发**。理由:留转发就等于两个名字指同一件事,
下次谁引哪个全凭手感 —— 错位没消灭,只是变隐蔽。
(同一类病已在记忆里记过账:事实复制到第二个地方,只更新其中一个。)

硬切的失败模式是好的:漏改任一调用点 → `AttributeError` 当场炸,不是静默错。
但"当场炸"要有人跑到那条路径才炸,所以仍然需要这条静态闸兜住。
"""
import os
import re
import unittest

import structure_moves as sm

SCAN_DIRS = ("bin", "tests", "web/src", "skills", "docs")
SCAN_EXT = (".py", ".ts", ".tsx", ".mjs", ".js", ".md", ".json")
# 判据自身与 track 工件必然要提到旧名字(讲的就是这次搬运),豁免。
EXEMPT = {
    "tests/test_no_stale_refs.py",
    "tests/structure_moves.py",
    "tests/structure_moves_baseline.json",
}


def _iter_files():
    for d in SCAN_DIRS:
        root = os.path.join(sm.REPO, d)
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [x for x in dirnames
                           if x not in ("node_modules", "dist", "__pycache__")]
            for fn in filenames:
                if not fn.endswith(SCAN_EXT):
                    continue
                p = os.path.join(dirpath, fn)
                rel = os.path.relpath(p, sm.REPO).replace(os.sep, "/")
                if rel in EXEMPT or rel.startswith("tracks/"):
                    continue
                yield rel, p


class NoStaleRefs(unittest.TestCase):

    def test_01_旧模块的旧名字零残留(self):
        """`ds_intake.load_taxonomy` / `ds_web._win_activate` 这类引用必须清零。

        两种形态都查(2026-08-02 panel-review subdeepseek 指出:原来只查限定引用,
        `from ds_intake import load_taxonomy` 这种漏网 —— 实测当前零命中,
        但判据不该有这个缺口)。
        """
        patterns = []
        for src, _dst, name in sm.MOVES:
            patterns.append((f"{src}.{name}", re.compile(rf"\b{src}\.{name}\b")))
            # from ds_intake import load_taxonomy[, x][ as y]
            patterns.append((f"from {src} import …{name}",
                             re.compile(rf"\bfrom\s+{src}\s+import\b[^\n#]*\b{name}\b")))
        hits = []
        for rel, path in _iter_files():
            with open(path, encoding="utf-8", errors="replace") as fh:
                for lineno, line in enumerate(fh, 1):
                    for label, rx in patterns:
                        if rx.search(line):
                            hits.append(f"{rel}:{lineno}  {label}  |  {line.strip()[:80]}")
        self.assertEqual(hits, [],
                         "旧限定名仍有残留(硬切不留转发):\n  " + "\n  ".join(hits))

    def test_02_豁免清单不许长(self):
        """护栏题:防止"往 EXEMPT 里加一行"变成通过判据的捷径。

        豁免只该有判据自身那三份。多一个就说明有人在拿豁免糊事。
        """
        self.assertEqual(len(EXEMPT), 3,
                         f"EXEMPT 被扩大到 {len(EXEMPT)} 项 —— "
                         "加豁免不是修 bug 的办法,请改调用点")


if __name__ == "__main__":
    unittest.main()
