#!/usr/bin/env python3
"""判据:静默安装**永远不许卡在等人点确定**(installer/OpenDesign.nsi)。

    python3 tests/test_installer_silent.py

## 为什么这份判据存在(2026-08-25,云机器实测抓到的)

NSIS 的 `/S` 只跳过**安装界面**,`MessageBox` **照弹**——除非写了 `/SD <默认>`。
而这个安装器的 4 个 MessageBox 一个都没写。后果在 GitHub 的云 Windows 机器上
当场复现(run 32801760571):配置初始化失败 → 弹框 → **没有人点确定** →
安装器 8 分钟不退出,而屏幕上那个框还被别的窗口盖着、截图里一个字都看不见。

**这不是"云机器特有的事"**:任何无人值守的安装(IT 批量部署、我们自己的 CI)
都会撞上同一堵墙,而现象是"安装程序假死",不给任何线索。

## 它问不出什么

它只问"每个 MessageBox 有没有默认答案",不问"那个默认答案选得对不对"——
后者是人的判断,写在下面每一条的注释里。
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
NSI = REPO / "installer" / "OpenDesign.nsi"

# `MessageBox` 到行尾(NSIS 用 `\` 续行,所以要把续行接起来再看)
MSGBOX = re.compile(r"^\s*MessageBox\b(.*)$")


def messagebox_calls() -> list[tuple[int, str]]:
    """(行号, 这条 MessageBox 的完整文本含续行)。"""
    lines = NSI.read_text(encoding="utf-8").splitlines()
    out: list[tuple[int, str]] = []
    i = 0
    while i < len(lines):
        m = MSGBOX.match(lines[i])
        if m:
            start = i + 1
            text = m.group(1)
            while text.rstrip().endswith("\\") and i + 1 < len(lines):
                i += 1
                text = text.rstrip()[:-1] + lines[i]
            out.append((start, text))
        i += 1
    return out


class SilentInstallNeverBlocks(unittest.TestCase):

    def test_s1_there_are_messageboxes_to_check(self):
        """先证明这道闸问得出东西 —— 一条都扫不到时它会永远绿。"""
        calls = messagebox_calls()
        self.assertGreaterEqual(
            len(calls), 4,
            f"只扫到 {len(calls)} 条 MessageBox —— 八成是解析坏了(NSIS 写法变了?),"
            "这道闸现在问不出东西")

    def test_s2_every_messagebox_has_a_silent_default(self):
        """🔴 每一条都必须有 `/SD` —— 没有它,静默安装就会停在那儿等人。

        选哪个默认值是**人的判断**,规矩是:
        · 纯告知型(点完照样继续装)→ `/SD IDOK`,别让它拦住无人值守的安装;
        · 涉及"可能删掉业主东西"的选择(目录非空那条)→ `/SD IDCANCEL`,
          **静默时选保守的那一侧**:没人在场就不许替业主承担数据风险。
        """
        missing = [(ln, t.strip()[:60]) for ln, t in messagebox_calls() if "/SD" not in t]
        self.assertEqual(
            [], missing,
            "这些 MessageBox 没有静默默认值 ⇒ `/S` 安装会卡在它上面等人点:\n  " +
            "\n  ".join(f"{NSI.name}:{ln}  {t}…" for ln, t in missing))

    def test_s3_the_data_loss_one_defaults_to_cancel(self):
        """目录非空那条是唯一一个"选错了会删掉业主东西"的 —— 它的默认必须是取消。

        它长这样:`MB_OKCANCEL` + "点确定就用这个已经有东西的文件夹",
        而卸载会把整个文件夹删掉。无人值守时点"确定" = 替业主承担了他没同意的风险。
        """
        okcancel = [(ln, t) for ln, t in messagebox_calls() if "MB_OKCANCEL" in t]
        self.assertEqual(1, len(okcancel),
                         f"预期只有一条 MB_OKCANCEL(目录非空那条),实际 {len(okcancel)} 条 —— "
                         "新增了选择型弹框的话,这条判据要跟着想清楚默认值")
        ln, text = okcancel[0]
        self.assertIn("/SD IDCANCEL", text,
                      f"{NSI.name}:{ln} 这条涉及删掉业主的东西,静默默认必须是 IDCANCEL(保守的那一侧)")


    def test_s4_the_silent_default_is_written_where_nsis_accepts_it(self):
        """🔴 `/SD` 必须写在**正文之后**,不是跟在 `MessageBox` 后面。

        NSIS 的语法是 `MessageBox mode text [/SD ret] [ret_check label]`。

        这条是被自己的疏忽逼出来的(2026-08-25):s2 只问了"有没有 /SD",
        于是我把它写成 `MessageBox /SD IDCANCEL MB_OKCANCEL|… "正文"` —— **s2/s3 全绿**,
        而 `makensis` 当场 abort(`Error in script "OpenDesign.nsi" on line 191`)。
        **一道连"编不编得过"都分不出来的闸,给的绿是假的。**
        （真正兜住它的是打包那一步 —— 但闸的价值在于更早、更便宜地说清楚哪里错。）
        """
        for ln, text in messagebox_calls():
            if "/SD" not in text:
                continue          # 有没有由 s2 管,这里只管位置
            quote = text.find('"')
            self.assertNotEqual(-1, quote, f"{NSI.name}:{ln} 这条 MessageBox 没有正文?")
            self.assertGreater(
                text.index("/SD"), quote,
                f"{NSI.name}:{ln} `/SD` 写在正文前面了 ⇒ makensis 编不过。"
                "语法是 `MessageBox mode text /SD <默认> [ret label]`")


if __name__ == "__main__":
    unittest.main(verbosity=2)
