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

// 假 GitHub 上的关卡检查:占位 = 新发一条(id 递增),写回 = 改那一条;同名检查 GitHub 只认最新(id 最大)的一条。
// 放在 calls.checks 上,几次运行共用一个 recorder 就是共用同一个 GitHub。
function recorder() {
  const calls = [];
  const checks = [];
  Object.defineProperty(calls, "checks", { value: checks }); // 不参与 calls 的比较
  const poster = {
    async start(sha) {
      calls.push(["start", sha]);
      checks.push({ id: checks.length + 1, head_sha: sha, name: policy.check_name, app: { id: policy.gate_app_id }, status: "in_progress", conclusion: null, output: { title: "重算中" } });
      return checks.length;
    },
    async finish(sha, result, id) {
      calls.push(["finish", sha, result.status, result.conclusion, result.title, id]);
      Object.assign(checks[id - 1], { status: result.status, conclusion: result.conclusion ?? null, output: { title: result.title } });
    },
  };
  const fuse = { async set(sha, state, description) { calls.push(["fuse", sha, state, description]); } };
  return { calls, poster, fuse };
}
// 按提交列关卡检查(GITHUB_TOKEN 读)
function checkRunsPage(calls, p) {
  const m = /\/commits\/([0-9a-f]{40})\/check-runs/.exec(p);
  if (!m) return null;
  const list = (calls.checks ?? []).filter((c) => c.head_sha === m[1]);
  return { data: { total_count: list.length, check_runs: list }, next: null };
}
const latestOn = (calls, sha) => calls.checks.filter((c) => c.head_sha === sha).at(-1);
const prObj = (over = {}) => ({ number: 10, state: "open", changed_files: 1, head: { sha: HEAD, ref: "claude/x", repo: { full_name: "o/r" } }, base: { ref: "main" }, ...over });
function goodApi(calls, over = {}) {
  return {
    async get(p) {
      calls.push(["get", p]);
      if (over.get) return over.get(p);
      if (p.endsWith("/pulls/10")) return prObj();
      throw new Error(`没料到的请求 ${p}`);
    },
    async getPage(p) {
      calls.push(["getPage", p]);
      const cr = checkRunsPage(calls, p);
      if (cr) return cr;
      const listed = over.list?.(p); // PR 列表(按提交 / 按分支)一律翻页读
      if (listed) return { data: listed, next: null };
      if (p.includes("/files")) return { data: [{ filename: "web/a.ts" }], next: null };
      if (p.includes("/reviews")) return { data: [], next: null };
      if (p.includes("/actions/runs")) return { data: { workflow_runs: [{ id: 1, path: ".github/workflows/ci.yml", head_sha: HEAD, status: "completed", conclusion: "success", pull_requests: [{ number: 10 }] }] }, next: null };
      if (p.includes("/activity")) return { data: [{ id: 1, timestamp: "t", activity_type: "push", after: HEAD, actor: { login: "SunJ1ayuBoT" } }], next: null };
      if (p.includes("/issues/10/events")) return { data: [], next: null };
      if (/\/commits\/[0-9a-f]{40}\/pulls/.test(p)) return { data: [prObj()], next: null }; // 含这个提交的 PR:#10(head 是 HEAD)
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

// ── aiwork-review[bot] 评审(PR #10 review 5354768826,@ ae8c58f)第 2 个阻断点 ─────────────────────
// workflow_run 没带关联 PR、运行的提交又不是 PR 当前 head(过时的提交 / 合并提交):
// 以前只在那个旧提交上写 failure 就收手,当前 head 上的旧 success 没人重算。
test("R16 workflow_run 没带 PR、提交已不是 head → 按提交查到 PR 后在当前 head 上重算,旧提交判 failure", async () => {
  const { calls, poster, fuse } = recorder();
  const api = goodApi(calls, { list: (p) => (p.includes(`/commits/${OLD}/pulls`) ? [prObj()] : undefined) });
  await gate({ repo: "o/r", eventName: "workflow_run", event: wrEvent({ head_sha: OLD, pull_requests: [] }), policy, api, poster, fuse });
  const fin = calls.filter((c) => c[0] === "finish");
  assert.deepEqual(fin.find((c) => c[1] === OLD)?.slice(2, 4), ["completed", "failure"]);
  assert.ok(fin.some((c) => c[1] === HEAD && c[2] === "completed"), "当前 head 上重算出新结论");
  assert.deepEqual(fuses(calls, HEAD), ["pending", "failure"], "当前 head 的保险丝跟新结论");
});

test("R16b 按提交查不到 PR(比如合并提交)→ 再按事件里的分支查;都查不到才在该提交上判 failure", async () => {
  const MERGE = "d".repeat(40);
  const { calls, poster, fuse } = recorder();
  const api = goodApi(calls, { list: (p) => (p.includes(`/commits/${MERGE}/pulls`) ? [] : p.startsWith("/repos/o/r/pulls?") ? [prObj()] : undefined) });
  const ev = wrEvent({ head_sha: MERGE, pull_requests: [], head_branch: "claude/x", head_repository: { full_name: "o/r", owner: { login: "o" } } });
  await gate({ repo: "o/r", eventName: "workflow_run", event: ev, policy, api, poster, fuse });
  const byBranch = calls.find((c) => c[0] === "getPage" && c[1].startsWith("/repos/o/r/pulls?"));
  assert.ok(byBranch && byBranch[1].includes("state=open") && byBranch[1].includes(encodeURIComponent("o:claude/x")), byBranch?.[1]);
  assert.ok(calls.some((c) => c[0] === "finish" && c[1] === HEAD && c[2] === "completed"), "在 PR 当前 head 上重算");
  const { calls: c2, poster: p2, fuse: f2 } = recorder();
  const none = (p) => (p.includes("/commits/") || p.startsWith("/repos/o/r/pulls?") ? [] : undefined);
  await gate({ repo: "o/r", eventName: "workflow_run", event: ev, policy, api: goodApi(c2, { list: none }), poster: p2, fuse: f2 });
  assert.deepEqual(c2.filter((c) => c[0] === "finish").map((c) => c.slice(1, 4)), [[MERGE, "completed", "failure"]]);
});

// ── aiwork-review[bot] 评审(PR #10 review 5360642584,@ 0ce3f73)第 1 个阻断点 ─────────────────────
// 旧提交的事件到来、PR 已推进、收集又出错:以前只在旧提交上判 G8,当前 head 上的旧 success 没人压。
test("R18 事件提交已不是 head 且收集出错 → 事件提交与当前 head 都判 G8 failure(App 检查 + 保险丝)", async () => {
  const { calls, poster, fuse } = recorder();
  const api = goodApi(calls, { get: (p) => (p.endsWith("/pulls/10") ? prObj() : []) });
  const base = api.getPage;
  api.getPage = async (p) => {
    if (p.includes("/files")) throw new Error("HTTP 502 files");
    return base(p);
  };
  await gate({ repo: "o/r", eventName: "workflow_run", event: wrEvent({ head_sha: OLD }), policy, api, poster, fuse });
  const fin = calls.filter((c) => c[0] === "finish");
  assert.deepEqual(fin.find((c) => c[1] === OLD)?.slice(2, 4), ["completed", "failure"]);
  const onHead = fin.find((c) => c[1] === HEAD);
  assert.ok(onHead, "当前 head 上也要写结论");
  assert.deepEqual(onHead.slice(2, 4), ["completed", "failure"]);
  assert.match(onHead[4], /G8/);
  assert.deepEqual(fuses(calls, HEAD), ["pending", "failure"]);
});

test("R18b 连 PR 本身都读不到 → 无从知道当前 head,只在事件提交上判 G8 failure", async () => {
  const { calls, poster, fuse } = recorder();
  const api = goodApi(calls, { get: () => { throw new Error("HTTP 503"); } });
  await gate({ repo: "o/r", eventName: "workflow_run", event: wrEvent({ head_sha: OLD }), policy, api, poster, fuse });
  const fin = calls.filter((c) => c[0] === "finish");
  assert.deepEqual(fin.map((c) => c.slice(1, 4)), [[OLD, "completed", "failure"]]);
  assert.match(fin[0][4], /G8/, "读不到就说读不到,不说它已不是 head");
});

// ── aiwork-review[bot] 补充评审(PR #10 review 5360728878,@ 0ce3f73)─────────────────────────────
// 同一提交可能同时是几个开着的 PR 的 head(目标分支不同 ⇒ 改动、要求都不同),而检查和保险丝都挂在提交上:
// 以前按 PR 各判各的、后写的覆盖先写的 ⇒ 一个 PR 的放行能盖掉另一个 PR 的不放行(还能专门开一个 PR 来"借"放行)。
const reviewBody = (sha, verdict = "PASS") => "```json\n" + JSON.stringify({ verdict, head_sha: sha, model: "gpt-x", family: "openai", completeness: "complete", files_read: ["a"] }) + "\n```";
// 假 GitHub:几个开着的 PR,各有自己的 head、改动文件和一条 aiwork-review 评审(默认 PASS);CI、推送记录都按各自的 head 给。
// 按提交列 PR 时把它们全列上(含这个提交的 PR),head 是不是这个提交由关卡自己看。
function prsApi(calls, prs, { siblingsFail = false } = {}) {
  const numbers = Object.keys(prs).map(Number);
  const pr = (n) => prObj({ number: n, head: { sha: prs[n].head, ref: `claude/pr${n}`, repo: { full_name: "o/r" } } });
  return {
    async get(p) {
      calls.push(["get", p]);
      const m = /\/pulls\/(\d+)$/.exec(p);
      if (m && prs[m[1]]) return pr(Number(m[1]));
      throw new Error(`没料到的请求 ${p}`);
    },
    async getPage(p) {
      calls.push(["getPage", p]);
      const cr = checkRunsPage(calls, p);
      if (cr) return cr;
      const m = /\/pulls\/(\d+)\/(files|reviews)/.exec(p);
      if (m && m[2] === "files") return { data: prs[m[1]].files.map((f) => ({ filename: f })), next: null };
      if (m && m[2] === "reviews") {
        const { head, verdict } = prs[m[1]];
        return { data: [{ id: 1, user: { login: "aiwork-review[bot]", type: "Bot" }, state: "COMMENTED", commit_id: head, submitted_at: "2026-09-29T09:00:00Z", body: reviewBody(head, verdict) }], next: null };
      }
      if (/\/commits\/[0-9a-f]{40}\/pulls/.test(p)) {
        if (siblingsFail) throw new Error("HTTP 502 commits/pulls");
        return { data: numbers.map(pr), next: null };
      }
      const ci = /\/actions\/runs\?head_sha=([0-9a-f]{40})/.exec(p);
      if (ci) {
        const on = numbers.filter((n) => prs[n].head === ci[1]).map((n) => ({ number: n }));
        return { data: { workflow_runs: [{ id: 1, path: ".github/workflows/ci.yml", head_sha: ci[1], status: "completed", conclusion: "success", pull_requests: on, created_at: "2026-09-29T08:00:00Z" }] }, next: null };
      }
      const act = /\/activity\?ref=refs%2Fheads%2Fclaude%2Fpr(\d+)/.exec(p);
      if (act) return { data: [{ id: 1, timestamp: "t", activity_type: "push", after: prs[act[1]].head, actor: { login: "SunJ1ayuBoT" } }], next: null };
      if (p.includes("/events")) return { data: [], next: null };
      throw new Error(`没料到的请求 ${p}`);
    },
  };
}
const sameHead = (files10, files11) => ({ 10: { head: HEAD, files: files10 }, 11: { head: HEAD, files: files11 } });

test("R20 同一提交上另一个开着的 PR 不放行 → 这个提交上的结论就是不放行(不管哪个 PR 后算)", async () => {
  for (const number of [10, 11]) {
    const { calls, poster, fuse } = recorder();
    await gate({ repo: "o/r", eventName: "pull_request_target", event: { pull_request: { number, head: { sha: HEAD } } }, policy, api: prsApi(calls, sameHead(["web/a.ts"], [".github/workflows/ci.yml"])), poster, fuse });
    const fin = calls.filter((c) => c[0] === "finish" && c[1] === HEAD);
    assert.equal(fin.at(-1)[3], "failure", `从 PR #${number} 触发:${fin.at(-1)[4]}`);
    if (number === 10) assert.match(fin.at(-1)[4], /#11/, "从放行的 PR 触发时,标题点名拦住它的那个 PR");
    assert.equal(fuses(calls, HEAD).at(-1), "failure");
  }
});

test("R20b 同一提交上的 PR 都放行 → 放行;查同一提交上的其他 PR 失败 → G8", async () => {
  const { calls, poster, fuse } = recorder();
  await gate({ repo: "o/r", eventName: "pull_request_target", event: prtEvent, policy, api: prsApi(calls, sameHead(["web/a.ts"], ["web/b.ts"])), poster, fuse });
  assert.equal(calls.filter((c) => c[0] === "finish").at(-1)[3], "success", "对照:两个都放行");
  const r2 = recorder();
  await gate({ repo: "o/r", eventName: "pull_request_target", event: prtEvent, policy, api: prsApi(r2.calls, sameHead(["web/a.ts"], [".github/workflows/ci.yml"]), { siblingsFail: true }), poster: r2.poster, fuse: r2.fuse });
  const last = r2.calls.filter((c) => c[0] === "finish").at(-1);
  assert.equal(last[3], "failure");
  assert.match(last[4], /G8/);
});

// ── aiwork-review[bot] 评审(PR #10 review 5361260820,@ 53fa9ed)第 1 个阻断点 ─────────────────────
// 并发组按事件的提交分,运行却写到 PR 当前的 head:旧提交的事件和新 head 的事件同时在算同一个 head 时互不取消。
// 以前保险丝"谁最后写听谁的":旧运行读到 PASS 后卡住,新运行读到 BLOCK 写回 failure,旧运行再写 success 就盖掉了。
// 现在一个提交上以最新的那条关卡检查为准(占位在读数据之前 ⇒ 最新那条背后的数据也最新),保险丝跟它走。
test("R22 旧运行慢一步:新运行已在同一 head 写回 failure,旧运行再写 success 也盖不掉(检查和保险丝都以最新那条为准)", async () => {
  const r = recorder();
  let release;
  const held = new Promise((res) => (release = res));
  let reached;
  const atWrite = new Promise((res) => (reached = res));
  const slow = { start: r.poster.start, async finish(sha, result, id) { if (sha === HEAD) { reached(); await held; } return r.poster.finish(sha, result, id); } };
  const pass = { 10: { head: HEAD, files: ["web/a.ts"] } };
  const block = { 10: { head: HEAD, files: ["web/a.ts"], verdict: "BLOCK" } };
  const older = gate({ repo: "o/r", eventName: "workflow_run", event: wrEvent({ head_sha: OLD }), policy, api: prsApi(r.calls, pass), poster: slow, fuse: r.fuse });
  await atWrite; // 旧运行:读到 PASS、算出 success,卡在写回之前
  await gate({ repo: "o/r", eventName: "pull_request_target", event: prtEvent, policy, api: prsApi(r.calls, block), poster: r.poster, fuse: r.fuse });
  release();
  await older;
  const onHead = r.calls.filter((c) => c[0] === "finish" && c[1] === HEAD).map((c) => c[3]);
  assert.deepEqual(onHead, ["failure", "success"], "前提:新运行先写 failure,旧运行后写 success");
  assert.equal(latestOn(r.calls, HEAD).conclusion, "failure", "最新那条检查是新运行的");
  assert.equal(fuses(r.calls, HEAD).at(-1), "failure", "保险丝跟最新那条检查,不跟最后写的旧运行");
});

test("R22b 之后又有两次运行占位:一次已写回 success、更新的那次还在算 → 以 id 最大的为准,保险丝停在 pending", async () => {
  const r = recorder();
  await gate({ repo: "o/r", eventName: "pull_request_target", event: prtEvent, policy, api: prsApi(r.calls, { 10: { head: HEAD, files: ["web/a.ts"] } }), poster: {
    start: r.poster.start,
    async finish(sha, result, id) {
      // 写回前,另外两次运行在同一 head 上先后占位;先占位的那次已经写回 success
      const done = await r.poster.start(sha);
      await r.poster.finish(sha, { status: "completed", conclusion: "success", title: "较早的一次:放行" }, done);
      await r.poster.start(sha);
      return r.poster.finish(sha, result, id);
    },
  }, fuse: r.fuse });
  assert.equal(r.calls.filter((c) => c[0] === "finish").at(-1)[3], "success", "前提:这次运行算出 success");
  assert.equal(fuses(r.calls, HEAD).at(-1), "pending");
});

test("R22c 看完最新那条、还没拨保险丝时,更新的运行已写回 failure(它的保险丝先落地)→ 拨完再看一眼,跟回 failure", async () => {
  const r = recorder();
  let interleaved = false;
  const fuse = {
    async set(sha, state, d) {
      if (sha === HEAD && state === "success" && !interleaved) {
        interleaved = true;
        const id = await r.poster.start(HEAD); // 另一次更新的运行:占位、算完、写回 failure、拨保险丝
        await r.poster.finish(HEAD, { status: "completed", conclusion: "failure", title: "新运行:不放行" }, id);
        await r.fuse.set(HEAD, "failure", "新运行:不放行");
      }
      return r.fuse.set(sha, state, d);
    },
  };
  await gate({ repo: "o/r", eventName: "pull_request_target", event: prtEvent, policy, api: prsApi(r.calls, { 10: { head: HEAD, files: ["web/a.ts"] } }), poster: r.poster, fuse });
  assert.ok(interleaved, "前提:这次运行算出 success、正要拨保险丝");
  assert.equal(fuses(r.calls, HEAD).at(-1), "failure");
});

test("R22d 同名检查不是 aiwork-gate App 发的(比如 PR 里的 workflow 用 GITHUB_TOKEN 冒充)→ 保险丝不跟它", async () => {
  const r = recorder();
  const poster = {
    start: r.poster.start,
    async finish(sha, result, id) {
      await r.poster.finish(sha, result, id);
      r.calls.checks.push({ id: 999, head_sha: sha, name: policy.check_name, app: { id: 15368 }, status: "completed", conclusion: "success", output: { title: "冒充的放行" } });
    },
  };
  await gate({ repo: "o/r", eventName: "pull_request_target", event: prtEvent, policy, api: goodApi(r.calls), poster, fuse: r.fuse });
  assert.equal(r.calls.filter((c) => c[0] === "finish").at(-1)[3], "failure", "前提:关卡自己的结论是不放行");
  assert.equal(fuses(r.calls, HEAD).at(-1), "failure");
});

// 自查:事件的提交已不是这个 PR 的 head,却还是另一个开着的 PR 的 head。以前直接判"已不是任何开着的 PR 的 head"
// (没按提交列 PR 就下结论),把另一个 PR 的 success 盖成 failure;现在事件的提交和各 head 用同一套判法。
test("R23 事件的提交还是另一个开着的 PR 的 head → 按那个 PR 判,不说它已不是 head", async () => {
  const r = recorder();
  const prs = { 10: { head: HEAD, files: ["web/a.ts"] }, 11: { head: OLD, files: ["web/b.ts"] } };
  await gate({ repo: "o/r", eventName: "pull_request_target", event: { pull_request: { number: 10, head: { sha: OLD } } }, policy, api: prsApi(r.calls, prs), poster: r.poster, fuse: r.fuse });
  assert.equal(latestOn(r.calls, OLD).conclusion, "success", latestOn(r.calls, OLD).output.title);
  assert.equal(fuses(r.calls, OLD).at(-1), "success");
  assert.equal(latestOn(r.calls, HEAD).conclusion, "success");
});
