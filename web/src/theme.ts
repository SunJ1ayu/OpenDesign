// 外观:深色(默认,照 ZCode Zai Dark)/ 浅色(原暖纸面)/ 跟随系统。
// 纯逻辑、零 React 依赖:判据 tests/test_theme.mjs 用 Node 直接跑。
//
// 生效方式:<html data-theme="dark|light">,app.css 里两套变量各一份。「跟随系统」不进 CSS,
// 这里按 prefers-color-scheme 解析成两者之一 —— 否则浅色那套变量要在媒体查询里再抄一遍。
// 开机第一帧由 index.html 里的内联脚本先设好(同一个 localStorage 键、同一套解析),免得浅色用户每次开软件先闪一下黑。

export type ThemePref = "dark" | "light" | "system";
export const THEME_KEY = "od-theme";
export const THEME_DEFAULT: ThemePref = "dark";

export function parseThemePref(raw: unknown): ThemePref {
  return raw === "light" || raw === "system" || raw === "dark" ? raw : THEME_DEFAULT;
}

export function resolveTheme(pref: ThemePref, systemDark: boolean): "dark" | "light" {
  if (pref === "system") return systemDark ? "dark" : "light";
  return pref;
}

type Win = {
  localStorage?: Storage;
  matchMedia?: (q: string) => MediaQueryList;
  document?: Document;
};

function systemDark(w: Win): boolean {
  try { return !!w.matchMedia?.("(prefers-color-scheme: dark)").matches; } catch { return true; }
}

export function loadThemePref(w: Win = globalThis as Win): ThemePref {
  try { return parseThemePref(w.localStorage?.getItem(THEME_KEY)); } catch { return THEME_DEFAULT; }
}

/** 记住并立刻生效。返回实际用上的那套。 */
export function applyTheme(pref: ThemePref, w: Win = globalThis as Win): "dark" | "light" {
  try { w.localStorage?.setItem(THEME_KEY, pref); } catch { /* 隐私模式:记不住就算了 */ }
  const eff = resolveTheme(pref, systemDark(w));
  w.document?.documentElement.setAttribute("data-theme", eff);
  return eff;
}

/** 「跟随系统」时,系统切了深浅要跟着变。返回取消监听。 */
export function watchSystemTheme(w: Win = globalThis as Win): () => void {
  const mq = w.matchMedia?.("(prefers-color-scheme: dark)");
  if (!mq) return () => {};
  const on = () => { if (loadThemePref(w) === "system") applyTheme("system", w); };
  mq.addEventListener?.("change", on);
  return () => mq.removeEventListener?.("change", on);
}
