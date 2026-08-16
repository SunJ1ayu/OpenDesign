// 桌面外壳的窗口栏 —— 纯逻辑层(零 DOM、零 pywebview 调用)。
//
// 由来:2026-08-16 业主真机「左上角出现的 OpenDesign 标题和我们本来有的前端
// OpenDesign 冲突了…为什么不能不要外面那个框」。于是窗口改成无边框,
// 最小化/最大化/关闭由我们自己画。
//
// 🔴 Windows 的边框不只是那三个按钮 ——「拖边缘改大小」也是它给的。框去掉,
//    这件事就得自己接回来:所以这里除了按钮,还要认出鼠标在不在四边四角上。
//
// 为什么单独一个文件:窗口栏最终要跑在**只有 Windows 才有**的运行时里
// (pywebview + WebView2),那一层我在 Linux 上一行都验不了。把"能判的"
// (在不在外壳里、鼠标落在哪条边上、边名和 Python 那边对不对得上)全挤到
// 这里,剩给真机的就只有"手感对不对"。

/** 八个方向 + 标题区。**这份名单是和 `bin/ds_shell.py` 的 HT 映射对表的**
 *  (tests/test_shell_window_contract.py 逐个比对);多一个少一个都是"拖了没反应"。 */
export const RESIZE_EDGES = [
  "top", "bottom", "left", "right",
  "topleft", "topright", "bottomleft", "bottomright",
] as const;

export type ResizeEdge = (typeof RESIZE_EDGES)[number];

/** 边缘感应带的宽度(CSS px)。太窄抓不住,太宽会吃掉贴边内容的点击。 */
export const GRIP = 6;

/** 我们是不是跑在桌面外壳里(而不是普通浏览器)。
 *
 *  🔴 判据 s-w1:浏览器里**一个窗口按钮都不许出现** —— 那边没有窗口可以关,
 *  按下去只会是"点了没反应"。pywebview 会把 `window.pywebview` 注进页面,
 *  这是外壳与浏览器唯一可靠的分界。 */
export function inDesktopShell(win: unknown = globalThis): boolean {
  const w = win as { pywebview?: { api?: unknown } } | null;
  return !!(w && w.pywebview && w.pywebview.api);
}

/** 鼠标落在窗口的哪条边/哪个角上;都不在就返回 null。
 *
 *  角优先于边(在左上角 6×6 那一小块里,业主想要的是斜着拉,不是只拉左边)。 */
export function resizeEdgeAt(
  x: number, y: number, width: number, height: number, grip: number = GRIP,
): ResizeEdge | null {
  const left = x <= grip;
  const right = x >= width - grip;
  const top = y <= grip;
  const bottom = y >= height - grip;

  if (top && left) return "topleft";
  if (top && right) return "topright";
  if (bottom && left) return "bottomleft";
  if (bottom && right) return "bottomright";
  if (top) return "top";
  if (bottom) return "bottom";
  if (left) return "left";
  if (right) return "right";
  return null;
}

/** 每条边配的鼠标指针(CSS cursor)。没有它,业主看不出哪儿能拉。 */
export function cursorFor(edge: ResizeEdge): string {
  if (edge === "top" || edge === "bottom") return "ns-resize";
  if (edge === "left" || edge === "right") return "ew-resize";
  if (edge === "topleft" || edge === "bottomright") return "nwse-resize";
  return "nesw-resize";
}
