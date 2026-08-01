// track opendesign-todo-one-view oracle:待办页收敛成单一看法后的三个纯函数契约。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
//   orderItems(items, today)          —— 卡内两轨排序(硬轨=有 due,软轨=无 due)
//   orderProjectCards(groups, today)  —— 卡序(改签名:旧的第二参 stale 已删)
//   latestRecordAge(items, today)     —— 卡徽标用的"最近记录 N 天前"
//   STALE_AFTER_DAYS                  —— 徽标显示阈值(7,与后端 ds_todo 同源)
//
// 跑法:node --test tests/test_todo_one_view.mjs(Node 22+,原生 strip-types)
// red-check:实现前 todo.ts 无 orderItems / latestRecordAge / STALE_AFTER_DAYS 导出,
//           且 orderProjectCards 仍是旧签名 ⇒ 本文件整体红。
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  latestRecordAge,
  orderItems,
  orderProjectCards,
  STALE_AFTER_DAYS,
} from "../web/src/todo.ts";

const TODAY = "2026-08-01";

// 条目工厂:只有 due / date 参与排序,其余字段填成合法值即可。
// id 用来在断言里指名道姓(比下标可读,且乱序后仍认得出是谁)。
const it_ = (id, { due = null, date = null, project = "P" } = {}) => ({
  project, line: id, raw: "", status: "待确认",
  cnum: id, date, space: null, text: `t${id}`, due,
});

const ids = (arr) => arr.map((x) => x.cnum);
const g = (project, items) => ({ project, items });

// ── orderItems:两轨不混排 ──────────────────────────────────────────────────

test("orderItems:有 due 的整体排在无 due 的前面(哪怕无 due 的记录日期更老)", () => {
  const got = orderItems([
    it_(1, { date: "2020-01-01" }),            // 无 due,极老
    it_(2, { due: "2099-12-31" }),             // 有 due,极远
  ], TODAY);
  assert.deepEqual(ids(got), [2, 1]);
});

test("orderItems:硬轨按 due 升序 —— 过期最久的最靠前,然后今天,然后未来", () => {
  const got = orderItems([
    it_(1, { due: "2026-08-05" }),   // 未来
    it_(2, { due: "2026-08-01" }),   // 今天
    it_(3, { due: "2026-07-01" }),   // 过期最久
    it_(4, { due: "2026-07-28" }),   // 过期
  ], TODAY);
  assert.deepEqual(ids(got), [3, 4, 2, 1]);
});

test("orderItems:软轨按记录日期升序 —— 最久没动静的在前", () => {
  const got = orderItems([
    it_(1, { date: "2026-07-30" }),
    it_(2, { date: "2026-06-01" }),
    it_(3, { date: "2026-07-10" }),
  ], TODAY);
  assert.deepEqual(ids(got), [2, 3, 1]);
});

// 这条是刻意偏离 GPT-5.6 建议的"最新在前",依据=用户 08-01 的打开动机
// 「看今天做什么,还有有什么忘记的事情」。把它钉成回归用例,免得日后被"顺手改回直觉序"。
test("orderItems:软轨**不是**倒序(最新的不许排最前)", () => {
  const got = orderItems([
    it_(1, { date: "2026-07-31" }),  // 最新
    it_(2, { date: "2026-05-01" }),  // 最老
  ], TODAY);
  assert.equal(got[0].cnum, 2, "最老的必须在前:软轨回答的是「什么被忘了」");
});

test("orderItems:没有记录日期的条目沉到软轨最底", () => {
  const got = orderItems([
    it_(1, { date: null }),
    it_(2, { date: "2026-07-20" }),
    it_(3, { date: null }),
    it_(4, { date: "2026-06-20" }),
  ], TODAY);
  assert.deepEqual(ids(got), [4, 2, 1, 3]);
});

test("orderItems:无 date 的条目仍排在任何有 due 的条目之后(两轨优先于日期缺失)", () => {
  const got = orderItems([
    it_(1, { date: null }),
    it_(2, { due: "2099-01-01" }),
  ], TODAY);
  assert.deepEqual(ids(got), [2, 1]);
});

test("orderItems:同 due 保持传入序(稳定)", () => {
  const got = orderItems([
    it_(1, { due: "2026-08-03" }),
    it_(2, { due: "2026-08-03" }),
    it_(3, { due: "2026-08-03" }),
  ], TODAY);
  assert.deepEqual(ids(got), [1, 2, 3]);
});

test("orderItems:同记录日期保持传入序(稳定)", () => {
  const got = orderItems([
    it_(1, { date: "2026-07-01" }),
    it_(2, { date: "2026-07-01" }),
  ], TODAY);
  assert.deepEqual(ids(got), [1, 2]);
});

test("orderItems:全是 null(既无 due 又无 date)= 原样保持传入序", () => {
  const got = orderItems([it_(1), it_(2), it_(3)], TODAY);
  assert.deepEqual(ids(got), [1, 2, 3]);
});

test("orderItems:不改传入数组(无副作用)", () => {
  const input = [it_(1, { date: "2026-07-30" }), it_(2, { date: "2026-06-01" })];
  orderItems(input, TODAY);
  assert.deepEqual(ids(input), [1, 2], "传入数组必须原封不动");
});

test("orderItems:空输入 = []", () => {
  assert.deepEqual(orderItems([], TODAY), []);
});

// ── ⚠️ 真实形态:用户至今一条截止日都没设过 ────────────────────────────────
// design.md 的「这个 oracle 能被什么骗过」第二条:夹具全是漂亮的混合数据,
// 而用户的真实档案**硬轨恒空**。这一组专测那个形态,别让它只在混合夹具下绿。

test("【真实形态】全部条目都没有 due:整页退化成纯软轨,按最久在前", () => {
  const got = orderItems([
    it_(1, { date: "2026-07-28" }),
    it_(2, { date: "2026-05-15" }),
    it_(3, { date: "2026-07-02" }),
    it_(4, { date: null }),
  ], TODAY);
  assert.deepEqual(ids(got), [2, 3, 1, 4]);
});

test("【真实形态】全部项目都没有 due:卡序按各卡最老记录日期升序", () => {
  const got = orderProjectCards([
    g("A", [it_(1, { date: "2026-07-20", project: "A" })]),
    g("B", [it_(2, { date: "2026-04-01", project: "B" })]),
    g("C", [it_(3, { date: "2026-07-01", project: "C" })]),
  ], TODAY);
  assert.deepEqual(got.map((c) => c.project), ["B", "C", "A"]);
});

// ── orderProjectCards:档位 → 最早 due → 最老记录日期 ───────────────────────

test("orderProjectCards:有过期条目的卡排最前(哪怕它条目最少)", () => {
  const got = orderProjectCards([
    g("A", [it_(1, { due: "2026-08-09", project: "A" }), it_(2, { due: "2026-08-10", project: "A" })]),
    g("B", [it_(3, { due: "2026-07-25", project: "B" })]), // 过期
  ], TODAY);
  assert.deepEqual(got.map((c) => c.project), ["B", "A"]);
});

test("orderProjectCards:四个档位的完整顺序(过期 → 今天 → 未来 → 无 due)", () => {
  const got = orderProjectCards([
    g("noDue",   [it_(1, { date: "2026-01-01", project: "noDue" })]),
    g("future",  [it_(2, { due: "2026-08-20", project: "future" })]),
    g("overdue", [it_(3, { due: "2026-07-01", project: "overdue" })]),
    g("today",   [it_(4, { due: "2026-08-01", project: "today" })]),
  ], TODAY);
  assert.deepEqual(got.map((c) => c.project), ["overdue", "today", "future", "noDue"]);
});

test("orderProjectCards:档位取卡内**最紧急**的那条,不是第一条也不是多数", () => {
  const got = orderProjectCards([
    // A 的第一条是很远的未来,但它藏着一条过期 —— 必须按过期算
    g("A", [it_(1, { due: "2026-12-31", project: "A" }), it_(2, { due: "2026-07-20", project: "A" })]),
    g("B", [it_(3, { due: "2026-08-01", project: "B" })]), // 今天
  ], TODAY);
  assert.deepEqual(got.map((c) => c.project), ["A", "B"]);
});

test("orderProjectCards:同档内按卡里最早的 due 升序", () => {
  const got = orderProjectCards([
    g("A", [it_(1, { due: "2026-07-20", project: "A" })]),
    g("B", [it_(2, { due: "2026-07-05", project: "B" })]),
    g("C", [it_(3, { due: "2026-07-28", project: "C" })]),
  ], TODAY);
  assert.deepEqual(got.map((c) => c.project), ["B", "A", "C"]);
});

test("orderProjectCards:全平局保持传入序(稳定排序)", () => {
  const got = orderProjectCards([
    g("X", [it_(1, { due: "2026-08-03", project: "X" })]),
    g("Y", [it_(2, { due: "2026-08-03", project: "Y" })]),
    g("Z", [it_(3, { due: "2026-08-03", project: "Z" })]),
  ], TODAY);
  assert.deepEqual(got.map((c) => c.project), ["X", "Y", "Z"]);
});

test("orderProjectCards:items 原样带过(同一引用,不复制不重排组内)", () => {
  const gA = g("A", [it_(2, { date: "2026-07-01", project: "A" }), it_(1, { date: "2026-06-01", project: "A" })]);
  const got = orderProjectCards([gA], TODAY);
  assert.equal(got[0].items, gA.items, "必须是同一个数组引用");
  assert.deepEqual(ids(got[0].items), [2, 1], "组内顺序由 orderItems 负责,卡序函数不许动它");
});

test("orderProjectCards:不改传入数组(无副作用)", () => {
  const input = [
    g("A", [it_(1, { date: "2026-07-01", project: "A" })]),
    g("B", [it_(2, { due: "2026-07-01", project: "B" })]),
  ];
  orderProjectCards(input, TODAY);
  assert.deepEqual(input.map((x) => x.project), ["A", "B"]);
});

test("orderProjectCards:空输入 = []", () => {
  assert.deepEqual(orderProjectCards([], TODAY), []);
});

test("orderProjectCards:空 items 的卡不炸,且沉到无 due 档", () => {
  const got = orderProjectCards([
    g("empty", []),
    g("A", [it_(1, { due: "2026-08-05", project: "A" })]),
  ], TODAY);
  assert.deepEqual(got.map((c) => c.project), ["A", "empty"]);
});

// 旧签名的第二参是后端那个坏指标(见 design.md 的实证)。这条钉死它不再被读:
// 传一个"按旧语义会把 Z 顶到最前"的 stale 数组,新实现必须完全无视它。
test("orderProjectCards:**不再接受也不再理会**旧的 stale 入参", () => {
  const groups = [
    g("A", [it_(1, { due: "2026-07-01", project: "A" })]), // 过期,应当最前
    g("Z", [it_(2, { date: "2026-07-31", project: "Z" })]),
  ];
  const legacyStale = [{ project: "Z", days: 999, last: "2020-01-01" }];
  const got = orderProjectCards(groups, TODAY, legacyStale);
  assert.deepEqual(got.map((c) => c.project), ["A", "Z"],
    "多余入参不许改变结果 —— 页脚 mtime 那个指标已被证伪,不能再参与卡序");
});

// ── latestRecordAge:卡徽标"最近记录 N 天前" ────────────────────────────────

test("latestRecordAge:取**最新**的记录日期算年龄(不是最老)", () => {
  const age = latestRecordAge([
    it_(1, { date: "2026-05-01" }),
    it_(2, { date: "2026-07-25" }),  // 最新
    it_(3, { date: "2026-06-01" }),
  ], TODAY);
  assert.equal(age, 7);
});

test("latestRecordAge:今天刚记的 = 0 天", () => {
  assert.equal(latestRecordAge([it_(1, { date: TODAY })], TODAY), 0);
});

test("latestRecordAge:一条都没有日期 → null", () => {
  assert.equal(latestRecordAge([it_(1), it_(2)], TODAY), null);
});

test("latestRecordAge:空输入 → null", () => {
  assert.equal(latestRecordAge([], TODAY), null);
});

test("latestRecordAge:混合有无日期时,只看有日期的那些", () => {
  assert.equal(latestRecordAge([it_(1), it_(2, { date: "2026-07-22" })], TODAY), 10);
});

test("latestRecordAge:跨月正确(不是按 30 天粗算)", () => {
  // 2026-06-30 → 2026-08-01 = 6月剩 0 天 + 7月 31 天 + 1 = 32 天
  assert.equal(latestRecordAge([it_(1, { date: "2026-06-30" })], TODAY), 32);
});

test("latestRecordAge:未来日期(手写错的档案)不返回负数,钳到 0", () => {
  assert.equal(latestRecordAge([it_(1, { date: "2026-09-01" })], TODAY), 0);
});

test("STALE_AFTER_DAYS = 7,与后端 ds_todo 的阈值同源", () => {
  assert.equal(STALE_AFTER_DAYS, 7);
});

// ── 批次小标题(2026-08-01 追加:用户拍板方案 1)────────────────────────────
// 背景:0.60.0「助手记录时给这一批起名」原来只在「按时间」看法里显示,本单砍掉那个
// 看法后它会变成**有人写、没人看**的字段 —— 正是本项目反复栽的那类病。
// 用户拍板搬进项目卡,主 agent 选了最轻的形态:**不加折叠层,只在同一批的第一条
// 上方加一行小标题**,且**只有助手真起过名的批次才显示**(没名字的老条目不显示,
// 否则满屏都是"首条内容 等 N 条"的噪音)。
//
// 能这么轻是因为一个巧合:同一批的条目**记录日期相同**,而软轨按记录日期排
// ⇒ 同一批天生挨着,加标题不打乱任何顺序。
import { batchCaption } from "../web/src/todoBatches.ts";

const withBatch = (id, title, over = {}) => ({
  ...it_(over.cnum ?? 1, over), batch: id === null ? null : { id, title },
});

test("batchCaption:一批的第一条给标题", () => {
  assert.equal(batchCaption(withBatch("b1", "效果图改浅色"), null), "效果图改浅色");
});

test("batchCaption:同一批的后续条目不再重复标题", () => {
  const a = withBatch("b1", "效果图改浅色", { cnum: 1 });
  const b = withBatch("b1", "效果图改浅色", { cnum: 2 });
  assert.equal(batchCaption(b, a), null);
});

test("batchCaption:换了一批就重新给标题", () => {
  const a = withBatch("b1", "效果图改浅色", { cnum: 1 });
  const b = withBatch("b2", "水电点位确认", { cnum: 2 });
  assert.equal(batchCaption(b, a), "水电点位确认");
});

test("batchCaption:没有名字的批次不给标题(不制造噪音)", () => {
  assert.equal(batchCaption(withBatch("b1", ""), null), null);
  assert.equal(batchCaption({ ...it_(1), batch: null }, null), null);
  assert.equal(batchCaption(it_(1), null), null);
});

test("batchCaption:从有名字批次回到无名条目,不残留上一条的标题", () => {
  const a = withBatch("b1", "效果图改浅色", { cnum: 1 });
  const b = { ...it_(2), batch: null };
  assert.equal(batchCaption(b, a), null);
});

test("batchCaption:同名但不同批(两次沟通碰巧起了同名)仍各自给标题", () => {
  const a = withBatch("b1", "改灯", { cnum: 1 });
  const b = withBatch("b2", "改灯", { cnum: 2 });
  assert.equal(batchCaption(b, a), "改灯", "认的是批次 id,不是标题字面");
});

test("batchCaption:过长标题截断加省略号(复用 BATCH_TITLE_MAX=14)", () => {
  const long = "一二三四五六七八九十一二三四五六";
  assert.equal(batchCaption(withBatch("b1", long), null), "一二三四五六七八九十一二三四…");
});

test("batchCaption:不含条数 —— 卡内看得见行,不需要「等 N 条」", () => {
  const cap = batchCaption(withBatch("b1", "效果图改浅色"), null);
  assert.ok(!/等\s*\d+\s*条/.test(cap), `小标题里不该有"等 N 条"(实测 ${cap})`);
});
