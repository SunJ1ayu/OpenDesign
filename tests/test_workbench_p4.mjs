// track p4 oracle:待办页分组/排序 + 搜索过滤/高亮 的纯逻辑层
// 跑法:node --test tests/test_workbench_p4.mjs(Node 22+,原生 strip-types)
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  groupByProject,
  groupByDate,
  buildEditRequest,
  isValidStatus,
  isTerminalStatus,
  STATUS_HINT,
  STATUSES,
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

test("groupByDate:日期倒序分批,无日期(null)恒沉底", () => {
  const g = groupByDate([
    item("甲", null, "2026-07-01", "旧"),
    item("甲", null, null, "无日期"),
    item("甲", "客厅", "2026-07-16", "新a"),
    item("甲", null, "2026-07-01", "旧2"),
    item("甲", null, "2026-07-16", "新b"),
  ]);
  assert.deepEqual(g.map((x) => x.date), ["2026-07-16", "2026-07-01", null]);
  assert.deepEqual(g[0].items.map((x) => x.text), ["新a", "新b"]);
  assert.deepEqual(g[1].items.map((x) => x.text), ["旧", "旧2"]);
  assert.equal(g[2].items[0].text, "无日期");
});

test("groupByDate:组内保持传入相对序(调用方先排好序再分组,不许乱序)", () => {
  // 原来这里借 sortByDateDesc 造输入,那个函数已随「按时间」看法删除。
  // groupByDate 本身仍被 workspace/changes.ts 用着,**覆盖不能丢** ——
  // 改成直接写出"已排序"的输入,断言一字未动(约束面不变)。
  const sorted = [
    item("甲", null, "2026-07-16", "a1"),
    item("乙", null, "2026-07-16", "b2"),
    item("乙", null, "2026-07-10", "b1"),
  ];
  const g = groupByDate(sorted);
  assert.deepEqual(g.map((x) => x.date), ["2026-07-16", "2026-07-10"]);
  assert.deepEqual(g[0].items.map((x) => x.text), ["a1", "b2"]);
});

test("groupByDate:空表回空,不炸", () => {
  assert.deepEqual(groupByDate([]), []);
});

// sortByDateDesc 及其用例已随 track opendesign-todo-one-view 删除:
// 唯一调用者是被砍掉的「按时间」看法,函数零生产调用者。
// (与下面 staleDays 同一条规矩:不留没人调用、判据还在发合格证的代码。)

// staleDays 已随 track opendesign-todo-layout 删除(生产调用者归 orderProjectCards,
// 其契约在 tests/test_todo_layout.mjs「附 stale 天数,无超期为 null」一例)。

// ---- 行内编辑:请求装配(track opendesign-todo-edit T6 / design test 14)------

const editable = (over = {}) => ({
  project: "翡翠湾", cnum: 3, status: "进行中", text: "客厅吊顶改平顶", ...over,
});

test("buildEditRequest:改状态 → 仅带 new_status", () => {
  const r = buildEditRequest(editable(), { status: "已完成" });
  assert.deepEqual(r, { project: "翡翠湾", cnum: 3, new_status: "已完成" });
});

test("buildEditRequest:状态 no-op(==原状态)不带", () => {
  assert.equal(buildEditRequest(editable(), { status: "进行中" }), null);
});

test("buildEditRequest:非法状态被剔除", () => {
  assert.equal(buildEditRequest(editable(), { status: "done" }), null);
});

test("buildEditRequest:改正文 trim 后 ≠ 原 → 带 new_text", () => {
  const r = buildEditRequest(editable(), { text: "  客厅吊顶改弧形  " });
  assert.deepEqual(r, { project: "翡翠湾", cnum: 3, new_text: "客厅吊顶改弧形" });
});

test("buildEditRequest:正文 no-op / 空白 不带", () => {
  assert.equal(buildEditRequest(editable(), { text: "客厅吊顶改平顶" }), null);
  assert.equal(buildEditRequest(editable(), { text: "   " }), null);
});

test("buildEditRequest:备注非空 → 带 note;空白不带", () => {
  assert.deepEqual(buildEditRequest(editable(), { note: " 业主确认 " }),
    { project: "翡翠湾", cnum: 3, note: "业主确认" });
  assert.equal(buildEditRequest(editable(), { note: "  " }), null);
});

test("buildEditRequest:备注==原备注(预填没动)→ 不重写(todo-ux2)", () => {
  assert.equal(buildEditRequest(editable(), { note: "业主确认" }, "业主确认"), null);
  assert.equal(buildEditRequest(editable(), { note: " 业主确认 " }, "业主确认"), null);
  assert.deepEqual(buildEditRequest(editable(), { note: "业主书面确认" }, "业主确认"),
    { project: "翡翠湾", cnum: 3, note: "业主书面确认" });
});

// 清空备注(track opendesign-note-clear;业主 2026-08-11 真机报:「删掉原来的备注但
// 还是之前的备注」)。根因之一就在这个纯函数:`if (n && …)` 把"清空"当成"没改",
// 于是若这次只清了备注,整个请求都不发 —— 界面关了,盘上一字未动。
test("buildEditRequest:清空备注(原来有)→ 带 note:\"\",这是一次真改动", () => {
  assert.deepEqual(buildEditRequest(editable(), { note: "" }, "业主确认"),
    { project: "翡翠湾", cnum: 3, note: "" });
  // 全删成空格也算清空(与后端 sanitize/trim 同口径,别让一个空格救活旧备注)
  assert.deepEqual(buildEditRequest(editable(), { note: "   " }, "业主确认"),
    { project: "翡翠湾", cnum: 3, note: "" });
});

test("buildEditRequest:本来就没备注 + 草稿也空 → 仍是 null(不发无谓写)", () => {
  assert.equal(buildEditRequest(editable(), { note: "" }, ""), null);
  assert.equal(buildEditRequest(editable(), { note: "  " }), null);
});

test("buildEditRequest:清空备注 + 同时改正文 → 两个字段都带", () => {
  assert.deepEqual(
    buildEditRequest(editable(), { text: "客厅吊顶改弧形", note: "" }, "业主确认"),
    { project: "翡翠湾", cnum: 3, new_text: "客厅吊顶改弧形", note: "" });
});

test("buildEditRequest:三字段同改 → 全带", () => {
  const r = buildEditRequest(editable(), {
    status: "已完成", text: "客厅吊顶改弧形", note: "拍板",
  });
  assert.deepEqual(r, {
    project: "翡翠湾", cnum: 3,
    new_status: "已完成", new_text: "客厅吊顶改弧形", note: "拍板",
  });
});

test("buildEditRequest:残缺行(cnum=null)不可编辑 → null", () => {
  assert.equal(buildEditRequest(editable({ cnum: null }), { status: "已完成" }), null);
});

test("buildEditRequest:无任何有效改动 → null", () => {
  assert.equal(buildEditRequest(editable(), {}), null);
});

test("isValidStatus:四状态通过,其余拒", () => {
  for (const s of ["待确认", "进行中", "已完成", "已关闭"]) assert.ok(isValidStatus(s));
  assert.equal(isValidStatus("done"), false);
  assert.equal(isValidStatus(""), false);
});

test("isTerminalStatus:已完成/已关闭为终态,两开放态非终态", () => {
  assert.equal(isTerminalStatus("已完成"), true);
  assert.equal(isTerminalStatus("已关闭"), true);
  assert.equal(isTerminalStatus("待确认"), false);
  assert.equal(isTerminalStatus("进行中"), false);
  assert.equal(isTerminalStatus("done"), false);
});

test("STATUS_HINT:覆盖全部四状态且非空", () => {
  for (const s of STATUSES) {
    assert.equal(typeof STATUS_HINT[s], "string");
    assert.ok(STATUS_HINT[s].length > 0);
  }
  assert.equal(STATUS_HINT["待确认"], "等业主确认");
  assert.equal(STATUS_HINT["进行中"], "我在做");
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
