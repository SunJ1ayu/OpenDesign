// track opendesign-todo-layout oracle:待办「按项目」视图的两个纯函数契约。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// orderProjectCards(groups, stale) —— I.7 卡序,稳定排序,四层键:
//   ① stale !== null 的整体在前;② 超期组内 days 降序;
//   ③ 非超期组内 items.length 降序;④ 全相等保持传入序。
//   返回 ProjectCard = { project, items, stale },project/items 原样带过。
// idleProjectKeys(allKeys, cardedKeys, staleKeys) —— 闲置项目 = 全部 − 有卡 − 已在
//   「⛑ N 天没动静」独立行报过的;保持 allKeys 传入序。
//
// 跑法:node --test tests/test_todo_layout.mjs(Node 22+,原生 strip-types)
// red-check:实现前 todo.ts 无这两个导出,本文件整体红。
import { test } from "node:test";
import assert from "node:assert/strict";
import { idleProjectKeys, orderProjectCards } from "../web/src/todo.ts";

// 造 n 条同项目的未办结条目(内容不重要,只有条数参与排序)
const items = (project, n) =>
  Array.from({ length: n }, (_, i) => ({
    project, line: i + 1, raw: "", status: "待确认",
    cnum: i + 1, date: null, space: null, text: `t${i}`, due: null,
  }));

const g = (project, n) => ({ project, items: items(project, n) });
const s = (project, days) => ({ project, days, last: "2026-07-01" });

// ── orderProjectCards ───────────────────────────────────────────────────────

test("orderProjectCards:超期卡整体排最前(即使未办结数更少)", () => {
  const got = orderProjectCards([g("A", 5), g("B", 1)], [s("B", 9)]);
  assert.deepEqual(got.map((c) => c.project), ["B", "A"]);
});

test("orderProjectCards:超期组内按天数降序", () => {
  const got = orderProjectCards(
    [g("A", 1), g("B", 1), g("C", 1)],
    [s("A", 8), s("B", 30), s("C", 15)],
  );
  assert.deepEqual(got.map((c) => c.project), ["B", "C", "A"]);
});

test("orderProjectCards:非超期组内按未办结数降序", () => {
  const got = orderProjectCards([g("A", 2), g("B", 7), g("C", 4)], []);
  assert.deepEqual(got.map((c) => c.project), ["B", "C", "A"]);
});

test("orderProjectCards:两组混合——超期(天数降序)在前,其余(条数降序)在后", () => {
  const got = orderProjectCards(
    [g("A", 9), g("B", 1), g("C", 3), g("D", 2)],
    [s("B", 12), s("D", 40)],
  );
  assert.deepEqual(got.map((c) => c.project), ["D", "B", "A", "C"]);
});

test("orderProjectCards:全平局保持传入序(稳定排序)", () => {
  const got = orderProjectCards([g("X", 3), g("Y", 3), g("Z", 3)], []);
  assert.deepEqual(got.map((c) => c.project), ["X", "Y", "Z"]);
});

test("orderProjectCards:同天数超期之间保持传入序(稳定排序)", () => {
  const got = orderProjectCards([g("P", 1), g("Q", 9)], [s("P", 10), s("Q", 10)]);
  assert.deepEqual(got.map((c) => c.project), ["P", "Q"]);
});

test("orderProjectCards:附 stale 天数,无超期为 null", () => {
  const got = orderProjectCards([g("A", 1), g("B", 1)], [s("A", 21)]);
  assert.deepEqual(got.map((c) => [c.project, c.stale]), [["A", 21], ["B", null]]);
});

test("orderProjectCards:items 原样带过(同一引用,不复制不重排组内)", () => {
  const gA = g("A", 3);
  const got = orderProjectCards([gA], []);
  assert.equal(got[0].items, gA.items);
  assert.deepEqual(got[0].items.map((i) => i.cnum), [1, 2, 3]);
});

test("orderProjectCards:不改传入数组(无副作用)", () => {
  const input = [g("A", 1), g("B", 5)];
  orderProjectCards(input, []);
  assert.deepEqual(input.map((x) => x.project), ["A", "B"]);
});

test("orderProjectCards:空输入 = []", () => {
  assert.deepEqual(orderProjectCards([], []), []);
  assert.deepEqual(orderProjectCards([], [s("A", 9)]), []);
});

test("orderProjectCards:stale 列表里有的项目没有卡——不凭空造卡", () => {
  const got = orderProjectCards([g("A", 1)], [s("A", 9), s("ZZ", 99)]);
  assert.deepEqual(got.map((c) => c.project), ["A"]);
});

// ── idleProjectKeys ─────────────────────────────────────────────────────────

test("idleProjectKeys:减掉有卡的项目", () => {
  assert.deepEqual(idleProjectKeys(["A", "B", "C"], ["B"], []), ["A", "C"]);
});

test("idleProjectKeys:减掉超期项目(已在独立行报过,不重复说)", () => {
  assert.deepEqual(idleProjectKeys(["A", "B", "C"], [], ["C"]), ["A", "B"]);
});

test("idleProjectKeys:两个减法同时生效", () => {
  assert.deepEqual(idleProjectKeys(["A", "B", "C", "D"], ["A"], ["C"]), ["B", "D"]);
});

test("idleProjectKeys:保持 allKeys 传入序(不排序)", () => {
  assert.deepEqual(idleProjectKeys(["Z", "M", "A"], [], []), ["Z", "M", "A"]);
});

test("idleProjectKeys:全被减完 = []", () => {
  assert.deepEqual(idleProjectKeys(["A", "B"], ["A"], ["B"]), []);
  assert.deepEqual(idleProjectKeys([], ["A"], ["B"]), []);
});

test("idleProjectKeys:既有卡又超期的项目只算减一次(不报错、不残留)", () => {
  assert.deepEqual(idleProjectKeys(["A", "B"], ["A"], ["A"]), ["B"]);
});
