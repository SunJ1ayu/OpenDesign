// 待办页批次的纯逻辑。
// 判据:tests/test_todo_one_view.mjs 的「批次小标题」一节。
//
// 2026-08-01 track opendesign-todo-one-view:本文件原来服务于「按时间」看法
// (人话标题 + 折叠规则,T4a/T4b)。那个看法本单被砍掉,于是 groupByBatch /
// groupHeading / batchTitle / isBatchOpen / TODO_BATCH_STORAGE_KEY /
// UNNAMED_ITEM_LABEL **全部零生产调用者**,连同它们的判据一起删除 ——
// 本项目的规矩:同一个问题不留第二个答案,更不留没人调用还在被判据发合格证的代码
// (opendesign-todo-layout 收货时 staleDays 孤儿化是同一个先例)。
//
// 留下的是仍然活着的两样:batchKey(项目卡折叠键仍在用)与批次小标题。

import type { OpenItem } from "./todo.ts";
import { loadBoolPrefs, type BoolPrefs } from "./boolPrefs.ts";

export { loadBoolPrefs };
export type { BoolPrefs };

/** 标题最多留几个字,超了截断加省略号。小标题是一行小字,长了会挤掉正文。 */
export const BATCH_TITLE_MAX = 14;

/** 一批的身份(后端 ds_todo 附在每条待办上;没有 `## 批次` 段的旧档案恒为 null)。 */
export type ItemBatch = { id: string; title: string } | null;

/** 折叠状态的持久化键。与视图 scope 绑:按时间/按项目各存各的,同一天不串。
 * 无日期批次走 "@none",不能塌成 undefined(否则所有"未标注日期"共用一个键)。
 * 格式与 TodoPage 原有的 toggled 键一致,不另起第二套写法。
 * batchId(T4b)可选:同一天的两个命名批次必须拿到不同的键,否则收一个另一个跟着收;
 * **不传时逐字节等于 T4a 的老键**(向后兼容,已存的折叠状态不作废)。 */
export function batchKey(scope: string, date: string | null, batchId: string | null = null): string {
  const base = `${scope}|${date ?? "@none"}`;
  return batchId ? `${base}|${batchId}` : base;
}

/** 同一批的**第一条**给一行小标题;后续条目返回 null(不重复)。
 * **只有助手真起过名的批次才给标题** —— 没名字的老条目返回 null,否则满屏噪音。
 * 认的是批次 **id** 不是标题字面:两次沟通碰巧起同名,仍各自给标题。
 * prev = 排序后紧挨着的上一条(没有则传 null)。 */
export function batchCaption(item: OpenItem, prev: OpenItem | null): string | null {
  const b = item.batch ?? null;
  if (!b || !b.title) return null;
  const pb = prev?.batch ?? null;
  if (pb && pb.id === b.id) return null;
  return b.title.length > BATCH_TITLE_MAX
    ? b.title.slice(0, BATCH_TITLE_MAX) + "…"
    : b.title;
}
