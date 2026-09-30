// aiwork 放行关卡入口 main.mjs 的整机冒烟:起一个假的 GitHub API,真跑 main.mjs 子进程。
// 钉住接线本身:JWT 用 App ID 签、公钥验得过;换令牌只要 checks:write;读数据用 GITHUB_TOKEN;
// 先发 in_progress 占位,再把同一条检查 PATCH 成结论;读 PR 出错时占位被改成 failure;
// 保险丝(commit status)只用 GITHUB_TOKEN 发,App 私钥坏了也拨得动。
// 跑法:node --test tests/test_aiwork_gate_main.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { generateKeyPairSync, createVerify } from "node:crypto";
import { spawn } from "node:child_process";
import { cpSync, mkdirSync, mkdtempSync, writeFileSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const policy = JSON.parse(readFileSync(new URL("../.aiwork/policy.json", import.meta.url), "utf8"));
const MAIN = new URL("../.github/aiwork-gate/main.mjs", import.meta.url).pathname;
const HEAD = "a".repeat(40);
const { privateKey, publicKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
const PEM = privateKey.export({ type: "pkcs8", format: "pem" });

function fakeGitHub(opts = {}) {
  const log = [];
  const server = createServer((req, res) => {
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      const auth = req.headers.authorization ?? "";
      log.push({ method: req.method, url: req.url, auth, body: body ? JSON.parse(body) : null });
      const send = (code, data) => { res.writeHead(code, { "content-type": "application/json" }); res.end(JSON.stringify(data)); };
      const u = req.url;
      if (u === "/repos/o/r/installation") return send(200, { id: 777 });
      if (u === "/app/installations/777/access_tokens") return send(201, { token: "ghs_fake_app_token" });
      if (u === "/repos/o/r/check-runs" && req.method === "POST") return opts.hang ? undefined : send(201, { id: 4242 }); // hang:一直不回
      if (u.startsWith("/repos/o/r/check-runs/") && req.method === "PATCH") return send(200, { id: 4242 });
      if (u.startsWith("/repos/o/r/statuses/") && req.method === "POST") return send(201, { id: 1 });
      if (opts.prFails && u === "/repos/o/r/pulls/10") return send(502, { message: "bad gateway" });
      const pr10 = { number: 10, state: "open", changed_files: 1, head: { sha: HEAD, ref: "claude/x", repo: { full_name: "o/r" } }, base: { ref: "main" } };
      if (u === "/repos/o/r/pulls?state=open&per_page=100") return send(200, [pr10]);
      if (u === "/repos/o/r/pulls/10") return send(200, pr10);
      if (u.startsWith("/repos/o/r/pulls/10/files")) return send(200, [{ filename: "web/a.ts" }]);
      if (u.startsWith("/repos/o/r/pulls/10/reviews")) return send(200, []);
      if (u.startsWith("/repos/o/r/actions/runs")) return send(200, { workflow_runs: [{ id: 1, path: ".github/workflows/ci.yml", head_sha: HEAD, status: "completed", conclusion: "success", pull_requests: [{ number: 10 }] }] });
      if (u.startsWith("/repos/o/r/activity")) return send(200, [{ id: 1, timestamp: "t", activity_type: "push", after: HEAD, actor: { login: "SunJ1ayuBoT" } }]);
      if (u.startsWith("/repos/o/r/issues/10/events")) return send(200, []);
      if (u === "/graphql" && req.method === "POST") return send(200, { data: { repository: { pullRequest: { reviews: { totalCount: 0, pageInfo: { hasNextPage: false }, nodes: [] } } } } });
      send(404, { message: `fake: no route ${u}` });
    });
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve({ server, log, url: `http://127.0.0.1:${server.address().port}` })));
}

function runMain(apiUrl, extraEnv = {}, main = MAIN) {
  const dir = mkdtempSync(join(tmpdir(), "gate-main-"));
  const eventPath = join(dir, "event.json");
  writeFileSync(eventPath, JSON.stringify({ pull_request: { number: 10, head: { sha: HEAD } } }));
  return new Promise((resolve) => {
    const child = spawn(process.execPath, [main], {
      timeout: 20_000, // 卡住就杀掉,测试红而不是挂住
      env: { PATH: process.env.PATH, GITHUB_API_URL: apiUrl, GITHUB_REPOSITORY: "o/r", GITHUB_EVENT_NAME: "pull_request_target", GITHUB_EVENT_PATH: eventPath, GITHUB_TOKEN: "read_token", AIWORK_GATE_PRIVATE_KEY: PEM, ...extraEnv },
    });
    let out = "";
    child.stdout.on("data", (d) => (out += d));
    child.stderr.on("data", (d) => (out += d));
    child.on("close", (code) => {
      rmSync(dir, { recursive: true, force: true });
      resolve({ code, out });
    });
  });
}

test("整机:JWT 验得过、只要 checks:write、读用 GITHUB_TOKEN、先占位再改成结论", async () => {
  const gh = await fakeGitHub();
  try {
    const { code, out } = await runMain(gh.url);
    assert.equal(code, 0, out);
    const inst = gh.log.find((r) => r.url === "/repos/o/r/installation");
    const jwt = inst.auth.replace(/^Bearer /, "");
    const [h, c, s] = jwt.split(".");
    assert.ok(createVerify("RSA-SHA256").update(`${h}.${c}`).verify(publicKey, Buffer.from(s, "base64url")), "JWT 签名验不过");
    const claims = JSON.parse(Buffer.from(c, "base64url").toString());
    assert.equal(claims.iss, String(policy.gate_app_id));
    assert.ok(claims.exp - claims.iat <= 600);
    const tok = gh.log.find((r) => r.url === "/app/installations/777/access_tokens");
    assert.deepEqual(tok.body, { repositories: ["r"], permissions: { checks: "write" } });
    const reads = gh.log.filter((r) => r.method === "GET" && r.url.startsWith("/repos/o/r/") && r.url !== "/repos/o/r/installation");
    assert.ok(reads.length >= 5 && reads.every((r) => r.auth === "Bearer read_token"), "读数据只用 GITHUB_TOKEN");
    const gql = gh.log.filter((r) => r.url === "/graphql");
    assert.ok(gql.length >= 1 && gql.every((r) => r.auth === "Bearer read_token"), "评审改写记录(GraphQL)也只用 GITHUB_TOKEN 读");
    const writes = gh.log.filter((r) => r.url.startsWith("/repos/o/r/check-runs"));
    assert.equal(writes[0].method, "POST");
    assert.equal(writes[0].body.status, "in_progress");
    assert.equal(writes[0].body.name, policy.check_name);
    assert.equal(writes[0].body.head_sha, HEAD);
    assert.ok(writes.every((w) => w.auth === "Bearer ghs_fake_app_token"), "发检查只用 App 令牌");
    const firstWrite = gh.log.indexOf(writes[0]);
    const firstRead = gh.log.findIndex((r) => r.url.startsWith("/repos/o/r/pulls/"));
    assert.ok(firstWrite < firstRead, "先占位,后读 PR 的数据");
    const last = writes.at(-1);
    assert.equal(last.method, "PATCH");
    assert.equal(last.url, "/repos/o/r/check-runs/4242");
    assert.equal(last.body.status, "completed");
    assert.equal(last.body.conclusion, "failure", "没有评审 ⇒ 不放行");
    assert.match(last.body.output.title, /缺合格评审/);
  } finally {
    gh.server.close();
  }
});

test("整机:读 PR 出错 → 占位被改成 failure(G8),进程正常结束", async () => {
  const gh = await fakeGitHub({ prFails: true });
  try {
    const { code, out } = await runMain(gh.url);
    assert.equal(code, 0, out);
    const last = gh.log.filter((r) => r.url.startsWith("/repos/o/r/check-runs")).at(-1);
    assert.equal(last.method, "PATCH");
    assert.equal(last.body.conclusion, "failure");
    assert.match(last.body.output.title, /G8/);
  } finally {
    gh.server.close();
  }
});

test("整机:没有私钥 → 进程失败,一条检查都不发、PR 的数据一条都不读(只列了开着的 PR)", async () => {
  const gh = await fakeGitHub();
  try {
    const { code } = await runMain(gh.url, { AIWORK_GATE_PRIVATE_KEY: "" });
    assert.notEqual(code, 0);
    assert.equal(gh.log.filter((r) => r.url.startsWith("/repos/o/r/check-runs") || r.url.startsWith("/repos/o/r/pulls/")).length, 0);
  } finally {
    gh.server.close();
  }
});

const fuseWrites = (log) => log.filter((r) => r.url.startsWith("/repos/o/r/statuses/"));

test("整机:保险丝只用 GITHUB_TOKEN 发,先 pending、App 写回之后跟结论走", async () => {
  const gh = await fakeGitHub();
  try {
    const { code, out } = await runMain(gh.url, { GITHUB_SERVER_URL: "https://github.com", GITHUB_RUN_ID: "123" });
    assert.equal(code, 0, out);
    const fw = fuseWrites(gh.log);
    assert.deepEqual(fw.map((r) => r.body.state), ["pending", "failure"]);
    assert.ok(fw.every((r) => r.method === "POST" && r.url === `/repos/o/r/statuses/${HEAD}`));
    assert.ok(fw.every((r) => r.auth === "Bearer read_token"), "保险丝不靠 App 令牌");
    assert.ok(fw.every((r) => r.body.context === "aiwork-gate/fuse" && r.body.description.length <= 140));
    assert.equal(fw[0].body.target_url, "https://github.com/o/r/actions/runs/123");
    assert.ok(gh.log.indexOf(fw[0]) < gh.log.findIndex((r) => r.url === "/repos/o/r/installation"), "先拨保险丝,再去换 App 令牌");
    assert.ok(gh.log.indexOf(fw[1]) > gh.log.findLastIndex((r) => r.url.startsWith("/repos/o/r/check-runs")), "App 写回之后才跟结论");
  } finally {
    gh.server.close();
  }
});

test("整机:没有私钥 → App 检查一条都发不出,但保险丝用 GITHUB_TOKEN 拨到 failure,旧 success 挡不住", async () => {
  const gh = await fakeGitHub();
  try {
    const { code } = await runMain(gh.url, { AIWORK_GATE_PRIVATE_KEY: "" });
    assert.notEqual(code, 0);
    assert.deepEqual(fuseWrites(gh.log).map((r) => r.body.state), ["pending", "failure"]);
    assert.ok(fuseWrites(gh.log).every((r) => r.auth === "Bearer read_token"));
  } finally {
    gh.server.close();
  }
});

// aiwork-review[bot] 评审(PR #10 review 5354768826,@ ae8c58f)第 4 个阻断点:main 上的策略文件不是合法 JSON 时,
// 进程在进 gate() 之前就崩了,保险丝没被拨到 failure。
test("整机:策略文件不是合法 JSON → 不发 App 检查、不读 PR 的数据,但保险丝照样拨到 failure", async () => {
  const gh = await fakeGitHub();
  const root = mkdtempSync(join(tmpdir(), "gate-policy-"));
  try {
    const src = new URL("../.github/aiwork-gate/", import.meta.url).pathname;
    mkdirSync(join(root, ".github"), { recursive: true });
    cpSync(src, join(root, ".github", "aiwork-gate"), { recursive: true });
    mkdirSync(join(root, ".aiwork"));
    writeFileSync(join(root, ".aiwork", "policy.json"), '{ "check_name": "aiwork-gate-shadow", ');
    const { code, out } = await runMain(gh.url, {}, join(root, ".github", "aiwork-gate", "main.mjs"));
    assert.notEqual(code, 0);
    assert.match(out, /policy\.json/);
    assert.deepEqual(fuseWrites(gh.log).map((r) => r.body.state), ["failure"]);
    assert.equal(gh.log.filter((r) => r.url.startsWith("/repos/o/r/check-runs") || r.url.startsWith("/repos/o/r/pulls/")).length, 0);
  } finally {
    gh.server.close();
    rmSync(root, { recursive: true, force: true });
  }
});

// aiwork-review[bot] 评审(PR #10 review 5362031164,@ a190849)第 3 个阻断点:一个请求卡住,整次运行被拖到超时。
test("整机:发占位的请求卡住 → 按单个请求的超时放弃,保险丝已先拨 pending、再拨 failure,进程报错结束", async () => {
  const gh = await fakeGitHub({ hang: true });
  try {
    const started = Date.now();
    const { code } = await runMain(gh.url, { AIWORK_GATE_TIMEOUT_MS: "300" });
    assert.notEqual(code, 0);
    assert.ok(Date.now() - started < 10_000, "没被卡住的请求拖住");
    assert.deepEqual(fuseWrites(gh.log).map((r) => r.body.state), ["pending", "failure"]);
  } finally {
    gh.server.closeAllConnections();
    gh.server.close();
  }
});
