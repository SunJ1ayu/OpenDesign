// 项目工作区变更列的纯逻辑层(track opendesign-completed-items C1)——
// 计数/筛选分类不掺 DOM,oracle 直测(tests/test_completed_items.mjs)。
// 数据形状 = /api/changes(Change[]),status ∈ 待确认/进行中/已完成/已关闭。

export type ChangeLike = { status: string };

// 四个真实状态(账本词表);进度一览按这四个键取计数。
export type StatusKey = "待确认" | "进行中" | "已完成" | "已关闭";

export type Filter = "open" | "待确认" | "进行中" | "done" | "all";

// 未办结 = 待确认 + 进行中(球还在场上);已办结 = 已完成 + 已关闭(做完/作废,都"翻篇了")。
// 两个聚合集互补:一条变更非未办结即已办结,不重不漏(未知状态归 all 但两集都不认领)。
export const OPEN_SET: ReadonlySet<string> = new Set(["待确认", "进行中"]);
export const DONE_SET: ReadonlySet<string> = new Set(["已完成", "已关闭"]);

// 进度一览的展示序(球在业主→球在设计师→做完→作废),与 AGENTS.md 状态语义同序。
export const PROGRESS_ORDER: readonly StatusKey[] = ["待确认", "进行中", "已完成", "已关闭"];

export type ChangeCounts = Record<StatusKey, number> & {
  open: number; // 待确认 + 进行中
  done: number; // 已完成 + 已关闭
  all: number; // 全部(含未知状态)
};

/** 各状态计数 + 未办结/已办结/全部聚合。一遍扫描;未知状态只进 all。 */
export function changeCounts(changes: ChangeLike[] | null): ChangeCounts {
  const list = changes ?? [];
  const c: ChangeCounts = {
    待确认: 0, 进行中: 0, 已完成: 0, 已关闭: 0, open: 0, done: 0, all: list.length,
  };
  for (const it of list) {
    if (it.status === "待确认") c.待确认++;
    else if (it.status === "进行中") c.进行中++;
    else if (it.status === "已完成") c.已完成++;
    else if (it.status === "已关闭") c.已关闭++;
    if (OPEN_SET.has(it.status)) c.open++;
    else if (DONE_SET.has(it.status)) c.done++;
  }
  return c;
}

/** 按筛选取子集,保持原序。all=全部;open/done=聚合集;待确认/进行中=精确单态。 */
export function filterChanges<T extends ChangeLike>(changes: T[] | null, filter: Filter): T[] {
  const list = changes ?? [];
  if (filter === "all") return list;
  if (filter === "open") return list.filter((c) => OPEN_SET.has(c.status));
  if (filter === "done") return list.filter((c) => DONE_SET.has(c.status));
  return list.filter((c) => c.status === filter);
}
