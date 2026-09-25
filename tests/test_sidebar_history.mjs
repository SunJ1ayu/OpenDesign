// oracle:侧栏「历史对话 + 项目」照 ZCode 改(方案一 + 方案二一起;track opendesign-sidebar-history)
// 跑法:node --test tests/test_sidebar_history.mjs(Node 22+,原生 strip-types)
//
// 业主 09-25「直接方案一和方案二一起做吧」:方案一 = 历史对话看得全(今天 / 昨天 / 更早 + 显示更多)、置顶、⋯ 置顶 / 改名 / 删除;
// 方案二 = 按项目看:每个项目下挂和它有关的对话(项目对话在前),没碰过项目的放「其他对话」。规则:碰过几个项目就在几个项目下都出现。
// 置顶的只在置顶区出现一次(4c C10);删掉的项目忽略(QA 设计);改名去空格、空 ⇒ 取消不改(QA Grok)、最长 160(网关上限)。
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  dayBucket,
  timeSections,
  displayTitle,
  sessionProjects,
  projectView,
  cleanRename,
  firstTag,
  withLastActive,
  makeSerial,
  TITLE_MAX,
} from "../web/src/workspace/sidebarModel.ts";

const NOW = new Date(2026, 8, 25, 15, 0, 0); // 本机时间 09-25 15:00
const iso = (d) => d.toISOString();
const at = (m, d, h, min = 0) => iso(new Date(2026, m - 1, d, h, min, 0));

test("s1 分段:今天 / 昨天 / 更早,按本机日期(不是 24 小时滚动)", () => {
  assert.equal(dayBucket(at(9, 25, 0, 0), NOW), "今天");
  assert.equal(dayBucket(at(9, 25, 14, 59), NOW), "今天");
  assert.equal(dayBucket(at(9, 24, 23, 59), NOW), "昨天");
  assert.equal(dayBucket(at(9, 24, 0, 0), NOW), "昨天");
  assert.equal(dayBucket(at(9, 23, 23, 59), NOW), "更早");
  assert.equal(dayBucket(undefined, NOW), "更早", "没有时间的归更早,不崩");
  assert.equal(dayBucket("不是时间", NOW), "更早");
});

test("s2 按时间:分段按顺序、段内最近在前;空段不出;置顶的抽走", () => {
  const ss = [
    { key: "websocket:a", updated_at: at(9, 20, 10) },
    { key: "websocket:b", updated_at: at(9, 25, 9) },
    { key: "websocket:c", updated_at: at(9, 25, 11) },
    { key: "websocket:d", updated_at: at(9, 24, 18) },
  ];
  const secs = timeSections(ss, NOW, ["websocket:c"]);
  assert.deepEqual(secs.map((s) => s.label), ["今天", "昨天", "更早"]);
  assert.deepEqual(secs[0].items.map((s) => s.key), ["websocket:b"], "c 置顶了,只在置顶区");
  assert.deepEqual(secs[1].items.map((s) => s.key), ["websocket:d"]);
  assert.deepEqual(secs[2].items.map((s) => s.key), ["websocket:a"]);
  const noYesterday = timeSections(ss.filter((s) => s.key !== "websocket:d"), NOW, []);
  assert.deepEqual(noYesterday.map((s) => s.label), ["今天", "更早"]);
  assert.deepEqual(noYesterday[0].items.map((s) => s.key), ["websocket:c", "websocket:b"], "段内最近在前");
});

test("s3 显示名:改过的名字优先,否则自动名字 / 预览 /「(未命名对话)」", () => {
  const s = { key: "websocket:a", title: "客厅吊顶改方案", preview: "我想把吊顶…" };
  assert.equal(displayTitle(s, { "websocket:a": "王女士吊顶" }), "王女士吊顶");
  assert.equal(displayTitle(s, {}), "客厅吊顶改方案");
  assert.equal(displayTitle({ key: "websocket:b", preview: "我想把吊顶…" }, {}), "我想把吊顶…");
  assert.equal(displayTitle({ key: "websocket:c" }, {}), "(未命名对话)");
});

const PROJECTS = [
  { key: "翡翠湾-1801", name: "翡翠湾-1801" },
  { key: "施工组:滨江-12F", name: "滨江-12F" },   // 分组项目:key =「组:名」
  { key: "陈总办公室", name: "陈总办公室" },
];

test("s4 对话碰过哪些项目:派生的 + 项目对话映射,去重、项目对话在前、按 key 或名字对上、删掉的项目忽略", () => {
  const derived = { "websocket:a": ["翡翠湾-1801", "滨江-12F", "已删项目", "翡翠湾-1801"] };
  const threadMap = { "陈总办公室": "a" };  // 项目对话映射:project → chat_id
  assert.deepEqual(sessionProjects("websocket:a", derived, threadMap, PROJECTS),
    ["陈总办公室", "翡翠湾-1801", "施工组:滨江-12F"], "项目对话在前;「滨江-12F」对上分组 key;已删项目忽略;不重复");
  assert.deepEqual(sessionProjects("websocket:z", derived, threadMap, PROJECTS), []);
  assert.deepEqual(sessionProjects("websocket:b", { "websocket:b": ["施工组:滨江-12F"] }, {}, PROJECTS), ["施工组:滨江-12F"]);
  assert.deepEqual(sessionProjects("websocket:q", {}, { "已删项目": "q" }, PROJECTS), [],
    "项目对话映射里的项目已经删了 ⇒ 忽略(回「其他对话」,QA 设计定)");
});

test("s5 按项目:碰过几个项目就在几个项目下都出现;项目对话在前、其余最近在前;没碰过的进「其他」;置顶的全抽走", () => {
  const ss = [
    { key: "websocket:t", updated_at: at(9, 20, 9) },   // 翡翠湾的项目对话(更旧也在前)
    { key: "websocket:x", updated_at: at(9, 25, 9) },   // 翡翠湾 + 滨江
    { key: "websocket:y", updated_at: at(9, 24, 9) },   // 翡翠湾
    { key: "websocket:o", updated_at: at(9, 25, 10) },  // 没碰过
    { key: "websocket:p", updated_at: at(9, 25, 11) },  // 翡翠湾,置顶
  ];
  const projectsOf = (k) => ({
    "websocket:t": ["翡翠湾-1801"], "websocket:x": ["翡翠湾-1801", "施工组:滨江-12F"],
    "websocket:y": ["翡翠湾-1801"], "websocket:p": ["翡翠湾-1801"],
  })[k] ?? [];
  const threadKeys = new Set(["websocket:t"]);
  const v = projectView(ss, projectsOf, ["websocket:p"], threadKeys);
  assert.deepEqual(v.byProject["翡翠湾-1801"].map((s) => s.key), ["websocket:t", "websocket:x", "websocket:y"]);
  assert.deepEqual(v.byProject["施工组:滨江-12F"].map((s) => s.key), ["websocket:x"]);
  assert.equal(v.byProject["陈总办公室"], undefined, "没有对话的项目没有这一项(界面显示 0 条)");
  assert.deepEqual(v.other.map((s) => s.key), ["websocket:o"]);
  assert.ok(!Object.values(v.byProject).flat().some((s) => s.key === "websocket:p"), "置顶的不在项目下重复");
});

// 空 / 全空格 ⇒ null = **取消,不改**(QA Grok TC-10:手一滑清空回车,起好的名字不能没了);超长截到 160
test("s6 改名:去首尾空格;空 / 全空格 ⇒ null(取消,名字不变);超长截到 160", () => {
  assert.equal(cleanRename("  王女士吊顶 "), "王女士吊顶");
  assert.equal(cleanRename(""), null);
  assert.equal(cleanRename("   "), null);
  assert.equal(TITLE_MAX, 160);
  const long = "长".repeat(200);
  assert.equal(cleanRename(long).length, 160);
});

test("s7 按时间视图的项目小标:第一个(项目对话优先)+「+N」;没有 ⇒ null", () => {
  const name = (k) => PROJECTS.find((p) => p.key === k)?.name ?? k;
  assert.equal(firstTag(["陈总办公室", "翡翠湾-1801", "施工组:滨江-12F"], name), "陈总办公室 +2");
  assert.equal(firstTag(["施工组:滨江-12F"], name), "滨江-12F");
  assert.equal(firstTag([], name), null);
});

// design P6:网关每 15 分钟空闲压缩一次,每次都把 updated_at 刷成当时 ⇒ 分段 / 排序 / 「几天前」要用后台读出的最后一条消息时间
test("s8 最后聊天时间盖掉网关的 updated_at;没有就用原来的;不改原数组", () => {
  const ss = [
    { key: "websocket:a", title: "A", updated_at: at(9, 25, 14, 50) },
    { key: "websocket:b", title: "B", updated_at: at(9, 25, 14, 50) },
  ];
  const out = withLastActive(ss, { "websocket:a": at(8, 16, 9, 30) });
  assert.equal(out[0].updated_at, at(8, 16, 9, 30));
  assert.equal(out[1].updated_at, at(9, 25, 14, 50));
  assert.equal(ss[0].updated_at, at(9, 25, 14, 50), "不改原数组");
  assert.equal(dayBucket(out[0].updated_at, NOW), "更早");
});

// 评审 GPT M2:快速连点两次置顶,两个请求的回话可能乱序到达,后到的旧状态会把界面盖回去 ⇒ 置顶 / 改名在前端排队依次发
test("s9 排队:后一个等前一个做完才开始;前一个失败不挡后一个;各自拿到自己的结果", async () => {
  const run = makeSerial();
  const log = [];
  const slow = run(async () => { log.push("1 开始"); await new Promise((r) => setTimeout(r, 30)); log.push("1 完"); return "一"; });
  const bad = run(async () => { log.push("2 开始"); throw new Error("坏了"); });
  const fast = run(async () => { log.push("3 开始"); log.push("3 完"); return "三"; });
  assert.equal(await slow, "一");
  await assert.rejects(bad, /坏了/);
  assert.equal(await fast, "三");
  assert.deepEqual(log, ["1 开始", "1 完", "2 开始", "3 开始", "3 完"]);
});
