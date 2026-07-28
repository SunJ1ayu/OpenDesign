// 截止日弹出日历「弹在哪」的纯逻辑层 oracle(新文件 web/src/duePicker.ts)。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// 为什么这块要单独抽成纯函数:用户要的是「贴着那一条就地弹出」,而待办列表里
// **总有条目贴着屏幕底边**。翻转/夹取写在组件里就只能靠 e2e 一格一格试,
// 抽出来才能把边界情形一次列全。
//
//   popoverPosition(anchor, size, viewport, gap) → { left, top, placement }
//     anchor/viewport/size 都是普通对象(不碰 DOM),便于直测。
//     - 默认贴 anchor 下方、左边界对齐 anchor 左边界;
//     - 下方装不下而上方装得下 → 翻到上方(placement="above");
//     - 上下都装不下 → 仍在下方,但**夹进视口**(宁可盖住一点也不许跑出屏幕外);
//     - 右侧会溢出 → 整体左移到贴右边距;左侧同理不许越出;
//     - 纯函数:不改入参。
//
// 跑法:node --test tests/test_due_picker.mjs(Node 22+,原生 strip-types)
// red-check:实现前 web/src/duePicker.ts 不存在,本文件整体红。
import { test } from "node:test";
import assert from "node:assert/strict";
import { popoverPosition } from "../web/src/duePicker.ts";

const VP = { width: 1440, height: 900 };
const SIZE = { width: 260, height: 300 };
const GAP = 6;
// 视口中部一个普通锚点:上下左右都宽裕
const mid = { left: 400, right: 460, top: 300, bottom: 320 };

test("空间充足:弹在下方,左边界对齐锚点", () => {
  const p = popoverPosition(mid, SIZE, VP, GAP);
  assert.equal(p.placement, "below");
  assert.equal(p.top, mid.bottom + GAP);
  assert.equal(p.left, mid.left);
});

test("下方装不下、上方装得下 → 翻到上方", () => {
  // 锚点靠近底边:下方只剩 900-820-6 = 74 < 300
  const low = { left: 400, right: 460, top: 800, bottom: 820 };
  const p = popoverPosition(low, SIZE, VP, GAP);
  assert.equal(p.placement, "above");
  assert.equal(p.top, low.top - GAP - SIZE.height);
  assert.ok(p.top >= 0, `翻上去也不许出上边界(实测 top=${p.top})`);
});

test("上下都装不下 → 不翻,但夹进视口(不许跑到屏幕外)", () => {
  const tiny = { width: 400, height: 320 }; // 比浮层还矮的视口
  const anchor = { left: 100, right: 160, top: 150, bottom: 170 };
  const p = popoverPosition(anchor, SIZE, tiny, GAP);
  assert.ok(p.top >= 0, `top 不许为负(实测 ${p.top})`);
  assert.ok(p.top + SIZE.height <= tiny.height || p.top === GAP,
    `装不下时顶到上边距即可,但不许把顶端推出视口(top=${p.top})`);
});

test("右侧会溢出 → 整体左移,右边界留出边距", () => {
  // 锚点贴右缘:left+260 = 1660 > 1440
  const right = { left: 1400, right: 1430, top: 300, bottom: 320 };
  const p = popoverPosition(right, SIZE, VP, GAP);
  assert.ok(p.left + SIZE.width <= VP.width - GAP + 0.01,
    `右边界不许越出视口(left=${p.left} + ${SIZE.width} > ${VP.width - GAP})`);
  assert.ok(p.left < right.left, "确实左移了");
});

test("锚点贴左缘 → 左边界不许为负", () => {
  const left = { left: 2, right: 40, top: 300, bottom: 320 };
  const p = popoverPosition(left, SIZE, VP, GAP);
  assert.ok(p.left >= 0, `left 不许为负(实测 ${p.left})`);
});

test("视口比浮层还窄 → 仍不许出左边界(夹取的优先级:左 > 右)", () => {
  const narrow = { width: 200, height: 900 };
  const anchor = { left: 150, right: 190, top: 300, bottom: 320 };
  const p = popoverPosition(anchor, SIZE, narrow, GAP);
  assert.ok(p.left >= 0, `窄视口下 left 仍不许为负(实测 ${p.left})`);
});

test("纯函数:不改入参", () => {
  const a = { left: 400, right: 460, top: 300, bottom: 320 };
  const s = { width: 260, height: 300 };
  const v = { width: 1440, height: 900 };
  const snap = JSON.stringify([a, s, v]);
  popoverPosition(a, s, v, GAP);
  assert.equal(JSON.stringify([a, s, v]), snap);
});

test("gap 缺省有值(调用方不传也不能算出 NaN)", () => {
  const p = popoverPosition(mid, SIZE, VP);
  assert.ok(Number.isFinite(p.left) && Number.isFinite(p.top), `实测 ${JSON.stringify(p)}`);
  assert.ok(p.top > mid.bottom, "缺省 gap 也要跟锚点隔开");
});
