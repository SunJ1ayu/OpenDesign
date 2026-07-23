// 待办页右栏(track opendesign-todo-rail T1)—— 日程月历 + 需要今天跟进的纯逻辑层。
// 契约见 tests/test_schedule.mjs(off-limits)。
//
// 关键第一性:圆点不发明新分类。红/琥珀直接用 todo.ts 既有的
// dueStatus(date, today) → overdue | today | upcoming;本文件只回答
// 「月历长什么样」「哪些日期有到期事项」「今天该跟进哪些条目」这三个纯派生问题。

import type { OpenItem } from "./todo";

export type CalCell = { date: string; inMonth: boolean };

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

function isoOf(utcMs: number): string {
  const d = new Date(utcMs);
  return `${d.getUTCFullYear()}-${pad2(d.getUTCMonth() + 1)}-${pad2(d.getUTCDate())}`;
}

/** 迷你月历网格:周一起始(表头 一二三四五六日),恒 6 行 × 7 列 = 42 格铺满,
 * 前后补邻月日期并标 inMonth=false。month 为 1-12(自然月份,非 JS 0-based)。 */
export function monthGrid(year: number, month: number): CalCell[] {
  const firstOfMonth = Date.UTC(year, month - 1, 1);
  const jsDow = new Date(firstOfMonth).getUTCDay(); // 0=Sun..6=Sat
  const isoDow = (jsDow + 6) % 7; // 0=Mon..6=Sun
  const gridStart = firstOfMonth - isoDow * 86400000;

  const cells: CalCell[] = [];
  for (let i = 0; i < 42; i++) {
    const t = gridStart + i * 86400000;
    const d = new Date(t);
    cells.push({
      date: isoOf(t),
      inMonth: d.getUTCFullYear() === year && d.getUTCMonth() + 1 === month,
    });
  }
  return cells;
}

/** 有到期事项的日期:去重、升序。不做分类——红/琥珀由 dueStatus 判,
 * 同一个问题不留第二个答案。 */
export function dueDates(items: OpenItem[]): string[] {
  const set = new Set<string>();
  for (const it of items) {
    if (it.due) set.add(it.due);
  }
  return [...set].sort();
}

/** 「需要今天跟进」= 只取 超期 + 今天到期;排序 = 超期在前且越久越前(due 升序),
 * 今天到期垫后(due 恒为选中集合里最大的一个);同 due 保持传入序(稳定)。 */
export function followUpItems(items: OpenItem[], today: string): OpenItem[] {
  return items
    .map((it, i) => ({ it, i }))
    .filter(({ it }) => it.due !== null && it.due <= today)
    .sort((a, b) => {
      const da = a.it.due as string;
      const db = b.it.due as string;
      if (da !== db) return da < db ? -1 : 1;
      return a.i - b.i;
    })
    .map((x) => x.it);
}
