// track opendesign-due-picker T3 oracle:左栏项目按**阶段**分堆的纯逻辑。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// 用户 07-28 拍板:左栏按**阶段**分堆折叠(不是"只折已交付",也不是按硬盘文件夹)。
// 契约(web/src/workspace/projectGroups.ts):
//   ① groupProjectsByStage(projects, stages) —— 按词表顺序分堆,空堆不出现,
//      堆内保持传入相对序;词表外的非空阶段(手改坏的档案头)各自成堆、排在词表堆之后;
//      空阶段(未建档/头部没有「- 阶段:」)统一进最后一堆「未建档」。
//      **不许丢项目**:各堆项目数之和恒等于传入数。
//   ② isStageGroupOpen(group, prefs) —— prefs 有显式值就听用户的;没有则
//      "整堆都已交付 → 默认收起",其余默认展开(已交付最占地方,这是分堆的由来)。
//   ③ loadStagePrefs(raw) —— 容错解析 localStorage 原文(坏 JSON/非对象/非布尔值一律丢)。
//      折叠状态**必须落盘**:待办页的 toggled 是 useState、刷新即忘,这条不许重蹈。
//   ④ revealStage(prefs, group) —— 选中项目时把它所在的堆展开。**返回新对象才算变**,
//      当前已是展开态要原样返回(否则 effect 里会自己把自己叫醒,写盘写不停)。
//      判"当前开没开"要走 ②:传 stage 字符串不够 —— 已交付堆默认收起,没存过偏好
//      不等于开着,那样选中一个已交付项目会看不见自己。
//      注意是 effect 语义、不是渲染期覆盖:渲染期强制展开会让那个堆的折叠键点了没反应。
//
// red-check:实现前 web/src/workspace/projectGroups.ts 不存在,本文件整体红。
// 跑法:node --test tests/test_project_groups.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  groupProjectsByStage,
  isStageGroupOpen,
  loadStagePrefs,
  revealStage,
  UNSTAGED_LABEL,
  SIDE_STAGE_STORAGE_KEY,
} from "../web/src/workspace/projectGroups.ts";

// 后端词表(ds_tools.PROJECT_STAGES)的副本只在判据里出现:前端从 /api/projects
// 的 stages 拿,不许硬编码 —— 所以这里当"外部输入"传进去。
const STAGES = ["洽谈", "量房", "平面方案", "方案深化", "效果图", "施工图",
                "施工交底", "施工跟进", "软装", "竣工验收", "售后"];

const p = (key, stage, delivered = false) => ({
  key, name: key, stage, delivered, open_count: 0,
});
const shape = (groups) => groups.map((g) => [g.stage, g.projects.map((x) => x.key)]);

test("groupProjectsByStage:按词表顺序分堆,空堆不出现", () => {
  const got = groupProjectsByStage(
    [p("B", "施工跟进"), p("A", "效果图"), p("C", "洽谈")],
    STAGES,
  );
  assert.deepEqual(shape(got), [["洽谈", ["C"]], ["效果图", ["A"]], ["施工跟进", ["B"]]]);
});

test("groupProjectsByStage:堆内保持传入相对序", () => {
  const got = groupProjectsByStage(
    [p("B", "效果图"), p("A", "效果图"), p("C", "效果图")],
    STAGES,
  );
  assert.deepEqual(shape(got), [["效果图", ["B", "A", "C"]]]);
});

test("groupProjectsByStage:空阶段进最后一堆「未建档」", () => {
  const got = groupProjectsByStage([p("U", ""), p("A", "效果图")], STAGES);
  assert.deepEqual(shape(got), [["效果图", ["A"]], [UNSTAGED_LABEL, ["U"]]]);
});

test("groupProjectsByStage:stage 缺失(undefined)也当未建档,不崩", () => {
  const got = groupProjectsByStage([{ key: "U", name: "U" }, p("A", "效果图")], STAGES);
  assert.deepEqual(shape(got), [["效果图", ["A"]], [UNSTAGED_LABEL, ["U"]]]);
});

test("groupProjectsByStage:词表外的非空阶段自成一堆,按首次出现序排在词表堆之后", () => {
  const got = groupProjectsByStage(
    [p("X", "打样"), p("A", "效果图"), p("Y", "回访"), p("X2", "打样"), p("U", "")],
    STAGES,
  );
  assert.deepEqual(shape(got), [
    ["效果图", ["A"]],
    ["打样", ["X", "X2"]],
    ["回访", ["Y"]],
    [UNSTAGED_LABEL, ["U"]],
  ]);
});

test("groupProjectsByStage:一个项目都不丢(总数守恒)", () => {
  const input = [p("A", "效果图"), p("B", "施工跟进"), p("C", "打样"), p("D", ""),
                 p("E", "效果图"), p("F", "售后", true)];
  const got = groupProjectsByStage(input, STAGES);
  const flat = got.flatMap((g) => g.projects.map((x) => x.key));
  assert.equal(flat.length, input.length);
  assert.deepEqual([...flat].sort(), input.map((x) => x.key).sort());
});

test("groupProjectsByStage:空列表 → 空数组(不造空堆)", () => {
  assert.deepEqual(groupProjectsByStage([], STAGES), []);
});

test("groupProjectsByStage:词表为空(接口没给)也不丢项目,按首次出现序", () => {
  const got = groupProjectsByStage([p("B", "施工跟进"), p("A", "效果图")], []);
  assert.deepEqual(shape(got), [["施工跟进", ["B"]], ["效果图", ["A"]]]);
});

// ── 默认展开/收起 ───────────────────────────────────────────────────────────
const grp = (stage, projects) => ({ stage, projects });

test("isStageGroupOpen:没存过偏好 → 默认展开", () => {
  assert.equal(isStageGroupOpen(grp("效果图", [p("A", "效果图")]), {}), true);
});

test("isStageGroupOpen:整堆都已交付 → 默认收起(已交付最占地方)", () => {
  const g = grp("竣工验收", [p("A", "竣工验收", true), p("B", "竣工验收", true)]);
  assert.equal(isStageGroupOpen(g, {}), false);
});

test("isStageGroupOpen:堆里还有没交付的 → 仍默认展开", () => {
  const g = grp("竣工验收", [p("A", "竣工验收", true), p("B", "竣工验收", false)]);
  assert.equal(isStageGroupOpen(g, {}), true);
});

test("isStageGroupOpen:空堆不算「都已交付」,默认展开(every 对空数组为真的坑)", () => {
  assert.equal(isStageGroupOpen(grp("售后", []), {}), true);
});

test("isStageGroupOpen:存过偏好就听用户的(压过默认,两个方向都要)", () => {
  const done = grp("售后", [p("A", "售后", true)]);
  const live = grp("效果图", [p("B", "效果图")]);
  assert.equal(isStageGroupOpen(done, { 售后: true }), true);
  assert.equal(isStageGroupOpen(live, { 效果图: false }), false);
});

test("isStageGroupOpen:别的堆的偏好不串台", () => {
  const g = grp("效果图", [p("A", "效果图")]);
  assert.equal(isStageGroupOpen(g, { 售后: false }), true);
});

// ── 偏好落盘 ────────────────────────────────────────────────────────────────
test("SIDE_STAGE_STORAGE_KEY:键名锁死(改名 = 所有人的折叠状态丢一次)", () => {
  assert.equal(SIDE_STAGE_STORAGE_KEY, "ds.side.stageOpen");
});

test("loadStagePrefs:正常 JSON 原样读回", () => {
  assert.deepEqual(loadStagePrefs('{"售后":true,"效果图":false}'),
                   { 售后: true, 效果图: false });
});

test("loadStagePrefs:null / 坏 JSON / 非对象 / 数组 → 空表,不抛", () => {
  for (const raw of [null, "", "{", "3", '"x"', "null", "[1,2]"]) {
    assert.deepEqual(loadStagePrefs(raw), {}, `raw=${JSON.stringify(raw)}`);
  }
});

test("loadStagePrefs:非布尔值剔除,同一份里的好值留下", () => {
  assert.deepEqual(loadStagePrefs('{"a":true,"b":"yes","c":1,"d":null,"e":false}'),
                   { a: true, e: false });
});

// ── 选中即展开 ──────────────────────────────────────────────────────────────
const doneGrp = grp("售后", [p("A", "售后", true)]);
const liveGrp = grp("效果图", [p("B", "效果图")]);

test("revealStage:用户手动收起的堆里点中项目 → 展开(新对象)", () => {
  const prefs = { 售后: false };
  const got = revealStage(prefs, doneGrp);
  assert.deepEqual(got, { 售后: true });
  assert.notEqual(got, prefs, "变了就要给新对象,否则 React 看不见");
});

test("revealStage:默认收起的已交付堆里点中项目 → 也要展开(没存过偏好 ≠ 开着)", () => {
  assert.deepEqual(revealStage({}, doneGrp), { 售后: true });
});

test("revealStage:已经展开(显式 true)→ 原样返回,不制造无谓写盘", () => {
  const prefs = { 售后: true };
  assert.equal(revealStage(prefs, doneGrp), prefs);
});

test("revealStage:默认就展开的堆 → 原样返回,不必写", () => {
  const prefs = {};
  assert.equal(revealStage(prefs, liveGrp), prefs);
});

test("revealStage:不动别的堆", () => {
  assert.deepEqual(revealStage({ 售后: false, 效果图: false }, doneGrp),
                   { 售后: true, 效果图: false });
});

test("revealStage:未建档堆(词表外的堆名)也照常展开", () => {
  const g = grp(UNSTAGED_LABEL, [p("U", "")]);
  assert.deepEqual(revealStage({ [UNSTAGED_LABEL]: false }, g),
                   { [UNSTAGED_LABEL]: true });
});
