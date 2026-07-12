// track p4 oracle:待办页分组/排序 + 搜索过滤/高亮 的纯逻辑层
// 跑法:node --test tests/test_workbench_p4.mjs(Node 22+,原生 strip-types)
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  groupByProject,
  groupBySpace,
  sortByDateDesc,
  staleDays,
} from "../web/src/todo.ts";
import { filterDocs, splitHighlight } from "../web/src/search.ts";

const item = (project, space, date, text, cnum = 1, status = "待确认") => ({
  project, line: 1, raw: "", status, cnum, date, space, text,
});

// ---- 待办分组 ----------------------------------------------------------

test("groupByProject:遇见序稳定,同项目聚一起", () => {
  const g = groupByProject([
    item("甲", "玄关", "2026-07-01", "a"),
    item("乙", null, "2026-07-02", "b"),
    item("甲", "客厅", "2026-07-03", "c"),
  ]);
  assert.deepEqual(g.map((x) => x.project), ["甲", "乙"]);
  assert.equal(g[0].items.length, 2);
});

test("groupBySpace:遇见序 + 未标注(null)恒排最后", () => {
  const g = groupBySpace([
    item("甲", null, null, "老记录"),
    item("甲", "客厅", null, "b"),
    item("甲", "玄关", null, "c"),
    item("甲", "客厅", null, "d"),
  ]);
  assert.deepEqual(g.map((x) => x.space), ["客厅", "玄关", null]);
  assert.equal(g[0].items.length, 2);
  assert.equal(g[2].items[0].text, "老记录");
});

test("sortByDateDesc:日期倒序、无日期沉底、同日稳定", () => {
  const s = sortByDateDesc([
    item("甲", null, "2026-07-01", "旧"),
    item("甲", null, null, "无日期"),
    item("甲", null, "2026-07-10", "新1"),
    item("甲", null, "2026-07-10", "新2"),
  ]);
  assert.deepEqual(s.map((x) => x.text), ["新1", "新2", "旧", "无日期"]);
});

test("staleDays:命中给天数,未超期 null", () => {
  const stale = [{ project: "乙", days: 8, last: "2026-07-04" }];
  assert.equal(staleDays(stale, "乙"), 8);
  assert.equal(staleDays(stale, "甲"), null);
});

// ---- 搜索 --------------------------------------------------------------

const docs = [
  { kind: "change", project: "保利", cnum: 11, status: "进行中",
    date: "2026-07-08", space: "客厅", text: "电视墙改用岩板,取消木格栅" },
  { kind: "change", project: "张三家", cnum: 5, status: "待确认",
    date: "2026-07-10", space: "玄关", text: "换鞋凳改内嵌式" },
  { kind: "image", project: "保利", id: "r3", file: "refs/a.jpg",
    note: "客厅 岩板电视墙 参考", space: ["客厅"], style: ["现代简约"] },
];

test("filterDocs:空 query 空结果(不倾倒全库)", () => {
  assert.deepEqual(filterDocs("", "all", docs), []);
  assert.deepEqual(filterDocs("   ", "all", docs), []);
});

test("filterDocs:关键词命中变更与图片;tab 过滤", () => {
  const all = filterDocs("岩板", "all", docs);
  assert.equal(all.length, 2);
  assert.deepEqual(filterDocs("岩板", "change", docs).map((d) => d.kind), ["change"]);
  assert.deepEqual(filterDocs("岩板", "image", docs).map((d) => d.kind), ["image"]);
});

test("filterDocs:空间/编号/项目名也算命中面", () => {
  assert.equal(filterDocs("玄关", "all", docs).length, 1);
  assert.equal(filterDocs("c11", "all", docs).length, 1); // 大小写不敏感 C11
  assert.equal(filterDocs("保利", "all", docs).length, 2);
});

test("splitHighlight:命中段标 hit,重组还原原文,多处命中", () => {
  const seg = splitHighlight("岩板配岩板", "岩板");
  assert.deepEqual(seg, [
    { t: "岩板", hit: true },
    { t: "配", hit: false },
    { t: "岩板", hit: true },
  ]);
  assert.equal(seg.map((s) => s.t).join(""), "岩板配岩板");
  // 大小写不敏感:保留原文大小写
  assert.deepEqual(splitHighlight("DWG 图纸", "dwg"),
    [{ t: "DWG", hit: true }, { t: " 图纸", hit: false }]);
  // 无命中 = 单段
  assert.deepEqual(splitHighlight("abc", "xyz"), [{ t: "abc", hit: false }]);
});
