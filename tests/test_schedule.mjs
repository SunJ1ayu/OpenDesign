// track opendesign-todo-rail oracle:待办页右栏(日程月历 + 需要今天跟进)的纯逻辑层。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// 三个纯函数(新文件 web/src/schedule.ts):
//   monthGrid(year, month) —— 迷你月历网格。周一起始(表头 一二三四五六日),
//     恒 6 行 × 7 列 = 42 格铺满,前后补邻月日期并标 inMonth=false。
//   dueDates(items) —— 有到期事项的日期(去重、升序)。**不做分类**:红/琥珀由既有
//     todo.ts::dueStatus(date, today) 判,同一个问题不留第二个答案。
//   followUpItems(items, today) —— 「需要今天跟进」= 只取 超期 + 今天到期;
//     排序 = 超期在前且越久越前(due 升序),然后今天到期;同 due 保持传入序(稳定)。
//
// 跑法:node --test tests/test_schedule.mjs(Node 22+,原生 strip-types)
// red-check:实现前 web/src/schedule.ts 不存在,本文件整体红。
import { test } from "node:test";
import assert from "node:assert/strict";
import { dueDates, followUpItems, monthGrid } from "../web/src/schedule.ts";

const it = (cnum, due, extra = {}) => ({
  project: "翡翠湾-1801", line: cnum, raw: "", status: "待确认",
  cnum, date: "2026-07-01", space: "主卧", text: `t${cnum}`, due, ...extra,
});

// ── monthGrid ───────────────────────────────────────────────────────────────

test("monthGrid:恒 42 格(6 行 × 7 列)", () => {
  for (const [y, m] of [[2026, 7], [2026, 2], [2026, 8], [2024, 2]]) {
    assert.equal(monthGrid(y, m).length, 42, `${y}-${m} 应 42 格`);
  }
});

test("monthGrid:周一起始——首格是包含 1 号那周的周一", () => {
  // 2026-07-01 是周三 → 该周周一 = 2026-06-29
  const g = monthGrid(2026, 7);
  assert.equal(g[0].date, "2026-06-29");
  assert.equal(g[0].inMonth, false);
});

test("monthGrid:本月日期连续且 inMonth=true,邻月 inMonth=false", () => {
  const g = monthGrid(2026, 7);
  const inM = g.filter((c) => c.inMonth).map((c) => c.date);
  assert.equal(inM.length, 31, "7 月 31 天");
  assert.equal(inM[0], "2026-07-01");
  assert.equal(inM[30], "2026-07-31");
  assert.ok(g.filter((c) => !c.inMonth).length === 11, "前后补 11 格邻月");
});

test("monthGrid:尾部补到 42 格(跨到下月)", () => {
  const g = monthGrid(2026, 7);
  assert.equal(g[41].date, "2026-08-09"); // 6-29 起第 42 天
  assert.equal(g[41].inMonth, false);
});

test("monthGrid:1 号正好是周一时不补前导格", () => {
  // 2026-06-01 是周一
  const g = monthGrid(2026, 6);
  assert.equal(g[0].date, "2026-06-01");
  assert.equal(g[0].inMonth, true);
});

test("monthGrid:闰年 2 月 29 天", () => {
  const inM = monthGrid(2024, 2).filter((c) => c.inMonth).map((c) => c.date);
  assert.equal(inM.length, 29);
  assert.equal(inM[28], "2024-02-29");
});

test("monthGrid:平年 2 月 28 天", () => {
  const inM = monthGrid(2026, 2).filter((c) => c.inMonth);
  assert.equal(inM.length, 28);
});

test("monthGrid:跨年——12 月尾格进次年 1 月", () => {
  const g = monthGrid(2026, 12);
  assert.ok(g.some((c) => c.date.startsWith("2027-01")), "尾部应出现 2027-01");
  const inM = g.filter((c) => c.inMonth);
  assert.equal(inM[inM.length - 1].date, "2026-12-31");
});

test("monthGrid:日期严格连续递增(无缺格无重复)", () => {
  const g = monthGrid(2026, 7);
  for (let i = 1; i < g.length; i++) {
    const prev = new Date(`${g[i - 1].date}T00:00:00Z`).getTime();
    const cur = new Date(`${g[i].date}T00:00:00Z`).getTime();
    assert.equal(cur - prev, 86400000, `第 ${i} 格应比前一格晚整一天`);
  }
});

// ── dueDates ────────────────────────────────────────────────────────────────

test("dueDates:去重 + 升序", () => {
  const got = dueDates([it(1, "2026-07-20"), it(2, "2026-07-15"), it(3, "2026-07-20")]);
  assert.deepEqual(got, ["2026-07-15", "2026-07-20"]);
});

test("dueDates:无 due 的条目不参与", () => {
  assert.deepEqual(dueDates([it(1, null), it(2, "2026-07-09"), it(3, null)]), ["2026-07-09"]);
});

test("dueDates:空输入 / 全无 due = []", () => {
  assert.deepEqual(dueDates([]), []);
  assert.deepEqual(dueDates([it(1, null)]), []);
});

test("dueDates:不改传入数组(无副作用)", () => {
  const input = [it(1, "2026-07-20"), it(2, "2026-07-15")];
  dueDates(input);
  assert.deepEqual(input.map((x) => x.cnum), [1, 2]);
});

// ── followUpItems ───────────────────────────────────────────────────────────

const TODAY = "2026-07-22";

test("followUpItems:只取超期 + 今天到期", () => {
  const got = followUpItems([
    it(1, "2026-07-15"), // 超期
    it(2, TODAY),        // 今天
    it(3, "2026-07-30"), // 未来 → 不取
    it(4, null),         // 无 due → 不取
  ], TODAY);
  assert.deepEqual(got.map((x) => x.cnum), [1, 2]);
});

test("followUpItems:超期在前,越久越前;今天到期垫后", () => {
  const got = followUpItems([
    it(1, TODAY), it(2, "2026-07-17"), it(3, "2026-07-15"),
  ], TODAY);
  assert.deepEqual(got.map((x) => x.cnum), [3, 2, 1]);
});

test("followUpItems:同 due 保持传入序(稳定)", () => {
  const got = followUpItems([it(7, "2026-07-15"), it(3, "2026-07-15")], TODAY);
  assert.deepEqual(got.map((x) => x.cnum), [7, 3]);
});

test("followUpItems:没有超期也没有今天到期 = []", () => {
  assert.deepEqual(followUpItems([it(1, "2026-07-30"), it(2, null)], TODAY), []);
  assert.deepEqual(followUpItems([], TODAY), []);
});

test("followUpItems:条目原样带过(同一引用)", () => {
  const a = it(1, "2026-07-15");
  assert.equal(followUpItems([a], TODAY)[0], a);
});

test("followUpItems:不改传入数组(无副作用)", () => {
  const input = [it(1, TODAY), it(2, "2026-07-15")];
  followUpItems(input, TODAY);
  assert.deepEqual(input.map((x) => x.cnum), [1, 2]);
});
