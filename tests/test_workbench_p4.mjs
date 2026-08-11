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

// ⚠️ 契约在 track opendesign-note-source 改过(业主 08-11「按第一性原理整理掉」):
// **这个函数不再判断"变没变"**,它只把"用户碰过哪个输入框"装配成请求。
//   - `draft` 里出现某个键 = 用户碰过它 ⇒ 照发,哪怕值和原来一样;
//   - "变没变"是事实,只有档案说了算 ⇒ 后端在文件锁里判,回 changed_fields;
//   - 前端只保留**校验**:cnum 缺失不可寻址、非法状态词剔除。
//   - `originalNote` 参数**已删除** —— 它是"值比较"的最后一个入口,留着就是留个后门。
// 被推翻的六条旧断言(全是「没有实质改动 ⇒ null」)逐条换成了下面更强的版本:
// 旧的只说"是 null",新的说清楚"请求里到底有什么、没有什么"。

test("buildEditRequest:碰了状态 → 带 new_status", () => {
  const r = buildEditRequest(editable(), { status: "已完成" });
  assert.deepEqual(r, { project: "翡翠湾", cnum: 3, new_status: "已完成" });
});

test("buildEditRequest:碰了状态但值==原状态 → 照发(后端判 no-op)", () => {
  assert.deepEqual(buildEditRequest(editable(), { status: "进行中" }),
    { project: "翡翠湾", cnum: 3, new_status: "进行中" });
});

test("buildEditRequest:非法状态被剔除(校验保留),请求本身仍返回", () => {
  assert.deepEqual(buildEditRequest(editable(), { status: "done" }),
    { project: "翡翠湾", cnum: 3 });
});

test("buildEditRequest:碰了正文 → 带 trim 后的 new_text", () => {
  assert.deepEqual(buildEditRequest(editable(), { text: "  客厅吊顶改弧形  " }),
    { project: "翡翠湾", cnum: 3, new_text: "客厅吊顶改弧形" });
});

test("buildEditRequest:碰了正文但值==原正文 → 照发", () => {
  assert.deepEqual(buildEditRequest(editable(), { text: "客厅吊顶改平顶" }),
    { project: "翡翠湾", cnum: 3, new_text: "客厅吊顶改平顶" });
});

// 空正文照发、由后端回 empty_text(ds_tools.py 早就有这个错误码)。
// 前端悄悄吞掉 = "清空正文点保存,什么也没发生也不报错" —— 那是把错误藏起来,不是校验。
test("buildEditRequest:碰了正文且清空了 → 带 new_text:\"\",交后端拒", () => {
  assert.deepEqual(buildEditRequest(editable(), { text: "   " }),
    { project: "翡翠湾", cnum: 3, new_text: "" });
});

test("buildEditRequest:碰了备注 → 带 trim 后的 note", () => {
  assert.deepEqual(buildEditRequest(editable(), { note: " 业主确认 " }),
    { project: "翡翠湾", cnum: 3, note: "业主确认" });
});

test("buildEditRequest:碰了备注但值==原备注 → 照发(不再比较,也没得比)", () => {
  assert.deepEqual(buildEditRequest(editable({ note: "业主确认" }), { note: "业主确认" }),
    { project: "翡翠湾", cnum: 3, note: "业主确认" });
});

// 清空备注(track opendesign-note-clear;业主 2026-08-11 真机报:「删掉原来的备注但
// 还是之前的备注」)。空串就是"我要它变成没有备注",后端据此删行。
test("buildEditRequest:清空备注 → 带 note:\"\"", () => {
  assert.deepEqual(buildEditRequest(editable({ note: "业主确认" }), { note: "" }),
    { project: "翡翠湾", cnum: 3, note: "" });
  // 全删成空格也算清空(与后端 sanitize/trim 同口径,别让一个空格救活旧备注)
  assert.deepEqual(buildEditRequest(editable({ note: "业主确认" }), { note: "   " }),
    { project: "翡翠湾", cnum: 3, note: "" });
});

test("buildEditRequest:本来就没备注、用户碰了又清空 → 仍带 note:\"\"(后端判 no-op)", () => {
  assert.deepEqual(buildEditRequest(editable(), { note: "" }),
    { project: "翡翠湾", cnum: 3, note: "" });
});

test("buildEditRequest:清空备注 + 同时改正文 → 两个字段都带", () => {
  assert.deepEqual(
    buildEditRequest(editable({ note: "业主确认" }), { text: "客厅吊顶改弧形", note: "" }),
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

test("buildEditRequest:残缺行(cnum=null)不可编辑 → null(校验,不是判定)", () => {
  assert.equal(buildEditRequest(editable({ cnum: null }), { status: "已完成" }), null);
});

test("buildEditRequest:一个框都没碰 → 仍返回可寻址请求(只有 project+cnum)", () => {
  assert.deepEqual(buildEditRequest(editable(), {}), { project: "翡翠湾", cnum: 3 });
});

// `originalNote` 那个参数已经删了。多传一个实参在 JS 里不会报错,所以这条断言问的是
// **行为**:第三个参数不许再影响结果(它一旦被重新接上,这条就红)。
test("buildEditRequest:多传第三个实参也不改变结果(originalNote 已删)", () => {
  const withExtra = buildEditRequest(editable({ note: "业主确认" }),
    { note: "业主确认" }, "业主确认");
  assert.deepEqual(withExtra, { project: "翡翠湾", cnum: 3, note: "业主确认" });
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
