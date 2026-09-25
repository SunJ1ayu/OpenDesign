// oracle:聊天输入框照 ZCode 改五条 + 上一单两条欠账(track opendesign-composer-zcode)
// 跑法:node --test tests/test_composer_zcode.mjs(Node 22+,原生 strip-types)
//
// 五条(业主 09-25「就按你建议的来吧」同意的对照图):①「+」菜单 = 图片 + 三个技能 ② 打 / 弹同一份技能表
// ③ 模型按钮带厂商名 ④ 发送 ↑ / 回复中 ■ 停止 ⑤ 问候语按时间变;欠账 Q3′(改写过的英文小字不叫「原文」)、
// R1(“Stopped N task(s).” 等英文系统句不许原样上屏)。
// 停止相关样本 = 本单探针的**逐字**帧(tracks/opendesign-composer-zcode/evidence/20260925-probe-stop.txt):
// 真 nanobot 网关 + 本机假厂商,回复中发 /stop ⇒ goal_status:running(重发)→ goal_status:idle → 无 kind message
// “Stopped 1 task(s).”;**不发 stream_end / turn_end**;回放里半截回答是一条助手行、那句英文也是一条助手行。
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  SKILLS,
  applySkillPrefill,
  slashQuery,
  filterSkills,
  greetingFor,
  nextGreetingDelayMs,
} from "../web/src/chat/composerSkills.ts";
import { describeSystemNote } from "../web/src/chat/systemNote.ts";
import { describeModelError } from "../web/src/chat/modelError.ts";
import { modelChipLabel, modelChipVendor } from "../web/src/chat/modelPicker.ts";
import { inputPlaceholder, composerPlaceholder } from "../web/src/chat/inputHint.ts";
import {
  emptyTranscript,
  appendLocalUser,
  applyEvent,
  hydrateFromThread,
  requestStop,
} from "../web/src/chat/transcript.ts";
import { readFileSync } from "node:fs";

const byName = (n) => SKILLS.find((s) => s.name === n);

// ---- ① / ② 技能表一份 ----------------------------------------------------------

test("c1 技能表:三个技能、开头与技能页原来的一字不差;技能页 import 同一份(不许两份)", () => {
  assert.deepEqual(SKILLS.map((s) => s.name), ["记一下", "整理文件夹", "找参考图"]);
  assert.equal(byName("记一下").prefill, "记一下:");
  assert.equal(byName("整理文件夹").prefill, "帮我扫描整理这个文件夹:");
  assert.equal(byName("找参考图").prefill, "找参考图:");
  const page = readFileSync(new URL("../web/src/SkillsPage.tsx", import.meta.url), "utf8");
  assert.match(page, /from "\.\/chat\/composerSkills(\.ts)?"/, "技能页要从 composerSkills 取技能表");
  assert.doesNotMatch(page, /prefill:\s*"/, "技能页里不许再手写一份 prefill");
});

test("c2 点技能补开头:空草稿 / 有字 / 已是别的技能开头 ⇒ 只留一个开头,原文保留", () => {
  const note = byName("记一下"), ref = byName("找参考图"), org = byName("整理文件夹");
  assert.equal(applySkillPrefill("", note), "记一下:");
  assert.equal(applySkillPrefill("客厅改浅色", note), "记一下:客厅改浅色");
  assert.equal(applySkillPrefill("记一下:客厅改浅色", ref), "找参考图:客厅改浅色", "换开头,不叠两个");
  assert.equal(applySkillPrefill("记一下:客厅改浅色", note), "记一下:客厅改浅色", "同一个技能点两次不叠");
  assert.equal(applySkillPrefill("帮我扫描整理这个文件夹:D:/下载", note), "记一下:D:/下载");
  // 业主自己手打的全角冒号也认(老「记一下」按钮认的是「记一下」三个字开头)
  assert.equal(applySkillPrefill("记一下:沙发换色", org), "帮我扫描整理这个文件夹:沙发换色");
  assert.equal(applySkillPrefill("记一下：沙发换色", org), "帮我扫描整理这个文件夹:沙发换色");
  // 草稿整段就是 / 查询 ⇒ 整段换成开头(不把 “/参考” 留在后面)
  assert.equal(applySkillPrefill("/参考", ref), "找参考图:");
  assert.equal(applySkillPrefill("、参考", ref), "找参考图:");
});

test("c3 打 / 才弹:整段草稿以 / 开头且没有空白;中文标点模式的「、」与全角「/」同样算", () => {
  assert.equal(slashQuery("/"), "");
  assert.equal(slashQuery("/参考"), "参考");
  assert.equal(slashQuery("、"), "", "微软拼音中文标点模式下按 / 键打出的是「、」");
  assert.equal(slashQuery("、账本"), "账本");
  assert.equal(slashQuery("／"), "");
  assert.equal(slashQuery(""), null);
  assert.equal(slashQuery("客厅/餐厅"), null, "不在开头不弹");
  assert.equal(slashQuery("/参考 图"), null, "有空格 ⇒ 当普通话发");
  assert.equal(slashQuery("第一行\n/参考"), null, "第二行的 / 不弹");
  assert.equal(slashQuery("/参考\n"), null);
});

test("c4 按字筛:名字 / 缩写 / 关键词;筛不到 ⇒ 空表(页面据此不弹、Enter 照常发)", () => {
  const names = (q) => filterSkills(q).map((s) => s.name);
  assert.deepEqual(names(""), ["记一下", "整理文件夹", "找参考图"]);
  assert.deepEqual(names("参考"), ["找参考图"]);
  assert.deepEqual(names("记"), ["记一下"]);
  assert.deepEqual(names("账本"), ["记一下"], "业主说的是「记进账本」");
  assert.deepEqual(names("文件"), ["整理文件夹"]);
  assert.deepEqual(names("xyz"), []);
  assert.deepEqual(names("不存在"), []);
});

// ---- 占位字 ---------------------------------------------------------------------

test("c5 占位字:聊天输入框前半句各处保留,后缀换成「输入 / 选技能」;待办小框没有技能表,保持原样(4c C4)", () => {
  assert.equal(composerPlaceholder("聊设计、找参考"), "聊设计、找参考;输入 / 选技能");
  assert.equal(composerPlaceholder("问这个项目"), "问这个项目;输入 / 选技能");
  // 待办小框(TodoRail 的 rail-ask)是普通输入框,打 / 不弹表 ⇒ 它的占位字不许提「选技能」;原来那句照旧
  assert.equal(inputPlaceholder("问待办"), "问待办,或「记一下…」");
  const rail = readFileSync(new URL("../web/src/TodoRail.tsx", import.meta.url), "utf8");
  assert.doesNotMatch(rail, /composerPlaceholder/);
  const page = readFileSync(new URL("../web/src/chat/ChatPage.tsx", import.meta.url), "utf8");
  assert.match(page, /composerPlaceholder\("聊设计、找参考"\)/);
  assert.match(page, /composerPlaceholder\("问这个项目"\)/);
});

// ---- ③ 模型按钮带厂商名 -------------------------------------------------------------

const status = (provider, label, current = "m1") => ({ provider, label, current, models: [{ id: current, label: current }] });

test("c6 厂商短名:内置五家按 id 查表(GLM 两家分得开);自定义原样;拿不到列表 ⇒ 没有厂商名", () => {
  assert.equal(modelChipVendor(status("mimo", "MiMo(小米)"))?.short, "MiMo");
  assert.equal(modelChipVendor(status("deepseek", "DeepSeek 官方"))?.short, "DeepSeek 官方");
  assert.equal(modelChipVendor(status("kimi", "Kimi 按量"))?.short, "Kimi 按量");
  assert.equal(modelChipVendor(status("glm_plan", "GLM 套餐(Coding Plan)"))?.short, "GLM 套餐");
  assert.equal(modelChipVendor(status("glm", "GLM 按量"))?.short, "GLM 按量");
  // 自定义:括号里可能正是身份(4c C5)⇒ 原样
  const custom = modelChipVendor(status("custom_a1b2", "王工(测试)中转"));
  assert.equal(custom?.short, "王工(测试)中转");
  assert.equal(custom?.full, "王工(测试)中转");
  assert.equal(modelChipVendor(status("mimo", "MiMo(小米)"))?.full, "MiMo(小米)", "悬停看全名");
  assert.equal(modelChipVendor(null), null);
  assert.equal(modelChipVendor({ provider: null, label: null, current: null, models: [] }), null);
  // 模型名那一半照旧(老判据 mp 的语义不动)
  assert.equal(modelChipLabel(status("mimo", "MiMo(小米)", "mimo-v2.5"), "gw"), "mimo-v2.5");
  assert.equal(modelChipLabel(null, "gw"), "gw");
});

// ---- ④ 停止 ---------------------------------------------------------------------

// 探针逐字(mode=stream):stream_id 与 turn 编号照抄
const SID = "websocket:bafd84e7-6516-4daa-8251-8d51a8054a08:1790325181359819164:0";
const RUNNING = { event: "goal_status", status: "running", started_at: 1790325181.4111564 };
const IDLE = { event: "goal_status", status: "idle" };
const D0 = { event: "delta", text: "第0段。", stream_id: SID, turn_id: "turn-1", turn_phase: "answer", turn_seq: 2 };
const D1 = { event: "delta", text: "第1段。", stream_id: SID, turn_id: "turn-1", turn_phase: "answer", turn_seq: 3 };
const STOPPED = { event: "message", text: "Stopped 1 task(s).", turn_id: "stop-1", turn_phase: "answer", turn_seq: 1 };
const NOTHING = { event: "message", text: "No active task to stop.", turn_id: "stop-1", turn_phase: "answer", turn_seq: 1 };
const run = (s, evs) => evs.reduce(applyEvent, s);

function midStream() {
  let s = appendLocalUser(emptyTranscript, "讲个长故事", "local-1", undefined, "turn-1");
  return run(s, [RUNNING, D0, D1]);
}

test("c7 回复中点停止:网关回 idle ⇒ 解锁、收思考、半截回答定稿留着;那句英文变成中文系统小字", () => {
  let s = midStream();
  assert.equal(s.busy, true);
  assert.equal(s.messages.at(-1).streaming, true);
  s = requestStop(s, "stop-1");
  assert.equal(s.busy, true, "点了还没回话 ⇒ 仍在回复(不本地先解锁)");
  s = run(s, [RUNNING, IDLE]);
  assert.equal(s.busy, false, "idle 且本栏点过停止 ⇒ 这一轮算完(网关不发 turn_end)");
  assert.equal(s.thinking, false);
  const half = s.messages.find((m) => m.id === SID);
  assert.equal(half.content, "第0段。第1段。");
  assert.equal(half.streaming, false, "半截回答定稿,不再挂着流式光标");
  s = applyEvent(s, STOPPED);
  const last = s.messages.at(-1);
  assert.equal(last.systemNote, true, "停止回话是系统小字,不是一条助手回复");
  assert.match(last.content, /已停止/);
  assert.match(last.content, /可能已(经)?做完/, "停在记账 / 挪文件中间时,那一步可能已经做了(QA Gemini)");
  assert.doesNotMatch(last.content, /[A-Za-z]/, "不许冒英文");
  assert.equal(s.messages.filter((m) => m.role === "user").length, 1, "不上屏一条 /stop 用户气泡");
});

test("c8 回话先于 idle 到(时序变了)⇒ 同样解锁;同一帧收两次只一条小字", () => {
  let s = requestStop(midStream(), "stop-1");
  s = run(s, [STOPPED, STOPPED]);
  assert.equal(s.busy, false);
  assert.equal(s.messages.at(-1).streaming, false);
  assert.equal(s.messages.filter((m) => m.systemNote).length, 1);
  s = applyEvent(s, IDLE);
  assert.equal(s.busy, false);
});

test("c9 没点过停止时,idle 不解锁(正常回复只认 turn_end —— 4c C2)", () => {
  let s = run(midStream(), [IDLE]);
  assert.equal(s.busy, true, "别处来的 idle 不许提前解锁:业主会在回复中途插话");
  assert.equal(s.messages.at(-1).streaming, true);
});

test("c10 还没出字(还在想)就停 ⇒ 解锁、收思考,没有空助手气泡", () => {
  let s = appendLocalUser(emptyTranscript, "讲个长故事", "local-1", undefined, "turn-1");
  s = run(s, [RUNNING]);
  assert.equal(s.thinking, true);
  s = run(requestStop(s, "stop-1"), [RUNNING, IDLE, STOPPED]);
  assert.equal(s.busy, false);
  assert.equal(s.thinking, false);
  assert.equal(s.messages.filter((m) => m.role === "assistant" && !m.systemNote).length, 0);
  assert.match(s.messages.at(-1).content, /已停止/);
});

test("c11 停止和刚好说完撞上:turn_end 先到 ⇒ 正常结束;随后「没有在进行的」⇒ 中文小字,不改已完成的回答", () => {
  let s = requestStop(midStream(), "stop-1");
  s = run(s, [
    { event: "stream_end", stream_id: SID, turn_id: "turn-1", turn_seq: 4 },
    { event: "turn_end", turn_id: "turn-1", turn_phase: "complete", turn_seq: 5 },
    NOTHING,
  ]);
  assert.equal(s.busy, false);
  assert.equal(s.messages.find((m) => m.id === SID).content, "第0段。第1段。");
  const last = s.messages.at(-1);
  assert.equal(last.systemNote, true);
  assert.match(last.content, /说完/);
  assert.doesNotMatch(last.content, /[A-Za-z]/);
});

test("c12 不在回复时 requestStop 不改任何状态(按钮本来就不该在)", () => {
  assert.deepEqual(requestStop(emptyTranscript, "stop-1"), emptyTranscript);
});

test("c13 回放(切走再回来 / 重开):同一句中文,与实时逐字相同;半截回答是普通回答", () => {
  // 探针 mode=stream 回放逐字
  const replay = hydrateFromThread({ messages: [
    { id: "u-0-8f23c297", role: "user", content: "讲个长故事", turnId: "turn-1", turnPhase: "user", turnSeq: 1, createdAt: 1790325192815 },
    { id: "buf-1-45a1ec93", role: "assistant", content: "第0段。第1段。", isStreaming: false, turnId: "turn-1", turnPhase: "answer", turnSeq: 3, createdAt: 1790325192816 },
    { id: "as-3-3b8730fb", role: "assistant", createdAt: 1790325192818, content: "Stopped 1 task(s).", turnId: "turn-stop", turnPhase: "answer", turnSeq: 1 },
    { id: "as-0-94865422", role: "assistant", createdAt: 1790325374379, content: "No active task to stop.", turnId: "turn-stop", turnPhase: "answer", turnSeq: 1 },
  ] });
  const [, half, stopped, nothing] = replay.messages;
  assert.equal(half.content, "第0段。第1段。");
  assert.ok(!half.systemNote);
  let live = applyEvent(requestStop(midStream(), "stop-1"), STOPPED);
  assert.equal(stopped.systemNote, true);
  assert.equal(stopped.content, live.messages.at(-1).content, "实时 = 回放");
  assert.equal(nothing.systemNote, true);
  assert.doesNotMatch(stopped.content + nothing.content, /[A-Za-z]/);
});

test("c14 R1:子任务空回报 “Background task completed.” 实时 / 回放都是中文小字;别的句子不误伤", () => {
  assert.match(describeSystemNote("Background task completed."), /后台/);
  assert.match(describeSystemNote("Stopped 3 task(s)."), /已停止/);
  assert.equal(describeSystemNote("Stopped 1 task(s). 然后我们继续聊客厅"), null, "只认整句");
  assert.equal(describeSystemNote("好的,已停止施工"), null);
  let s = applyEvent(emptyTranscript, { event: "message", text: "Background task completed." });
  assert.equal(s.messages[0].systemNote, true);
  const r = hydrateFromThread({ messages: [{ id: "a1", role: "assistant", content: "Background task completed." }] });
  assert.equal(r.messages[0].content, s.messages[0].content);
});

// ---- 欠账 Q3′ ----------------------------------------------------------------------

test("c15 Q3′:网关换过的固定英文 ⇒ 小字不叫「原文」;真透传的仍叫「原文」", () => {
  const arrears = "The AI provider rejected the request because the API key is out of quota or the account is in arrears. Please top up / check the billing status of your API key and try again.";
  const glm1113 = "Error: {'code': '1113', 'message': '余额不足或无可用资源包,请充值。'}";
  const a = describeModelError(arrears);
  assert.ok(a && a.rawLabel && a.rawLabel !== "原文", `欠费固定句的小字标签:${a?.rawLabel}`);
  assert.match(a.rawLabel, /聊天服务/);
  assert.equal(describeModelError(glm1113)?.rawLabel, "原文");
  assert.equal(describeModelError("Error: {'message': 'Invalid API key', 'type': 'invalid_request_error'}")?.rawLabel, "原文");
});

test("c16 D2:key 错那句指到右下角的新写法(厂商名 + 模型名)", () => {
  const k = describeModelError("Error: {'message': 'Invalid API key', 'type': 'invalid_request_error'}");
  assert.match(k.text, /右下角/);
  assert.match(k.text, /哪家/, "按钮上现在写着厂商名,说明要对得上");
});

// ---- ⑤ 问候语 -------------------------------------------------------------------------

const at = (h, m = 0) => new Date(2026, 8, 25, h, m, 0);

test("c17 问候语六档(分界照 ZCode 5/9/12/14/18/23),措辞照对照图", () => {
  const g = (h, m) => greetingFor(at(h, m));
  assert.equal(g(4, 59), "夜深了,还在忙吗?");
  assert.equal(g(5, 0), "早上好,今天想聊点什么?");
  assert.equal(g(8, 59), "早上好,今天想聊点什么?");
  assert.equal(g(9, 0), "上午好,今天想聊点什么?");
  assert.equal(g(11, 59), "上午好,今天想聊点什么?");
  assert.equal(g(12, 0), "中午好,今天想聊点什么?");
  assert.equal(g(13, 59), "中午好,今天想聊点什么?");
  assert.equal(g(14, 0), "下午好,今天想聊点什么?");
  assert.equal(g(17, 59), "下午好,今天想聊点什么?");
  assert.equal(g(18, 0), "晚上好,今天想聊点什么?");
  assert.equal(g(22, 59), "晚上好,今天想聊点什么?");
  assert.equal(g(23, 0), "夜深了,还在忙吗?");
});

test("c18 窗口开着过分界自动换:到下一个分界点的毫秒数", () => {
  assert.equal(nextGreetingDelayMs(at(13, 30)), 30 * 60 * 1000);
  assert.equal(nextGreetingDelayMs(at(23, 30)), 5.5 * 3600 * 1000, "跨零点到早上 5 点");
  assert.equal(nextGreetingDelayMs(at(14, 0)), 4 * 3600 * 1000, "正好在分界上 ⇒ 下一个分界");
});
