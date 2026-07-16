// track opendesign-completed-items oracle:项目工作区变更列 计数 + 筛选分类 纯逻辑。
// 跑法:node --test tests/test_completed_items.mjs(Node 22+,原生 strip-types)
//
// red-check(commit message 附结果):
//   把 DONE_SET 改成只含 已完成 → test_counts_aggregate / test_filter_done 变红
//   把 filterChanges 的 done 分支删掉(fallthrough 到精确匹配)→ test_filter_done 变红
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  changeCounts,
  filterChanges,
  OPEN_SET,
  DONE_SET,
  PROGRESS_ORDER,
} from "../web/src/workspace/changes.ts";

const ch = (status) => ({ status, cnum: 1, text: "x", date: null, space: null, source: null });

const sample = [
  ch("待确认"),
  ch("进行中"), ch("进行中"),
  ch("已完成"), ch("已完成"), ch("已完成"), ch("已完成"), ch("已完成"),
  ch("已关闭"),
];

// ---- 计数 ----------------------------------------------------------------

test("changeCounts:各态计数 + 未办结/已办结聚合", () => {
  const c = changeCounts(sample);
  assert.equal(c.待确认, 1);
  assert.equal(c.进行中, 2);
  assert.equal(c.已完成, 5);
  assert.equal(c.已关闭, 1);
  assert.equal(c.open, 3); // 待确认 + 进行中
  assert.equal(c.done, 6); // 已完成 + 已关闭 —— red-check:DONE_SET 缺 已关闭 → 变 5
  assert.equal(c.all, 9);
});

test("changeCounts:null/空 安全", () => {
  assert.equal(changeCounts(null).all, 0);
  assert.equal(changeCounts([]).done, 0);
});

test("changeCounts:未知状态只进 all,不进 open/done", () => {
  const c = changeCounts([ch("待确认"), ch("草稿")]);
  assert.equal(c.all, 2);
  assert.equal(c.open, 1);
  assert.equal(c.done, 0);
});

test("open 与 done 聚合互补:合计 ≤ all,已知态不重不漏", () => {
  const c = changeCounts(sample);
  assert.equal(c.open + c.done, c.all); // 本样例全是已知态
});

// ---- 筛选 ----------------------------------------------------------------

test("filterChanges done:只留 已完成 + 已关闭,保序", () => {
  const got = filterChanges(sample, "done").map((c) => c.status);
  assert.deepEqual(got, ["已完成", "已完成", "已完成", "已完成", "已完成", "已关闭"]);
});

test("filterChanges open:只留 待确认 + 进行中", () => {
  const got = filterChanges(sample, "open").map((c) => c.status);
  assert.deepEqual(got, ["待确认", "进行中", "进行中"]);
});

test("filterChanges all:原样返回,保序", () => {
  assert.equal(filterChanges(sample, "all").length, sample.length);
});

test("filterChanges 精确单态:待确认 / 进行中", () => {
  assert.equal(filterChanges(sample, "待确认").length, 1);
  assert.equal(filterChanges(sample, "进行中").length, 2);
});

test("filterChanges:null 安全", () => {
  assert.deepEqual(filterChanges(null, "done"), []);
});

// ---- 常量契约 ------------------------------------------------------------

test("OPEN_SET / DONE_SET 无交集,并起来 = 四态", () => {
  for (const s of OPEN_SET) assert.ok(!DONE_SET.has(s));
  const all = new Set([...OPEN_SET, ...DONE_SET]);
  assert.deepEqual([...all].sort(), ["已完成", "已关闭", "待确认", "进行中"].sort());
});

test("PROGRESS_ORDER = 球在业主→设计师→完成→作废", () => {
  assert.deepEqual(PROGRESS_ORDER, ["待确认", "进行中", "已完成", "已关闭"]);
});
