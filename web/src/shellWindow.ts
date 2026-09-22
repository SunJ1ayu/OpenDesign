// 桌面外壳的窗口栏标记。Electron 保留原生 thickFrame，前端不再实现缩放把手。
export const SHELL_MARK = "shell=1";

/** 我们是不是跑在桌面外壳里(而不是普通浏览器)。
 *
 *  🔴 判据 s-w1:浏览器里**一个窗口按钮都不许出现** —— 那边没有窗口可以关,
 *  按下去只会是"点了没反应"。
 *  地址标记在第一帧就确定，不依赖 preload API 的调用时机。 */
export function inDesktopShell(win: unknown = globalThis): boolean {
  const w = win as { location?: { search?: string } } | null;
  const [key, value] = SHELL_MARK.split("=");
  // 用 URLSearchParams 而不是 `search.includes(SHELL_MARK)`:子串匹配会让
  // `?noshell=1` 假命中(判据 s-w2c)。
  return new URLSearchParams(w?.location?.search ?? "").get(key) === value;
}
