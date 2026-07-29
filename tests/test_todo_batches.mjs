// track opendesign-due-picker T4a oracle:待办「按时间」批次的折叠规则 + 兜底标题。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// 用户拍板的规则(tasks.md T4):
//   「1~2 条不折;**≥3 条默认折起**;**有过了截止日的自动展开**(急压过整洁)。
//    折叠状态持久化(同 T3)。标题:助手起名 + **没名字自动兜底**「第一条内容 等 3 条」,
//    **永不空白**。」
// 本单(T4a)只做**兜底标题**与折叠规则,纯前端零后端改动;助手起名 = T4b 另走 full。
//
// 契约(web/src/todoBatches.ts):
//   ① batchTitle(items) —— 永不空白。1 条 = 该条内容;≥2 条 = 「首条内容 等 N 条」。
//      内容过长截断加省略号(BATCH_TITLE_MAX);内容空白/缺失的条目退回「未命名」,
//      **不许返回空串**(空标题 = 批次头看起来没东西可点,折叠控件形同消失)。
//   ② isBatchOpen(batch, prefs, today) —— 显式偏好压过一切(同 T3「显式偏好压过默认」);
//      没存过偏好时:**含过期条目 → 展开**;否则 **≤2 条展开 / ≥3 条收起**。
//      过期判定复用 todo.ts 的 dueStatus,不自造第二份日期比较。
//   ③ batchKey(scope, date) —— 持久化键,与视图 scope 绑(按时间/按项目各存各的),
//      无日期批次有稳定键(不能塌成 undefined,否则所有"未标注日期"共用一个键)。
//   ④ TODO_BATCH_STORAGE_KEY 锁死 = "ds.todo.batchOpen"。改名 = 所有人折叠状态丢一次。
//   ⑤ loadBoolPrefs(raw) —— 容错解析 localStorage 原文(坏 JSON/非对象/数组/非布尔值一律丢)。
//      **共享给 T3 的 loadStagePrefs 用同一份实现**,不留第二个答案。
//      折叠状态必须落盘:TodoPage 现有的 toggled 是 useState、刷新即忘,这条不许重蹈。
//
// red-check:实现前 web/src/todoBatches.ts 不存在,本文件整体红。
// 跑法:node --test tests/test_todo_batches.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  batchTitle,
  isBatchOpen,
  batchKey,
  loadBoolPrefs,
  TODO_BATCH_STORAGE_KEY,
  BATCH_TITLE_MAX,
  UNNAMED_ITEM_LABEL,
} from "../web/src/todoBatches.ts";
import { loadStagePrefs } from "../web/src/workspace/projectGroups.ts";

const TODAY = "2026-07-29";

/** 造一条待办。due 默认 null(不参与过期判定)。 */
const item = (text, due = null) => ({
  project: "张宅",
  line: 10,
  raw: "",
  status: "待确认",
  cnum: 1,
  date: "2026-07-28",
  space: null,
  text,
  due,
});

const batch = (items, date = "2026-07-28") => ({ date, items });

// ── ① batchTitle:永不空白 ──────────────────────────────────────────────────

test("单条批次:标题就是那条内容本身,不加「等 N 条」", () => {
  assert.equal(batchTitle([item("客厅吊顶改平顶")]), "客厅吊顶改平顶");
});

test("多条批次:「首条内容 等 N 条」", () => {
  const t = batchTitle([item("效果图改浅色"), item("餐桌换圆桌"), item("主卧加衣柜")]);
  assert.equal(t, "效果图改浅色 等 3 条");
});

test("两条也照样带「等 2 条」(只有 1 条时才省)", () => {
  assert.equal(batchTitle([item("甲"), item("乙")]), "甲 等 2 条");
});

test("首条内容过长 → 截断加省略号,且截断后仍带「等 N 条」", () => {
  const long = "客厅的吊顶要改成平顶另外把电视墙的造型全部去掉换成大白墙";
  const t = batchTitle([item(long), item("乙")]);
  assert.ok(t.length < long.length, "过长标题必须被截断");
  assert.ok(t.includes("…"), "截断要有省略号提示还有下文");
  assert.ok(t.endsWith("等 2 条"), `截断不能把「等 N 条」吃掉,实际:${t}`);
  assert.ok(
    t.startsWith(long.slice(0, BATCH_TITLE_MAX)),
    "截断要保留开头,不许从中间取",
  );
});

test("首条内容为空/全空白 → 退回「未命名」,绝不返回空串", () => {
  assert.equal(batchTitle([item("   ")]), UNNAMED_ITEM_LABEL);
  assert.equal(batchTitle([item("")]), UNNAMED_ITEM_LABEL);
  const t = batchTitle([item(""), item("乙")]);
  assert.equal(t, `${UNNAMED_ITEM_LABEL} 等 2 条`);
});

test("空批次(理论上不该出现)也不许炸、不许返回空串", () => {
  const t = batchTitle([]);
  assert.equal(typeof t, "string");
  assert.ok(t.length > 0, "空批次标题也必须有字,不然批次头是空的");
});

test("首尾空白要裁掉(档案里手写的行常带尾空格)", () => {
  assert.equal(batchTitle([item("  客厅改色  ")]), "客厅改色");
});

// ── ② isBatchOpen:显式偏好 > 过期 > 条数 ────────────────────────────────────

test("默认:1~2 条展开", () => {
  assert.equal(isBatchOpen(batch([item("甲")]), {}, TODAY), true);
  assert.equal(isBatchOpen(batch([item("甲"), item("乙")]), {}, TODAY), true);
});

test("默认:≥3 条收起", () => {
  const b = batch([item("甲"), item("乙"), item("丙")]);
  assert.equal(isBatchOpen(b, {}, TODAY), false);
});

test("含过期条目 → 即使 5 条也默认展开(急压过整洁)", () => {
  const b = batch([
    item("甲"),
    item("乙"),
    item("丙"),
    item("丁"),
    item("戊过期了", "2026-07-01"),
  ]);
  assert.equal(isBatchOpen(b, {}, TODAY), true);
});

test("截止日 = 今天 不算过期(只有真过了才强制展开)", () => {
  const b = batch([item("甲"), item("乙"), item("丙", TODAY)]);
  assert.equal(isBatchOpen(b, {}, TODAY), false, "今天到期 ≠ 过期,不该推翻「≥3 收起」");
});

test("截止日在未来 不算过期", () => {
  const b = batch([item("甲"), item("乙"), item("丙", "2026-08-30")]);
  assert.equal(isBatchOpen(b, {}, TODAY), false);
});

test("显式偏好压过「≥3 条收起」:用户点开了就得开着", () => {
  const b = batch([item("甲"), item("乙"), item("丙")]);
  const prefs = { [batchKey("@time", b.date)]: true };
  assert.equal(isBatchOpen(b, prefs, TODAY), true);
});

test("显式偏好压过「过期自动展开」:用户点收了就得收着", () => {
  // T3 的教训:自动展开写成压过用户,那个折叠键就成了死键(点了没反应)。
  const b = batch([item("甲"), item("乙"), item("丙过期", "2026-07-01")]);
  const prefs = { [batchKey("@time", b.date)]: false };
  assert.equal(isBatchOpen(b, prefs, TODAY), false, "折叠键不许因为过期变成死键");
});

test("偏好按 scope 分开存:按时间视图收起,不影响别的视图同一天", () => {
  const b = batch([item("甲")]);
  const prefs = { [batchKey("@time", b.date)]: false };
  assert.equal(isBatchOpen(b, prefs, TODAY), false);
  assert.notEqual(batchKey("@time", b.date), batchKey("@proj", b.date));
});

test("空批次不炸(≤2 条 → 展开)", () => {
  assert.equal(isBatchOpen(batch([]), {}, TODAY), true);
});

// ── ③ batchKey:无日期批次要有稳定键 ────────────────────────────────────────

test("无日期(null)批次的键稳定且不含 undefined/null 字样塌陷", () => {
  const k1 = batchKey("@time", null);
  const k2 = batchKey("@time", null);
  assert.equal(k1, k2, "同样输入必须同样键");
  assert.ok(k1.length > 0);
  assert.notEqual(k1, batchKey("@time", "2026-07-28"), "无日期不能和有日期撞键");
});

test("不同日期不同键", () => {
  assert.notEqual(batchKey("@time", "2026-07-28"), batchKey("@time", "2026-07-27"));
});

// ── ④⑤ 持久化 ──────────────────────────────────────────────────────────────

test("存储键锁死(改名 = 所有人折叠状态丢一次)", () => {
  assert.equal(TODO_BATCH_STORAGE_KEY, "ds.todo.batchOpen");
});

test("loadBoolPrefs:坏输入一律退空表,不许抛", () => {
  assert.deepEqual(loadBoolPrefs(null), {});
  assert.deepEqual(loadBoolPrefs(""), {});
  assert.deepEqual(loadBoolPrefs("{坏 JSON"), {});
  assert.deepEqual(loadBoolPrefs("[1,2]"), {}, "数组不是偏好表");
  assert.deepEqual(loadBoolPrefs("null"), {});
  assert.deepEqual(loadBoolPrefs('"字符串"'), {});
});

test("loadBoolPrefs:只留布尔值,杂质剔除", () => {
  const raw = '{"a":true,"b":false,"c":1,"d":"x","e":null}';
  assert.deepEqual(loadBoolPrefs(raw), { a: true, b: false });
});

test("loadBoolPrefs 与 T3 的 loadStagePrefs 是同一份实现(不留第二个答案)", () => {
  const raw = '{"施工中":false,"竣工验收":true,"坏":1}';
  assert.deepEqual(loadBoolPrefs(raw), loadStagePrefs(raw));
  assert.deepEqual(loadBoolPrefs("{坏"), loadStagePrefs("{坏"));
});

// ── 回归:整批往返 ──────────────────────────────────────────────────────────

test("往返:点收 → 存盘 → 重新解析 → 仍是收着(刷新不忘)", () => {
  const b = batch([item("甲"), item("乙")]); // 默认展开
  assert.equal(isBatchOpen(b, {}, TODAY), true);
  const prefs = { ...loadBoolPrefs(null), [batchKey("@time", b.date)]: false };
  const reloaded = loadBoolPrefs(JSON.stringify(prefs));
  assert.equal(isBatchOpen(b, reloaded, TODAY), false);
});
