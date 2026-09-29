// aiwork 放行关卡入口(.github/aiwork-gate/run.mjs)的失败处理:任何一步出错都不许留下旧的"放行"。
// GPT 评审(PR #10 @ 58d9bea)第 4、5 条:策略缺 App ID 时要在动手前就失败;G8 之外的 API 失败(查 PR 号、
// 读 PR)不能让关卡半路退出、把上一次的 success 留在 head 上。
// 跑法:node --test tests/test_aiwork_gate_run.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const { gate, validatePolicy, targetsFromEvent } = await import("../.github/aiwork-gate/run.mjs");
const policy = JSON.parse(readFileSync(new URL("../.aiwork/policy.json", import.meta.url), "utf8"));
const HEAD = "a".repeat(40);
const OLD = "b".repeat(40);

function recorder() {
  const calls = [];
  let n = 0;
  const poster = {
    async start(sha) { calls.push(["start", sha]); return ++n; },
    async finish(sha, result, id) { calls.push(["finish", sha, result.status, result.conclusion, result.title, id]); },
  };
  return { calls, poster };
}
const prObj = (over = {}) => ({ number: 10, state: "open", changed_files: 1, head: { sha: HEAD, ref: "claude/x", repo: { full_name: "o/r" } }, base: { ref: "main" }, ...over });
function goodApi(calls, over = {}) {
  return {
    async get(p) {
      calls.push(["get", p]);
      if (over.get) return over.get(p);
      if (p.endsWith("/pulls/10")) return prObj();
      if (p.includes("/commits/")) return [prObj()];
      throw new Error(`没料到的请求 ${p}`);
    },
    async getPage(p) {
      calls.push(["getPage", p]);
      if (p.includes("/files")) return { data: [{ filename: "web/a.ts" }], next: null };
      if (p.includes("/reviews")) return { data: [], next: null };
      if (p.includes("/actions/runs")) return { data: { workflow_runs: [{ id: 1, path: ".github/workflows/ci.yml", head_sha: HEAD, status: "completed", conclusion: "success", pull_requests: [{ number: 10 }] }] }, next: null };
      if (p.includes("/activity")) return { data: [{ id: 1, timestamp: "t", activity_type: "push", after: HEAD, actor: { login: "SunJ1ayuBoT" } }], next: null };
      throw new Error(`没料到的请求 ${p}`);
    },
  };
}
const prtEvent = { pull_request: { number: 10, head: { sha: HEAD } } };
const wrEvent = (over = {}) => ({ workflow_run: { event: "pull_request_review", head_sha: HEAD, pull_requests: [{ number: 10 }], ...over } });

test("R4 策略缺 App ID(或其他必填项)→ 在读任何数据、发任何检查之前就失败", async () => {
  assert.throws(() => validatePolicy({ ...policy, gate_app_id: null }), /gate_app_id/);
  assert.throws(() => validatePolicy({ ...policy, check_name: "" }), /check_name/);
  assert.throws(() => validatePolicy({ ...policy, builders: {} }), /builders/);
  assert.doesNotThrow(() => validatePolicy(policy));
  const { calls, poster } = recorder();
  await assert.rejects(gate({ repo: "o/r", eventName: "pull_request_target", event: prtEvent, policy: { ...policy, gate_app_id: null }, api: goodApi(calls), poster }));
  assert.deepEqual(calls, [], "一个请求都不该发出去");
});

test("R5 先占位(in_progress)再读数据:占位压掉旧结论,之后半路出任何事 head 上都不会是旧的 success", async () => {
  const { calls, poster } = recorder();
  await gate({ repo: "o/r", eventName: "pull_request_target", event: prtEvent, policy, api: goodApi(calls), poster });
  assert.deepEqual(calls[0], ["start", HEAD], "第一件事是占位");
  const fin = calls.filter((c) => c[0] === "finish");
  assert.equal(fin.length, 1);
  assert.equal(fin[0][1], HEAD);
  assert.equal(fin[0][2], "completed");
  assert.equal(fin[0][5], 1, "结论写回占位的那一条检查");
});

test("R5b 查 PR 号的请求失败(G8 之外)→ 在事件给的提交上判 failure,不是半路退出", async () => {
  const { calls, poster } = recorder();
  const api = goodApi(calls, { get: (p) => { throw new Error(`HTTP 502 ${p}`); } });
  await gate({ repo: "o/r", eventName: "workflow_run", event: wrEvent({ pull_requests: [] }), policy, api, poster });
  const fin = calls.filter((c) => c[0] === "finish");
  assert.equal(fin.length, 1);
  assert.deepEqual(fin[0].slice(1, 4), [HEAD, "completed", "failure"]);
  assert.ok(calls.findIndex((c) => c[0] === "start") < calls.findIndex((c) => c[0] === "get"), "先占位再查");
});

test("R5c 读 PR 本身失败 → 占位改成 failure(G8)", async () => {
  const { calls, poster } = recorder();
  const api = goodApi(calls, { get: () => { throw new Error("HTTP 403 rate limit"); } });
  await gate({ repo: "o/r", eventName: "pull_request_target", event: prtEvent, policy, api, poster });
  const fin = calls.filter((c) => c[0] === "finish");
  assert.deepEqual(fin[0].slice(1, 4), [HEAD, "completed", "failure"]);
  assert.match(fin[0][4], /G8/);
});

test("R5d 占位本身发不出去(App 令牌坏了)→ 整个运行失败,也不去读数据", async () => {
  const calls = [];
  const poster = { async start() { throw new Error("换令牌失败"); }, async finish() { calls.push(["finish"]); } };
  await assert.rejects(gate({ repo: "o/r", eventName: "pull_request_target", event: prtEvent, policy, api: goodApi(calls), poster }), /换令牌失败/);
  assert.deepEqual(calls, []);
});

test("R5e PR 在事件之后又推了新提交:旧提交上的占位判 failure,新 head 另起一条检查", async () => {
  const { calls, poster } = recorder();
  await gate({ repo: "o/r", eventName: "workflow_run", event: wrEvent({ head_sha: OLD }), policy, api: goodApi(calls), poster });
  const fin = calls.filter((c) => c[0] === "finish");
  const old = fin.find((c) => c[1] === OLD);
  const now = fin.find((c) => c[1] === HEAD);
  assert.deepEqual(old.slice(2, 4), ["completed", "failure"]);
  assert.equal(now[2], "completed");
  assert.ok(calls.some((c) => c[0] === "start" && c[1] === HEAD));
});

test("R5f 与 PR 无关的 workflow_run(比如 main 上的 push 触发的 CI)→ 什么都不做", async () => {
  const { calls, poster } = recorder();
  await gate({ repo: "o/r", eventName: "workflow_run", event: wrEvent({ event: "push", pull_requests: [] }), policy, api: goodApi(calls), poster });
  assert.deepEqual(calls, []);
  assert.ok(targetsFromEvent("workflow_run", wrEvent({ event: "push" })).skip);
});

test("R5g PR 已关闭 → 占位判 failure 收尾,不留 in_progress 也不给 success", async () => {
  const { calls, poster } = recorder();
  const api = goodApi(calls, { get: (p) => (p.endsWith("/pulls/10") ? prObj({ state: "closed" }) : [prObj()]) });
  await gate({ repo: "o/r", eventName: "pull_request_target", event: prtEvent, policy, api, poster });
  const fin = calls.filter((c) => c[0] === "finish");
  assert.deepEqual(fin[0].slice(1, 4), [HEAD, "completed", "failure"]);
});
