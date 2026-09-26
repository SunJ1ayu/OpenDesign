// oracle:模型出错时聊天页要说人话(track opendesign-chat-error-visible)
// 跑法:node --test tests/test_chat_model_error.mjs(Node 22+,原生 strip-types)
//
// 病:网关出错时发的是一条**没有 kind** 的 `message`(整句原文),`applyEvent` 只认 progress/tool_hint,
// 实时整句丢 ⇒ 业主发完一句「没反应」;切走再回来,回放里那条 assistant 行又冒出英文原文。
// 样本 = 本单探针的**逐字**输出(tracks/opendesign-chat-error-visible/evidence/20260925-probe-gateway-errors.txt):
// 真 nanobot 网关 + 本机假厂商;四家的 401 报错体是拿明显的假 key 打真厂商抓回来的原文。
// 没抓到的几种(超时 / 模型不存在 / 太长 / 助手自身出错)照 nanobot 源码里的格式手写,注明出处。
//
// 判据只钉「意思」不钉整句:每类必须带出该去的那一步,且**不许带出别类的那一步**
// (最伤人的不是没提示,是把人指错门:欠费叫他改 key、限流叫他充值、厂商出错叫他查网络 —— QA 设计两家同指)。
import { test } from "node:test";
import assert from "node:assert/strict";
import { describeModelError } from "../web/src/chat/modelError.ts";
import {
  emptyTranscript,
  appendLocalUser,
  applyEvent,
  hydrateFromThread,
} from "../web/src/chat/transcript.ts";

// ---- 样本 --------------------------------------------------------------------

// 探针逐字(网关 message 帧的 text)
const CAPTURED = {
  fakeKey: "Error: {'message': 'Invalid API key', 'type': 'invalid_request_error'}",
  mimo401: "Error: {'message': 'Invalid API Key', 'param': 'Please provide valid API Key', 'code': '401', 'type': 'invalid_key'}",
  deepseek401: "Error: {'message': 'Authentication Fails, Your api key: ****0000 is invalid (request_id: b3895a70-4933-49a6-b70c-f7a84cab683c)', 'type': 'authentication_error', 'param': None, 'code': 'invalid_request_error'}",
  kimi401: "Error: {'message': 'Invalid Authentication', 'type': 'invalid_authentication_error'}",
  glm401: "Error: {'code': '401', 'message': '令牌已过期或验证不正确'}",
  arrears: "The AI provider rejected the request because the API key is out of quota or the account is in arrears. Please top up / check the billing status of your API key and try again.",
  glm1113: "Error: {'code': '1113', 'message': '余额不足或无可用资源包,请充值。'}",
  rate: "Error: {'message': 'Rate limit reached for requests', 'type': 'rate_limit_error'}",
  server: "Error: {'message': 'internal server error', 'type': 'server_error'}",
  conn: "Error calling LLM: Connection error.",
};

// 照 nanobot 源码格式手写(site-packages/nanobot/…)
const FROM_SOURCE = {
  // agent/runner.py:853 / :848
  timeout: "Error calling LLM: timed out after 120s",
  stalled: "Error calling LLM: stream stalled",
  // openai 兼容层 `Error: {body}`;Grok 4c 反例:type 是 invalid_request_error,但其实是模型名不对
  notFound: "Error: {'message': 'The model `mimo-v9` does not exist or you do not have access to it.', 'type': 'invalid_request_error', 'code': 'model_not_found'}",
  tooLong: "Error: {'message': \"This model's maximum context length is 131072 tokens. However, your messages resulted in 140000 tokens.\", 'type': 'invalid_request_error', 'code': 'context_length_exceeded'}",
  // Grok 4c 反例:图片被拒,同样是 invalid_request_error —— 认不出 ⇒ 通用,不许说成 key
  imageRejected: "Error: {'message': 'Invalid image data', 'type': 'invalid_request_error'}",
  // runner.py:475 的 Python 异常形状(主聊天里只在子任务出现,但形状要认得)
  toolCrash: "Error: RuntimeError: tool execution failed",
  // loop.py:1070 主循环未捕获异常
  loopCrash: "Sorry, I encountered an error.",
  // runner.py:59 默认错误句
  defaultError: "Sorry, I encountered an error calling the AI model.",
  // utils/runtime.py EMPTY_FINAL_RESPONSE_MESSAGE
  emptyAnswer: "I completed the tool steps but couldn't produce a final answer. Please try again or narrow the task.",
  // runner.py:64 占位
  placeholder: "[Assistant reply unavailable due to model error.]",
  unknown: "Error: {'message': 'something odd happened', 'type': 'weird_error'}",
  openaiKey: "Error: {'message': 'Incorrect API key provided: sk-proj-abcdefghijklmnop1234. You can find your API key at https://platform.openai.com/account/api-keys.', 'type': 'invalid_request_error', 'code': 'invalid_api_key'}",
};

// 每类「该去的那一步」的标志词。实现的措辞可以改,但这几个词代表的去向不许丢、不许串。
const STEP = {
  refillKey: /重新填/,        // 去模型设置重填 key
  topUp: /充值|余额/,          // 去厂商那边充值 / 看余额
  wait: /稍等/,               // 等一会儿再发
  network: /网络/,            // 检查网络
};

function d(raw) {
  const r = describeModelError(raw);
  assert.ok(r, `这句是网关的出错原文,却没认出来:${raw}`);
  assert.equal(typeof r.text, "string");
  assert.ok(!/Error|error/.test(r.text), `中文说明里夹着英文原文:${r.text}`);
  assert.ok(/[一-鿿]/.test(r.text), `说明不是中文:${r.text}`);
  return r;
}

function assertSteps(label, text, { must = [], mustNot = [] }) {
  for (const k of must) assert.ok(STEP[k].test(text), `${label}:缺了该去的那一步(${k}):${text}`);
  for (const k of mustNot) assert.ok(!STEP[k].test(text), `${label}:把人指到别处去了(${k}):${text}`);
}

// ---- 分类:每类带对去向、不串门 -------------------------------------------------

test("key 不对:四家真 401 + 假厂商那句 ⇒ 去模型设置重填、点「测试」;不许叫他充值 / 等 / 查网络", () => {
  for (const k of ["fakeKey", "mimo401", "deepseek401", "kimi401", "glm401"]) {
    const { text } = d(CAPTURED[k]);
    assertSteps(k, text, { must: ["refillKey"], mustNot: ["topUp", "wait", "network"] });
    assert.ok(/API Key/.test(text) && /模型设置/.test(text) && /测试/.test(text), `${k}:没指到「设置 → 模型设置」的「测试」:${text}`);
  }
  const { text } = d(FROM_SOURCE.openaiKey);
  assertSteps("openaiKey", text, { must: ["refillKey"], mustNot: ["topUp", "wait", "network"] });
});

test("额度 / 欠费:网关的欠费固定句 + GLM 余额不足 ⇒ 去充值看余额;**不许叫他改 key**(那句英文里明明写着 API key)", () => {
  for (const k of ["arrears", "glm1113"]) {
    const { text } = d(CAPTURED[k]);
    assertSteps(k, text, { must: ["topUp"], mustNot: ["refillKey", "wait", "network"] });
  }
});

test("限流 ⇒ 稍等再发;不许叫他充值 / 改 key / 查网络(欠费和限流都是 429,最容易混)", () => {
  const { text } = d(CAPTURED.rate);
  assertSteps("rate", text, { must: ["wait"], mustNot: ["topUp", "refillKey", "network"] });
});

test("连不上 ⇒ 查网络;不许叫他改 key / 充值", () => {
  const { text } = d(CAPTURED.conn);
  assertSteps("conn", text, { must: ["network"], mustNot: ["refillKey", "topUp"] });
});

test("厂商出错(5xx)⇒ 稍后再试;不许叫他查网络 / 改 key / 充值(网好好的)", () => {
  const { text } = d(CAPTURED.server);
  assertSteps("server", text, { mustNot: ["network", "refillKey", "topUp"] });
  assert.ok(/厂商/.test(text) && /稍后/.test(text), `没说是厂商那边、稍后再试:${text}`);
});

test("超时 / 卡住 ⇒ 说超时、稍后再试;不许叫他改 key / 充值", () => {
  for (const k of ["timeout", "stalled"]) {
    const { text } = d(FROM_SOURCE[k]);
    assertSteps(k, text, { mustNot: ["refillKey", "topUp"] });
    assert.ok(/超时/.test(text), `${k}:没说超时:${text}`);
  }
});

test("Grok 反例:invalid_request_error 不等于 key 错 —— 模型不存在 ⇒ 换模型;图片被拒 ⇒ 通用;都不许叫他重填 key", () => {
  const nf = d(FROM_SOURCE.notFound).text;
  assertSteps("notFound", nf, { mustNot: ["refillKey", "topUp", "wait", "network"] });
  assert.ok(/换一个模型/.test(nf), `模型不存在却没叫他换模型:${nf}`);
  const img = d(FROM_SOURCE.imageRejected).text;
  assertSteps("imageRejected", img, { mustNot: ["refillKey", "topUp", "wait", "network"] });
});

test("对话太长 ⇒ 开新对话;不许叫他改 key / 充值", () => {
  const { text } = d(FROM_SOURCE.tooLong);
  assertSteps("tooLong", text, { mustNot: ["refillKey", "topUp"] });
  assert.ok(/太长/.test(text) && /新对话/.test(text), `没说太长、开新对话:${text}`);
});

test("认不出的 ⇒「模型那边出错了」+ 去点「测试」看看;不猜去向", () => {
  for (const raw of [FROM_SOURCE.unknown, FROM_SOURCE.imageRejected, FROM_SOURCE.defaultError, FROM_SOURCE.placeholder]) {
    const { text } = d(raw);
    assert.ok(/模型那边出错了/.test(text) && /测试/.test(text), `认不出时的通用说明不对:${text}`);
    assertSteps(raw, text, { mustNot: ["refillKey", "topUp", "wait", "network"] });
  }
});

test("Grok 反例:助手自己出错(Python 异常形状 / 主循环兜底句)⇒ 说是助手这边;不许赖厂商、叫他改 key 或充值", () => {
  for (const raw of [FROM_SOURCE.toolCrash, FROM_SOURCE.loopCrash]) {
    const { text } = d(raw);
    assert.ok(/助手这边/.test(text), `没说是助手这边出错:${text}`);
    assert.ok(!/厂商/.test(text), `助手自己出错却赖到厂商头上:${text}`);
    assertSteps(raw, text, { mustNot: ["refillKey", "topUp"] });
  }
});

test("空答固定句 ⇒ 中文说「没整理出回答」", () => {
  const { text } = d(FROM_SOURCE.emptyAnswer);
  assert.ok(/没整理出/.test(text), text);
});

test("原文原样留着备查(raw),只给 key 形状的长串打码", () => {
  for (const raw of Object.values(CAPTURED)) {
    assert.equal(d(raw).raw, raw, "没有 key 形状的串时,原文必须一字不差");
  }
  const r = d(FROM_SOURCE.openaiKey);
  assert.ok(!r.raw.includes("sk-proj-abcdefghijklmnop1234"), `原文小字把 key 原样亮出来了:${r.raw}`);
  assert.ok(r.raw.includes("1234") && r.raw.includes("****"), `打码后看不出是哪把 key(末 4 位)了:${r.raw}`);
  assert.ok(r.raw.includes("platform.openai.com"), "打码误伤了别的内容");
  const b = d("Error: {'message': 'bad header Bearer tp-abcdefghij0123456789xyz', 'type': 'weird'}");
  assert.ok(!b.raw.includes("tp-abcdefghij0123456789xyz"), `Bearer 后面的 key 没打码:${b.raw}`);
});

test("不是网关出错壳的正常回复一律不动(Grok 4c:回放分不清「报错」和「助手在引用这句报错」)", () => {
  const normal = [
    "",
    "   ",
    "好的,已经帮你记下了。",
    "我查到的报错是:Error: {'message': 'Invalid API key'},意思是 key 不对。",
    "Error handling 是指…(不带冒号,不是网关的壳)",
    "你刚才转给我的那句是:" + CAPTURED.arrears,
    CAPTURED.arrears + " 这句话的意思是欠费了。",
    "错误:网关没回。",
  ];
  for (const s of normal) assert.equal(describeModelError(s), null, `正常回复被当成出错改写了:${s}`);
});

// ---- 第 1 轮 QA 判卷 + 代码评审后补的(verify.md Q1 / Q2 / R2 / R3)-----------------

test("Q2 key 不对 ⇒ 要指到输入框右下角(屏上唯一能对上号的线索;design 写了、第一版实现漏了)", () => {
  for (const k of ["mimo401", "glm401"]) {
    const { text } = d(CAPTURED[k]);
    assert.ok(/右下角/.test(text), `${k}:没指到输入框右下角那个模型按钮:${text}`);
  }
});

test("Q1 认不出的错不许替「测试」许愿(测试只测得出这家能不能用,测不出图片被拒这类)", () => {
  for (const raw of [FROM_SOURCE.unknown, FROM_SOURCE.imageRejected, FROM_SOURCE.defaultError]) {
    const { text } = d(raw);
    assert.ok(!/告诉你|具体哪里/.test(text), `许诺「测试」会说明原因,而它说明不了:${text}`);
    assert.ok(/图/.test(text), `没提醒「带了图的话先去掉图」(最常见的认不出来的错):${text}`);
  }
});

test("R2 厂商回了报错体 = 连得上 ⇒ 不许叫他查网络;代理认证失败不许说成 key 不对", () => {
  const upstream502 = "Error: {'message': 'Bad gateway: failed to establish upstream connection', 'type': 'server_error', 'code': 502}";
  const upstream503 = "Error: {'message': 'upstream connection error', 'code': 503}";
  for (const raw of [upstream502, upstream503]) {
    const { text } = d(raw);
    assertSteps("upstream", text, { mustNot: ["network", "refillKey", "topUp"] });
    assert.ok(/厂商/.test(text), `厂商那边的 5xx 没说是厂商那边:${text}`);
  }
  const proxy407 = "Error: {'message': 'proxy authentication required', 'code': 407}";
  const p = d(proxy407).text;
  assertSteps("proxy407", p, { must: ["network"], mustNot: ["refillKey", "topUp"] });
  // 网关自己连不上(没有报错体)仍是「连不上」
  assertSteps("conn", d(CAPTURED.conn).text, { must: ["network"] });
});

test("R3 原文打码也认 GLM 的 <id>.<secret> 形状与 api_key= 写法", () => {
  const glmKey = "0123456789abcdef0123456789abcdef.AbCdEfGh12345678";
  const g = d(`Error: {'code': '401', 'message': 'key ${glmKey} 令牌已过期或验证不正确'}`);
  assert.ok(!g.raw.includes(glmKey) && !g.raw.includes("AbCdEfGh12345678"), `GLM 形状的 key 原样亮出来了:${g.raw}`);
  assert.ok(g.raw.includes("令牌已过期或验证不正确"), "打码误伤了报错正文");
  const a = d("Error: {'message': 'bad request api_key=XyZ0123456789abcdefLONG', 'type': 'weird'}");
  assert.ok(!a.raw.includes("XyZ0123456789abcdefLONG"), `api_key= 后面的 key 没打码:${a.raw}`);
  for (const raw of Object.values(CAPTURED)) assert.equal(d(raw).raw, raw, "探针原文里没有 key,打码不许动它");
});

// ---- 接进 applyEvent:实时 --------------------------------------------------------

// 探针里 401 那一轮的真实帧序(turn_id / stream_id 换成短串,字段一个不少)
function realErrorFrames(text, turn = "turn-1") {
  return [
    { event: "goal_status", chat_id: "c", status: "running", started_at: 1790313657.58 },
    { event: "stream_end", chat_id: "c", stream_id: "websocket:c:1:0", turn_id: turn, turn_phase: "answer", turn_seq: 2 },
    { event: "message", chat_id: "c", text, latency_ms: 1305, turn_id: turn, turn_phase: "answer", turn_seq: 3 },
    { event: "turn_end", chat_id: "c", latency_ms: 1305, goal_state: { active: false }, turn_id: turn, turn_phase: "complete", turn_seq: 4 },
  ];
}

function sendThen(frames, userText = "你好") {
  const s0 = appendLocalUser(emptyTranscript, userText, "u1", undefined, "turn-1");
  return frames.reduce(applyEvent, s0);
}

test("实时:真帧序(错 key)⇒ 用户那句下面恰好一条出错气泡,说人话,输入解锁、思考动画收掉", () => {
  const s = sendThen(realErrorFrames(CAPTURED.mimo401));
  assert.equal(s.messages.length, 2, `应是 用户一句 + 出错说明一条:${JSON.stringify(s.messages)}`);
  const [u, a] = s.messages;
  assert.equal(u.role, "user");
  assert.equal(a.role, "assistant");
  assert.equal(a.streaming, false);
  // 0.98.14 起多带小字标签(track opendesign-composer-zcode,上一单欠账 Q3′):厂商真原话 ⇒「原文」。整形相等照旧,多钉一格。
  assert.deepEqual(a.modelError, { raw: CAPTURED.mimo401, rawLabel: "原文" });
  assert.equal(a.content, describeModelError(CAPTURED.mimo401).text);
  assert.equal(s.busy, false);
  assert.equal(s.thinking, false);
});

test("实时:出错说明一到就收掉「正在思考」(不用等 turn_end)", () => {
  const frames = realErrorFrames(CAPTURED.conn).slice(0, 3);
  const s = sendThen(frames);
  assert.equal(s.thinking, false, "说明已经出来了,思考动画还挂着");
  assert.equal(s.messages.at(-1).modelError?.raw, CAPTURED.conn);
});

test("实时:五类探针原文各走一遍真帧序,都恰好一条出错气泡", () => {
  for (const [k, raw] of Object.entries(CAPTURED)) {
    const s = sendThen(realErrorFrames(raw));
    const bubbles = s.messages.filter((m) => m.role === "assistant");
    assert.equal(bubbles.length, 1, `${k}:助手气泡数不对`);
    assert.ok(bubbles[0].modelError, `${k}:没标成出错`);
  }
});

test("实时:没有 kind 的普通消息(助手主动发的话 / 定时提醒)⇒ 原样一条普通助手气泡,不标出错、不动 busy", () => {
  const idle = applyEvent(emptyTranscript, {
    event: "message", chat_id: "c", text: "提醒:明天上午 10 点去王先生家量房。",
  });
  assert.equal(idle.messages.length, 1);
  assert.equal(idle.messages[0].role, "assistant");
  assert.equal(idle.messages[0].content, "提醒:明天上午 10 点去王先生家量房。");
  assert.equal(idle.messages[0].modelError, undefined);
  assert.equal(idle.busy, false, "空闲时来一条通知,不该把输入锁上");

  const mid = appendLocalUser(emptyTranscript, "帮我查下", "u1", undefined, "t1");
  const s = applyEvent(mid, { event: "message", chat_id: "c", text: "我先看一下待办,稍等。", turn_id: "t1", turn_seq: 2 });
  assert.equal(s.busy, true, "一轮还没完,中途一句话不该解锁输入");
  assert.equal(s.messages.at(-1).content, "我先看一下待办,稍等。");
});

test("实时:同一帧收两次(同 turn_id + turn_seq)只一条;同一轮两句不同的各一条", () => {
  const f = { event: "message", chat_id: "c", text: "第一句", turn_id: "t1", turn_seq: 3 };
  const once = applyEvent(emptyTranscript, f);
  const twice = applyEvent(once, f);
  assert.equal(twice.messages.length, 1);
  const two = applyEvent(twice, { ...f, text: "第二句", turn_seq: 5 });
  assert.equal(two.messages.length, 2);
  // 没有 turn_id / turn_seq(例如定时推送)也得能连着来两条,不许互相吞
  const a = applyEvent(emptyTranscript, { event: "message", text: "通知一" });
  const b = applyEvent(a, { event: "message", text: "通知二" });
  assert.deepEqual(b.messages.map((m) => m.content), ["通知一", "通知二"]);
  assert.notEqual(b.messages[0].id, b.messages[1].id);
});

test("实时:空 text / 非字符串 / 不认识的 kind ⇒ 不出气泡(只放开「没有 kind」这一种)", () => {
  let s = applyEvent(emptyTranscript, { event: "message", text: "" });
  s = applyEvent(s, { event: "message", text: "   " });
  s = applyEvent(s, { event: "message", text: 42 });
  s = applyEvent(s, { event: "message" });
  s = applyEvent(s, { event: "message", kind: "将来才有的 kind", text: "内部痕迹" });
  assert.deepEqual(s.messages, []);
});

test("回归:正常流式一轮(delta…stream_end→turn_end)+ 活动回执 ⇒ 仍只一条正文气泡,不多出任何东西", () => {
  const s = sendThen([
    { event: "goal_status", status: "running" },
    { event: "message", kind: "progress", text: "", turn_id: "turn-1", turn_seq: 2,
      tool_events: [{ phase: "end", name: "mcp_design-studio_list_todos_tool" }] },
    { event: "delta", stream_id: "s1", text: "你有 3 条待办" },
    { event: "delta", stream_id: "s1", text: ",最急的是…" },
    { event: "stream_end", stream_id: "s1" },
    { event: "turn_end", turn_id: "turn-1" },
  ]);
  const bubbles = s.messages.filter((m) => m.role === "assistant");
  assert.equal(bubbles.length, 1);
  assert.equal(bubbles[0].content, "你有 3 条待办,最急的是…");
  assert.equal(bubbles[0].modelError, undefined);
});

test("回归:进行中的一轮先有 activity,出错说明到了之后 activity 不被吞(turn_end 才清)", () => {
  const s0 = appendLocalUser(emptyTranscript, "你好", "u1", undefined, "turn-1");
  const s1 = applyEvent(s0, { event: "message", kind: "progress", text: "", tool_events: [{ name: "x" }] });
  const s2 = applyEvent(s1, { event: "message", text: CAPTURED.server, turn_id: "turn-1", turn_seq: 5 });
  assert.equal(s2.activity.length, 1);
});

// ---- 回放:切走再回来同一句 --------------------------------------------------------

test("回放:webui-thread 里那条英文原文 ⇒ 与实时**同一句**中文 + 同一份原文;正常回复不动", () => {
  // 回放行 = 探针抓到的 webui-thread 形状
  const payload = {
    messages: [
      { id: "u-0-4b07db61", role: "user", content: "你好", turnId: "turn-1", turnPhase: "user", turnSeq: 1, createdAt: 1 },
      { id: "as-2-1670ef59", role: "assistant", content: CAPTURED.mimo401, latencyMs: 1475, turnId: "turn-1", turnPhase: "answer", turnSeq: 3, isStreaming: false },
      { id: "u-4", role: "user", content: "现在呢", turnId: "turn-2" },
      { id: "as-6", role: "assistant", content: "好的,已经帮你记下了。", turnId: "turn-2" },
    ],
  };
  const replay = hydrateFromThread(payload);
  const live = sendThen(realErrorFrames(CAPTURED.mimo401));
  const r = replay.messages[1];
  const l = live.messages[1];
  assert.equal(r.content, l.content, "切走再回来,说法变了");
  assert.deepEqual(r.modelError, l.modelError);
  assert.equal(replay.messages[3].content, "好的,已经帮你记下了。");
  assert.equal(replay.messages[3].modelError, undefined);
  // 每一种探针原文回放都得是中文说明,不再冒英文
  for (const raw of Object.values(CAPTURED)) {
    const h = hydrateFromThread({ messages: [{ id: "a", role: "assistant", content: raw }] });
    assert.equal(h.messages[0].content, describeModelError(raw).text);
  }
});
