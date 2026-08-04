// O1 判据:断线自愈的纯逻辑层(track opendesign-chat-reconnect,T6)。
// 跑法:node --test tests/test_chat_reconnect.mjs(Node 22+,原生 strip-types)
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// 依据 = docs/nanobot-ws-protocol.md §4「重连流(断线自愈,T6 依据)」+ 本 track design.md。
// 被判的模块 `web/src/chat/reconnect.ts` **只回答一个问题**:
//   "刚出的这件事之后,等多久再试、还是根本不该再试"。
//   零 DOM、零 ws、零计时器 —— 定时器是接线层的事,这里只算数。
//
// ⚠️ 本文件最重要的一组是「两种 401 的分界」(下面 §4)。协议文档原话:
//   「重 bootstrap(旧 ws token 已被消费,复用必 401 —— **别把这个 401 误判成口令失效**)」
// 判错的后果不是少个功能,是**把功能做反**:每次正常重连都把用户踹回登录框。
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  BACKOFF_MS,
  JITTER,
  initialReconnect,
  reduceReconnect,
  isPasswordFailure,
} from "../web/src/chat/reconnect.ts";
import { PasswordRejected } from "../web/src/chat/connection.ts";

// 抖动注入:rand=0.5 ⇒ 不抖(正好等于基准值),便于逐值断言
const noJitter = () => 0.5;
const step = (state, ev, rand = noJitter) => reduceReconnect(state, ev, rand);

// ---- §1 退避序列 -------------------------------------------------------

test("退避序列逐值:500 / 1000 / 2000 / 4000 / 8000 / 15000", () => {
  assert.deepEqual([...BACKOFF_MS], [500, 1000, 2000, 4000, 8000, 15000]);
  let s = initialReconnect;
  const got = [];
  for (let i = 0; i < BACKOFF_MS.length; i++) {
    const r = step(s, { type: "closed" });
    s = r.state;
    assert.equal(r.action.kind, "schedule");
    got.push(r.action.delayMs);
  }
  assert.deepEqual(got, [500, 1000, 2000, 4000, 8000, 15000]);
});

test("到 15s 封顶后不再增长,而且永远不放弃(常驻工作台:合盖一夜回来该自己好了)", () => {
  let s = initialReconnect;
  let last = null;
  for (let i = 0; i < 40; i++) {
    const r = step(s, { type: "closed" });
    s = r.state;
    assert.equal(r.action.kind, "schedule", `第 ${i + 1} 次失败后仍必须继续排队重连`);
    last = r.action.delayMs;
  }
  assert.equal(last, 15000);
  assert.equal(s.mode, "waiting");
});

test("抖动:±15%,给定随机源可复现,且始终是整数毫秒", () => {
  const first = (rand) => step(initialReconnect, { type: "closed" }, rand).action.delayMs;
  assert.equal(first(() => 0), Math.round(500 * (1 - JITTER)));
  assert.equal(first(() => 1), Math.round(500 * (1 + JITTER)));
  assert.equal(first(() => 0.5), 500);
  for (const r of [0, 0.13, 0.5, 0.77, 1]) {
    const d = first(() => r);
    assert.ok(Number.isInteger(d), `延迟必须是整数毫秒,得到 ${d}`);
  }
});

test("抖动的真实理由是多标签页:同一状态两次算出的值不该恒等", () => {
  // 不是密码学随机性检验,只钉死"rand 真的被用上了"——写死忽略 rand 的实现会红
  const a = step(initialReconnect, { type: "closed" }, () => 0).action.delayMs;
  const b = step(initialReconnect, { type: "closed" }, () => 1).action.delayMs;
  assert.notEqual(a, b);
});

// ---- §2 连上之后 -------------------------------------------------------

test("连上 ⇒ 失败计数清零、回 connected、不再排队", () => {
  let s = initialReconnect;
  for (let i = 0; i < 3; i++) s = step(s, { type: "closed" }).state;
  assert.equal(s.failures, 3);
  const r = step(s, { type: "connected" });
  assert.equal(r.state.failures, 0);
  assert.equal(r.state.mode, "connected");
  assert.equal(r.action.kind, "none");
});

test("连上之后再断,退避从头开始(不接着上次的 8 秒)", () => {
  let s = initialReconnect;
  for (let i = 0; i < 3; i++) s = step(s, { type: "closed" }).state;
  s = step(s, { type: "connected" }).state;
  const r = step(s, { type: "closed" });
  assert.equal(r.action.delayMs, 500);
});

// ---- §3 网络回来 / 页面回到前台 ----------------------------------------

test("online / 回到前台 ⇒ 退避清零并立刻试一次(合盖恢复是主路径)", () => {
  for (const type of ["online", "visible"]) {
    let s = initialReconnect;
    for (let i = 0; i < 5; i++) s = step(s, { type: "closed" }).state;
    assert.equal(step(s, { type: "closed" }).action.delayMs, 15000, "前置条件:已经退到封顶");
    const r = step(s, { type });
    assert.equal(r.action.kind, "schedule", `${type} 必须触发一次立即重试`);
    assert.equal(r.action.delayMs, 0, `${type} 之后不该再等 15 秒`);
    assert.equal(r.state.failures, 0);
  }
});

test("已经连着的时候收到 online / 回到前台 ⇒ 什么都不做(别把好好的连接踹掉)", () => {
  for (const type of ["online", "visible"]) {
    const r = step(initialReconnect, { type });
    assert.equal(r.action.kind, "none");
    assert.equal(r.state.mode, "connected");
  }
});

// ---- §4 两种 401 的分界(本单最容易做反的地方)-------------------------

test("bootstrap 返 401(口令真失效)⇒ 停止重连、回登录框", () => {
  const r = step(initialReconnect, { type: "failed", error: new PasswordRejected() });
  assert.equal(r.action.kind, "login");
  assert.equal(r.state.mode, "stopped");
});

test("ws 断开 ⇒ 一律照常重连,**永远不产生 login**(握手 token 一次性,复用必 401)", () => {
  // 协议文档 §4 白纸黑字:别把这个 401 误判成口令失效。
  // 关闭码全谱扫一遍:正常关闭 / 异常断开 / 上游自定义的 4401
  for (const code of [1000, 1001, 1006, 1011, 4401, 4001, undefined]) {
    const r = step(initialReconnect, { type: "closed", code });
    assert.equal(r.action.kind, "schedule", `关闭码 ${code} 不该被当成口令失效`);
    assert.notEqual(r.state.mode, "stopped");
  }
});

test("普通错误(gateway 没起、网络不通)⇒ 照常重连,不清口令", () => {
  for (const err of [new Error("fetch failed"), new TypeError("boom"), "字符串错误", null, undefined]) {
    const r = step(initialReconnect, { type: "failed", error: err });
    assert.equal(r.action.kind, "schedule", `${String(err)} 不该被当成口令失效`);
  }
});

test("isPasswordFailure 认的是 PasswordRejected,而且靠 name 认(跨模块 instanceof 不可靠)", () => {
  assert.equal(isPasswordFailure(new PasswordRejected()), true);
  // 另一个 realm/打包副本里造出来的同名错误,照样要认
  const lookalike = Object.assign(new Error("口令未通过验证"), { name: "PasswordRejected" });
  assert.equal(isPasswordFailure(lookalike), true);
  assert.equal(isPasswordFailure(new Error("PasswordRejected")), false, "只是消息像不算");
  for (const x of [null, undefined, "PasswordRejected", 42, {}]) {
    assert.equal(isPasswordFailure(x), false);
  }
});

test("停下来之后不许自己复活:stopped 态收到 closed / online 一律不排队", () => {
  const stopped = step(initialReconnect, { type: "failed", error: new PasswordRejected() }).state;
  for (const ev of [{ type: "closed" }, { type: "online" }, { type: "visible" }]) {
    const r = step(stopped, ev);
    assert.equal(r.action.kind, "none", `stopped 态收到 ${ev.type} 不该重连`);
    assert.equal(r.state.mode, "stopped");
  }
  // 重新登录成功 = connected 事件,这是唯一的复活路径
  assert.equal(step(stopped, { type: "connected" }).state.mode, "connected");
});

// ---- §5 纯函数纪律 -----------------------------------------------------

test("reducer 不改入参(React state 直接换引用)", () => {
  const before = { ...initialReconnect };
  const r = step(initialReconnect, { type: "closed" });
  assert.deepEqual(initialReconnect, before);
  assert.notEqual(r.state, initialReconnect);
});

test("认不出的事件原样返回,不崩(协议会长,老约定不许退化)", () => {
  for (const ev of [{ type: "什么鬼" }, {}, null, undefined, "closed"]) {
    const r = step(initialReconnect, ev);
    assert.equal(r.action.kind, "none");
    assert.deepEqual(r.state, initialReconnect);
  }
});
