// 待办「按时间」批次的纯逻辑(track opendesign-due-picker T4a):人话标题 + 折叠规则。
// 判据:tests/test_todo_batches.mjs(纯函数)+ tests/e2e/todo_batches.e2e.mjs(真浏览器)。
//
// 用户拍板的规则:1~2 条不折;≥3 条默认折起;**有过了截止日的自动展开**(急压过整洁);
// 折叠状态落盘(待办页原来的 toggled 是 useState、刷新即忘)。
// 标题**永不空白** —— 助手起名是 T4b,本单先把兜底做出来:「第一条内容 等 N 条」。

import type { DateGroup, OpenItem } from "./todo.ts";
import { dueStatus } from "./todo.ts";
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
 * 格式与 TodoPage 原有的 toggled 键一致,不另起第二套写法。 */
export function batchKey(scope: string, date: string | null): string {
  return `${scope}|${date ?? "@none"}`;
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
  batch: DateGroup,
  prefs: BoolPrefs,
  today: string,
  scope = "@time",
): boolean {
  const saved = prefs[batchKey(scope, batch.date)];
  if (typeof saved === "boolean") return saved;
  if (batch.items.some((it) => dueStatus(it.due, today) === "overdue")) return true;
  return batch.items.length <= 2;
}
