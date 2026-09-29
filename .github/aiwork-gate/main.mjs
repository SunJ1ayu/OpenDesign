// aiwork 放行关卡入口:由 .github/workflows/aiwork-gate.yml 调用,代码永远是 main 上的这一份。
// 读用 GITHUB_TOKEN(只读);发检查结果用 aiwork-gate App 的临时令牌 —— 分支规则只认这个 App 发的结果,
// PR 自己加的 workflow 用 GITHUB_TOKEN 发一个同名检查也冒充不了。
import { createSign } from "node:crypto";
import { appendFileSync, readFileSync } from "node:fs";
import { collect } from "./collect.mjs";
import { decide } from "./decide.mjs";

const API = "https://api.github.com";
const env = process.env;
const repo = env.GITHUB_REPOSITORY;
const policy = JSON.parse(readFileSync(new URL("../../.aiwork/policy.json", import.meta.url), "utf8"));

function headers(token) {
  return {
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "aiwork-gate",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function request(method, url, token, body) {
  const res = await fetch(url.startsWith("http") ? url : `${API}${url}`, {
    method,
    headers: { ...headers(token), ...(body ? { "Content-Type": "application/json" } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`${method} ${url} → HTTP ${res.status}:${text.slice(0, 300)}`);
  return { data: text ? JSON.parse(text) : null, link: res.headers.get("link") };
}

function nextLink(link) {
  const m = /<([^>]+)>;\s*rel="next"/.exec(link ?? "");
  return m ? m[1] : null;
}

const readToken = env.GITHUB_TOKEN;
const api = {
  async get(path) {
    return (await request("GET", path, readToken)).data;
  },
  async getPage(path) {
    const { data, link } = await request("GET", path, readToken);
    return { data, next: nextLink(link) };
  },
};

function b64url(buf) {
  return Buffer.from(buf).toString("base64url");
}

async function appToken() {
  const appId = policy.gate_app_id;
  const key = env.AIWORK_GATE_PRIVATE_KEY;
  if (!appId || !key) throw new Error("缺 aiwork-gate App 的 App ID(.aiwork/policy.json 的 gate_app_id)或私钥(environment secret AIWORK_GATE_PRIVATE_KEY)");
  const now = Math.floor(Date.now() / 1000);
  const unsigned = `${b64url(JSON.stringify({ alg: "RS256", typ: "JWT" }))}.${b64url(JSON.stringify({ iat: now - 60, exp: now + 540, iss: String(appId) }))}`;
  const jwt = `${unsigned}.${b64url(createSign("RSA-SHA256").update(unsigned).sign(key))}`;
  const inst = (await request("GET", `/repos/${repo}/installation`, jwt)).data;
  const tok = (
    await request("POST", `/app/installations/${inst.id}/access_tokens`, jwt, {
      repositories: [repo.split("/")[1]],
      permissions: { checks: "write" },
    })
  ).data;
  return tok.token;
}

async function prNumbers(event) {
  if (env.GITHUB_EVENT_NAME === "pull_request_target") return [{ number: event.pull_request.number, sha: event.pull_request.head.sha }];
  if (env.GITHUB_EVENT_NAME === "workflow_run") {
    const run = event.workflow_run;
    const listed = (run.pull_requests ?? []).map((p) => ({ number: p.number, sha: run.head_sha }));
    if (listed.length) return listed;
    const prs = await api.get(`/repos/${repo}/commits/${run.head_sha}/pulls`);
    return prs.filter((p) => p.state === "open" && p.head.sha === run.head_sha).map((p) => ({ number: p.number, sha: run.head_sha }));
  }
  throw new Error(`不支持的事件 ${env.GITHUB_EVENT_NAME}`);
}

async function post(token, headSha, result) {
  const body = {
    name: policy.check_name,
    head_sha: headSha,
    status: result.status,
    output: { title: result.title, summary: result.summary.slice(0, 60000) },
  };
  if (result.status === "completed") body.conclusion = result.conclusion;
  await request("POST", `/repos/${repo}/check-runs`, token, body);
}

const event = JSON.parse(readFileSync(env.GITHUB_EVENT_PATH, "utf8"));
const targets = await prNumbers(event);
if (!targets.length) {
  console.log("这次事件没有对应的开着的 PR,不用判");
  process.exit(0);
}
const token = await appToken();
for (const t of targets) {
  let result;
  let headSha = t.sha;
  try {
    const facts = await collect(api, repo, t.number, policy);
    if (facts.pr.state !== "open") {
      console.log(`PR #${t.number} 已不是 open,跳过`);
      continue;
    }
    headSha = facts.pr.head_sha;
    result = decide(facts, policy);
  } catch (e) {
    result = { status: "completed", conclusion: "failure", title: "不放行:数据不全(G8)", summary: `读 GitHub 数据出错,按失败处理:\n\n${e.message}` };
  }
  await post(token, headSha, result);
  const line = `PR #${t.number} @ ${headSha.slice(0, 7)}:${result.title}`;
  console.log(`${line}\n${result.summary}`);
  if (env.GITHUB_STEP_SUMMARY) appendFileSync(env.GITHUB_STEP_SUMMARY, `### ${line}\n\n${result.summary}\n\n`);
}
