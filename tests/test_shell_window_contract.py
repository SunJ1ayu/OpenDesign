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
        它问的是层序本身 —— 将来谁再加一个 `inset:0` 的浮层,这里会自己响。
        """
        bar = _z_of(".win-bar")
        self.assertIsNotNone(bar, "窗口栏没有 z-index ⇒ 层序无从谈起")

        masks = []
        for sel, body in _css_rules():
            if "fixed" not in (_prop(body, "position") or ""):
                continue
            inset = _prop(body, "inset")
            if not (inset and inset.split()[0] == "0"):
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

    def test_x7_the_css_grips_match_the_edge_list(self):
        """🔴 **判据自己咬空过**:`shellWindow.ts` 里有个 `resizeEdgeAt()` 被五条判据
        围着测,而 `WindowChrome.tsx` 一次都没用过它 —— 真正决定"能不能拖边"的是
        `app.css` 里那八个 `.win-grip-*` 的定位,那边一条判据都没有。
        (08-17 四审 subkimi 在被断线砍断之前正好摸到这一条。)
        ⇒ 把断言搬到问得出的地方:CSS 里的把手名单必须和方向名单一一对应。
        """
        block = re.search(r"RESIZE_EDGES\s*=\s*\[(.*?)\]", _read(TS_EDGES), re.S)
        edges = set(re.findall(r'"([a-z]+)"', block.group(1)))
        in_css = set(re.findall(r"\.win-grip-([a-z]+)\b", _read(CSS)))
        self.assertEqual(edges, in_css,
                         f"CSS 里的把手和方向名单对不上:少了 {sorted(edges - in_css)}、"
                         f"多了 {sorted(in_css - edges)} ⇒ 那几条边拖了没反应")

    def test_x8_the_grips_never_eat_the_buttons(self):
        """把手不许压在三个按钮身上(点关闭按钮的上沿必须是关闭,不是"改窗口大小")。

        🔴 **这一条的第一版是假绿,而且犯的正是本版一直在治的那种病。**
        它当时只比 `.win-btns`(220) > `.win-grip`(210) 两个**声明数字**,
        判绿。可 `.win-bar` 是 `position:fixed` + `z-index:200` ——
        **它自己就是一个 stacking context**;`.win-btns` 是它的 DOM 子元素,
        那个 220 只在栏内部有效。根上下文里参与比较的是**整个栏的 200**
        对把手的 210 ⇒ 把手照样画在按钮上面,F7 原样没修。
        (08-17 四审 subkimi F-1;另一条腿在同一处判了"properly fixed"。)

        ⇒ 层号自己说明不了问题,**得先问结构**:要参与根层序比较的三者
        必须是**同一层的兄弟**,谁也不许被谁的 stacking context 关起来。
        """
        tsx = _read(TSX_CHROME)
        self.assertIn('className="win-btns"', tsx, "按钮区不见了")
        self.assertTrue(
            _jsx_tag_is_self_closing(tsx, "win-bar"),
            "窗口栏里装了东西 ⇒ 栏是 fixed+z-index、自己就是一个 stacking context,"
            "装在里面的层号在根上下文里**不算数**,把手照样吃掉按钮上沿。"
            "栏必须是空的纯拖动区,按钮区做它的兄弟节点。")

        bar_z, grip, btns = _z_of(".win-bar"), _z_of(".win-grip"), _z_of(".win-btns")
        for name, z in (("窗口栏", bar_z), ("把手", grip), ("按钮区", btns)):
            self.assertIsNotNone(z, f"{name}没有 z-index ⇒ 层序无从谈起")
        self.assertLess(bar_z, grip, "把手要压过栏,否则整条顶边改不了大小")
        self.assertLess(grip, btns, "按钮要压过把手,否则按钮上沿点下去是改大小")

    def test_x9_every_grip_actually_sits_on_its_edge(self):
        """把手的**几何**:贴边、且有厚度。

        x7 只问名字、x8 只问层序 —— 把某个把手挪到屏幕中间、或把厚度改成 0,
        两条都照绿,而业主那边"这条边拖不动"(08-17 四审 subdeepseek 记的覆盖缺口)。
        """
        css = _read(CSS)
        for edge in ("top", "bottom", "left", "right",
                     "topleft", "topright", "bottomleft", "bottomright"):
            m = re.search(rf"\.win-grip-{edge}\s*\{{([^}}]*)\}}", css)
            self.assertIsNotNone(m, f".win-grip-{edge} 不见了")
            body = m.group(1)
            # 贴边:名字里的每个方向,对应的 offset 必须是 0
            for side in ("top", "bottom", "left", "right"):
                if side in edge:
                    self.assertRegex(body, rf"{side}\s*:\s*0(?![.\d])",
                                     f".win-grip-{edge} 没贴住 {side} 边 ⇒ 那儿拖不动")
            # 有厚度:宽或高至少有一个是正数(0 = 一条抓不住的线)
            sizes = [int(v) for v in re.findall(r"(?:width|height)\s*:\s*(\d+)px", body)]
            self.assertTrue(sizes and all(v > 0 for v in sizes),
                            f".win-grip-{edge} 的尺寸是 {sizes} —— 0 像素的把手抓不住")

    def test_x4_the_chrome_never_shows_up_in_a_plain_browser(self):
        """浏览器里没有窗口可关,画出来就是三个按下去没反应的按钮。
        分界必须走 inDesktopShell(判据 s-w1/s-w2 咬着它的行为)。"""
        self.assertIn("inDesktopShell", _read(TSX_CHROME),
                      "窗口栏没问过'我是不是在外壳里' ⇒ 浏览器里也会画出来")


if __name__ == "__main__":
    unittest.main()
