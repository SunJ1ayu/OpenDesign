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

/** 发布页地址。版本号拼不出来时返回 null —— 宁可不给链接,也不给一个坏链接。 */
export function releasePageUrl(version: string | null | undefined): string | null {
  if (!version) return null;
  if (!/^\d+(\.\d+)*$/.test(version)) return null;
  return `https://github.com/${REPO}/releases/tag/win-installer-${version}`;
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
