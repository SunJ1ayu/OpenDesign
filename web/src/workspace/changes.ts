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

// ── 单项目变更列 时间/空间 分组(track opendesign-todo-batch-space T2)──────────
// 语义镜像 web/src/todo.ts 的 groupByDate/spaceSections(日期倒序·null 沉底 /
// 空间首现序·null 沉底,组内保持传入相对序),但基于 Change 形状独立实现,
// 不复用 todo.ts(design.md:blast radius 隔离)。契约见 tests/test_change_grouping.mjs(off-limits)。

export type DateGroupLike<T> = { date: string | null; items: T[] };
export type SpaceGroupLike<T> = { space: string | null; items: T[] };

type Dated = { date: string | null };
type Spaced = { space: string | null };

/** 按日期分组:日期倒序(字符串序),无日期(null)组恒置末,组内保持传入相对序。 */
export function groupByDate<T extends Dated>(items: T[]): DateGroupLike<T>[] {
  const map = new Map<string | null, T[]>();
  for (const it of items) {
    const key = it.date;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(it);
  }
  const dated = [...map.keys()].filter((d): d is string => d !== null).sort((a, b) => b.localeCompare(a));
  const tail: (string | null)[] = map.has(null) ? [null] : [];
  return [...dated, ...tail].map((date) => ({ date, items: map.get(date)! }));
}

/** 按空间分组:首现序,无空间(null)组恒置末,组内保持传入相对序。 */
export function groupBySpace<T extends Spaced>(items: T[]): SpaceGroupLike<T>[] {
  const order: (string | null)[] = [];
  const map = new Map<string | null, T[]>();
  for (const it of items) {
    if (!map.has(it.space)) {
      map.set(it.space, []);
      order.push(it.space);
    }
    map.get(it.space)!.push(it);
  }
  const named = order.filter((s): s is string => s !== null);
  const sections: SpaceGroupLike<T>[] = named.map((space) => ({ space, items: map.get(space)! }));
  if (map.has(null)) sections.push({ space: null, items: map.get(null)! });
  return sections;
}
