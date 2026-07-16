// 项目级对话(track opendesign-project-thread)—— 项目→会话映射的纯逻辑层。
// 每个项目一条「工作对话」:映射存 localStorage(本机;丢=重开新对话,PKB 零损失)。
// 本文件不碰 DOM/storage,oracle 直测(tests/test_project_thread.mjs);
// 读写 localStorage 在 App 层。

export type ThreadMap = Record<string, string>; // projectKey → chat_id

/** localStorage 键。改名=所有用户丢映射(退化为全部重开新对话),oracle 锁死。 */
export const THREADS_STORAGE_KEY = "odw.projectThreads";

/** 容错解析 localStorage 原文:坏 JSON/非对象 → 空表;非 string 值剔除。 */
export function loadThreadMap(raw: string | null): ThreadMap {
  if (!raw) return {};
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return {};
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) return {};
  const out: ThreadMap = {};
  for (const [k, v] of Object.entries(parsed)) {
    if (typeof v === "string" && v) out[k] = v;
  }
  return out;
}

export function threadFor(map: ThreadMap, project: string): string | null {
  return map[project] ?? null;
}

/** immutable:返回新表,原表不动(React state 直接换引用)。 */
export function withThread(map: ThreadMap, project: string, chatId: string): ThreadMap {
  return { ...map, [project]: chatId };
}

export function withoutThread(map: ThreadMap, project: string): ThreadMap {
  const { [project]: _drop, ...rest } = map;
  return rest;
}

/**
 * 侧栏历史行的项目小标:sessionKey(`websocket:<chat_id>`)→ 项目显示名。
 * 显示名从项目列表取(depth2 的 `组:名` key 显示纯名);项目已不在列表
 * (被删/改名后映射残留)→ 回落 key 本身,标签仍可读。
 */
export function sessionLabels(
  map: ThreadMap,
  projects: ReadonlyArray<{ key: string; name?: string }>,
): Record<string, string> {
  const nameOf = new Map(projects.map((p) => [p.key, p.name || p.key]));
  const out: Record<string, string> = {};
  for (const [project, chatId] of Object.entries(map)) {
    out[`websocket:${chatId}`] = nameOf.get(project) ?? project;
  }
  return out;
}

/**
 * 项目会话首条消息的前缀 —— 与 AGENTS.md「【当前项目:X】」规则同源的单一真相源。
 * 对用户可见(消息气泡里能看到),诚实透明。
 */
export function projectPrefix(name: string): string {
  return `【当前项目:${name}】`;
}
