// T5 oracle:聊天流式渲染的纯逻辑层 + markdown 安全渲染
// 跑法:node --test tests/test_chat_transcript.mjs(Node 22+,原生 strip-types)
// 依据 = docs/nanobot-ws-protocol.md §2(T0 实抓)+ design.md D-C3:
//   出站信封一律 webui:true + turn_id;
//   delta 按 stream_id 归组拼接 → stream_end 定稿 → turn_end 收尾解锁输入;
//   reasoning_* / tool_hint / progress / 未知事件安全降级(忽略不崩);
//   markdown 禁 raw HTML(渲染为文本不执行,oracle #4 焊死不靠自觉);
//   Enter 发送必须查 isComposing(+keyCode 229 兜底)——中文输入法。
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  emptyTranscript,
  appendLocalUser,
  applyEvent,
  messageEnvelope,
  shouldSendOnEnter,
} from "../web/src/chat/transcript.ts";
import { renderMarkdown } from "../web/src/chat/markdown.ts";
// react-dom 只装在 web/ 下(前端依赖不上提仓根),从 web/ 解析
import { createRequire } from "node:module";
const { renderToStaticMarkup } = createRequire(
  new URL("../web/", import.meta.url),
)("react-dom/server");

// ---- 出站信封 ----------------------------------------------------------

test("messageEnvelope:webui:true + turn_id 一等路径(协议 §2 入站)", () => {
  const env = messageEnvelope("chat-1", "你好", "turn-1");
  assert.deepEqual(env, {
    type: "message",
    chat_id: "chat-1",
    content: "你好",
    webui: true,
    turn_id: "turn-1",
  });
});

// ---- 本地上屏 + 锁输入 --------------------------------------------------

test("appendLocalUser:用户消息上屏 + busy 锁输入;原 state 不被改动", () => {
  const s0 = emptyTranscript;
  const s1 = appendLocalUser(s0, "记一下:张三要改玄关", "u-1");
  assert.equal(s1.messages.length, 1);
  assert.deepEqual(s1.messages[0], {
    id: "u-1",
    role: "user",
    content: "记一下:张三要改玄关",
    streaming: false,
  });
  assert.equal(s1.busy, true);
  // 纯函数:emptyTranscript 不被原地污染
  assert.equal(s0.messages.length, 0);
  assert.equal(s0.busy, false);
});

// ---- delta 归组拼接 -----------------------------------------------------

const delta = (streamId, text) => ({
  event: "delta",
  stream_id: streamId,
  text,
  turn_id: "t-1",
  turn_phase: "answer",
  turn_seq: 8,
});

test("delta:首个 delta 建 assistant 消息(streaming),后续按 stream_id 追加", () => {
  let s = appendLocalUser(emptyTranscript, "hi", "u-1");
  s = applyEvent(s, delta("ws:c:1:0", "收到"));
  s = applyEvent(s, delta("ws:c:1:0", "收到"));
  assert.equal(s.messages.length, 2);
  const a = s.messages[1];
  assert.equal(a.role, "assistant");
  assert.equal(a.content, "收到收到");
  assert.equal(a.streaming, true);
});

test("delta:不同 stream_id 各自归组,互不串流", () => {
  let s = emptyTranscript;
  s = applyEvent(s, delta("s-a", "甲"));
  s = applyEvent(s, delta("s-b", "乙"));
  s = applyEvent(s, delta("s-a", "甲"));
  const contents = s.messages.map((m) => m.content);
  assert.deepEqual(contents, ["甲甲", "乙"]);
});

// ---- stream_end 定稿 / turn_end 收尾 ------------------------------------

test("stream_end:按 stream_id 定稿(streaming=false),不动别的流", () => {
  let s = emptyTranscript;
  s = applyEvent(s, delta("s-a", "甲"));
  s = applyEvent(s, delta("s-b", "乙"));
  s = applyEvent(s, { event: "stream_end", stream_id: "s-a", turn_seq: 9 });
  assert.equal(s.messages[0].streaming, false);
  assert.equal(s.messages[1].streaming, true);
});

test("turn_end:解锁输入 + 兜底定稿所有仍 streaming 的消息", () => {
  let s = appendLocalUser(emptyTranscript, "hi", "u-1");
  s = applyEvent(s, delta("s-a", "回复"));
  s = applyEvent(s, {
    event: "turn_end",
    latency_ms: 3390,
    goal_state: { active: false },
    turn_phase: "complete",
    turn_seq: 10,
  });
  assert.equal(s.busy, false);
  assert.equal(s.messages[1].streaming, false);
});

// ---- 安全降级:协议会长,未知的不崩 -------------------------------------

// ⚠️ 2026-08-04 改题面(track opendesign-chat-reconnect / T5b),说明为什么:
// 这条原本断言 reasoning_delta / goal_status / message(tool_hint|progress) **全部忽略**。
// 那是 T5 期「本期不做」的记录,不是产品该有的样子 —— 实测正是这四类事件被丢掉,
// 才让"发出去到出字"的几十秒里界面完全没有反应(看着像卡死)。
// 本单**故意**让其中三类产生可见反馈 ⇒ 旧断言与新规格直接冲突,必须改。
// 按规矩「断言要搬到问得出的地方、而且更强」:
//   - 仍然该忽略的(session_updated / 未知事件)留在这条,一字不放松;
//   - 三类新行为搬进下面 §T5b 的专门用例,断言比原来强得多(还断言了不许出现什么)。
// 另记一笔:旧断言里的 tool_hint 样本写的是 `{kind:"tool_hint", content:"调工具中"}`
// —— **那个形状是当时凭空想的**,真帧里没有 `content` 这个键(实抓见
// docs/nanobot-ws-protocol.md §2)。新用例一律用实抓样本。
test("session_updated / 未知事件仍然一律忽略,state 原样(老约定不许退化)", () => {
  const s1 = applyEvent(emptyTranscript, { event: "session_updated", scope: "thread" });
  const s2 = applyEvent(s1, { event: "将来才有的新事件" });
  const s3 = applyEvent(s2, { event: "reasoning_end", turn_seq: 7 });
  assert.deepEqual(s3, emptyTranscript);
});

// ---- §T5b 助手干活时的界面反馈(判据按 2026-08-04 实抓的真帧写)-----------

// 实抓样本(docs/nanobot-ws-protocol.md §2;原始帧存 track 的 evidence/):
// text 是空串、没有 content 键、有信息的是 tool_events[].name,phase 只见过 end。
const REAL_PROGRESS_FRAME = {
  event: "message",
  kind: "progress",
  chat_id: "<uuid>",
  turn_id: "<uuid>",
  turn_phase: "activity",
  turn_seq: 23,
  text: "",
  tool_events: [
    {
      version: 1,
      phase: "end",
      call_id: "<call_…>",
      name: "mcp_design-studio_list_todos_tool",
      arguments: { stale_days: 7 },
      result: "{…}",
      error: null,
      files: [],
      embeds: [],
    },
  ],
};

test("等待态:goal_status:running 与 reasoning_delta 都开启「正在思考」", () => {
  const a = applyEvent(emptyTranscript, { event: "goal_status", status: "running" });
  assert.equal(a.thinking, true);
  const b = applyEvent(emptyTranscript, {
    event: "reasoning_delta", text: "思考中", turn_phase: "reasoning",
  });
  assert.equal(b.thinking, true, "等待期间真正在流的就是它,忽略它 = 界面死着");
});

test("等待态:第一个答案 delta 一到就关掉(别和正文一起挂着)", () => {
  let s = applyEvent(emptyTranscript, { event: "goal_status", status: "running" });
  s = applyEvent(s, { event: "delta", stream_id: "s1", text: "你好" });
  assert.equal(s.thinking, false);
  assert.equal(s.messages.length, 1);
});

test("等待态:turn_end 收尾一定关掉(哪怕一个 delta 都没来过)", () => {
  let s = applyEvent(emptyTranscript, { event: "goal_status", status: "running" });
  s = applyEvent(s, { event: "turn_end", latency_ms: 1 });
  assert.equal(s.thinking, false);
});

test("reasoning 正文一个字都不许进气泡(那是没定稿的草稿,不是给用户看的结论)", () => {
  const s = applyEvent(emptyTranscript, {
    event: "reasoning_delta", text: "用户可能是想问…先假设他要的是 X", turn_phase: "reasoning",
  });
  assert.deepEqual(s.messages, []);
  assert.ok(!JSON.stringify(s.messages).includes("先假设"));
});

test("活动回执:真帧 ⇒ 落一条人话,且**不进 messages[] 气泡**", () => {
  const s = applyEvent(emptyTranscript, REAL_PROGRESS_FRAME);
  assert.deepEqual(s.messages, [], "工具回执是临时行,不是对话内容");
  assert.equal(s.activity.length, 1);
  assert.equal(s.activity[0], "查了待办清单");
});

test("活动回执:认不出的工具名 ⇒ 通用文案,**绝不把工具原名甩给机主**", () => {
  const frame = {
    ...REAL_PROGRESS_FRAME,
    tool_events: [{ ...REAL_PROGRESS_FRAME.tool_events[0], name: "mcp_design-studio_某个新工具_tool" }],
  };
  const s = applyEvent(emptyTranscript, frame);
  assert.equal(s.activity.length, 1);
  const line = s.activity[0];
  assert.ok(!line.includes("mcp_"), `不许出现原始工具名:${line}`);
  assert.ok(!line.includes("_tool"), `不许出现原始工具名:${line}`);
  assert.ok(line.length > 0);
});

test("活动回执:kind:\"tool_hint\" 同样收下(本轮没抓到,但不许因此崩)", () => {
  const s = applyEvent(emptyTranscript, { ...REAL_PROGRESS_FRAME, kind: "tool_hint" });
  assert.equal(s.activity.length, 1);
});

test("活动回执:一轮里多次调工具 ⇒ 按顺序累积,不去重成一条", () => {
  let s = applyEvent(emptyTranscript, REAL_PROGRESS_FRAME);
  s = applyEvent(s, REAL_PROGRESS_FRAME);
  assert.equal(s.activity.length, 2);
});

test("活动回执:turn_end 清空(下一轮不该顶着上一轮的尾巴)", () => {
  let s = applyEvent(emptyTranscript, REAL_PROGRESS_FRAME);
  s = applyEvent(s, { event: "turn_end", latency_ms: 1 });
  assert.deepEqual(s.activity, []);
});

test("活动回执:畸形 tool_events 一律不崩、不落空行", () => {
  for (const te of [undefined, null, [], "x", [{}], [{ name: 123 }], [null]]) {
    const s = applyEvent(emptyTranscript, { ...REAL_PROGRESS_FRAME, tool_events: te });
    assert.ok(Array.isArray(s.activity), `tool_events=${JSON.stringify(te)}`);
    for (const line of s.activity) assert.ok(line.trim().length > 0, "不许落空行");
  }
});

test("emptyTranscript 自带这两个新字段,且是冻结的(别让调用方靠 undefined 判断)", () => {
  assert.equal(emptyTranscript.thinking, false);
  assert.deepEqual(emptyTranscript.activity, []);
});

test("畸形输入不崩:非对象 / 缺字段 / text 非字符串,一律原样返回", () => {
  let s = applyEvent(emptyTranscript, null);
  s = applyEvent(s, "not json object");
  s = applyEvent(s, 42);
  s = applyEvent(s, {}); // 没有 event
  s = applyEvent(s, { event: "delta" }); // 缺 stream_id/text
  s = applyEvent(s, { event: "delta", stream_id: "s", text: 123 }); // text 非串
  s = applyEvent(s, { event: "stream_end" }); // 缺 stream_id
  assert.deepEqual(s, emptyTranscript);
});

test("delta 撞用户消息 id:不往用户气泡拼,另起 assistant 消息(role 守卫)", () => {
  let s = appendLocalUser(emptyTranscript, "原文", "u-1");
  s = applyEvent(s, delta("u-1", "注入"));
  assert.equal(s.messages[0].content, "原文");
  assert.equal(s.messages.length, 2);
  assert.equal(s.messages[1].role, "assistant");
});

test("stream_end 未知 stream_id = no-op;turn_end 空 transcript 不崩", () => {
  const s1 = applyEvent(emptyTranscript, { event: "stream_end", stream_id: "没这条流" });
  assert.deepEqual(s1, emptyTranscript);
  const s2 = applyEvent(emptyTranscript, { event: "turn_end", turn_seq: 1 });
  assert.equal(s2.busy, false);
  assert.deepEqual(s2.messages, []);
});

test("error 事件:解锁 busy(失败路径不发 turn_end 时输入条不死锁)", () => {
  let s = appendLocalUser(emptyTranscript, "hi", "u-1");
  s = applyEvent(s, { event: "error", detail: "上游模型调用失败" });
  assert.equal(s.busy, false);
});

// ---- Enter 发送 × 中文输入法(F8) ---------------------------------------

test("shouldSendOnEnter:Enter 发;isComposing / keyCode 229 / Shift+Enter 不发", () => {
  assert.equal(shouldSendOnEnter({ key: "Enter" }), true);
  assert.equal(shouldSendOnEnter({ key: "Enter", isComposing: true }), false);
  assert.equal(shouldSendOnEnter({ key: "Enter", keyCode: 229 }), false);
  assert.equal(shouldSendOnEnter({ key: "Enter", shiftKey: true }), false);
  assert.equal(shouldSendOnEnter({ key: "a" }), false);
});

// ---- markdown 渲染:XSS 闸(oracle #4)+ GFM 真的开了 --------------------

test("XSS 闸:raw HTML 渲染为转义文本,不产生元素(<img onerror> 不执行)", () => {
  const html = renderToStaticMarkup(renderMarkdown("前<img src=x onerror=alert(1)>后"));
  assert.ok(!/<img/i.test(html), `不得出现 <img 元素:${html}`);
  assert.ok(!/onerror/i.test(html) || /&lt;/.test(html), `onerror 只能以转义文本出现:${html}`);
  assert.match(html, /&lt;img/i); // 原文以文本形式可见,不静默吞
});

test("XSS 闸:<script> 同样只出转义文本", () => {
  const html = renderToStaticMarkup(renderMarkdown("<script>alert(1)</script>"));
  assert.ok(!/<script/i.test(html), `不得出现 <script 元素:${html}`);
  assert.match(html, /&lt;script&gt;/i);
});

test("XSS 闸:javascript:/data: 链接的 href 被剥空(默认 urlTransform,谁覆盖谁红)", () => {
  const js = renderToStaticMarkup(renderMarkdown("[点我](javascript:alert(1))"));
  assert.ok(!/javascript:/i.test(js), `href 不得保留 javascript::${js}`);
  const data = renderToStaticMarkup(renderMarkdown("[点我](data:text/html,x)"));
  assert.ok(!/href="data:/i.test(data), `href 不得保留 data::${data}`);
  // 正常链接不误伤
  const ok = renderToStaticMarkup(renderMarkdown("[官网](https://example.com)"));
  assert.match(ok, /href="https:\/\/example\.com"/);
});

// ---- §T5b 链接在新标签页打开(track opendesign-chat-reconnect)------------
// 为什么算在断线自愈这一单里:今天点助手给的外链会**顶掉工作台本页**,
// 回来要重新连一次 —— 它自己就是一次人为断线。

test("外链带 target=_blank(点了不顶掉工作台)", () => {
  const html = renderToStaticMarkup(renderMarkdown("[官网](https://example.com)"));
  assert.match(html, /target="_blank"/, `外链必须开新标签:${html}`);
});

test("外链带 rel,且必须含 noreferrer(新标签页拿不到 window.opener)", () => {
  const html = renderToStaticMarkup(renderMarkdown("[官网](https://example.com)"));
  const m = html.match(/rel="([^"]*)"/);
  assert.ok(m, `必须有 rel 属性:${html}`);
  assert.ok(m[1].includes("noreferrer"), `rel 必须含 noreferrer,得到 ${m[1]}`);
});

test("加了 components.a 之后,XSS 闸一条都不许松(href 剥空的仍然剥空)", () => {
  // 覆盖 a 组件最容易顺手把 href 原样透传回去 —— 那会把上面那条 javascript: 闸打穿
  const js = renderToStaticMarkup(renderMarkdown("[点我](javascript:alert(1))"));
  assert.ok(!/javascript:/i.test(js), `href 不得保留 javascript::${js}`);
  const data = renderToStaticMarkup(renderMarkdown("[点我](data:text/html,x)"));
  assert.ok(!/href="data:/i.test(data), `href 不得保留 data::${data}`);
  // 链接文字仍在(别把整个链接吞掉)
  assert.match(js, /点我/);
});

test("GFM:表格渲染为 <table>(remark-gfm 真的挂上了)", () => {
  const html = renderToStaticMarkup(
    renderMarkdown("| 项 | 状态 |\n|---|---|\n| 玄关 | 待确认 |"),
  );
  assert.match(html, /<table>/);
  assert.match(html, /<td>玄关<\/td>/);
});

test("GFM:代码块/列表基本形状", () => {
  const html = renderToStaticMarkup(renderMarkdown("- 甲\n- 乙\n\n```\nlet x = 1\n```"));
  assert.match(html, /<ul>[\s\S]*<li>甲<\/li>/);
  assert.match(html, /<pre><code>/);
});

// ---- p6:历史对话回放 + attach 信封 -------------------------------------
// design.md D1/D2:attach 续聊(非只读);thread 回放只收 user/assistant 字符串
// content,跳 trace 与空 assistant;id 缺省 replay-<i>;busy=false 不锁输入。

import { hydrateFromThread, attachEnvelope } from "../web/src/chat/transcript.ts";

test("attachEnvelope:协议 attach 信封形状", () => {
  assert.deepEqual(attachEnvelope("chat-9"), { type: "attach", chat_id: "chat-9" });
});

test("hydrateFromThread:正常回放(role 过滤/id 沿用/不锁输入)", () => {
  const s = hydrateFromThread({
    messages: [
      { id: "u1", role: "user", content: "记一下:玄关柜 2.4 米" },
      { id: "a1", role: "assistant", content: "已记录 C3。" },
      { id: "t1", role: "assistant", content: "tool trace…", kind: "trace" },
      { id: "x1", role: "system", content: "不该出现" },
      { id: "a2", role: "assistant", content: "   " },
      { id: "a3", role: "assistant", content: 42 },
    ],
  });
  assert.ok(s);
  assert.deepEqual(
    s.messages.map((m) => [m.id, m.role, m.content, m.streaming]),
    [
      ["u1", "user", "记一下:玄关柜 2.4 米", false],
      ["a1", "assistant", "已记录 C3。", false],
    ],
  );
  assert.equal(s.busy, false);
});

test("hydrateFromThread:id 缺失/非字符串 → replay-<i> 兜底且不重复", () => {
  const s = hydrateFromThread({
    messages: [
      { role: "user", content: "一" },
      { id: 7, role: "assistant", content: "二" },
    ],
  });
  assert.ok(s);
  assert.deepEqual(s.messages.map((m) => m.id), ["replay-0", "replay-1"]);
});

test("hydrateFromThread:畸形 payload → null(安全降级,不崩)", () => {
  for (const bad of [null, undefined, 42, "x", {}, { messages: "no" }, { messages: null }]) {
    assert.equal(hydrateFromThread(bad), null, `payload=${JSON.stringify(bad)}`);
  }
});

test("hydrateFromThread:全被过滤 → 空消息列表(仍是合法 state,非 null)", () => {
  const s = hydrateFromThread({ messages: [{ role: "system", content: "x" }] });
  assert.ok(s);
  assert.deepEqual(s.messages, []);
  assert.equal(s.busy, false);
});

// ── track opendesign-turn-id:重连对账的「真身份」 ────────────────────────────
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// 病根(chat-reconnect 四审 P3/F4 记过账、design.md 明写「本单不做」):
// 重连后合并服务端历史与本地消息,判"哪条是本地独有"用的是 `role\0content` 启发式
// ⇒ **同一句话说两遍、中间断了线,第二遍会被当成第一遍而消失**(用户的话凭空没了)。
//
// 地基是实抓的(scratchpad/probe_turnid.py,08-05 对活 gateway 实跑):
// webui-thread 回放里 user 行的 `turnId` **逐字节等于**我们出站信封里填的 `turn_id`。
// 但同一 turn 的 assistant 行**带同一个 turnId** ⇒ turnId 不是消息级唯一键,
// 只能用来认 **user 侧**(与 P3「助手侧一律以服务端为准」的既有结论一致)。
//
// 判定规则(这段就是规格,实现照它写):
//   服务端已记 = replay 里 role==="user" 的行
//   本地一条 user 消息算"服务端已记上":
//     · 本地有 turnId → **只看 turnId**:turnId ∈ 服务端 turnId 集合
//     · 本地没有 turnId → 老启发式:文本命中服务端**任意** user 行(行为不倒退)
//   本地 assistant 一律丢弃(半截气泡以服务端为准)
//   输出顺序 = [...服务端历史, ...本地独有]
//
// ⚠️ 「本地有 turnId 时还要拿文本兜一层」那条**曾经写在这里,08-05 四审后删掉了**。
// 删的理由是证据不是口味:
//   ① 实测 gateway 把我们发的 turn_id 原样写进每一条 user 行(抽样 7 个会话,
//      带 turnId 7 / 不带 0),协议 §2 也把它列为出站信封的一等字段 ⇒
//      "服务端记下了这条、却没有它的 turnId" 这种状态在现实里没出现过;
//   ② 而那层文本兜底有确定的代价:**用户重复说一句上周说过的话、正好断线**,
//      新说的那句会被当成老那条而消失 —— 正是本单要消灭的病,换了个入口回来;
//   ③ 万一 ① 的假设哪天不成立,两种错法里 **"多一个气泡" 远好于 "少一句话"**。
// (MiMo 判它 LOW「不改也对」,Kimi 判 MEDIUM 建议改;我按 ①②③ 采纳后者。)

import { reconcileThread } from "../web/src/chat/transcript.ts";

const u = (id, content, turnId) => ({
  id, role: "user", content, streaming: false, ...(turnId ? { turnId } : {}),
});
const a = (id, content, streaming = false) => ({
  id, role: "assistant", content, streaming,
});

test("对账①:同一句话说两遍、服务端只记上第一遍 ⇒ 两条都还在(本单要修的那个 bug)", () => {
  const local = [u("l1", "帮我改一下玄关柜", "t-1"), u("l2", "帮我改一下玄关柜", "t-2")];
  const replay = [u("u-0", "帮我改一下玄关柜", "t-1"), a("as-1", "好的")];
  const out = reconcileThread(local, replay);
  assert.equal(
    out.filter((m) => m.role === "user" && m.content === "帮我改一下玄关柜").length,
    2,
    "第二遍是断线时发出、服务端没记上的 —— 吃掉它就是把用户说的话弄丢了",
  );
  // 顺序:服务端历史在前,本地独有的补在尾部
  assert.deepEqual(out.map((m) => m.id), ["u-0", "as-1", "l2"]);
});

test("对账②:服务端已经记上的不重复追加(turnId 命中)", () => {
  const local = [u("l1", "量房定在周三", "t-9")];
  const replay = [u("u-0", "量房定在周三", "t-9"), a("as-1", "记下了")];
  const out = reconcileThread(local, replay);
  assert.deepEqual(out.map((m) => m.id), ["u-0", "as-1"]);
});

test("对账③:本地 assistant 半截气泡一律丢弃(以服务端完整版为准)", () => {
  const local = [u("l1", "问题", "t-1"), a("as-local", "正在回答的半", true)];
  const replay = [u("u-0", "问题", "t-1"), a("as-1", "正在回答的半截话已经说完了")];
  const out = reconcileThread(local, replay);
  assert.equal(out.some((m) => m.id === "as-local"), false,
    "留着它 = 一条永远转圈的重复回复,顺序还错(四审 P3)");
  assert.deepEqual(out.map((m) => m.id), ["u-0", "as-1"]);
});

test("对账④:本地消息没有 turnId ⇒ 退回文本启发式,老行为不倒退", () => {
  const local = [u("l1", "老会话里前插进来的一句")];        // 无 turnId
  const replay = [u("u-0", "老会话里前插进来的一句", "t-5")];
  assert.deepEqual(reconcileThread(local, replay).map((m) => m.id), ["u-0"]);
});

test("对账⑤:本地有 turnId、服务端旧行没有 turnId 且文本一样 ⇒ **本地那条要留住**", () => {
  // 场景:用户上周说过「上周聊过的那句」(服务端那条老记录没有 turnId),
  // 今天又说了一遍、正好断线、服务端没记上。这两条是**不同的消息**,
  // 而"服务端记下了却没写 turnId"这种状态实测不存在(见本节顶部 ①)⇒
  // 按文本把今天这句吃掉,就是本单要消灭的那个病换了个入口回来。
  const local = [u("l1", "上周聊过的那句", "t-7")];
  const replay = [u("u-0", "上周聊过的那句")];              // 服务端无 turnId
  assert.deepEqual(reconcileThread(local, replay).map((m) => m.id), ["u-0", "l1"]);
});

test("对账⑤b:服务端旧行没有 turnId、本地那条也没有 ⇒ 仍按文本去重(老行为不倒退)", () => {
  // 前插回放进来的本地消息就是这种:它的字段全部来自服务端,没有 turnId。
  const local = [u("l1", "上周聊过的那句")];
  const replay = [u("u-0", "上周聊过的那句")];
  assert.deepEqual(reconcileThread(local, replay).map((m) => m.id), ["u-0"]);
});

test("对账⑥:turnId 不同但文本不同 ⇒ 本地那条照常保留(别把不同的话合并掉)", () => {
  const local = [u("l1", "第一句", "t-1"), u("l2", "第二句", "t-2")];
  const replay = [u("u-0", "第一句", "t-1")];
  assert.deepEqual(reconcileThread(local, replay).map((m) => m.content),
    ["第一句", "第二句"]);
});

test("对账⑦:空本地 / 空回放不崩,且不凭空造消息", () => {
  assert.deepEqual(reconcileThread([], [u("u-0", "只有服务端", "t-1")]).map((m) => m.id),
    ["u-0"]);
  assert.deepEqual(reconcileThread([u("l1", "只有本地", "t-1")], []).map((m) => m.id),
    ["l1"]);
  assert.deepEqual(reconcileThread([], []), []);
});

test("对账⑧:不改动入参(纯函数,原数组与原对象都不许被动)", () => {
  const local = [u("l1", "本地独有", "t-2")];
  const replay = [u("u-0", "服务端的", "t-1")];
  const localCopy = JSON.parse(JSON.stringify(local));
  const replayCopy = JSON.parse(JSON.stringify(replay));
  reconcileThread(local, replay);
  assert.deepEqual(local, localCopy);
  assert.deepEqual(replay, replayCopy);
});

test("hydrateFromThread:回放的 turnId 读回本地消息(对账的地基)", () => {
  const s = hydrateFromThread({
    messages: [
      { id: "u-0", role: "user", content: "你好", turnId: "t-1", turnPhase: "user" },
      { id: "as-1", role: "assistant", content: "在", turnId: "t-1", turnPhase: "answer" },
      { id: "u-2", role: "user", content: "老会话没有这个字段" },
      { id: "u-3", role: "user", content: "空的不算", turnId: "" },
      { id: "u-4", role: "user", content: "非字符串不算", turnId: 42 },
    ],
  });
  assert.ok(s);
  assert.deepEqual(s.messages.map((m) => m.turnId),
    ["t-1", "t-1", undefined, undefined, undefined]);
});

test("appendLocalUser:存得住 turnId,且必须是**发出去的那一个**", () => {
  const s = appendLocalUser(emptyTranscript, "发出去的话", "local-1", undefined, "turn-abc");
  assert.equal(s.messages[0].turnId, "turn-abc");
  // 不给 turnId 时不许凭空造一个(老调用方行为不变)
  const s2 = appendLocalUser(emptyTranscript, "没给 id", "local-2");
  assert.equal(s2.messages[0].turnId, undefined);
});
