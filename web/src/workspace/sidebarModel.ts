// 侧栏「历史对话 + 项目」的纯逻辑(track opendesign-sidebar-history;oracle tests/test_sidebar_history.mjs)。
// 业主 09-25「直接方案一和方案二一起做吧」:
//   方案一 = 按时间:今天 / 昨天 / 更早 分段 + 显示更多、置顶区、改名;
//   方案二 = 按项目:每个项目下挂和它有关的对话(项目对话在前),碰过几个项目就在几个项目下都出现,没碰过的进「其他对话」。
// 置顶的只在置顶区出现一次(4c C10)。本文件不碰 DOM / 网络,Node 原生 strip-types 直接跑 ⇒ 只用可擦除的 TS 语法、不 import 运行时模块。

export type SessionLike = { key: string; title?: string; preview?: string; updated_at?: string };
export type ProjectLike = { key: string; name?: string };
export type DayLabel = "今天" | "昨天" | "更早";

/** 改名上限,与网关标题上限、后端 ds_sessions.TITLE_MAX 一致。 */
export const TITLE_MAX = 160;

const DAY_ORDER: DayLabel[] = ["今天", "昨天", "更早"];

function stamp(s: { updated_at?: string }): number {
  const t = s.updated_at ? Date.parse(s.updated_at) : NaN;
  return Number.isNaN(t) ? 0 : t;
}

/** 最近聊的在前(没时间的沉底)。不改原数组。 */
export function byRecent<T extends { updated_at?: string }>(list: readonly T[]): T[] {
  return [...list].sort((a, b) => stamp(b) - stamp(a));
}

/** 按本机日期分段(不是 24 小时滚动):今天 00:00 起 = 今天,昨天 00:00 起 = 昨天;没时间 / 坏时间 = 更早。 */
export function dayBucket(updatedAt: string | undefined, now: Date): DayLabel {
  const t = updatedAt ? Date.parse(updatedAt) : NaN;
  if (Number.isNaN(t)) return "更早";
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1).getTime();
  if (t >= today) return "今天";
  if (t >= yesterday) return "昨天";
  return "更早";
}

/**
 * 按时间视图:置顶的抽走,其余最近在前,切成 今天 / 昨天 / 更早;空段不出。
 * limit = 「显示更多」翻到第几条(先按时间排好再截,再分段)。
 */
export function timeSections<T extends SessionLike>(
  sessions: readonly T[], now: Date, pinned: readonly string[], limit?: number,
): { label: DayLabel; items: T[] }[] {
  const pin = new Set(pinned);
  let rest = byRecent(sessions.filter((s) => !pin.has(s.key)));
  if (limit !== undefined) rest = rest.slice(0, limit);
  const out = new Map<DayLabel, T[]>();
  for (const s of rest) {
    const d = dayBucket(s.updated_at, now);
    if (!out.has(d)) out.set(d, []);
    out.get(d)!.push(s);
  }
  return DAY_ORDER.filter((d) => out.has(d)).map((label) => ({ label, items: out.get(label)! }));
}

/** 行上显示的名字:改过的名字 > 自动名字 > 第一句预览 >「(未命名对话)」。 */
export function displayTitle(s: SessionLike, overrides: Readonly<Record<string, string>>): string {
  return overrides[s.key] || s.title || s.preview || "(未命名对话)";
}

/**
 * 一段对话碰过哪些项目(返回当前项目列表里的 key):
 *   ① 它是哪些项目的项目对话(前端既有映射 project → chat_id)—— 排最前;
 *   ② 后台从对话记录读出的项目名(ds_sessions.session_projects):先按 key 对,再按名字对(分组项目 key =「组:名」,
 *      助手常只写名字);同名的项目不止一个就对不上(不猜);
 *   删掉 / 不在列表里的忽略;不重复。
 */
export function sessionProjects(
  sessionKey: string,
  derived: Readonly<Record<string, readonly string[]>>,
  threadMap: Readonly<Record<string, string>>,
  projects: readonly ProjectLike[],
): string[] {
  const keys = new Set(projects.map((p) => p.key));
  const byName = new Map<string, string[]>();
  for (const p of projects) {
    const n = p.name || p.key;
    byName.set(n, [...(byName.get(n) ?? []), p.key]);
  }
  const out: string[] = [];
  const add = (k: string | undefined) => { if (k && keys.has(k) && !out.includes(k)) out.push(k); };
  for (const [project, chatId] of Object.entries(threadMap)) {
    if (`websocket:${chatId}` === sessionKey) add(project);
  }
  for (const n of derived[sessionKey] ?? []) {
    if (keys.has(n)) add(n);
    else {
      const hits = byName.get(n) ?? [];
      if (hits.length === 1) add(hits[0]);
    }
  }
  return out;
}

/**
 * 按项目视图:每个项目 ⇒ 它的对话(它自己的项目对话在最前,其余最近在前);没碰过项目的 ⇒ other(最近在前);
 * 置顶的全部抽走(只在置顶区出现一次)。没有对话的项目不出现在 byProject 里。
 */
export function projectView<T extends SessionLike>(
  sessions: readonly T[],
  projectsOf: (key: string) => readonly string[],
  pinned: readonly string[],
  threadKeys: ReadonlySet<string>,
): { byProject: Record<string, T[]>; other: T[] } {
  const pin = new Set(pinned);
  const byProject: Record<string, T[]> = {};
  const other: T[] = [];
  for (const s of byRecent(sessions)) {
    if (pin.has(s.key)) continue;
    const ps = projectsOf(s.key);
    if (ps.length === 0) {
      other.push(s);
      continue;
    }
    for (const p of ps) (byProject[p] ??= []).push(s);
  }
  for (const [p, list] of Object.entries(byProject)) {
    // 「它自己的项目对话」= 是项目对话、且排第一的项目就是 p(sessionProjects 把项目对话的项目排最前)
    const own = (s: T) => threadKeys.has(s.key) && projectsOf(s.key)[0] === p;
    byProject[p] = [...list.filter(own), ...list.filter((s) => !own(s))];
  }
  return { byProject, other };
}

/** 改名输入:去首尾空格;空 / 全空格 ⇒ null(界面当取消,起好的名字不能手一滑就没了);超长截到 160。 */
export function cleanRename(raw: string): string | null {
  const t = raw.trim();
  return t ? t.slice(0, TITLE_MAX) : null;
}

/** 按时间视图行上的项目小标:第一个(项目对话优先)+「+N」;没有 ⇒ null。 */
export function firstTag(projectKeys: readonly string[], nameOf: (key: string) => string): string | null {
  if (projectKeys.length === 0) return null;
  const first = nameOf(projectKeys[0]);
  return projectKeys.length > 1 ? `${first} +${projectKeys.length - 1}` : first;
}
