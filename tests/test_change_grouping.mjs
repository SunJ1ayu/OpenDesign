// track opendesign-todo-batch-space oracle:单项目变更列的「按时间 / 按空间」分组纯函数。
// 进单个项目后,「项目」维度冗余 → 提供时间/空间两轴分组(切换在 ChangesColumn)。
// 语义与待办页 todo.ts 同口径,避免两处心智不一致:
//   groupByDate:按日期分组,**日期倒序**(YYYY-MM-DD 字符串序),无日期(null)组**恒置末**;
//   groupBySpace:按空间**首现序**分组,无空间(null)组**恒置末**;
//   两者组内均保持传入相对序;空输入 = []。
// 跑法:node --test tests/test_change_grouping.mjs(Node 22+ 原生 strip-types)
//
// red-check:实现前 changes.ts 无 groupByDate/groupBySpace 导出,本文件整体红。
import { test } from "node:test";
import assert from "node:assert/strict";
import { groupByDate, groupBySpace } from "../web/src/workspace/changes.ts";

const c = (cnum, date, space) => ({ cnum, date, space, status: "待确认", text: `c${cnum}` });

test("groupByDate:日期倒序,同日保持相对序", () => {
  const got = groupByDate([
    c(1, "2026-07-18", null), c(2, "2026-07-21", null), c(3, "2026-07-18", null),
  ]);
  assert.deepEqual(got.map((g) => g.date), ["2026-07-21", "2026-07-18"]);
  assert.deepEqual(got[1].items.map((x) => x.cnum), [1, 3]);
});

test("groupByDate:无日期组恒置末(即使首现)", () => {
  const got = groupByDate([
    c(1, null, null), c(2, "2026-07-20", null), c(3, null, null),
  ]);
  assert.deepEqual(got.map((g) => g.date), ["2026-07-20", null]);
  assert.deepEqual(got[1].items.map((x) => x.cnum), [1, 3]);
});

test("groupByDate:空输入 → []", () => {
  assert.deepEqual(groupByDate([]), []);
});

test("groupBySpace:按空间首现序,组内保持相对序", () => {
  const got = groupBySpace([
    c(1, null, "玄关"), c(2, null, "客厅"), c(3, null, "玄关"),
  ]);
  assert.deepEqual(got.map((g) => g.space), ["玄关", "客厅"]);
  assert.deepEqual(got[0].items.map((x) => x.cnum), [1, 3]);
});

test("groupBySpace:无空间组恒置末(即使首现)", () => {
  const got = groupBySpace([
    c(1, null, null), c(2, null, "玄关"), c(3, null, null),
  ]);
  assert.deepEqual(got.map((g) => g.space), ["玄关", null]);
  assert.deepEqual(got[1].items.map((x) => x.cnum), [1, 3]);
});

test("groupBySpace:空输入 → []", () => {
  assert.deepEqual(groupBySpace([]), []);
});

test("分组不改传入数组(纯函数)", () => {
  const input = [c(1, "2026-07-18", "玄关"), c(2, "2026-07-21", null)];
  const snap = JSON.parse(JSON.stringify(input));
  groupByDate(input);
  groupBySpace(input);
  assert.deepEqual(input, snap);
});
