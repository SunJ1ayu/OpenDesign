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
  const fuse = { async set(sha, state, description) { calls.push(["fuse", sha, state, description]); } };
  return { calls, poster, fuse };
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

test("R4 策略缺 App ID(或其他必填项)→ 在读任何数据、发任何检查之前就失败(只拨保险丝)", async () => {
  assert.throws(() => validatePolicy({ ...policy, gate_app_id: null }), /gate_app_id/);
  assert.throws(() => validatePolicy({ ...policy, check_name: "" }), /check_name/);
  assert.throws(() => validatePolicy({ ...policy, builders: {} }), /builders/);
  assert.doesNotThrow(() => validatePolicy(policy));
  const { calls, poster, fuse } = recorder();
  await assert.rejects(gate({ repo: "o/r", eventName: "pull_request_target", event: prtEvent, policy: { ...policy, gate_app_id: null }, api: goodApi(calls), poster, fuse }));
  assert.deepEqual(calls.filter((c) => c[0] !== "fuse"), [], "不读数据、不发 App 检查");
  assert.deepEqual(calls.map((c) => c.slice(0, 3)), [["fuse", HEAD, "failure"]], "只把保险丝拨到 failure");
});

test("R5 先占位(in_progress)再读数据:占位压掉旧结论,之后半路出任何事 head 上都不会是旧的 success", async () => {
  const { calls, poster, fuse } = recorder();
  await gate({ repo: "o/r", eventName: "pull_request_target", event: prtEvent, policy, api: goodApi(calls), poster, fuse });
  assert.deepEqual(calls[0].slice(0, 3), ["fuse", HEAD, "pending"], "第一件事是拨保险丝(不靠 App 私钥)");
  assert.deepEqual(calls[1], ["start", HEAD], "第二件事是 App 占位,都在读数据之前");
  const fin = calls.filter((c) => c[0] === "finish");
  assert.equal(fin.length, 1);
  assert.equal(fin[0][1], HEAD);
  assert.equal(fin[0][2], "completed");
  assert.equal(fin[0][5], 1, "结论写回占位的那一条检查");
});

test("R5b 查 PR 号的请求失败(G8 之外)→ 在事件给的提交上判 failure,不是半路退出", async () => {
  const { calls, poster, fuse } = recorder();
  const api = goodApi(calls, { get: (p) => { throw new Error(`HTTP 502 ${p}`); } });
  await gate({ repo: "o/r", eventName: "workflow_run", event: wrEvent({ pull_requests: [] }), policy, api, poster, fuse });
  const fin = calls.filter((c) => c[0] === "finish");
  assert.equal(fin.length, 1);
  assert.deepEqual(fin[0].slice(1, 4), [HEAD, "completed", "failure"]);
  assert.ok(calls.findIndex((c) => c[0] === "start") < calls.findIndex((c) => c[0] === "get"), "先占位再查");
});

test("R5c 读 PR 本身失败 → 占位改成 failure(G8)", async () => {
  const { calls, poster, fuse } = recorder();
  const api = goodApi(calls, { get: () => { throw new Error("HTTP 403 rate limit"); } });
  await gate({ repo: "o/r", eventName: "pull_request_target", event: prtEvent, policy, api, poster, fuse });
  const fin = calls.filter((c) => c[0] === "finish");
  assert.deepEqual(fin[0].slice(1, 4), [HEAD, "completed", "failure"]);
  assert.match(fin[0][4], /G8/);
});

test("R5d 占位本身发不出去(App 令牌坏了)→ 整个运行失败,也不去读数据", async () => {
  const calls = [];
  const poster = { async start() { throw new Error("换令牌失败"); }, async finish() { calls.push(["finish"]); } };
  const fuse = { async set(sha, state) { calls.push(["fuse", sha, state]); } };
  await assert.rejects(gate({ repo: "o/r", eventName: "pull_request_target", event: prtEvent, policy, api: goodApi(calls), poster, fuse }), /换令牌失败/);
  assert.deepEqual(calls.filter((c) => c[0] !== "fuse"), [], "不读数据、不写结论");
});

test("R5e PR 在事件之后又推了新提交:旧提交上的占位判 failure,新 head 另起一条检查", async () => {
  const { calls, poster, fuse } = recorder();
  await gate({ repo: "o/r", eventName: "workflow_run", event: wrEvent({ head_sha: OLD }), policy, api: goodApi(calls), poster, fuse });
  const fin = calls.filter((c) => c[0] === "finish");
  const old = fin.find((c) => c[1] === OLD);
  const now = fin.find((c) => c[1] === HEAD);
  assert.deepEqual(old.slice(2, 4), ["completed", "failure"]);
  assert.equal(now[2], "completed");
  assert.ok(calls.some((c) => c[0] === "start" && c[1] === HEAD));
});

test("R5f 与 PR 无关的 workflow_run(比如 main 上的 push 触发的 CI)→ 什么都不做", async () => {
  const { calls, poster, fuse } = recorder();
  await gate({ repo: "o/r", eventName: "workflow_run", event: wrEvent({ event: "push", pull_requests: [] }), policy, api: goodApi(calls), poster, fuse });
  assert.deepEqual(calls, []);
  assert.ok(targetsFromEvent("workflow_run", wrEvent({ event: "push" })).skip);
});

test("R5g PR 已关闭 → 占位判 failure 收尾,不留 in_progress 也不给 success", async () => {
  const { calls, poster, fuse } = recorder();
  const api = goodApi(calls, { get: (p) => (p.endsWith("/pulls/10") ? prObj({ state: "closed" }) : [prObj()]) });
  await gate({ repo: "o/r", eventName: "pull_request_target", event: prtEvent, policy, api, poster, fuse });
  const fin = calls.filter((c) => c[0] === "finish");
  assert.deepEqual(fin[0].slice(1, 4), [HEAD, "completed", "failure"]);
});

// ── aiwork-review[bot] 评审(PR #10 review 5353990150,@ 875569c)第 3 个阻断点 ─────────────────────
// 同一 head 已有 success,之后来了 BLOCK,重算时 App 私钥坏了:App 发不出新检查,旧 success 就一直挂着。
// 只有 App 自己能改它发的检查,所以另设一道不靠 App 私钥的"保险丝"(GITHUB_TOKEN 发的 commit status):
// 每次重算先把保险丝拨到 pending,App 把结论写回之后才跟着结论走;App 那一步出任何错 → 保险丝 failure。
// 转真拦截时两道都设为必过,旧 success 就挡不住保险丝。
const fuses = (calls, sha) => calls.filter((c) => c[0] === "fuse" && (!sha || c[1] === sha)).map((c) => c[2]);

test("R14 重算时 App 发不出占位(私钥坏了)→ 保险丝在该提交上判 failure,不读数据", async () => {
  const calls = [];
  const poster = { async start() { calls.push(["start"]); throw new Error("缺 aiwork-gate App 的私钥"); }, async finish() { calls.push(["finish"]); } };
  const fuse = { async set(sha, state, d) { calls.push(["fuse", sha, state, d]); } };
  await assert.rejects(gate({ repo: "o/r", eventName: "pull_request_target", event: prtEvent, policy, api: goodApi(calls), poster, fuse }), /私钥/);
  assert.deepEqual(fuses(calls, HEAD), ["pending", "failure"]);
  assert.ok(calls.findIndex((c) => c[0] === "fuse") < calls.findIndex((c) => c[0] === "start"), "保险丝先于 App 拨下,不靠 App 私钥");
  assert.ok(!calls.some((c) => c[0] === "get" || c[0] === "getPage"), "不读数据");
});

test("R14b 正常重算:保险丝先 pending,App 写回结论之后才跟着结论走", async () => {
  const { calls, poster, fuse } = recorder();
  await gate({ repo: "o/r", eventName: "pull_request_target", event: prtEvent, policy, api: goodApi(calls), poster, fuse });
  assert.deepEqual(fuses(calls, HEAD), ["pending", "failure"], "没有评审 ⇒ App 判 failure,保险丝同样 failure");
  const lastFuse = calls.findLastIndex((c) => c[0] === "fuse");
  assert.ok(calls.findIndex((c) => c[0] === "finish") < lastFuse, "App 写回之后才拨保险丝");
  assert.ok(calls.findIndex((c) => c[0] === "fuse") < calls.findIndex((c) => c[0] === "start"));
});

test("R14c App 写不回结论(PATCH 失败)→ 保险丝 failure,运行失败", async () => {
  const { calls, fuse } = recorder();
  const poster = { async start() { return 1; }, async finish() { throw new Error("HTTP 401 Bad credentials"); } };
  await assert.rejects(gate({ repo: "o/r", eventName: "pull_request_target", event: prtEvent, policy, api: goodApi(calls), poster, fuse }), /401/);
  assert.equal(fuses(calls, HEAD).at(-1), "failure");
});

test("R14d 策略不合法 → 不读数据、不发检查,但保险丝照样拨到 failure", async () => {
  const { calls, poster, fuse } = recorder();
  await assert.rejects(gate({ repo: "o/r", eventName: "pull_request_target", event: prtEvent, policy: { ...policy, gate_app_id: null }, api: goodApi(calls), poster, fuse }), /gate_app_id/);
  assert.deepEqual(calls.filter((c) => c[0] !== "fuse"), []);
  assert.deepEqual(fuses(calls, HEAD), ["failure"]);
});

test("R14e PR 中途推进:旧提交保险丝 failure,新 head 保险丝跟新结论", async () => {
  const { calls, poster, fuse } = recorder();
  await gate({ repo: "o/r", eventName: "workflow_run", event: wrEvent({ head_sha: OLD }), policy, api: goodApi(calls), poster, fuse });
  assert.equal(fuses(calls, OLD).at(-1), "failure");
  assert.deepEqual(fuses(calls, HEAD), ["pending", "failure"]);
});

test("R14f 保险丝本身拨不动(GITHUB_TOKEN 出错)→ App 照常写回结论,运行最后报错", async () => {
  const { calls, poster } = recorder();
  const fuse = { async set() { calls.push(["fuse-fail"]); throw new Error("HTTP 403 statuses"); } };
  await assert.rejects(gate({ repo: "o/r", eventName: "pull_request_target", event: prtEvent, policy, api: goodApi(calls), poster, fuse }), /statuses/);
  const fin = calls.filter((c) => c[0] === "finish");
  assert.deepEqual(fin.map((c) => c.slice(1, 4)), [[HEAD, "completed", "failure"]], "App 的新结论照样写回");
});
