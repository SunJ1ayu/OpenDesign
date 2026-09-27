// 业主同意卡:点完之后结果有没有送到助手、没送到告诉哪个聊天 —— track opendesign-consent-dock。
// 跑法:node --test tests/test_consent_notice.mjs
//
// 由来(PR #2 两轮本地审查,都是实机复现):
//   R1 助手等确认时点「停止」,再点「同意」:后端仍报 waiter=true(nanobot 不把取消传给 MCP),
//      前端只看 waiter ⇒ 不通知助手,对话卡住。
//   R2 修成"waiter 且任意聊天在跑"之后:首页停止 → 项目助手跑另一条 → 回首页点同意,
//      "项目助手在跑"被当成"这张卡有人接" ⇒ 又吞掉。
//   R3 修成"按聊天归属"之后:首页提 A → 停止 → 首页又提 B → 点 A 的旧卡:首页在跑的是 B 那一轮,
//      仍被当成"A 有人接" ⇒ 又吞掉。另:补话只说"点了同意",助手以为没办,拿同样参数又调一遍。
// ⇒ 按**卡片归属到"哪个聊天的哪一轮"**判;补话带上落盘结果并明说已生效。
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { ConsentOwners, consentNoticeText } from "../web/src/chat/consentNotice.ts";

const CARD = "20260926-120000-abcdef";

test("n1 提卡的聊天还在跑、工具在等 ⇒ 结果已作为工具返回值送到,不补话", () => {
  const o = new ConsentOwners();
  o.setBusy("home", true);
  o.observe([CARD]);
  assert.equal(o.delivered(CARD, true), true);
});

test("n2 🔴 R1:单聊点了停止(waiter 仍为 true)⇒ 没送到,告诉提卡的首页", () => {
  const o = new ConsentOwners();
  o.setBusy("home", true);
  o.observe([CARD]);
  o.setBusy("home", false);                       // ■ 停止
  assert.equal(o.delivered(CARD, true), false);
  assert.equal(o.target(CARD, "home"), "home");
});

test("n3 🔴 R2:首页停止 → 项目助手跑另一条 → 回首页点同意 ⇒ 没送到,告诉首页", () => {
  const o = new ConsentOwners();
  o.setBusy("home", true);
  o.observe([CARD]);                              // 卡在首页跑着时冒出来 ⇒ 归首页
  o.setBusy("home", false);                       // 首页 ■ 停止
  o.setBusy("workspace", true);                   // 项目助手开始跑别的事
  o.observe([CARD]);                              // 快拉照常进行,归属不许被改写
  assert.equal(o.delivered(CARD, true), false, "项目助手在跑 ≠ 这张卡有人接");
  assert.equal(o.target(CARD, "home"), "home");
  assert.equal(o.target(CARD, "workspace"), "home", "在项目助手里点的,也要告诉提卡的首页");
});

test("n4 卡冒出来时两个聊天都在跑(归属不明):只有全都还在跑才算送到", () => {
  const o = new ConsentOwners();
  o.setBusy("home", true);
  o.setBusy("workspace", true);
  o.observe([CARD]);
  assert.equal(o.delivered(CARD, true), true);
  o.setBusy("home", false);                       // 其中一个停了(可能正是提卡的那个)
  assert.equal(o.delivered(CARD, true), false, "分不清是谁提的 ⇒ 宁可多说一句");
  assert.equal(o.target(CARD, "todo"), "todo", "归属不唯一 ⇒ 告诉业主点卡的这个聊天");
});

test("n5 没有工具在等 / 归属不明(页面刚打开时看见的旧卡)⇒ 都算没送到", () => {
  const o = new ConsentOwners();
  o.observe([CARD]);                              // 看见时没有聊天在跑
  o.setBusy("home", true);
  assert.equal(o.delivered(CARD, true), false);
  assert.equal(o.delivered(CARD, false), false);
  assert.equal(o.delivered(CARD, undefined), false, "老后端不回 waiter ⇒ 按没人在等处理");
});

test("n6 卡被点掉(列表里消失)后归属清掉;同一 id 再出现按新的一轮记", () => {
  const o = new ConsentOwners();
  o.setBusy("home", true);
  o.observe([CARD]);
  o.observe([]);
  o.setBusy("home", false);
  o.setBusy("workspace", true);
  o.observe([CARD]);
  assert.equal(o.target(CARD, "home"), "workspace");
});

test("n7 替业主说的话写明点了什么、点的是哪张卡", () => {
  const t = "助手想把工作区根目录改成:D:\\设计";
  assert.match(consentNoticeText(t, true), /同意/);
  assert.match(consentNoticeText(t, false), /拒绝/);
  assert.ok(consentNoticeText(t, true).includes(t), "没有结果时至少说清是哪张卡");
});

test("n9 🔴 R3:同一个聊天停了又开新一轮 ⇒ 新一轮不是提卡的那一轮,照样告诉它", () => {
  const o = new ConsentOwners();
  o.setBusy("home", true);          // 第 1 轮:请求 A
  o.observe([CARD]);                // A 的卡归「首页第 1 轮」
  o.setBusy("home", false);         // ■ 停止
  o.setBusy("home", true);          // 第 2 轮:请求 B
  o.observe([CARD]);
  assert.equal(o.delivered(CARD, true), false, "首页在跑的是 B 那一轮,A 的结果没人接");
  assert.equal(o.target(CARD, "home"), "home");
});

test("n10 🔴 R3:补话带上落盘结果并明说已生效,助手别再拿同样参数申请一遍", () => {
  const t = "助手想把工作区根目录改成:D:\\设计";
  const ws = consentNoticeText(t, true, { ok: true, root: "D:\\设计", folder_count: 3 });
  assert.match(ws, /认出 3 个项目夹/);
  assert.match(ws, /已经生效/);
  assert.match(ws, /不用再调用工具/);
  const bind = consentNoticeText("x", true, { ok: true, project: "翡翠湾", folder: "2026:翡翠湾" });
  assert.match(bind, /翡翠湾」已经关联到文件夹「2026:翡翠湾/);
  assert.match(consentNoticeText(t, false), /什么都没改/);
  const src = readFileSync(new URL("../web/src/chat/ChatPage.tsx", import.meta.url), "utf-8");
  assert.match(src, /consentNoticeText\(.*,\s*res\.result\)/, "ChatPage 没把落盘结果交给补话");
});

test("n8 ChatPage 按卡片归属判断并把话送回提卡的聊天(不是只看 waiter / 任意聊天在跑)", () => {
  const src = readFileSync(new URL("../web/src/chat/ChatPage.tsx", import.meta.url), "utf-8");
  assert.match(src, /consentDelivered\(p\.pending_id,\s*res\.waiter\)/);
  assert.match(src, /deliverConsentNotice\(p\.pending_id,/);
  assert.match(src, /registerConsentNotice\(/);
  assert.doesNotMatch(src, /if \(res\.waiter\) return/, "R1 的旧判定还在");
  assert.doesNotMatch(src, /anyChatBusy/, "R2 的旧判定还在");
  const store = readFileSync(new URL("../web/src/chat/consentStore.ts", import.meta.url), "utf-8");
  assert.match(store, /owners\.observe\(/, "拉到卡片时没记归属");
  assert.match(store, /owners\.setBusy\(slot, false\)/, "聊天停止/结束时没登记");
});
