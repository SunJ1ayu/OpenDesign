#!/usr/bin/env python3
"""窗口栏的**跨语言对表闸**:前端按下去的名字,Python 那边接不接得住。

无边框窗口那一套横跨两种语言、跑在一个我在 Linux 上开不出来的运行时里
(WebView2 + WinForms)。中间只靠**字符串**连着:
  · 前端把方向名(`"bottomright"`)发过去,Python 拿它查 `WindowApi.HIT`;
  · 前端叫 `pywebview.api.toggle_maximize()`,pywebview 按**方法名**去 Python 找。
两边任意一个名字对不上,后果都是同一种:**按下去没反应,而且哪儿都不报错**。
这正是真机上最难描述、最容易被当成"手感问题"放过去的那类坏法。

所以这道闸只问一件机器答得了的事:两份名单是不是一字不差。
(按下去到底动不动 —— 那只有 Windows 真机答得了,已进真机清单。)
"""
from __future__ import annotations

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bin"))

import ds_shell  # noqa: E402

TS_EDGES = os.path.join(ROOT, "web", "src", "shellWindow.ts")
TSX_CHROME = os.path.join(ROOT, "web", "src", "workspace", "WindowChrome.tsx")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class WindowContract(unittest.TestCase):

    def test_x1_the_edge_names_match_on_both_sides(self):
        """前端的 RESIZE_EDGES ↔ Python 的 HIT(去掉标题区那一项)。"""
        block = re.search(r"RESIZE_EDGES\s*=\s*\[(.*?)\]", _read(TS_EDGES), re.S)
        self.assertIsNotNone(block, "前端那份方向名单没找到 —— 名字或写法变了")
        ts = set(re.findall(r'"([a-z]+)"', block.group(1)))
        py = set(ds_shell.WindowApi.HIT) - {"caption"}
        self.assertEqual(ts, py,
                         f"两边的方向名对不上:前端有 {sorted(ts - py)}、"
                         f"Python 有 {sorted(py - ts)} ⇒ 那几条边拖了没反应")
        self.assertEqual(8, len(ts), "四边四角一共八个,少一个就是一条边拖不动")

    def test_x2_every_button_calls_a_method_that_really_exists(self):
        """pywebview 按**方法名**把 `pywebview.api.xxx()` 接到 Python 上。
        前端写 `close_window()` 而 Python 叫 `close()` ⇒ 关闭按钮永远点不动,
        且控制台之外没有任何提示。"""
        called = set(re.findall(r"api\(\)\?\.([a-z_]+)\(", _read(TSX_CHROME)))
        self.assertTrue(called, "前端一个 api 调用都没扫到 —— 这道闸问不出东西")
        for name in sorted(called):
            self.assertTrue(
                callable(getattr(ds_shell.WindowApi, name, None)),
                f"前端叫了 pywebview.api.{name}(),Python 那边没有这个方法 ⇒ 那个按钮是死的")

    def test_x3_the_three_buttons_are_all_wired(self):
        """业主要的就是这三个。少接一个 = 少一个按钮,而界面上看不出来。"""
        tsx = _read(TSX_CHROME)
        for ui, what in (("window-min", "最小化"), ("window-max", "最大化"),
                         ("window-close", "关闭")):
            self.assertIn(f'data-ui="{ui}"', tsx, f"{what}按钮没了")

    def test_x4_the_chrome_never_shows_up_in_a_plain_browser(self):
        """浏览器里没有窗口可关,画出来就是三个按下去没反应的按钮。
        分界必须走 inDesktopShell(判据 s-w1/s-w2 咬着它的行为)。"""
        self.assertIn("inDesktopShell", _read(TSX_CHROME),
                      "窗口栏没问过'我是不是在外壳里' ⇒ 浏览器里也会画出来")


if __name__ == "__main__":
    unittest.main()
