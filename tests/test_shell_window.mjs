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
  cursorFor,
  inDesktopShell,
} from "../web/src/shellWindow.ts";

// 🔴 2026-08-17:这里原来还有五条(s-w3~s-w6、s-w8)围着 `resizeEdgeAt()` 转 ——
// 而生产代码从来没调用过那个函数。**五条全绿,问的是一段没上线的代码。**
// 真正决定"能不能拖边"的是 app.css 里那八个 `.win-grip-*`,断言已搬到
// tests/test_shell_window_contract.py 的 x7/x8(它们咬的是真实生效的那套)。
// 删判据是敏感动作,所以把理由留在这儿:不是"它红了所以删",是"它问的东西不存在"。

// ── ① 浏览器里一个按钮都不许出现 ─────────────────────────────────────
test("s-w1 普通浏览器里不算在外壳里 —— 那边没有窗口可关", () => {
  assert.equal(inDesktopShell({}), false);
  assert.equal(inDesktopShell(null), false);
  // 有 pywebview 但 api 还没注进来(注入有先后)⇒ 这时候画按钮,按下去会炸
  assert.equal(inDesktopShell({ pywebview: {} }), false);
});

test("s-w2 外壳里(pywebview.api 已就位)才算", () => {
  assert.equal(inDesktopShell({ pywebview: { api: {} } }), true);
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

