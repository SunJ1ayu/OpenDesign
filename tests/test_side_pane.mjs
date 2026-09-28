// 项目页右侧面板(照 ZCode Side Pane)的纯逻辑 + 结构判据。
// 真键盘 / 拖宽 / 同意卡自动切过去的整链在 tests/e2e/side_pane.e2e.mjs。
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  clampRatio, parseSidePane, revealAssistant, SIDE_PANE_DEFAULT, SIDE_PANE_MAX_RATIO, SIDE_PANE_MIN_PX,
} from "../web/src/workspace/sidePane.ts";

const read = (p) => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");

test("s1 默认:开着、停在「项目助手」(主交互 + 同意卡在这)、占 45%(照 ZCode SIDE_PANE_DEFAULT_EXPANDED_RATIO)", () => {
  assert.deepEqual(SIDE_PANE_DEFAULT, { open: true, tab: "assistant", ratio: 0.45 });
  assert.equal(SIDE_PANE_MAX_RATIO, 0.65);
});

test("s2 宽度夹在 [最窄像素, 65%]:拖太宽 / 太窄都拉回来;坏值回默认", () => {
  assert.equal(clampRatio(0.9, 1000), 0.65);
  assert.equal(clampRatio(0.05, 1000), SIDE_PANE_MIN_PX / 1000);
  assert.equal(clampRatio(0.5, 1000), 0.5);
  assert.equal(clampRatio(NaN, 1000), 0.45);
  // 宿主很窄时,最窄像素换算出来超过 65% ⇒ 以 65% 为准,不能反过来撑破
  assert.equal(clampRatio(0.3, 300), 0.65);
});

test("s3 记在本机的状态读回来:坏 JSON / 缺字段 / 乱值都回默认,不崩", () => {
  assert.deepEqual(parseSidePane(null), SIDE_PANE_DEFAULT);
  assert.deepEqual(parseSidePane("{oops"), SIDE_PANE_DEFAULT);
  assert.deepEqual(parseSidePane('{"open":false,"tab":"assistant","ratio":0.5}'),
    { open: false, tab: "assistant", ratio: 0.5 });
  assert.deepEqual(parseSidePane('{"open":"yes","tab":"x","ratio":9}'),
    { open: true, tab: "assistant", ratio: 0.65 });
});

test("s4 🔴 有事要看项目助手 ⇒ 面板打开并切到「项目助手」;已经在那里就原样返回(不触发多余的存盘)", () => {
  assert.deepEqual(revealAssistant({ open: false, tab: "files", ratio: 0.5 }),
    { open: true, tab: "assistant", ratio: 0.5 });
  const already = { open: true, tab: "assistant", ratio: 0.4 };
  assert.equal(revealAssistant(already), already);
});

test("s5 🔴 keep-mounted:面板收起 / 切标签只走 CSS 隐藏,两个标签页都始终渲染(卸载 = 丢对话)", () => {
  const sp = read("web/src/workspace/SidePane.tsx");
  assert.match(sp, /className=\{`side-pane\$\{open \? "" : " route-hidden"\}`\}/);
  assert.match(sp, /className=\{`spane-panel\$\{tab === "files" \? "" : " route-hidden"\}`\}/);
  assert.match(sp, /className=\{`spane-panel\$\{tab === "assistant" \? "" : " route-hidden"\}`\}/);
  assert.doesNotMatch(sp, /\{open && /, "不许按 open 条件渲染");
  assert.doesNotMatch(sp, /tab === "(files|assistant)" && /, "不许按标签条件渲染");
});

test("s6 🔴 往项目助手发话 / 它冒出同意卡,都会把面板切过去", () => {
  const app = read("web/src/App.tsx");
  const dispatch = app.slice(app.indexOf("const dispatchCol = useCallback"), app.indexOf("}, [showAssistant]);"));
  assert.match(dispatch, /showAssistant\(\)/, "dispatchCol 没切面板");
  assert.match(app, /onConsentPending=\{showAssistant\}/, "同意卡没接到面板");
  const chat = read("web/src/chat/ChatPage.tsx");
  assert.match(chat, /if \(hasConsent\) onConsentPending\?\.\(\)/);
  // 面板收着时同意卡仍要参与(不能因为看不见就不拉卡 —— 那样永远不会切过去)
  const col = read("web/src/workspace/ChatColumn.tsx");
  assert.match(col, /consentActive=\{inboxActive\}/);
});

test("s7 开关与标签的无障碍:开关 aria-expanded / aria-controls;标签是 tablist + roving tabindex", () => {
  const app = read("web/src/App.tsx");
  assert.match(app, /data-ui="side-pane-toggle"[\s\S]{0,200}aria-controls="ws-side-pane"[\s\S]{0,60}aria-expanded=\{sidePane\.open\}/);
  const sp = read("web/src/workspace/SidePane.tsx");
  assert.match(sp, /role="tablist"/);
  assert.match(sp, /tabIndex=\{i === cur \? 0 : -1\}/);
  assert.match(sp, /role="separator"/);
});
