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
  /** 发布页地址 —— **由 GitHub 给的**(评审 F1),不是我们拿版本号拼的。 */
  release_url: string | null;
};

export type UpdateState = "idle" | "checking" | "done";

// 🔴 评审 F1(2026-09-07,subdeepseek 抓到、我复现确认):**地址不再由我们拼。**
//
// 原来这里拿 `latest` 拼 `…/tag/win-installer-${version}`。而我修 S1 时给版本号补了零
// (`1.0` → `1.0.0`),于是业主宣布 1.0、tag 打成 `win-installer-1.0` 的那一天,
// 拼出来的是 `win-installer-1.0.0` —— **认出来了,却给一个 404 的链接**。
// 现在地址由 GitHub 在 html_url 里给,这个函数只负责**验它**:
// 界面上那个链接是要业主去点的,所以后端给什么就渲染什么是不行的。
const RELEASE_URL_RE = /^https:\/\/github\.com\/SunJ1ayu\/OpenDesign\/releases\//;

/** 放行本仓 releases 下的 https 地址;别的一律 null。 */
export function safeReleaseUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  return RELEASE_URL_RE.test(url) ? url : null;
}

/** 本仓发布页 —— 编译期常量,永远打得开。 */
export const RELEASES_PAGE = "https://github.com/SunJ1ayu/OpenDesign/releases";

/** 业主要点的那个地址:验过就用它,验不过退回发布页。
 *
 * 🔴 评审 F-C:GitHub 在仓库改名/转 Org 之后会把 `html_url` 换成新 full_name,
 * 前缀闸会把它拦下 ⇒ 下载那一行**静默消失**,而"有新版"的蓝点还亮着 ——
 * 业主看见有新版,却没有任何地方可点。**闸掉一个可疑地址是对的,
 * 但不能因此把业主晾在那儿。**
 */
export function downloadUrl(url: string | null | undefined): string {
  return safeReleaseUrl(url) ?? RELEASES_PAGE;
}

/** 设置那一行要不要挂个"有新版"的记号。
 *
 * 🔴 评审 F2:那句"有新版"原来只出现在**默认收起来的**设置弹层里 ——
 * 规格写的是"软件告诉你",做出来是"你翻开菜单才看得到"。业主不会天天翻设置。
 */
export function hasUpdateBadge(info: { update_available: boolean } | null | undefined): boolean {
  return !!info && info.update_available === true;
}

/** 蓝点的悬停说明。
 *
 * 🔴 和 `updateLabel` 是**同一个组合**(有新版但后端没给版本号,评审 F-D):
 * 那边修了、这边原样拼 `${info?.latest}` ⇒ 悬停上去写着「有新版 null」。
 * 第三轮自审 MR-2 —— **一个 bug 只修一侧,就是造了一个新分叉**(判据 u19/u20 + e2e D)。
 */
export function badgeTitle(info: { latest?: string | null } | null | undefined): string {
  const v = info?.latest;
  return v ? `有新版 ${v}` : "有新版";
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
    // 🔴 跳过的依据是"**它本来就是个 markdown 标题**",不是"它以某几个词开头"。
    //    原来按开头几个词判,会把「这一版修了一个导致白屏的 bug」这种**正文**也跳掉
    //    (submimo 第二轮补充 1)。标题没信息量,正文有 —— 分界线在记号上,不在词上。
    const isHeading = /^\s*#+\s/.test(raw);
    // 标题整行跳过(上面 isHeading),所以这里**不再剥 `#`** —— 剥它反而有害:
    // 一行 `#123 修复了…`(issue 编号,不是标题)会被剥成 `123 修复了…`。
    // 红检 v6 漏网把这条照了出来:那个替换在加了 isHeading 之后已是半死代码,
    // 而半死代码里还藏着一个真 bug。
    const line = raw
      .replace(/\*\*|__|`/g, "")     // 粗体 / 行内代码
      .trim();
    if (!line) continue;
    if (isHeading) continue;
    return line.length > max ? line.slice(0, max - 1) + "…" : line;
  }
  return "";
}

export function updateLabel(
  s: { state: UpdateState; info: UpdateInfo | null; version?: string | null },
): string {
  if (s.state === "checking") return "检查中…";
  // 评审 F3:查完了却什么都没拿到(端点 403 那条路可达),**不许长得像"还没查过"** ——
  // 那正是本单在治的"安静地错"。只有 idle 才显示版本号。
  if (s.state === "done" && !s.info) return "查不到更新";
  if (s.state === "idle" || !s.info) {
    return s.version ? `ds-web v${s.version}` : "服务离线";
  }
  const info = s.info;
  // 顺序要紧:先问"查成了没有",再问"有没有新版"。
  // 反过来写的话,一次断网就会显示成"已是最新"(判据 u3 钉的就是这个次序)。
  if (info.error) return "查不到更新";
  if (info.update_available && info.latest) return `有新版 ${info.latest} ›`;
  // 评审 F-D:`update_available` 为真但没版本号时,原来会掉进下面那句 ——
  // 于是"有新版"的蓝点亮着,而同一屏上写着"已是最新"。今天后端产生不了这个组合,
  // 但这是个未来的回归绊线,不是理论洁癖。
  if (info.update_available) return "有新版 ›";
  return `已是最新 v${info.current}`;
}
