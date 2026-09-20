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
  release_url?: string | null;
  auto_update?: {
    eligible?: boolean;
    why_not?: string | null;
    recent_failure?: boolean;
  } | null;
};

export type UpdateState = "idle" | "checking" | "done";
export type ApplyState = "idle" | "applying" | "done";
export type ApplyResult = {
  ok: boolean;
  stage?: string | null;
  error?: string | null;
  latest?: string | null;
} | null;

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
// setext 标题的下划线(标题写在上一行,下一行整行是 === 或 ---)与分隔线。
// 🔴 第三轮评审 F1:原来只认 ATX(`# 标题`)⇒ setext 写法的标题被当正文印给业主,
//    而正文以 `---` 开头时界面上直接印一串横杠,还把"去发布页 ›"那句兜底顶掉。
//    和 submimo 补充 1 治的是同一种病,只是形态不同。
const SETEXT_UNDERLINE = /^\s*(?:=+|-+)\s*$/;
const HORIZONTAL_RULE = /^\s*([-*_=])\s*(?:\1\s*){2,}$/;
// 列表项的记号。setext 的标题必须是**段落**,而列表不是段落 ——
// GitHub 把 `- 要点` 后面紧跟的 `---` 渲染成"列表项 + 分隔线",不是标题(判据 u25)。
const LIST_ITEM = /^\s*(?:[-*+]\s|\d+[.)]\s)/;

/** 哪些行属于 setext 标题(**标题那几行 + 下划线那一行**,全都要跳)。
 *
 * 🔴 第二刀开工时补的三条(第四轮 panel 的 LOW,第一刀判"接受不改"):
 * 原来的写法是**每行各自问一句"我的下一行是不是下划线"**,于是同一个根子长出三种病:
 *   u23 管不到下划线**自己** —— `HORIZONTAL_RULE` 要求"首字符 + 至少 2 个同样的",
 *       `==` / `--` 这种两字符的下划线漏网,标题跳掉之后它自己成了"第一句有意义的话";
 *   u24 管不到标题有**好几行** —— setext 的标题是下划线上面**那一整段**,只跳最后一行,
 *       前半截照印给业主;
 *   u25 **误伤列表** —— `- 要点` 的下一行恰好是 `---` 时,业主最想看的那条要点被吞掉。
 *
 * 所以改成按**段落**看:先找下划线,再往回收它上面那一整段连续非空行。
 * 这样三条同时消失 —— 因为它们本来就是一个 bug 的三种形态。
 */
function setextRows(rows: string[]): Set<number> {
  const skip = new Set<number>();
  for (let i = 0; i < rows.length; i++) {
    if (!SETEXT_UNDERLINE.test(rows[i])) continue;
    // 往回收:下划线上面那段连续非空行。
    let start = i;
    while (start > 0 && rows[start - 1].trim() !== "") start--;
    // ⚠️ 这里曾经有一句 `if (start === i) continue;`(上面没段落就当分隔线放过)。
    //    **删掉了,而且是变异测试逼出来的**:m4 把它去掉,24 条判据一条都没红 ⇒
    //    我给它写的理由("正文以 `---` 开头那一路走的就是这里")是**假的** ——
    //    `---` 本来就被 HORIZONTAL_RULE 接住,跟这句没关系。
    //    真去量了一遍才发现它不只是多余,是**有害**:开头是两字符的 `==` / `--` 时,
    //    它让那一行漏到正文里印给业主(u23 那个 bug 换了个位置而已)。判据 u26 钉住。
    //    留这段话是因为下一个人很可能想把这个"看起来该有的"豁免加回来。
    // 段落的第一行是列表项 ⇒ 它是列表不是段落,那根 `---` 是分隔线(判据 u25)。
    if (LIST_ITEM.test(rows[start])) continue;
    for (let r = start; r <= i; r++) skip.add(r);
  }
  return skip;
}

export function notesSummary(notes: string | null | undefined, max = 80): string {
  if (!notes) return "";
  const rows = notes.split(/\r?\n/);
  const setext = setextRows(rows);
  for (let i = 0; i < rows.length; i++) {
    const raw = rows[i];
    // 🔴 跳过的依据是"**它本来就是个 markdown 标题**",不是"它以某几个词开头"。
    //    原来按开头几个词判,会把「这一版修了一个导致白屏的 bug」这种**正文**也跳掉
    //    (submimo 第二轮补充 1)。标题没信息量,正文有 —— 分界线在记号上,不在词上。
    const isAtx = /^\s*#+\s/.test(raw);
    const isSetext = setext.has(i);
    const isRule = HORIZONTAL_RULE.test(raw);
    // 标题整行跳过,所以这里**不再剥 `#`** —— 剥它反而有害:
    // 一行 `#123 修复了…`(issue 编号,不是标题)会被剥成 `123 修复了…`。
    // 红检 v6 漏网把这条照了出来:那个替换在加了 isAtx 之后已是半死代码,
    // 而半死代码里还藏着一个真 bug。
    const line = raw
      .replace(/\*\*|__|`/g, "")     // 粗体 / 行内代码
      .trim();
    if (!line) continue;
    if (isAtx || isSetext || isRule) continue;
    return line.length > max ? line.slice(0, max - 1) + "…" : line;
  }
  return "";
}

/**
 * 「查不到更新」下面那一行小字:**为什么查不到**(判据 rl11,track opendesign-update-check-rate-limit)。
 *
 * 🔴 由来:业主 09-15 夜点「检查更新」一直「查不到更新」,真原因(GitHub 未登录限流 403)只在接口的 error 字段里,
 *    靠他开 PowerShell 才拿到,来回三轮。原因的人话由后端写(ds_update.explain),这里只决定显不显示。
 */
export function updateReason(s: { state: UpdateState; info: UpdateInfo | null }): string {
  if (s.state !== "done") return "";
  if (!s.info) return "软件后台没响应";
  return s.info.error ? s.info.error : "";
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

/** 是否给「更新」按钮:只有查更新成功、有版本号、有完整安装包时才放行。
 *
 * 🔴 **这个函数永远不许抛。** 它在 `Sidebar` 的渲染体里被调用
 * (`const showApply = canApply(updateInfo)`)—— 抛一次 React 就卸掉整棵树,
 * 业主看到的是**整页白**,而不是"没有更新按钮"。本项目 0.94、0.98 两次白屏
 * 都是同一个形状。判据 u35b/u35c 钉着这件事。
 *
 * 输入是**网络数据**,不是我们自己造的对象:后端 `ds_update.decide()` 那几个字段
 * 取自 `asset.get(...)`,取不到就是 `None` ⇒ 过 JSON 就是 `null`。
 * TypeScript 的类型只在编译期成立,**挡不住运行时进来的 null**。
 */
function nonEmptyText(v: unknown): boolean {
  return typeof v === "string" && v.trim().length > 0;
}

export function canApply(info: UpdateInfo | null): boolean {
  if (!info || typeof info !== "object") return false;
  if (info.error || info.update_available !== true || !nonEmptyText(info.latest)) return false;
  const asset = info.asset as Record<string, unknown> | null | undefined;
  if (!asset || typeof asset !== "object") return false;
  return (
    nonEmptyText(asset.name) &&
    nonEmptyText(asset.url) &&
    typeof asset.size === "number" &&
    asset.size > 0 &&
    nonEmptyText(asset.digest)
  );
}

function autoStatus(info: unknown): Record<string, unknown> | null {
  if (!info || typeof info !== "object" || Array.isArray(info)) return null;
  const auto = (info as Record<string, unknown>).auto_update;
  if (!auto || typeof auto !== "object" || Array.isArray(auto)) return null;
  return auto as Record<string, unknown>;
}

/** ⚠️ 2026-09-19 起**前端不再用它决定装不装**(track opendesign-startup-not-blocked-by-update)。
 *  该不该装由后端 `ds_update_startup.startup_decision` 看盘上的包答(大小 + sha256 都对得上才算)。
 *  这里留着是因为 test_update_ui 还在钉它的语义;**别再把它当成启动路径上的闸** ——
 *  上一次"以为还有人走的那条路其实没人走了",代价是回滚提示整条消失(判据 AC-C2)。
 */
export function shouldAutoUpdate(info: unknown): boolean {
  try {
    return canApply(info as UpdateInfo | null) && autoStatus(info)?.eligible === true;
  } catch {
    return false;
  }
}

export function autoRecentFailureText(info: unknown): string {
  try {
    if (!info || typeof info !== "object" || Array.isArray(info)) return "";
    const rec = info as Record<string, unknown>;
    const auto = autoStatus(info);
    if (rec.update_available !== true || auto?.why_not !== "attempted" ||
        auto.recent_failure !== true) return "";
    const version = nonEmptyText(rec.latest) ? String(rec.latest).trim() : "这个版本";
    return `上次自动更新 ${version} 没成功,这个版本不会再自动更新。你可以手动点「更新」。`;
  } catch {
    return "";
  }
}

export function autoWhyNotHint(info: unknown): string {
  try {
    if (!info || typeof info !== "object" || Array.isArray(info)) return "";
    const rec = info as Record<string, unknown>;
    const auto = autoStatus(info);
    if (rec.update_available !== true || auto?.why_not !== "attempted") return "";
    return "这个版本已经自动试过一次,不会再自动更新。你仍然可以手动点「更新」。";
  } catch {
    return "";
  }
}

/** 自动更新按钮那句话。started 只是开始切换,不能说成已经装好。 */
export function applyLabel(s: { state: ApplyState; result: ApplyResult }): string {
  if (s.state === "applying") return "正在更新,OpenDesign 会自动关掉再重新打开";
  if (!s.result) return "更新";
  if (s.result.ok) return "OpenDesign 会自动关掉再重新打开";
  if (s.result.stage === "no_update") return "没有可安装的新版";
  return "自动更新失败";
}

/** 自动更新失败后的解释。这里不把 stage/error 原样甩给业主。 */
export function applyHint(result: ApplyResult): string {
  if (!result || result.ok) return "";
  switch (result.stage) {
    case "no_update":
      return "这台机器已经没有可安装的新版。可以到发布页核对最新版本。";
    case "digest":
      return "安装包缺少安全校验信息,没有继续安装。可以去发布页手动下载。";
    case "download":
      return "安装包没能下载下来。可以到发布页手动下载。";
    case "verify":
      return "安全校验没通过,安装包可能不完整或被改过,没有继续安装。可以去发布页手动下载。";
    case "install":
      return "新版没有准备到可安装状态。可以到发布页手动下载。";
    case "newtree":
      return "新版文件没有放到可切换的位置。可以到发布页手动下载。";
    case "handoff":
      return "桌面程序没有接住这次自动切换。可以到发布页手动下载。";
    case "shell":
      return "旧窗口没能完成收尾。可以到发布页手动下载。";
    default:
      return "自动更新没能继续。可以到发布页手动下载。";
  }
}

export function autoFailureText(result: ApplyResult): string {
  try {
    if (!result || result.ok) return "";
    if (result.stage === "auto_skipped" || result.stage === "busy" ||
        result.stage === "no_update") return "";
    if (result.stage === "auto_unrecorded") {
      return "这次自动更新没有开始:没能记下本次尝试。可以稍后再试,也可以手动点「更新」。";
    }
    if (result.stage === null) {
      return "这次自动更新结果不确定。可以稍后再试,也可以手动点「更新」。";
    }
    const hint = applyHint(result);
    return `${hint} 这个版本不会再自动更新,你可以手动点「更新」。`;
  } catch {
    return "这次自动更新没有开始。可以手动点「更新」。";
  }
}

function isRecord(body: unknown): body is Record<string, unknown> {
  return typeof body === "object" && body !== null && !Array.isArray(body);
}

/** /api/update/apply 的 HTTP 200 也可能是业务失败,必须读 body.ok。 */
export function readApplyResponse(
  status: number,
  body: unknown,
): { ok: boolean; stage: string | null; error: string | null } {
  if (status !== 200 || !isRecord(body) || typeof body.ok !== "boolean") {
    return { ok: false, stage: null, error: null };
  }
  const stage = typeof body.stage === "string" && body.stage ? body.stage : null;
  const error = typeof body.error === "string" && body.error ? body.error : null;
  return { ok: body.ok === true && stage === "started", stage, error };
}

/** 点按钮前的防重入闸:正在更新时绝不再发第二个 apply 请求。 */
export function beginApply(state: ApplyState): boolean {
  return state !== "applying";
}

/** 启动时**只**问这一个接口 —— 它只读盘、不联网(track opendesign-startup-not-blocked-by-update)。
 *
 * 🔴 **不许在启动路径上换回 `/api/update/check`。** 那条要联网,实测最坏 20.1 秒,
 * 而这段时间整个工作区不渲染 —— 业主原话「每次打开都会弹出正在检测更新,这严重拖慢了开软件的速度」。
 * 判据 sg5 钉死这个常量。
 */
export const STARTUP_LOCAL_ENDPOINT = "/api/update/startup";

/** 启动最多等这么久。这是**本地读盘**,毫秒级;留 500ms 是给后端还没起来的那一瞬。
 *
 * 🔴 对照:改之前这里是 35000(前端给联网查更新留的余量)。
 * **把 35000 改小并不是修复** —— 只要启动还在联网,网一慢照样等。判据 sg1 + sg5 一起拦。
 */
export const STARTUP_LOCAL_TIMEOUT_MS = 500;

/** 后台备货用的端点:查到有新版就把它下下来,下一次打开软件才装。
 *
 * 🔴 **只许在进入工作区之后调**,绝不许出现在启动路径上 —— 它会下 46MB。
 */
export const STARTUP_PREPARE_ENDPOINT = "/api/update/prepare";

/** 进了工作区之后,等这么久才做第一次后台查更新与备货。
 *
 * 不许是 0:那等于换个地方接着抢启动资源。也别太久:业主开一会儿就关的话备不上货。
 * 🔴 **这个数只许有这一份**(判据 sg9)。它曾经在 App.tsx 和后端各写一份、互不知道,
 *    而后端那份根本没有调用方 —— 同一个数两处各写一份是本项目的老病。
 */
export const BACKGROUND_FIRST_CHECK_MS = 60_000;

/** 读懂启动接口的回应。**读不懂一律进工作区**,绝不卡住(判据 sg4/sg6)。
 *
 * 本项目已有四次"某个前置步骤没按预期返回 ⇒ 界面再也不往下走"的前科。
 */
/** 启动要装的是哪一版。**只在真要装的时候有值**;读不出来回 null(界面显示"新版本")。
 *
 * 🔴 为什么不从 updateInfo 拿:启动路径上**不查更新**(本单的全部意义),
 *    那个对象此刻必然是 null。版本就在启动回包里 —— 后端 startup_decision
 *    是逐字节校验过盘上那个包之后才带上它的。判据 sg8。
 */
export function startupVersion(resp: unknown): string | null {
  try {
    if (startupAction(resp) !== "install") return null;
    const v = (resp as Record<string, unknown>).version;
    return typeof v === "string" && v !== "" ? v : null;
  } catch {
    return null;
  }
}

export function startupAction(resp: unknown): "install" | "enter" {
  try {
    if (!resp || typeof resp !== "object" || Array.isArray(resp)) return "enter";
    return (resp as Record<string, unknown>).action === "install" ? "install" : "enter";
  } catch {
    return "enter";
  }
}
