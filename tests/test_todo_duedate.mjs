// track opendesign-todo-duedate oracle:截止日相对今天的分类纯函数。
// 契约:dueStatus(due, today) —— due=null→null;due<today→"overdue";
//   ==today→"today";>today→"upcoming"。today/due 均 "YYYY-MM-DD"。
//   供变更行/待办行截止日着色,下一 track 日历/今日跟进复用。
// 跑法:node --test tests/test_todo_duedate.mjs(Node 22+ 原生 strip-types)
//
// red-check:实现前 todo.ts 无 dueStatus 导出,本文件整体红。
import { test } from "node:test";
import assert from "node:assert/strict";
import { dueStatus } from "../web/src/todo.ts";

const TODAY = "2026-07-22";

test("dueStatus:null due → null", () => {
  assert.equal(dueStatus(null, TODAY), null);
});

test("dueStatus:过去 → overdue", () => {
  assert.equal(dueStatus("2026-07-21", TODAY), "overdue");
  assert.equal(dueStatus("2026-01-01", TODAY), "overdue");
});

test("dueStatus:今天 → today", () => {
  assert.equal(dueStatus("2026-07-22", TODAY), "today");
});

test("dueStatus:将来 → upcoming", () => {
  assert.equal(dueStatus("2026-07-23", TODAY), "upcoming");
  assert.equal(dueStatus("2026-12-31", TODAY), "upcoming");
});
