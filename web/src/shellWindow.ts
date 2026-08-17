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

// 🔴 这里原来还有 `GRIP` 和 `resizeEdgeAt(x, y, w, h)` —— 一个按坐标算"鼠标在哪条边上"
// 的纯函数,外加**五条**围着它转的判据。2026-08-17 四审时发现:`WindowChrome.tsx`
// 一次都没调用过它。真正决定"能不能拖边"的是 app.css 里那八个 `.win-grip-*` 的定位,
// 而那边一条判据都没有 —— **五条全绿的考卷,问的是一段没上线的代码。**
// ⇒ 函数和那五条判据一起删掉,断言搬到 `test_shell_window_contract.py` 的 x7/x8
// (咬 CSS 里真实生效的那套:把手名单要和方向名单一一对应、且不许盖住按钮)。
// 教训同 [[field-needs-a-writer-before-ui]]:先问"谁在用它",再问"它对不对"。

/** 我们是不是跑在桌面外壳里(而不是普通浏览器)。
 *
 *  🔴 判据 s-w1:浏览器里**一个窗口按钮都不许出现** —— 那边没有窗口可以关,
 *  按下去只会是"点了没反应"。pywebview 会把 `window.pywebview` 注进页面,
 *  这是外壳与浏览器唯一可靠的分界。 */
export function inDesktopShell(win: unknown = globalThis): boolean {
  const w = win as { pywebview?: { api?: unknown } } | null;
  return !!(w && w.pywebview && w.pywebview.api);
}

/** 每条边配的鼠标指针(CSS cursor)。没有它,业主看不出哪儿能拉。 */
export function cursorFor(edge: ResizeEdge): string {
  if (edge === "top" || edge === "bottom") return "ns-resize";
  if (edge === "left" || edge === "right") return "ew-resize";
  if (edge === "topleft" || edge === "bottomright") return "nwse-resize";
  return "nesw-resize";
}
