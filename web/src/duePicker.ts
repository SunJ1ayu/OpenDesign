// 截止日弹出日历的纯逻辑层(track opendesign-due-picker)。契约见
// tests/test_due_picker.mjs(off-limits)。这里只回答「弹在哪」——不碰 DOM,便于直测。
//
// 为什么单独抽出来:用户要「贴着那一条就地弹出」,而待办列表里**总有条目贴着屏幕
// 底边**。翻转/夹取写在组件里就只能靠 e2e 一格一格试,抽出来才能把边界一次列全。

export type Rect = { left: number; right: number; top: number; bottom: number };
export type Size = { width: number; height: number };
export type Viewport = { width: number; height: number };
export type Placement = "below" | "above";
export type PopoverPos = { left: number; top: number; placement: Placement };

/**
 * 浮层落点。默认贴锚点下方、左边界对齐锚点左边界;
 *  - 下方装不下而上方装得下 → 翻到上方;
 *  - 上下都装不下 → 仍在下方,但夹进视口(宁可盖住一点也不许跑出屏幕外);
 *  - 水平溢出右缘 → 整体左移;窄视口下**左边界优先**(宁可右边露不全,
 *    也不让日历的左半边跑到屏幕外 —— 那半边是日期数字,丢了就没法点了)。
 * 纯函数,不改入参。
 */
export function popoverPosition(
  anchor: Rect,
  size: Size,
  viewport: Viewport,
  gap = 6,
): PopoverPos {
  const belowTop = anchor.bottom + gap;
  const aboveTop = anchor.top - gap - size.height;
  const fitsBelow = belowTop + size.height <= viewport.height;
  const fitsAbove = aboveTop >= 0;

  let placement: Placement = "below";
  let top = belowTop;
  if (!fitsBelow && fitsAbove) {
    placement = "above";
    top = aboveTop;
  } else if (!fitsBelow) {
    // 上下都装不下:顶到上边距,能露多少露多少(不改 placement —— 它仍是
    // "从锚点下方长出来"的那个语义,只是被视口按住了)。
    top = Math.max(gap, viewport.height - size.height - gap);
    if (top + size.height > viewport.height) top = gap;
  }

  let left = anchor.left;
  if (left + size.width > viewport.width - gap) {
    left = viewport.width - size.width - gap;
  }
  if (left < gap) left = gap;   // 左边界优先:最后夹一次,窄视口下它说了算
  if (left < 0) left = 0;

  return { left, top, placement };
}
