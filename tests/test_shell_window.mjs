// 判据:桌面外壳的窗口栏纯逻辑层(track opendesign-key-startup-crash)。
// 跑法:node --test tests/test_shell_window.mjs(Node 22+,原生 strip-types)
//
// 被判的模块 `web/src/shellWindow.ts` 只回答两个问题:
//   ① 我现在是不是在外壳里(决定那三个按钮渲不渲染);
//   ② 鼠标落在窗口的哪条边上(决定往 Python 那边报哪个方向)。
// 窗口真的动不动得了,只有 Windows 真机答得了 —— 那部分不在这里。
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  RESIZE_EDGES,
  SHELL_MARK,
  cursorFor,
  inDesktopShell,
} from "../web/src/shellWindow.ts";

/** 造一个假 window:只有地址栏(和可选的 pywebview)。 */
const win = (search, extra = {}) => ({ location: { search }, ...extra });

// 🔴 2026-08-17:这里原来还有五条(s-w3~s-w6、s-w8)围着 `resizeEdgeAt()` 转 ——
// 而生产代码从来没调用过那个函数。**五条全绿,问的是一段没上线的代码。**
// 真正决定"能不能拖边"的是 app.css 里那八个 `.win-grip-*`,断言已搬到
// tests/test_shell_window_contract.py 的 x7/x8(它们咬的是真实生效的那套)。
// 删判据是敏感动作,所以把理由留在这儿:不是"它红了所以删",是"它问的东西不存在"。

// ── ① 外壳自己在地址里报身份 ─────────────────────────────────────────
// 🔴 2026-08-17 改写这两条,证据方向说清楚(改判据是敏感动作):
//    不是"它们红了所以改",是它们**问的东西在真运行时里问不出来**。
//    旧版把「`window.pywebview.api` 在不在」当成「我在不在外壳里」,而
//    pywebview 5.4 的 Windows 后端在 `on_navigation_completed` 里才注入
//    (webview/platforms/edgechromium.py:314,`finish.js` 还要再晚一个线程)——
//    也就是**页面脚本跑完之后**。React 挂载那一刻问它,答案必然是 false ⇒
//    业主机器上窗口栏整块没画出来(0.89.0/0.90.0 两版都带着这个病发出去了)。
//    所以分界换成"外壳打开页面时在地址里带的标记",它在第一帧就在。
test("s-w1 地址里没标记 = 不在外壳里(浏览器里一个窗口按钮都不许出现)", () => {
  assert.equal(inDesktopShell(win("")), false);
  assert.equal(inDesktopShell({}), false);          // 连 location 都没有
  assert.equal(inDesktopShell(null), false);
});

test("s-w2 地址里带标记才算在外壳里", () => {
  assert.equal(inDesktopShell(win(`?${SHELL_MARK}`)), true);
  // 外壳将来往地址里加别的参数,也得照样认
  assert.equal(inDesktopShell(win(`?foo=bar&${SHELL_MARK}`)), true);
});

test("s-w2b 只有 pywebview 注进来、地址没标记 ⇒ 仍然不算(本单的病根标本)", () => {
  // 真机上这个条件在首帧**永远不成立**,拿它当分界等于窗口栏永远不画。
  // 这一条钉住"别再把它当依据"——将来谁把 pywebview 加回判断里,它会响。
  assert.equal(inDesktopShell(win("", { pywebview: { api: {} } })), false);
});

test("s-w2c 长得像的参数不许假命中(别用子串匹配)", () => {
  // `search.includes("shell=1")` 会让下面三个全变 true:业主的界面无所谓,
  // 但那意味着分界是"地址里恰好有这几个字",不是"外壳报了身份"。
  assert.equal(inDesktopShell(win("?shell=0")), false);
  assert.equal(inDesktopShell(win("?shellx=1")), false);
  assert.equal(inDesktopShell(win("?noshell=1")), false);
});

// ── ③ 名单本身 ──────────────────────────────────────────────────────
test("s-w7 八个方向每个都有指针,且指针方向对得上", () => {
  assert.equal(RESIZE_EDGES.length, 8);
  for (const edge of RESIZE_EDGES) {
    assert.match(cursorFor(edge), /^(ns|ew|nwse|nesw)-resize$/, `${edge} 没有指针`);
  }
  // 对角线两组不许配反:配反了鼠标显示的方向和实际拉的方向是拧着的
  assert.equal(cursorFor("topleft"), cursorFor("bottomright"));
  assert.equal(cursorFor("topright"), cursorFor("bottomleft"));
  assert.notEqual(cursorFor("topleft"), cursorFor("topright"));
});

