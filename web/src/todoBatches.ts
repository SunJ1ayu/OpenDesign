// 待办「按时间」批次的纯逻辑(track opendesign-due-picker T4a):人话标题 + 折叠规则。
// 判据:tests/test_todo_batches.mjs(纯函数)+ tests/e2e/todo_batches.e2e.mjs(真浏览器)。
//
// 用户拍板的规则:1~2 条不折;≥3 条默认折起;**有过了截止日的自动展开**(急压过整洁);
// 折叠状态落盘(待办页原来的 toggled 是 useState、刷新即忘)。
// 标题**永不空白** —— 助手起名是 T4b,本单先把兜底做出来:「第一条内容 等 N 条」。

import type { DateGroup, OpenItem } from "./todo.ts";
import { dueStatus, groupByDate } from "./todo.ts";
import { loadBoolPrefs, type BoolPrefs } from "./boolPrefs.ts";

export { loadBoolPrefs };
export type { BoolPrefs };

/** localStorage 键。改名 = 所有人的折叠状态丢一次,oracle 锁死。 */
export const TODO_BATCH_STORAGE_KEY = "ds.todo.batchOpen";

/** 标题里首条内容最多留几个字,超了截断加省略号。批次头是一行小字,长了会挤掉条数。 */
export const BATCH_TITLE_MAX = 14;

/** 内容空白的条目(档案里手写坏行)在标题里的替身 —— 宁可写"未命名"也不留空。 */
export const UNNAMED_ITEM_LABEL = "未命名";

/** 折叠状态的持久化键。与视图 scope 绑:按时间/按项目各存各的,同一天不串。
 * 无日期批次走 "@none",不能塌成 undefined(否则所有"未标注日期"共用一个键)。
 * 格式与 TodoPage 原有的 toggled 键一致,不另起第二套写法。
 * batchId(T4b)可选:同一天的两个命名批次必须拿到不同的键,否则收一个另一个跟着收;
 * **不传时逐字节等于 T4a 的老键**(向后兼容,已存的折叠状态不作废)。 */
export function batchKey(scope: string, date: string | null, batchId: string | null = null): string {
  const base = `${scope}|${date ?? "@none"}`;
  return batchId ? `${base}|${batchId}` : base;
}

/** 一批的身份(后端 ds_todo 附在每条待办上;没有 `## 批次` 段的旧档案恒为 null)。 */
export type ItemBatch = { id: string; title: string } | null;

/** 一组待办 = 一次记录动作(T4b)或一天里所有没被命名的条目(id=null)。
 * foldId = 折叠偏好的锚:**带项目名 + 只取区间起点**。
 *   · 带项目:C 编号是每个项目各自从 1 起编的(ds_tools._max_change_num 只扫单文件),
 *     而「按时间」视图跨项目 —— 不带项目名,两个项目同日的 C1-C2 会撞成一组/一把键。
 *   · 只取起点:助手往这批再记一条,区间会从 C1-C2 延成 C1-C3;键若跟着变,
 *     用户刚点开的那批会悄悄合上(≥3 条默认收起)。 */
export type BatchGroup = {
  date: string | null;
  id: string | null;
  title: string | null;
  foldId: string | null;
  items: OpenItem[];
};

/** 按(日期, 项目, 批次)分组。日期序沿用 groupByDate(倒序、无日期沉底);
 * 同一天里各命名批次按首次出现序在前,**没有名字的合成一组垫在该日期末尾**
 * (它们是零散记录,不该插在成批的中间;这一组沿用 T4a 的跨项目日期语义)。
 * 组内保持传入相对序,一条都不丢。 */
export function groupByBatch(items: OpenItem[]): BatchGroup[] {
  const out: BatchGroup[] = [];
  for (const dg of groupByDate(items)) {
    const named = new Map<string, BatchGroup>();
    const loose: OpenItem[] = [];
    for (const it of dg.items) {
      const b = it.batch ?? null;
      if (!b) {
        loose.push(it);
        continue;
      }
      const key = `${it.project}|${b.id}`; // 项目维度不可省,见 foldId 注释
      let g = named.get(key);
      if (!g) {
        g = {
          date: dg.date,
          id: b.id,
          title: b.title,
          foldId: `${it.project}|${b.id.split("-")[0]}`,
          items: [],
        };
        named.set(key, g);
        out.push(g);
      }
      g.items.push(it);
    }
    if (loose.length) {
      out.push({ date: dg.date, id: null, title: null, foldId: null, items: loose });
    }
  }
  return out;
}

/** 组标题:助手起的名优先(同样截断、同样带「等 N 条」),没有就走 T4a 兜底。 */
export function groupHeading(group: BatchGroup): string {
  if (!group.title) return batchTitle(group.items);
  const head = group.title.length > BATCH_TITLE_MAX
    ? group.title.slice(0, BATCH_TITLE_MAX) + "…"
    : group.title;
  return group.items.length <= 1 ? head : `${head} 等 ${group.items.length} 条`;
}

/** 一批的标题。1 条 = 那条内容本身;≥2 条 = 「首条内容 等 N 条」。
 * 首条内容过长截断加省略号;空白内容退回「未命名」。**任何输入都不返回空串** ——
 * 空标题会让批次头看起来没东西可点,折叠控件形同消失。 */
export function batchTitle(items: OpenItem[]): string {
  if (items.length === 0) return UNNAMED_ITEM_LABEL;
  const raw = (items[0]?.text ?? "").trim();
  const head = raw === ""
    ? UNNAMED_ITEM_LABEL
    : raw.length > BATCH_TITLE_MAX
      ? raw.slice(0, BATCH_TITLE_MAX) + "…"
      : raw;
  return items.length === 1 ? head : `${head} 等 ${items.length} 条`;
}

/** 这批现在开着吗。**显式偏好压过一切**:用户点收了就得收着,过期也不许把它顶开
 * —— 否则那个折叠键就成了死键(T3 教训:自动展开写成压过用户 = 点了没反应)。
 * 没存过偏好时:含过期条目 → 展开(急压过整洁);否则 ≤2 条展开 / ≥3 条收起。
 * 过期判定复用 todo.ts 的 dueStatus,不自造第二份日期比较。 */
export function isBatchOpen(
  batch: DateGroup | BatchGroup,
  prefs: BoolPrefs,
  today: string,
  scope = "@time",
): boolean {
  const saved = prefs[batchKey(scope, batch.date, (batch as BatchGroup).foldId ?? null)];
  if (typeof saved === "boolean") return saved;
  if (batch.items.some((it) => dueStatus(it.due, today) === "overdue")) return true;
  return batch.items.length <= 2;
}
