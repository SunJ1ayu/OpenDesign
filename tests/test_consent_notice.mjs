// 业主同意卡:点完之后要不要在对话里替业主告诉助手 —— track opendesign-consent-dock。
// 跑法:node --test tests/test_consent_notice.mjs
//
// 由来:PR #2 本地审查实机复现 —— 助手等确认时点「停止」,再点「同意」,工作区已改,
// 但后端仍报 waiter=true(nanobot 不把取消传给 MCP 进程,那次工具调用还在等),
// 前端据此不通知助手,对话就此卡住。判定改成 waiter **且** 有聊天在跑。
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { consentNoticeText, shouldTellAssistant } from "../web/src/chat/consentNotice.ts";

test("n1 有工具在等、且有聊天在跑 ⇒ 结果已作为工具返回值送到,不再补话", () => {
  assert.equal(shouldTellAssistant(true, true), false);
});

test("n2 🔴 点了停止之后(工具还在傻等 waiter=true,但没有聊天在跑)⇒ 必须告诉助手", () => {
  assert.equal(shouldTellAssistant(true, false), true);
});

test("n3 没有工具在等(超时 / 早先留下的卡)⇒ 告诉助手,不管有没有别的聊天在跑", () => {
  assert.equal(shouldTellAssistant(false, false), true);
  assert.equal(shouldTellAssistant(false, true), true);
  assert.equal(shouldTellAssistant(undefined, true), true, "老后端不回 waiter ⇒ 按没人在等处理");
});

test("n4 替业主说的话写明点了什么、点的是哪张卡", () => {
  const t = "助手想把工作区根目录改成:D:\\设计";
  assert.match(consentNoticeText(t, true), /同意/);
  assert.match(consentNoticeText(t, false), /拒绝/);
  assert.ok(consentNoticeText(t, true).includes(t));
});

test("n5 ChatPage 真的用了这两个条件(不是只看 res.waiter)", () => {
  const src = readFileSync(new URL("../web/src/chat/ChatPage.tsx", import.meta.url), "utf-8");
  assert.match(src, /shouldTellAssistant\(res\.waiter,\s*anyChatBusy\(\)\)/);
  assert.doesNotMatch(src, /if \(res\.waiter\) return/, "旧判定(只看 waiter)还在");
});
