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
CSS = os.path.join(ROOT, "web", "src", "app.css")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _css_rules() -> list[tuple[str, str]]:
    """(选择器, 规则体) 的粗切分。够用就好 —— 这里只问 position/inset/z-index。"""
    text = re.sub(r"/\*.*?\*/", "", _read(CSS), flags=re.S)
    return [(sel.strip(), body) for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", text, re.S)]


def _prop(body: str, name: str) -> str | None:
    m = re.search(rf"(?:^|;|\s){name}\s*:\s*([^;}}]+)", body)
    return m.group(1).strip() if m else None


def _zindex(body: str) -> int | None:
    v = _prop(body, "z-index")
    return int(v) if v and v.lstrip("-").isdigit() else None


def _jsx_tag_is_self_closing(src: str, class_name: str) -> bool:
    """`className="<class_name>"` 那个 JSX 标签是不是自闭合(`/>`)。

    🔴 **别用正则找标签的结束**:`onMouseDown={(e) => …}` 里的箭头就是一个 `>`,
    非贪婪匹配会停在那儿。x6 的第一版栽过一次、x8 的第一版又栽了同一次 ——
    所以这里老老实实扫一遍,数着 `{}` 的深度、跳过字符串,只认深度为 0 的那个收尾。
    """
    i = src.index(f'className="{class_name}"')
    i = src.rindex("<", 0, i)                     # 回到这个标签的开头
    depth, quote = 0, ""
    while i < len(src):
        c = src[i]
        if quote:
            if c == quote:
                quote = ""
        elif c in "\"'":
            quote = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif depth == 0 and c == ">":
            return src[i - 1] == "/"
        i += 1
    raise AssertionError(f"没找到 {class_name} 标签的收尾 —— 这道闸问不出东西")


def _call_args(src: str, func: str) -> str:
    """`func(...)` 括号里那一段(**数括号深度,不用正则找边界**)。

    🔴 「用正则找边界」这个坑本仓已经踩了四次(JSX 标签里的 `=>`、
    参数里的 `min_size=(960, 640)` 都会让非贪婪匹配停错地方)。老实扫。
    """
    i = src.index(func + "(") + len(func)
    start, depth, quote = i + 1, 0, ""
    while i < len(src):
        c = src[i]
        if quote:
            if c == quote and src[i - 1] != "\\":
                quote = ""
        elif c in "\"'":
            quote = c
        elif c == "#":                      # 行内注释里的括号不算
            i = src.find("\n", i)
            if i < 0:
                break
            continue
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return src[start:i]
        i += 1
    raise AssertionError(f"没找到 {func}( 的收尾 —— 这道闸问不出东西")


def _ts_code_only(src: str) -> str:
    """把 TS 源码里的注释剥掉(块注释 + 行注释)。

    🔴 不剥就是一场**误报**:这个文件的注释里必然要讲 pywebview 那段历史,
    而 x11 问的是"代码里还读不读它"。误报和假绿一样坏(08-13 记过)。
    """
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(line.split("//")[0] for line in src.splitlines())


def _z_of(selector: str) -> int | None:
    """某个类自己声明的 z-index(取最后一次声明 —— 后面的赢)。"""
    found = None
    for sel, body in _css_rules():
        if re.search(rf"(^|,|\s){re.escape(selector)}(?![\w-])", sel):
            z = _zindex(body)
            if z is not None:
                found = z
    return found


class WindowContract(unittest.TestCase):

    # ── 2026-08-17 四审之后补的四条 ──────────────────────────────────────
    # 上面 x1~x4 问的都是"名字对不对得上"。这一版真正会让业主骂人的四件事,
    # 一条都不在那四问的射程里 —— 补在下面。

    def test_x5_nothing_is_allowed_to_cover_the_window_bar(self):
        """🔴 **业主装完第一次打开必然撞上**:填 key 的连接弹窗
        (`.connect-modal-mask`,`inset:0` + z-index 70)盖在窗口栏(z-index 60)上面
        ⇒ 那一刻最小化/最大化/关闭三个按钮全点不动,窗口也拖不动。
        无边框窗口把这三个按钮变成了**唯一**的出口 —— 系统标题栏已经没有了,
        盖住它 = 业主只能去任务管理器。

        所以窗口栏必须在**所有**全屏遮罩之上。这道闸不点名任何一个遮罩,
        它问的是层序本身 —— 将来谁再加一个铺满屏幕的浮层,这里会自己响。

        🔴 **2026-08-17 补盲区**(评审 F3):原来只认 `inset: 0` 那一种写法。
        今天 app.css 里三个遮罩恰好都这么写,所以它是绿的 —— 但换成
        `top:0;left:0;right:0;bottom:0` 或 `width:100vw;height:100vh`,
        这道闸会**静默漏掉**它,而漏掉的后果正是它存在的全部理由(任务管理器陷阱)。
        ⇒ 三种写法都认。
        """
        bar = _z_of(".win-bar")
        self.assertIsNotNone(bar, "窗口栏没有 z-index ⇒ 层序无从谈起")

        def _covers_screen(body: str) -> bool:
            inset = _prop(body, "inset")
            if inset and inset.split()[0] == "0":
                return True
            # 四个 offset 各写一遍(等价于 inset:0)
            if all((_prop(body, s) or "").startswith("0")
                   for s in ("top", "right", "bottom", "left")):
                return True
            # 视口尺寸铺满
            return ((_prop(body, "width") or "").startswith("100v")
                    and (_prop(body, "height") or "").startswith("100v"))

        masks = []
        for sel, body in _css_rules():
            if "fixed" not in (_prop(body, "position") or ""):
                continue
            if not _covers_screen(body):
                continue
            if ".win-" in sel:
                continue
            masks.append((sel.split("{")[-1].strip(), _zindex(body) or 0))

        self.assertGreaterEqual(len(masks), 3,
                                f"只扫到 {len(masks)} 个全屏遮罩 —— 这道闸八成解析坏了,"
                                "它现在问不出东西(app.css 里的写法变了?)")
        over = [(s, z) for s, z in masks if z >= bar]
        self.assertEqual([], over,
                         f"这些浮层压在窗口栏(z-index {bar})上面或同层:{over} ⇒ "
                         "它们一出现,业主就关不掉窗口了")

    def test_x6_clicking_a_window_button_never_also_moves_the_window(self):
        """点/双击三个按钮,不许连带触发窗口栏自己的动作(拖窗口 / 最大化)。

        栏上挂着 `onMouseDown=拖窗口` 和 `onDoubleClick=最大化`。按钮**曾经**是栏的
        子元素,于是双击关闭按钮会白送一次最大化(08-17 四审 subdeepseek F1);
        当时的修法是在按钮区 stopPropagation 两个事件。

        第二轮把按钮区**抬成了栏的兄弟节点**(subkimi F-1,stacking context)——
        不再是父子,事件根本不冒泡过去,那两个 stopPropagation 成了白留的。
        ⇒ 这一条跟着改问**结构**:两者不许是父子。**比原来强** ——
        原来只挡住了两个点名的事件,现在整类都不可能发生。
        (结构断言由 x8 咬同一件事的层序一面。)
        """
        tsx = _read(TSX_CHROME)
        self.assertIn('className="win-btns"', tsx, "按钮区不见了")
        self.assertTrue(
            _jsx_tag_is_self_closing(tsx, "win-bar"),
            "按钮区又回到窗口栏里了 ⇒ 点按钮会冒泡成拖窗口、双击会白送一次最大化")

    def test_x4_the_chrome_never_shows_up_in_a_plain_browser(self):
        """浏览器里没有窗口可关,画出来就是三个按下去没反应的按钮。
        分界必须走 inDesktopShell(判据 s-w1/s-w2 咬着它的行为)。"""
        self.assertIn("inDesktopShell", _read(TSX_CHROME),
                      "窗口栏没问过'我是不是在外壳里' ⇒ 浏览器里也会画出来")

    def test_x11_the_shell_flag_is_the_only_gate(self):
        """分界不许再回到 `window.pywebview` 上(x10 那个病的入口)。

        e2e(tests/e2e/shell_chrome.e2e.mjs)从行为面咬同一件事:真 chromium 里
        `/?shell=1` 必须画出三个按钮 —— 那边没有 pywebview,谁把它加回判断里就红。
        这里补一条静态的,理由是**读起来一眼看得见**:这个文件里出现
        `pywebview` 只能是在讲那段历史(注释),不能是代码。
        """
        code = _ts_code_only(_read(TS_EDGES))
        self.assertIn("SHELL_MARK", code, "这道闸问不出东西:剥完注释连常量都没了")
        self.assertNotIn("pywebview", code,
                         "分界又读 pywebview 了 ⇒ 注入发生在页面脚本之后,"
                         "这个问法在真机上永远答 false(窗口栏整块不画)")


if __name__ == "__main__":
    unittest.main()
