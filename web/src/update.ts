// 查更新那一行在界面上说什么(track opendesign-in-app-update,第一刀)。
//
// 这个文件只管**措辞**,不碰网络;拿数据的是 /api/update/check。
// 判据:tests/test_update_ui.mjs
//
// 🔴 这里唯一不能错的方向:**查不动的时候不许说「已是最新」**(判据 u3)。
//    那是把失败伪装成成功,业主会以为自己在最新版上,而他可能落后好几版。

export type UpdateInfo = {
  current: string;
  update_available: boolean;
  latest: string | null;
  asset: { name: string; url: string; size: number; digest: string | null } | null;
  notes: string;
  error: string | null;
};

export type UpdateState = "idle" | "checking" | "done";

const REPO = "SunJ1ayu/OpenDesign";

// 什么算版本号:**2~4 段数字**。单段不算(会撞上一堆随便的数字)。
// 🔴 这条正则必须和 bin/ds_update.py 的 _NUM 同口径 —— 原来这边收两段、那边只收三段,
//    两处对同一件事口径不一致(S1 自审抓到)。判据 u8 两侧一起钉。
const VERSION_RE = /^\d+(\.\d+){1,3}$/;

/** 发布页地址。版本号拼不出来时返回 null —— 宁可不给链接,也不给一个坏链接。 */
export function releasePageUrl(version: string | null | undefined): string | null {
  if (!version) return null;
  if (!VERSION_RE.test(version)) return null;
  return `https://github.com/${REPO}/releases/tag/win-installer-${version}`;
}

/** 自动查更新的开关键。默认**开**,只有业主显式关过才算关。 */
export const AUTO_CHECK_PREF = "update.autoCheck";

/** 要不要在打开软件时自动查一次。
 *
 * 🔴 这个开关存在的理由:这一单之前,这个软件唯一往外连的地方是业主自己配了 key 的
 * 大模型接口。查更新给它加了一个**无条件的**外部目的地(每次打开都发)。
 * 功能上没问题,但**业主的机器该业主做主** —— 给得起这个开关就该给。
 */
export function autoCheckEnabled(prefs: Record<string, boolean>): boolean {
  return prefs[AUTO_CHECK_PREF] !== false;
}

/** 更新说明取第一句有意义的话,洗掉 markdown 记号并截断。
 *
 * 后端把 release 正文整段带下来了。**取了就要用** —— 留一个"取了不显示"的字段
 * 等于假装做了这件事(S4 自审)。界面上只放得下一行,所以这里只取一行。
 */
export function notesSummary(notes: string | null | undefined, max = 80): string {
  if (!notes) return "";
  for (const raw of notes.split(/\r?\n/)) {
    const line = raw
      .replace(/^\s*#+\s*/, "")      // 标题记号
      .replace(/\*\*|__|`/g, "")     // 粗体 / 行内代码
      .trim();
    if (!line) continue;
    // 第一行常常是"这一版改了什么"这种小标题,没信息量 —— 跳过它,取下一行真内容。
    if (/^这一版|^更新内容|^改了什么/.test(line)) continue;
    return line.length > max ? line.slice(0, max - 1) + "…" : line;
  }
  return "";
}

export function updateLabel(
  s: { state: UpdateState; info: UpdateInfo | null; version?: string | null },
): string {
  if (s.state === "checking") return "检查中…";
  if (s.state === "idle" || !s.info) {
    return s.version ? `ds-web v${s.version}` : "服务离线";
  }
  const info = s.info;
  // 顺序要紧:先问"查成了没有",再问"有没有新版"。
  // 反过来写的话,一次断网就会显示成"已是最新"(判据 u3 钉的就是这个次序)。
  if (info.error) return "查不到更新";
  if (info.update_available && info.latest) return `有新版 ${info.latest} ›`;
  return `已是最新 v${info.current}`;
}
