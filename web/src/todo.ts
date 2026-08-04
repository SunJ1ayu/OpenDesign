// 待办页纯逻辑层(track p4 T3)—— 分组/排序不掺 DOM,oracle 直测
// (tests/test_workbench_p4.mjs)。数据形状 = /api/todos(ds_todo.collect 单一真相源)。

export type OpenItem = {
  project: string;
  line: number;
  raw: string;
  status: string; // 待确认 | 进行中
  cnum: number | null;
  date: string | null; // YYYY-MM-DD
  space: string | null; // 【空间】前缀(T1);旧行 null
  text: string;
  due: string | null; // 截止日 YYYY-MM-DD(track opendesign-todo-duedate);旧行 null
  // T4b:助手记录时给这一批起的名(ds_todo.collect 附;没有 `## 批次` 段的旧档案恒 null)。
  // 写进类型是为了后端改名时前端有编译期告警 —— 靠 `as` 强取会静默退回兜底分组。
  batch?: { id: string; title: string } | null;
};

export type StaleItem = { project: string; days: number; last: string };

export type ProjectGroup = { project: string; items: OpenItem[] };
export type DateGroup = { date: string | null; items: OpenItem[] };

/** 按项目分组,保持 collect 的遇见序(= projects/ 文件名序,稳定)。 */
export function groupByProject(open: OpenItem[]): ProjectGroup[] {
  const order: string[] = [];
  const map = new Map<string, OpenItem[]>();
  for (const it of open) {
    if (!map.has(it.project)) {
      map.set(it.project, []);
      order.push(it.project);
    }
    map.get(it.project)!.push(it);
  }
  return order.map((project) => ({ project, items: map.get(project)! }));
}

/** 按日期分批(todo-v3):日期倒序,无日期(null)恒沉底,组内保持传入相对序。
 * 一次贴入业主反馈 = 一批同日期变更,批次即层级(点头部展开/收起)。 */
export function groupByDate(items: OpenItem[]): DateGroup[] {
  const map = new Map<string | null, OpenItem[]>();
  for (const it of items) {
    const key = it.date;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(it);
  }
  const dated = [...map.keys()].filter((d): d is string => d !== null).sort((a, b) => b.localeCompare(a));
  const tail: (string | null)[] = map.has(null) ? [null] : [];
  return [...dated, ...tail].map((date) => ({ date, items: map.get(date)! }));
}

// sortByDateDesc 已删(track opendesign-todo-one-view):唯一调用者是被砍掉的
// 「按时间」看法。同一个问题不留第二个答案,更不留没人调用的死代码。

// staleDays(项目名 → 超期天数)已删除(track opendesign-todo-layout 收货)。
// track opendesign-todo-one-view 又进一步证伪了后端 stale 作为卡序/卡徽标指标:
// 项目卡改用 due/date 排序和 latestRecordAge;后端 stale 只留给无未办结条目的独立行。

// ── 待办「按项目」卡内排序(track opendesign-todo-one-view A)───────────────

/** 卡内两轨排序:有 due 的硬轨整体在前并按 due 升序;无 due 的软轨按记录日期
 * 升序(最久在前),date=null 沉底。稳定、纯函数、不改传入数组。 */
export function orderItems(items: OpenItem[], today: string): OpenItem[] {
  void today; // due 是 ISO 日期,due 升序本身已覆盖过期→今天→未来。
  return items
    .map((it, i) => ({ it, i }))
    .sort((a, b) => {
      const aDue = a.it.due !== null;
      const bDue = b.it.due !== null;
      if (aDue !== bDue) return aDue ? -1 : 1;
      if (aDue && bDue && a.it.due !== b.it.due) {
        return (a.it.due as string).localeCompare(b.it.due as string);
      }
      const ad = a.it.date;
      const bd = b.it.date;
      if (ad !== bd) {
        if (ad === null) return 1;
        if (bd === null) return -1;
        return ad.localeCompare(bd);
      }
      return a.i - b.i;
    })
    .map((x) => x.it);
}

// ── 待办「按项目」卡内按空间分小节(track opendesign-frontend-p2-polish 修改单 G1)──

export type SpaceSection = { space: string | null; items: OpenItem[] };

/** 按空间**首现序**分组;无空间(null)条目归一个小节且**恒置末**(即使首现),
 * 组内保持传入相对序;空输入 = []。契约见 tests/test_todo_spaces.mjs。 */
export function spaceSections(items: OpenItem[]): SpaceSection[] {
  const order: (string | null)[] = [];
  const map = new Map<string | null, OpenItem[]>();
  for (const it of items) {
    if (!map.has(it.space)) {
      map.set(it.space, []);
      order.push(it.space);
    }
    map.get(it.space)!.push(it);
  }
  const named = order.filter((s): s is string => s !== null);
  const sections: SpaceSection[] = named.map((space) => ({ space, items: map.get(space)! }));
  if (map.has(null)) sections.push({ space: null, items: map.get(null)! });
  return sections;
}

// ── 行内编辑(track opendesign-todo-edit T6)──────────────────────────────────
// 纯逻辑层:编辑态草稿 → POST /api/changes/edit 的请求体装配。DOM/fetch 不在这里,
// 便于 mjs oracle 直测(tests/test_workbench_p4.mjs test 14)。后端 ds_tools.edit_change
// 是唯一写口径(名字闸/保格式/留痕全在核心);本层只负责"该不该发、发哪些字段"。

/** 四状态(与 ds_tools.STATUSES / ds_todo.STATUS_WORDS 同源)—— 状态点选用。 */
export const STATUSES = ["待确认", "进行中", "已完成", "已关闭"] as const;
export type Status = (typeof STATUSES)[number];

export function isValidStatus(s: string): s is Status {
  return (STATUSES as readonly string[]).includes(s);
}

/** 终态 = 离开 OPEN_STATUS(ds_todo.py)的两个:改到终态后该项从 /api/todos 消失,
 * 页面够不到 → 必须弹撤销 toast(A2)。非终态(待确认↔进行中)项仍在页面,无需 toast。 */
export function isTerminalStatus(s: string): boolean {
  return s === "已完成" || s === "已关闭";
}

/** 状态含义短语(A4)—— pill/快捷菜单的 title 与测试同源。用户定义:
 * 待确认=球在业主(等业主拍板);进行中=球在设计师(在做);已完成=做完;已关闭=作废/取消。 */
export const STATUS_HINT: Record<Status, string> = {
  待确认: "等业主确认",
  进行中: "我在做",
  已完成: "做完了",
  已关闭: "作废 / 取消",
};

/** 行内编辑草稿:三字段皆可选,未触碰的字段 undefined。 */
export type EditDraft = {
  status?: string; // 点选的新状态
  text?: string; // 编辑中的正文(未 trim)
  note?: string; // 备注输入(未 trim)
};

/** POST /api/changes/edit 请求体(仅含实际要改的字段;后端按缺省跳过)。 */
export type EditRequest = {
  project: string;
  cnum: number;
  new_status?: string;
  new_text?: string;
  note?: string;
};

// ── 批量改状态(track opendesign-todo-batch-space T1)────────────────────────
// 契约见 tests/test_todo_batch.mjs(off-limits):选中项 → 逐条 /api/changes/edit
// 请求体,跳过 cnum===null(残缺行不可寻址)与 status===newStatus(空操作),
// 保持传入相对序,newStatus 非法抛,纯函数不改入参。

export type BatchEditRequest = { project: string; cnum: number; new_status: Status };

/** 选中项 → 逐条批量改状态请求体(客户端串行发,复用既有 /api/changes/edit 写针孔)。 */
export function batchEditRequests(
  items: Pick<OpenItem, "project" | "cnum" | "status">[],
  newStatus: string,
): BatchEditRequest[] {
  if (!isValidStatus(newStatus)) {
    throw new Error(`非法目标状态: ${newStatus}`);
  }
  const out: BatchEditRequest[] = [];
  for (const it of items) {
    if (it.cnum === null) continue;
    if (it.status === newStatus) continue;
    out.push({ project: it.project, cnum: it.cnum, new_status: newStatus });
  }
  return out;
}

/**
 * 草稿 → 请求体。只放"真的变了且合法"的字段:
 *  - new_status:是合法状态且 ≠ 原状态;
 *  - new_text:trim 后非空且 ≠ 原正文(no-op 不发,免后端写 `原:X`==新值噪声);
 *  - note:trim 后非空**且 ≠ 原备注**(todo-ux2:编辑时备注预填,没动就不重写)。
 * cnum 缺失(残缺行)不可编辑 → null;都无有效改动 → null(无可提交)。
 * originalNote:编辑框预填的既有备注(缺省空串=新加备注场景,行为不变)。
 */
export function buildEditRequest(
  item: Pick<OpenItem, "project" | "cnum" | "status" | "text">,
  draft: EditDraft,
  originalNote = "",
): EditRequest | null {
  if (item.cnum === null) return null;
  const req: EditRequest = { project: item.project, cnum: item.cnum };
  let dirty = false;

  if (
    draft.status !== undefined &&
    isValidStatus(draft.status) &&
    draft.status !== item.status
  ) {
    req.new_status = draft.status;
    dirty = true;
  }
  if (draft.text !== undefined) {
    const t = draft.text.trim();
    if (t && t !== item.text) {
      req.new_text = t;
      dirty = true;
    }
  }
  if (draft.note !== undefined) {
    const n = draft.note.trim();
    if (n && n !== originalNote.trim()) {
      req.note = n;
      dirty = true;
    }
  }
  return dirty ? req : null;
}

// ── 截止日着色(track opendesign-todo-duedate)────────────────────────────────
// 契约见 tests/test_todo_duedate.mjs(off-limits):due=null→null;
// due<today→"overdue";==today→"today";>today→"upcoming"。due/today 均 "YYYY-MM-DD",
// 字符串字典序比较即可(ISO 日期格式下与日期序一致,无需 Date 解析)。
// 供变更行/待办行截止日着色复用,也是下一 track 日历/今日跟进的基础。
export type DueStatus = "overdue" | "today" | "upcoming" | null;

export function dueStatus(due: string | null, today: string): DueStatus {
  if (due === null) return null;
  if (due < today) return "overdue";
  if (due === today) return "today";
  return "upcoming";
}

// ── 「按项目」卡序 + 记录年龄 + 闲置项目(track opendesign-todo-one-view)────

export const STALE_AFTER_DAYS = 7;

export type ProjectCard = { project: string; items: OpenItem[] };

function dateToUtcDay(date: string): number {
  const [y, m, d] = date.split("-").map(Number);
  return Date.UTC(y, m - 1, d);
}

/** 今天 − 项目条目里最新记录日期;无日期=null;未来日期钳到 0。 */
export function latestRecordAge(items: OpenItem[], today: string): number | null {
  let latest: string | null = null;
  for (const it of items) {
    if (it.date !== null && (latest === null || it.date > latest)) latest = it.date;
  }
  if (latest === null) return null;
  const days = Math.floor((dateToUtcDay(today) - dateToUtcDay(latest)) / 86_400_000);
  return Math.max(0, days);
}

function projectUrgency(items: OpenItem[], today: string): { tier: number; earliestDue: string | null; oldestDate: string | null } {
  let tier = 3;
  let earliestDue: string | null = null;
  let oldestDate: string | null = null;
  for (const it of items) {
    const status = dueStatus(it.due, today);
    if (status !== null) {
      const itemTier = status === "overdue" ? 0 : status === "today" ? 1 : 2;
      tier = Math.min(tier, itemTier);
      if (earliestDue === null || (it.due as string) < earliestDue) earliestDue = it.due;
    } else if (it.date !== null && (oldestDate === null || it.date < oldestDate)) {
      oldestDate = it.date;
    }
  }
  return { tier, earliestDue, oldestDate };
}

/** 卡序。groups 原样带过(project/items 不改),不读旧 stale 入参。
 *
 * 排序键**分两支**(2026-08-04 补做评审时把这条写清楚,原来只在 commit message 里
 * 写成「档位 → 最早 due → 最老记录日期」,读起来像对所有卡都生效的三级链条,不是):
 *   有 due 的档(过期/今天/未来):档位 → 卡内最早 due → 传入序
 *   无 due 的档:                档位 → 卡内最老记录日期 → 传入序
 * `oldestDate` 只从**没有 due 的条目**里取,所以它天然只在无 due 那一档有意义。
 */
export function orderProjectCards(groups: ProjectGroup[], today: string): ProjectCard[] {
  return groups
    .map((g, i) => ({ project: g.project, items: g.items, ...projectUrgency(g.items, today), i }))
    .sort((a, b) => {
      if (a.tier !== b.tier) return a.tier - b.tier;
      if (a.tier < 3 && a.earliestDue !== b.earliestDue) {
        if (a.earliestDue === null) return 1;
        if (b.earliestDue === null) return -1;
        return a.earliestDue.localeCompare(b.earliestDue);
      }
      if (a.tier === 3 && a.oldestDate !== b.oldestDate) {
        if (a.oldestDate === null) return 1;
        if (b.oldestDate === null) return -1;
        return a.oldestDate.localeCompare(b.oldestDate);
      }
      return a.i - b.i;
    })
    .map(({ project, items }) => ({ project, items }));
}

/** 闲置项目 = 全部项目 − 有卡的 − 已在「档案 N 天没更新」独立行报过的。保持 allKeys 传入序。 */
export function idleProjectKeys(allKeys: string[], cardedKeys: string[], staleKeys: string[]): string[] {
  const carded = new Set(cardedKeys);
  const stale = new Set(staleKeys);
  return allKeys.filter((k) => !carded.has(k) && !stale.has(k));
}
