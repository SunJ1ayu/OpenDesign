// aiwork 放行关卡(.github/aiwork-gate/)的对抗用例。计划:SunJ1ayu/aiwork WORKFLOW-MIGRATION-PLAN.md 第 5 节。
// 跑法:node --test tests/test_aiwork_gate.mjs
// 编号 1–14 = 应拦下;A–C = 应放行(对照组,证明拦的不是一切)。
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";

const { decide, parseReviewBlock, matchAny } = await import("../.github/aiwork-gate/decide.mjs");
const { collect, collectCi, collectPushes, paginate } = await import("../.github/aiwork-gate/collect.mjs");
const policy = JSON.parse(readFileSync(new URL("../.aiwork/policy.json", import.meta.url), "utf8"));

const HEAD = "a".repeat(40);
const OLD = "b".repeat(40);

function review({ id = 1, login = "aiwork-review[bot]", type = "Bot", state = "COMMENTED", commit = HEAD, at = "2026-09-29T10:00:00Z", ...v }) {
  const block = {
    verdict: "PASS",
    head_sha: commit,
    model: "gpt-5-codex",
    family: "openai",
    completeness: "complete",
    files_read: ["web/src/a.ts"],
    ...v,
  };
  return { id, login, type, state, commit_id: commit, submitted_at: at, body: `评审意见……\n\n\`\`\`json\n${JSON.stringify(block)}\n\`\`\`\n` };
}
const approve = (commit = HEAD, at = "2026-09-29T11:00:00Z", state = "APPROVED") => ({
  id: 99, login: "SunJ1ayu", type: "User", state, commit_id: commit, submitted_at: at, body: "",
});

function facts(over = {}) {
  return {
    pr: { number: 10, state: "open", head_sha: HEAD, head_ref: "claude/x", base_ref: "main" },
    files: ["web/src/a.ts"],
    reviews: [review({})],
    ci: { state: "success", detail: "运行 1" },
    pushes: { covers_head: true, actors: ["SunJ1ayuBoT", "SunJ1ayuBoT"] },
    ...over,
  };
}
const run = (over) => decide(facts(over), policy);
const blocked = (r, rule) => {
  assert.equal(r.conclusion, "failure", `应拦下,实际 ${r.conclusion}:${r.title}`);
  if (rule) assert.match(r.summary, new RegExp(`❌ ${rule}`), `应因 ${rule} 拦下:\n${r.summary}`);
};

// ── 对照组 ──────────────────────────────────────────────────────────────
test("A 机器账号推送 + CI 绿 + 当前 head 上一条非 Claude 家族的 PASS → 放行", () => {
  const r = run();
  assert.equal(r.conclusion, "success", r.summary);
  assert.equal(r.status, "completed");
  assert.equal(r.author.family, "anthropic");
});

test("B UNKNOWN 作者 + 一条 PASS + 业主在当前 head 批准 + CI 绿 → 放行", () => {
  const r = run({ pushes: { covers_head: true, actors: ["SunJ1ayuBoT", "SunJ1ayu"] }, reviews: [review({}), approve()] });
  assert.equal(r.conclusion, "success", r.summary);
});

test("C high 路径 + 两个不同非作者家族 PASS + 业主批准 + CI 绿 → 放行", () => {
  const r = run({
    files: ["desktop/main.js"],
    reviews: [review({ id: 1 }), review({ id: 2, family: "deepseek", model: "deepseek-v4" }), approve()],
  });
  assert.equal(r.conclusion, "success", r.summary);
});

// ── 应拦下 ──────────────────────────────────────────────────────────────
test("1 CI 红 / 被跳过 / neutral / 还在跑 / 没跑 → 不放行(G1),业主批准也豁免不了", () => {
  for (const conclusion of ["failure", "skipped", "neutral", "cancelled"]) {
    blocked(run({ ci: { state: "failure", detail: `结论 ${conclusion}` }, reviews: [review({}), approve()] }), "G1");
  }
  for (const state of ["pending", "missing"]) {
    const r = run({ ci: { state, detail: "" }, reviews: [review({}), approve()] });
    assert.equal(r.status, "in_progress", "CI 没跑完时挂起等待,不给结论");
    assert.equal(r.conclusion, null);
  }
});

test("2 PR 新增一个同名的假 ci job:只认 ci.yml 这条路径的运行(G1)", async () => {
  const pr10 = [{ number: 10 }];
  const fake = { id: 9, path: ".github/workflows/sneaky.yml", head_sha: HEAD, status: "completed", conclusion: "success", name: "ci", pull_requests: pr10 };
  const real = { id: 5, path: ".github/workflows/ci.yml", head_sha: HEAD, status: "completed", conclusion: "failure", html_url: "u", pull_requests: pr10 };
  const api = { getPage: async () => ({ data: { workflow_runs: [fake, real] }, next: null }) };
  assert.equal((await collectCi(api, "o/r", HEAD, policy, 10)).state, "failure");
  const onlyFake = { getPage: async () => ({ data: { workflow_runs: [fake] }, next: null }) };
  assert.equal((await collectCi(onlyFake, "o/r", HEAD, policy, 10)).state, "missing");
  const withRef = { getPage: async () => ({ data: { workflow_runs: [{ ...real, path: ".github/workflows/ci.yml@refs/pull/10/merge", conclusion: "success" }] }, next: null }) };
  assert.equal((await collectCi(withRef, "o/r", HEAD, policy, 10)).state, "success", "路径带 @ref 后缀也认");
  const rerun = { getPage: async () => ({ data: { workflow_runs: [{ ...real, id: 5, conclusion: "success" }, { ...real, id: 6, conclusion: "failure" }] }, next: null }) };
  assert.equal((await collectCi(rerun, "o/r", HEAD, policy, 10)).state, "failure", "以最新一次运行为准");
  const running = { getPage: async () => ({ data: { workflow_runs: [{ ...real, status: "in_progress", conclusion: null }] }, next: null }) };
  assert.equal((await collectCi(running, "o/r", HEAD, policy, 10)).state, "pending");
});

test("3 改 ci.yml / run-all.sh / .aiwork/ 且业主未批准 → 不放行(G2);批准后放行", () => {
  for (const f of [".github/workflows/ci.yml", "tests/run-all.sh", "tests/e2e/run-all.sh", ".aiwork/policy.json", "tests/dead_assertions.allow"]) {
    blocked(run({ files: ["web/src/a.ts", f] }), "G7");
    assert.equal(run({ files: [f], reviews: [review({}), approve()] }).conclusion, "success", f);
  }
  assert.ok(!matchAny(policy.judging_surface, "tests/test_foo.py"), "普通测试文件不算判卷面");
});

test("4 没有评审;评审针对旧 head → 不放行(G3),业主批准也豁免不了", () => {
  blocked(run({ reviews: [] }), "G3");
  blocked(run({ reviews: [review({ commit: OLD })] }), "G3");
  blocked(run({ reviews: [review({ commit: OLD }), approve()] }), "G3");
  const mismatch = review({});
  mismatch.body = mismatch.body.replace(HEAD, OLD);
  blocked(run({ reviews: [mismatch] }), "G3");
  // 反过来:评审挂在旧提交上,结论块却写着当前 head —— 两处都得是当前 head 才算
  const postedOnOld = { ...review({}), commit_id: OLD };
  blocked(run({ reviews: [postedOnOld] }), "G3");
});

test("5 PASS 不是 aiwork-review 发的(机器账号或业主贴一段 PASS 的 JSON)→ 不算(G3)", () => {
  blocked(run({ reviews: [review({ login: "SunJ1ayuBoT", type: "User" })] }), "G3");
  blocked(run({ reviews: [review({ login: "SunJ1ayu", type: "User" })] }), "G3");
  blocked(run({ reviews: [review({ login: "aiwork-review[bot]", type: "User" })] }), "G3");
});

test("6 评审超时、降级、零上下文 → 不算(G3)", () => {
  blocked(run({ reviews: [review({ completeness: "partial" })] }), "G3");
  blocked(run({ reviews: [review({ completeness: "none" })] }), "G3");
  blocked(run({ reviews: [review({ files_read: [] })] }), "G3");
  blocked(run({ reviews: [review({ verdict: "NEEDS_MORE_INFO" })] }), "G3");
  const two = review({});
  two.body += "\n```json\n{}\n```\n";
  blocked(run({ reviews: [two] }), "G3");
  assert.equal(parseReviewBlock("```json\n{不是 json}\n```").ok, false);
});

test("7 评审家族等于作者家族(Claude 审 Claude)→ 不算(G3)", () => {
  blocked(run({ reviews: [review({ family: "anthropic", model: "claude-x" })] }), "G3");
});

test("8 分支上有非机器账号的推送(PR #6 的情形)→ UNKNOWN,要业主批准(G4)", () => {
  const r = run({ pushes: { covers_head: true, actors: ["SunJ1ayuBoT", "SunJ1ayu"] } });
  blocked(r, "G4");
  assert.match(r.title, /等业主批准/);
  blocked(run({ pushes: { covers_head: true, actors: ["SunJ1ayuBoT", "(已注销账号)"] } }), "G4");
});

test("9 活动记录里找不到当前 head 的推送 → UNKNOWN(G4)", () => {
  blocked(run({ pushes: { covers_head: false, actors: ["SunJ1ayuBoT"] } }), "G4");
  blocked(run({ pushes: { covers_head: true, actors: [] } }), "G4");
});

test("10 当前 head 上既有 PASS 又有 BLOCK → 不放行(G5);撤销掉的 BLOCK 照样算", () => {
  blocked(run({ reviews: [review({ id: 1 }), review({ id: 2, verdict: "BLOCK", family: "deepseek" })] }), "G5");
  blocked(run({ reviews: [review({ id: 1 }), review({ id: 2, verdict: "BLOCK", state: "DISMISSED" })] }), "G5");
  const rc = review({ id: 2, state: "CHANGES_REQUESTED" });
  blocked(run({ reviews: [review({ id: 1 }), rc] }), "G5");
  const ok = run({ reviews: [review({ id: 1 }), review({ id: 2, verdict: "BLOCK" }), approve()] });
  assert.equal(ok.conclusion, "success", "业主在当前 head 批准可以豁免 BLOCK");
});

test("11 high 路径只有一家 PASS,或缺业主批准 → 不放行(G6)", () => {
  blocked(run({ files: ["desktop/lib/updateState.js"], reviews: [review({}), approve()] }), "G6");
  blocked(run({ files: ["installer/RELEASE.md"], reviews: [review({ id: 1 }), review({ id: 2, model: "gpt-5" }), approve()] }), "G6");
  blocked(run({ files: ["bin/ds_credential.py"], reviews: [review({ id: 1 }), review({ id: 2, family: "deepseek" })] }), "G7");
});

test("12 业主批准针对旧 head;业主批准豁免不了红 CI(G7)", () => {
  blocked(run({ pushes: { covers_head: true, actors: ["SunJ1ayu"] }, reviews: [review({}), approve(OLD)] }), "G7");
  blocked(run({ ci: { state: "failure", detail: "x" }, reviews: [review({}), approve()] }), "G1");
  const later = approve(HEAD, "2026-09-29T12:00:00Z", "CHANGES_REQUESTED");
  blocked(run({ pushes: { covers_head: true, actors: ["SunJ1ayu"] }, reviews: [review({}), approve(), { ...later, id: 100 }] }), "G7");
});

test("13 API 出错、限流、分页不全、条数对不上 → 抛错(G8,由 main.mjs 判 failure)", async () => {
  const boom = { get: async () => { throw new Error("HTTP 403 rate limit"); }, getPage: async () => { throw new Error("HTTP 403"); } };
  await assert.rejects(collect(boom, "o/r", 10, policy));
  let n = 0;
  const endless = { getPage: async () => ({ data: [n++], next: "more" }) };
  await assert.rejects(paginate(endless, "/x"), /还没取完/);
  const pr = { number: 10, state: "open", changed_files: 3, head: { sha: HEAD, ref: "claude/x", repo: { full_name: "o/r" } }, base: { ref: "main" } };
  const short = {
    get: async () => pr,
    getPage: async (p) => ({ data: p.includes("/files") ? [{ filename: "a" }] : [], next: null }),
  };
  await assert.rejects(collect(short, "o/r", 10, policy), /改动文件取到 1 个/);
  const notList = { getPage: async () => ({ data: { message: "Not Found" }, next: null }) };
  await assert.rejects(paginate(notList, "/y"), /不是列表/);
});

test("14 PR 改 .github/aiwork-gate/ 或策略本身 → 算判卷面(G2)", () => {
  for (const f of [".github/aiwork-gate/decide.mjs", ".github/workflows/aiwork-gate.yml", ".aiwork/policy.json"]) {
    blocked(run({ files: [f] }), "G2");
  }
});

// ── 收集:作者只看这一世分支的推送者 ─────────────────────────────────────
test("推送者:只数到最近一次建分支;删分支之前的上一世不算;没推到当前 head 就不算覆盖", async () => {
  const acts = [
    { id: 5, timestamp: "2026-09-29T05:00:00Z", activity_type: "push", after: HEAD, actor: { login: "SunJ1ayuBoT" } },
    { id: 4, timestamp: "2026-09-29T04:00:00Z", activity_type: "branch_creation", after: OLD, actor: { login: "SunJ1ayuBoT" } },
    { id: 3, timestamp: "2026-09-28T03:00:00Z", activity_type: "branch_deletion", after: "0".repeat(40), actor: { login: "SunJ1ayu" } },
    { id: 2, timestamp: "2026-09-28T02:00:00Z", activity_type: "push", after: OLD, actor: { login: "SunJ1ayu" } },
  ];
  const api = { getPage: async () => ({ data: acts, next: null }) };
  assert.deepEqual(await collectPushes(api, "o/r", "claude/x", HEAD), { covers_head: true, actors: ["SunJ1ayuBoT", "SunJ1ayuBoT"] });
  const noDel = acts.filter((a) => a.id !== 3 && a.id !== 4);
  const api2 = { getPage: async () => ({ data: noDel, next: null }) };
  assert.deepEqual((await collectPushes(api2, "o/r", "claude/x", HEAD)).actors, ["SunJ1ayuBoT", "SunJ1ayu"], "没建删记录就一直往回数");
  const api3 = { getPage: async () => ({ data: acts, next: null }) };
  assert.equal((await collectPushes(api3, "o/r", "claude/x", "c".repeat(40))).covers_head, false);
});

test("收集:fork 来的 PR 没有推送记录 → 作者 UNKNOWN;改名文件的旧路径也算改动", async () => {
  const pr = { number: 10, state: "open", changed_files: 1, head: { sha: HEAD, ref: "x", repo: { full_name: "evil/r" } }, base: { ref: "main" } };
  const api = {
    get: async () => pr,
    getPage: async (p) => {
      if (p.includes("/files")) return { data: [{ filename: "web/a.ts", previous_filename: ".github/workflows/ci.yml" }], next: null };
      if (p.includes("/actions/runs")) return { data: { workflow_runs: [] }, next: null };
      return { data: [], next: null };
    },
  };
  const f = await collect(api, "o/r", 10, policy);
  assert.equal(f.pushes.covers_head, false);
  assert.ok(f.files.includes(".github/workflows/ci.yml"));
  blocked(decide({ ...f, ci: { state: "success", detail: "" }, reviews: [review({})] }, policy), "G2");
});

test("策略:check 名先用 shadow;判卷面罩住 .github 与 .aiwork;Builder 只有机器账号", () => {
  assert.equal(policy.check_name, "aiwork-gate-shadow");
  for (const p of [".github/**", ".aiwork/**"]) assert.ok(policy.judging_surface.includes(p));
  assert.deepEqual(policy.builders, { SunJ1ayuBoT: "anthropic" });
  assert.equal(policy.reviewer_bot, "aiwork-review[bot]");
  assert.ok(Number.isInteger(policy.gate_app_id) && policy.gate_app_id > 0, "gate_app_id 要填 aiwork-gate App 的 App ID");
});

// ── GPT 评审(PR #10 @ 58d9bea)指出的阻断点:先复现再修 ─────────────────────
test("R1 UNKNOWN 作者时,Builder 家族(anthropic)的 PASS 也不算 —— 不能靠 Claude 审 Claude 加业主批准放行", () => {
  const r = run({
    pushes: { covers_head: true, actors: ["SunJ1ayuBoT", "SunJ1ayu"] },
    reviews: [review({ family: "anthropic", model: "claude-x" }), approve()],
  });
  blocked(r, "G3");
  const high = run({
    files: ["desktop/main.js"],
    pushes: { covers_head: false, actors: [] },
    reviews: [review({ id: 1 }), review({ id: 2, family: "anthropic", model: "claude-x" }), approve()],
  });
  blocked(high, "G6");
});

test("R2 别的 PR 在同一提交上的 CI 不算到本 PR(G1)", async () => {
  const mine = { id: 5, path: ".github/workflows/ci.yml", head_sha: HEAD, status: "completed", conclusion: "failure", html_url: "u", pull_requests: [{ number: 10 }] };
  const other = { id: 9, path: ".github/workflows/ci.yml", head_sha: HEAD, status: "completed", conclusion: "success", pull_requests: [{ number: 11 }] };
  const api = { getPage: async () => ({ data: { workflow_runs: [mine, other] }, next: null }) };
  assert.equal((await collectCi(api, "o/r", HEAD, policy, 10)).state, "failure", "只认关联到本 PR 的运行");
  const onlyOther = { getPage: async () => ({ data: { workflow_runs: [other] }, next: null }) };
  assert.notEqual((await collectCi(onlyOther, "o/r", HEAD, policy, 10)).state, "success");
  const unlinked = { getPage: async () => ({ data: { workflow_runs: [{ ...other, pull_requests: [] }] }, next: null }) };
  assert.notEqual((await collectCi(unlinked, "o/r", HEAD, policy, 10)).state, "success", "没关联任何 PR 的运行也不算");
});

test("R3 业主批准早于 BLOCK:豁免不了那条 BLOCK;BLOCK 之后再批准才算(G5 / G7)", () => {
  const early = run({ reviews: [review({ id: 1 }), approve(HEAD, "2026-09-29T11:00:00Z"), review({ id: 2, verdict: "BLOCK", at: "2026-09-29T12:00:00Z" })] });
  blocked(early, "G7");
  const late = run({ reviews: [review({ id: 1 }), review({ id: 2, verdict: "BLOCK", at: "2026-09-29T12:00:00Z" }), approve(HEAD, "2026-09-29T13:00:00Z")] });
  assert.equal(late.conclusion, "success", late.summary);
});

test("R3b 业主在当前 head 上 Request changes:哪怕是普通 PR 也不放行", () => {
  blocked(run({ reviews: [review({}), approve(HEAD, "2026-09-29T11:00:00Z", "CHANGES_REQUESTED")] }), "G7");
});

// ── GPT 评审(PR #10 @ e604a31,aiwork-review[bot])的 3 个阻断点 ──────────────────
// 前两条的根因是"清单靠手抄":这里改成从仓库本身推出应该在清单里的文件,以后新加的也跑不掉。
const ROOT = new URL("../", import.meta.url);
const read = (p) => readFileSync(new URL(p, ROOT), "utf8");

test("R6 总跑实际调用的测试框架文件都算判卷面(含 tests/tmpdir-leak-gate.sh)", () => {
  const harness = new Set([
    ...read("tests/run-all.sh").match(/tests\/[A-Za-z0-9_./-]+\.(?:sh|py|allow|mjs)/g),
    ...read("tests/e2e/run-all.sh").match(/tests\/[A-Za-z0-9_./-]+\.(?:sh|py|allow|mjs)/g),
    ...readdirSync(new URL("tests/e2e/", ROOT))
      .filter((f) => !/\.e2e\.(?:mjs|py)$/.test(f) && f !== "README.md")
      .map((f) => `tests/e2e/${f}`),
    "tests/dead_assertions.allow",
  ]);
  const missing = [...harness].filter((f) => !matchAny(policy.judging_surface, f));
  assert.deepEqual(missing, [], `这些测试框架文件改了不用业主批准:${missing.join("、")}`);
  assert.ok(harness.has("tests/tmpdir-leak-gate.sh"), "量具:总跑确实调用 tmpdir-leak-gate.sh");
});

test("R7 bin/ 里凡是碰密钥(用 ds_credential 或处理 apiKey)的文件都在 high 里", () => {
  const keyFiles = readdirSync(new URL("bin/", ROOT))
    .filter((f) => /\.(?:py|ps1)$/.test(f))
    .filter((f) => /\bds_credential\b|apiKey|api_key/.test(read(`bin/${f}`)))
    .map((f) => `bin/${f}`);
  assert.ok(keyFiles.includes("bin/ds_web.py") && keyFiles.includes("bin/ds_credential.py"), "量具:扫得到");
  const missing = keyFiles.filter((f) => !matchAny(policy.high, f));
  assert.deepEqual(missing, [], `这些碰密钥的文件改了只要一家 PASS:${missing.join("、")}`);
  for (const f of ["bin/ds_merge_config.py", "bin/ds_shell_core.py"]) assert.ok(matchAny(policy.high, f), `${f} 管首次配置 / 启动注入 key`);
  const r = run({ files: ["bin/ds_web.py"], reviews: [review({})] });
  blocked(r, "G6");
});

test("真实样本:review-pr 第一次真发的评审(PR #10 review 5353128020)关卡读得懂,算作 BLOCK", () => {
  const sha = "e604a31d6f303ff6f9d305d4b73778acada787b8";
  const body = "**aiwork-review · subcodex · gpt-6-sol**\n\n## Findings\n\n- **P1 · …**\n\nConclusion: BLOCK\n\n```json\n" +
    '{"verdict":"BLOCK","head_sha":"e604a31d6f303ff6f9d305d4b73778acada787b8","model":"gpt-6-sol","family":"openai","completeness":"complete","files_read":[".aiwork/policy.json",".github/aiwork-gate/decide.mjs"]}' +
    "\n```\n";
  const p = parseReviewBlock(body);
  assert.equal(p.ok, true, p.why);
  assert.equal(p.value.family, "openai");
  const r = decide(facts({
    pr: { number: 10, state: "open", head_sha: sha, head_ref: "claude/exciting-johnson-w8a35g", base_ref: "main" },
    reviews: [{ id: 5353128020, login: "aiwork-review[bot]", type: "Bot", state: "COMMENTED", commit_id: sha, submitted_at: "2026-09-29T13:16:31Z", body }],
  }), policy);
  assert.equal(r.blocks.length, 1);
  blocked(r, "G5");
});

// ── aiwork-review[bot] 人工复核(评论 5891150875,@ e604a31)的 2 个阻断点 + 同类的撤销绕过 ─────────
const human = (login, state, at, id) => ({ id, login, type: "User", state, commit_id: HEAD, submitted_at: at, body: "" });

test("R9 其他协作者在当前 head 上 Request changes → 算 BLOCK(G5);业主在其后批准才放行", () => {
  blocked(run({ reviews: [review({}), human("someone", "CHANGES_REQUESTED", "2026-09-29T12:00:00Z", 50)] }), "G5");
  const waived = run({ reviews: [review({}), human("someone", "CHANGES_REQUESTED", "2026-09-29T12:00:00Z", 50), approve(HEAD, "2026-09-29T13:00:00Z")] });
  assert.equal(waived.conclusion, "success", waived.summary);
  const early = run({ reviews: [review({}), approve(HEAD, "2026-09-29T11:00:00Z"), human("someone", "CHANGES_REQUESTED", "2026-09-29T12:00:00Z", 50)] });
  blocked(early, "G7");
  const retracted = run({ reviews: [review({}), human("someone", "CHANGES_REQUESTED", "2026-09-29T12:00:00Z", 50), human("someone", "APPROVED", "2026-09-29T12:30:00Z", 51)] });
  assert.equal(retracted.conclusion, "success", "同一个人后来改成 Approve,就不再算反对");
  const onOld = { ...human("someone", "CHANGES_REQUESTED", "2026-09-29T12:00:00Z", 50), commit_id: OLD };
  assert.equal(run({ reviews: [review({}), onOld] }).conclusion, "success", "旧提交上的 Request changes 不管当前 head");
});

test("R9b 撤销评审抹不掉反对:被撤销的 Request changes 仍算 BLOCK,业主的也仍算业主反对", () => {
  blocked(run({ reviews: [review({}), human("someone", "DISMISSED", "2026-09-29T12:00:00Z", 50)] }), "G5");
  blocked(run({ reviews: [review({}), approve(HEAD, "2026-09-29T11:00:00Z", "CHANGES_REQUESTED"), approve(HEAD, "2026-09-29T11:00:00Z", "DISMISSED")].map((r, i) => ({ ...r, id: 90 + i })) }), "G7");
});

test("R10 分页响应自带 total_count 时,取到的条数必须对上,否则按 G8 抛错", async () => {
  const run1 = { id: 5, path: ".github/workflows/ci.yml", head_sha: HEAD, status: "completed", conclusion: "success", pull_requests: [{ number: 10 }] };
  const short = { getPage: async () => ({ data: { total_count: 2, workflow_runs: [run1] }, next: null }) };
  await assert.rejects(collectCi(short, "o/r", HEAD, policy, 10), /条数/);
  const exact = { getPage: async () => ({ data: { total_count: 1, workflow_runs: [run1] }, next: null }) };
  assert.equal((await collectCi(exact, "o/r", HEAD, policy, 10)).state, "success");
  let page = 0;
  const twoPages = { getPage: async () => ({ data: { total_count: 2, workflow_runs: [{ ...run1, id: 5 + page }] }, next: page++ === 0 ? "p2" : null }) };
  assert.equal((await collectCi(twoPages, "o/r", HEAD, policy, 10)).state, "success", "分两页取齐也对得上");
});

// ── aiwork-review[bot] 评审(PR #10 review 5353990150,@ 875569c)的前 2 个阻断点 ─────────────────
test("R12 aiwork-review 在当前 head 上发的东西,除非是格式完整、结论不是 BLOCK 的评审,否则一律按 BLOCK 算", () => {
  // 结论块写着 BLOCK,但缺 files_read —— 明确的 BLOCK 不能因为格式不全被当成"无效评审"丢掉
  const noFiles = review({ id: 2, verdict: "BLOCK" });
  noFiles.body = noFiles.body.replace(/,"files_read":\[[^\]]*\]/, "");
  assert.equal(parseReviewBlock(noFiles.body).ok, false, "量具:这条确实格式不全");
  const r = run({ reviews: [review({ id: 1 }), noFiles] });
  blocked(r, "G5");
  assert.equal(r.blocks.length, 1);
  // 看不懂的(两个结论块、不是 JSON、没有结论块、空正文)也按 BLOCK:看不出它原来想说什么,就当它反对
  for (const body of ["```json\n{\"verdict\":\"PASS\"}\n```\n```json\n{}\n```", "```json\n{不是 json}\n```", "Conclusion: BLOCK", ""]) {
    blocked(run({ reviews: [review({ id: 1 }), { ...review({ id: 3 }), body }] }), "G5");
  }
  // 结论块写 PASS、正文结论行却写 BLOCK:自相矛盾,按 BLOCK
  const contradict = review({ id: 4 });
  contradict.body = `**aiwork-review · subcodex · gpt-x**\n\nConclusion: BLOCK\n\n${contradict.body}`;
  blocked(run({ reviews: [review({ id: 1 }), contradict] }), "G5");
  // 业主在这些 BLOCK 之后批准,照常豁免
  const waived = run({ reviews: [review({ id: 1 }), noFiles, approve(HEAD, "2026-09-29T11:00:00Z")] });
  assert.equal(waived.conclusion, "success", waived.summary);
  // 对照:格式完整、只是不合格的 PASS(不完整、Builder 家族)不算 BLOCK,只是不算 PASS
  assert.equal(run({ reviews: [review({ id: 1 }), review({ id: 5, completeness: "partial" })] }).conclusion, "success");
  assert.equal(run({ reviews: [review({ id: 1 }), review({ id: 6, family: "anthropic" })] }).conclusion, "success");
  // 对照:旧提交上格式不全的评审不管当前 head
  assert.equal(run({ reviews: [review({ id: 1 }), { ...noFiles, commit_id: OLD }] }).conclusion, "success");
});

test("R13 首次安装 / 启动脚本调用的 bin 脚本、写登录口令的 bin 脚本,都在 high 里(含 bin/enable_webui.py)", () => {
  const launchers = readdirSync(new URL("bin/", ROOT)).filter((f) => f.endsWith(".ps1")).map((f) => `bin/${f}`).filter((f) => matchAny(policy.high, f));
  assert.ok(launchers.includes("bin/install.ps1"), "量具:安装脚本本身在 high");
  const called = [...new Set(launchers.flatMap((f) => [...read(f).matchAll(/bin[\\/]([A-Za-z0-9_.-]+\.(?:py|ps1))/g)].map((m) => `bin/${m[1]}`)))];
  assert.ok(called.includes("bin/enable_webui.py"), "量具:install.ps1 确实调用 enable_webui.py");
  const tokenWriters = readdirSync(new URL("bin/", ROOT))
    .filter((f) => /\.(?:py|ps1)$/.test(f))
    .filter((f) => /口令|password|\[["']token["']\]/i.test(read(`bin/${f}`)))
    .map((f) => `bin/${f}`);
  assert.ok(tokenWriters.includes("bin/enable_webui.py") && tokenWriters.includes("bin/ds_provision.py"), "量具:扫得到写口令的脚本");
  const missing = [...new Set([...called, ...tokenWriters])].filter((f) => !matchAny(policy.high, f));
  assert.deepEqual(missing, [], `这些首次配置 / 写口令的脚本改了只要一家 PASS:${missing.join("、")}`);
  blocked(run({ files: ["bin/enable_webui.py"], reviews: [review({})] }), "G6");
});

// ── aiwork-review[bot] 评审(PR #10 review 5354768826,@ ae8c58f)的第 1、3 个阻断点 ─────────────────
// 碰密钥的正则:ds_credential、apiKey / api_key、FOO_KEY 这类环境变量、口令、password、["token"] 写入
const SECRET_RE = /\bds_credential\b|apiKey|api_key|\b[A-Z][A-Z0-9_]*_KEY\b|口令|[Pp]assword|\[["']token["']\]/;

test("R15 首次配置模板(config/nanobot.config*.jsonc)、安装脚本引用的 bin/ 与 config/ 文件、bin/ 里碰密钥的文件(不限扩展名)都在 high", () => {
  const launchers = readdirSync(new URL("bin/", ROOT)).filter((f) => f.endsWith(".ps1")).map((f) => `bin/${f}`).filter((f) => matchAny(policy.high, f));
  const referenced = [...new Set(launchers.flatMap((f) => [...read(f).matchAll(/\b(bin|config)[\\/]([A-Za-z0-9_.-]+)/g)].map((m) => `${m[1]}/${m[2]}`)))]
    .filter((p) => existsSync(new URL(p, ROOT)));
  assert.ok(referenced.includes("config/nanobot.config.windows.jsonc"), "量具:install.ps1 把这份模板合进用户配置");
  const templates = readdirSync(new URL("config/", ROOT)).filter((f) => /^nanobot\.config.*\.jsonc$/.test(f)).map((f) => `config/${f}`);
  assert.ok(templates.length >= 2, "量具:Windows 与 Linux 两份模板");
  const keyFiles = readdirSync(new URL("bin/", ROOT), { withFileTypes: true })
    .filter((d) => d.isFile() && !d.name.endsWith(".pyc"))
    .map((d) => `bin/${d.name}`)
    .filter((f) => SECRET_RE.test(read(f)));
  assert.ok(keyFiles.includes("bin/ds-nanobot"), "量具:没有扩展名的 Linux 启动脚本(读 MIMO_TP_KEY)也扫得到");
  const missing = [...new Set([...referenced, ...templates, ...keyFiles])].filter((f) => !matchAny(policy.high, f));
  assert.deepEqual(missing, [], `这些首次配置 / 碰密钥的文件改了只要一家 PASS:${missing.join("、")}`);
  blocked(run({ files: ["config/nanobot.config.windows.jsonc"], reviews: [review({})] }), "G6");
  assert.ok(!matchAny(policy.high, "config/taxonomy.default.json"), "对照:分类表是产品数据,不算 high");
});

test("R17 目标分支在这次 CI 之后(或同一时刻)改过 → G1 不算通过(业主批准也豁免不了);CI 缺创建时间也不算", () => {
  const ci = { state: "success", detail: "运行 1", created_at: "2026-09-29T10:00:00Z" };
  blocked(run({ ci, base_changed_at: "2026-09-29T11:00:00Z" }), "G1");
  blocked(run({ ci, base_changed_at: "2026-09-29T11:00:00Z", reviews: [review({}), approve()] }), "G1");
  assert.equal(run({ ci, base_changed_at: "2026-09-29T09:00:00Z" }).conclusion, "success", "改目标在 CI 之前:这次 CI 测的就是新目标");
  assert.equal(run({ ci, base_changed_at: null }).conclusion, "success", "没改过目标分支");
  assert.match(run({ ci, base_changed_at: "2026-09-29T11:00:00Z" }).title, /CI/);
  blocked(run({ ci, base_changed_at: ci.created_at }), "G1");
  blocked(run({ ci: { state: "success", detail: "运行 1" }, base_changed_at: "2026-09-29T09:00:00Z" }), "G1");
});

test("R17b 收集:CI 运行带上创建时间;从 PR 事件里取最后一次改目标分支的时间", async () => {
  const run1 = { id: 5, path: ".github/workflows/ci.yml", head_sha: HEAD, status: "completed", conclusion: "success", pull_requests: [{ number: 10 }], created_at: "2026-09-29T10:00:00Z" };
  assert.equal((await collectCi({ getPage: async () => ({ data: { workflow_runs: [run1] }, next: null }) }, "o/r", HEAD, policy, 10)).created_at, "2026-09-29T10:00:00Z");
  const pr = { number: 10, state: "open", changed_files: 1, head: { sha: HEAD, ref: "x", repo: { full_name: "o/r" } }, base: { ref: "main" } };
  const events = [
    { id: 1, event: "base_ref_changed", created_at: "2026-09-29T08:00:00Z" },
    { id: 2, event: "labeled", created_at: "2026-09-29T12:00:00Z" },
    { id: 3, event: "base_ref_changed", created_at: "2026-09-29T11:00:00Z" },
  ];
  const seen = [];
  const api = {
    get: async () => pr,
    getPage: async (p) => {
      seen.push(p);
      if (p.includes("/files")) return { data: [{ filename: "web/a.ts" }], next: null };
      if (p.includes("/actions/runs")) return { data: { workflow_runs: [run1] }, next: null };
      if (p.includes("/issues/10/events")) return { data: events, next: null };
      return { data: [], next: null };
    },
  };
  const f = await collect(api, "o/r", 10, policy);
  assert.equal(f.base_changed_at, "2026-09-29T11:00:00Z");
  assert.ok(seen.some((p) => p.startsWith("/repos/o/r/issues/10/events")));
  blocked(decide({ ...f, reviews: [review({})], pushes: { covers_head: true, actors: ["SunJ1ayuBoT"] } }, policy), "G1");
  const boom = { ...api, getPage: async (p) => { if (p.includes("/issues/10/events")) throw new Error("HTTP 502"); return api.getPage(p); } };
  await assert.rejects(collect(boom, "o/r", 10, policy), /502/, "读不到事件 ⇒ G8,不能当成没改过");
});

// ── aiwork-review[bot] 评审(PR #10 review 5360642584,@ 0ce3f73)第 2 个阻断点 ─────────────────────
// 被撤销的评审按反对算(R9b);反对的时刻是**撤销那一刻**,不是它当初提交的时刻。
test("R19 评审在业主批准之后才被撤销 → 那次批准豁免不了;撤销在批准之前 → 照常豁免;缺撤销时间 → 豁免不了", () => {
  const dismissed = (at) => ({ ...human("someone", "DISMISSED", "2026-09-29T10:00:00Z", 50), dismissed_at: at });
  const owner = approve(HEAD, "2026-09-29T11:00:00Z");
  blocked(run({ reviews: [review({}), dismissed("2026-09-29T12:00:00Z"), owner] }), "G7");
  assert.equal(run({ reviews: [review({}), dismissed("2026-09-29T10:30:00Z"), owner] }).conclusion, "success", "撤销在批准之前");
  blocked(run({ reviews: [review({}), dismissed(undefined), owner] }), "G7");
  // 业主在撤销之后再批准 ⇒ 放行
  assert.equal(run({ reviews: [review({}), dismissed("2026-09-29T12:00:00Z"), approve(HEAD, "2026-09-29T13:00:00Z")] }).conclusion, "success");
});

test("R19b 收集:从 PR 事件里取每条被撤销评审的撤销时间;人的被撤销评审找不到撤销事件 → G8 抛错", async () => {
  const pr = { number: 10, state: "open", changed_files: 1, head: { sha: HEAD, ref: "x", repo: { full_name: "o/r" } }, base: { ref: "main" } };
  const reviews = [
    { id: 50, user: { login: "someone", type: "User" }, state: "DISMISSED", commit_id: HEAD, submitted_at: "2026-09-29T10:00:00Z", body: "" },
    { id: 51, user: { login: "someone", type: "User" }, state: "APPROVED", commit_id: OLD, submitted_at: "2026-09-29T09:00:00Z", body: "" },
  ];
  const mk = (events) => ({
    get: async () => pr,
    getPage: async (p) => {
      if (p.includes("/files")) return { data: [{ filename: "web/a.ts" }], next: null };
      if (p.includes("/reviews")) return { data: reviews, next: null };
      if (p.includes("/actions/runs")) return { data: { workflow_runs: [] }, next: null };
      if (p.includes("/issues/10/events")) return { data: events, next: null };
      return { data: [], next: null };
    },
  });
  const ev = { id: 7, event: "review_dismissed", created_at: "2026-09-29T12:00:00Z", dismissed_review: { review_id: 50, state: "changes_requested" } };
  const f = await collect(mk([ev]), "o/r", 10, policy);
  assert.equal(f.reviews.find((r) => r.id === 50).dismissed_at, "2026-09-29T12:00:00Z");
  assert.equal(f.reviews.find((r) => r.id === 51).dismissed_at, null);
  await assert.rejects(collect(mk([]), "o/r", 10, policy), /撤销/);
});
