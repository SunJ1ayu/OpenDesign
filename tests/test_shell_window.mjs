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
  GRIP,
  RESIZE_EDGES,
  cursorFor,
  inDesktopShell,
  resizeEdgeAt,
} from "../web/src/shellWindow.ts";

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

// ── ② 边和角 ────────────────────────────────────────────────────────
test("s-w3 四条边各自认得出来", () => {
  const W = 800, H = 600;
  assert.equal(resizeEdgeAt(400, 1, W, H), "top");
  assert.equal(resizeEdgeAt(400, H - 1, W, H), "bottom");
  assert.equal(resizeEdgeAt(1, 300, W, H), "left");
  assert.equal(resizeEdgeAt(W - 1, 300, W, H), "right");
});

test("s-w4 角优先于边 —— 在角上业主要的是斜着拉", () => {
  const W = 800, H = 600;
  assert.equal(resizeEdgeAt(0, 0, W, H), "topleft");
  assert.equal(resizeEdgeAt(W - 1, 0, W, H), "topright");
  assert.equal(resizeEdgeAt(0, H - 1, W, H), "bottomleft");
  assert.equal(resizeEdgeAt(W - 1, H - 1, W, H), "bottomright");
});

test("s-w5 中间大片区域不许算成边 —— 不然整个界面都点不动", () => {
  const W = 800, H = 600;
  assert.equal(resizeEdgeAt(400, 300, W, H), null);
  assert.equal(resizeEdgeAt(GRIP + 1, GRIP + 1, W, H), null);
});

test("s-w6 感应带正好 GRIP 宽:边界那一像素算边,再进一格就不算", () => {
  const W = 800, H = 600;
  assert.equal(resizeEdgeAt(GRIP, 300, W, H), "left");
  assert.equal(resizeEdgeAt(GRIP + 0.5, 300, W, H), null);
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

test("s-w8 resizeEdgeAt 只会吐出名单里的名字", () => {
  const W = 40, H = 30;
  const seen = new Set();
  for (let x = 0; x <= W; x++) {
    for (let y = 0; y <= H; y++) {
      const edge = resizeEdgeAt(x, y, W, H);
      if (edge !== null) seen.add(edge);
    }
  }
  assert.deepEqual([...seen].sort(), [...RESIZE_EDGES].sort(),
    "有方向永远走不到(或吐出了名单外的名字)⇒ 那条边拖了没反应");
});
