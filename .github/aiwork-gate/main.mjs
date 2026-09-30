// aiwork 放行关卡入口:由 .github/workflows/aiwork-gate.yml 调用,代码永远是 main 上的这一份。
// 这里只管"接线":真实的 GitHub API、aiwork-gate App 的令牌、发 / 改检查。流程和失败处理在 run.mjs。
// 读数据、拨保险丝用 GITHUB_TOKEN(除 statuses: write 外只读);发检查结果用 aiwork-gate App 的临时令牌 ——
// 分支规则只认这个 App 发的结果,PR 自己加的 workflow 用 GITHUB_TOKEN 发一个同名检查也冒充不了。
// 保险丝故意不靠 App 私钥:私钥坏了 App 就改不了自己发过的旧 success,只能靠它挡(见 run.mjs 文件头)。
import { createSign } from "node:crypto";
import { appendFileSync, readFileSync } from "node:fs";
import { FUSE_CONTEXT, gate } from "./run.mjs";

const env = process.env;
const API = env.GITHUB_API_URL || "https://api.github.com";
const repo = env.GITHUB_REPOSITORY;
// 读不出 / 不是合法 JSON 也不在这里崩:交给 gate() 按"策略不合法"处理,它会先把保险丝拨到 failure
let policy = null;
try {
  policy = JSON.parse(readFileSync(new URL("../../.aiwork/policy.json", import.meta.url), "utf8"));
} catch (e) {
  console.log(`读不了 .aiwork/policy.json:${e.message}`);
}

// 每个请求最多等这么久:卡住的请求不能把整次运行拖到超时(后面的提交就来不及写)
const TIMEOUT_MS = Number(env.AIWORK_GATE_TIMEOUT_MS) || 30_000;

async function request(method, url, token, body) {
  const res = await fetch(url.startsWith("http") ? url : `${API}${url}`, {
    method,
    signal: AbortSignal.timeout(TIMEOUT_MS),
    headers: {
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "aiwork-gate",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`${method} ${url} → HTTP ${res.status}:${text.slice(0, 300)}`);
  return { data: text ? JSON.parse(text) : null, link: res.headers.get("link") };
}

const actionsToken = env.GITHUB_TOKEN;
const api = {
  async get(path) {
    return (await request("GET", path, actionsToken)).data;
  },
  async getPage(path) {
    const { data, link } = await request("GET", path, actionsToken);
    const m = /<([^>]+)>;\s*rel="next"/.exec(link ?? "");
    return { data, next: m ? m[1] : null };
  },
  // REST 不给的(评审改写时间)才走 GraphQL;有 errors 就当读失败
  async graphql(query, variables) {
    const { data } = await request("POST", env.GITHUB_GRAPHQL_URL || `${API}/graphql`, actionsToken, { query, variables });
    if (data?.errors?.length) throw new Error(`GraphQL:${data.errors.map((e) => e.message).join(";").slice(0, 300)}`);
    return data?.data;
  },
};

const runUrl = env.GITHUB_SERVER_URL && env.GITHUB_RUN_ID ? `${env.GITHUB_SERVER_URL}/${repo}/actions/runs/${env.GITHUB_RUN_ID}` : null;
const fuse = {
  async set(sha, state, description) {
    await request("POST", `/repos/${repo}/statuses/${sha}`, actionsToken, {
      state,
      context: FUSE_CONTEXT,
      description: String(description).slice(0, 140),
      ...(runUrl ? { target_url: runUrl } : {}),
    });
  },
};

const b64url = (x) => Buffer.from(x).toString("base64url");
let appTokenCache = null;
async function appToken() {
  if (appTokenCache) return appTokenCache;
  const key = env.AIWORK_GATE_PRIVATE_KEY;
  if (!key) throw new Error("缺 aiwork-gate App 的私钥(environment aiwork-gate 的 secret AIWORK_GATE_PRIVATE_KEY)");
  const now = Math.floor(Date.now() / 1000);
  const unsigned = `${b64url(JSON.stringify({ alg: "RS256", typ: "JWT" }))}.${b64url(JSON.stringify({ iat: now - 60, exp: now + 540, iss: String(policy.gate_app_id) }))}`;
  const jwt = `${unsigned}.${b64url(createSign("RSA-SHA256").update(unsigned).sign(key))}`;
  const inst = (await request("GET", `/repos/${repo}/installation`, jwt)).data;
  const tok = (
    await request("POST", `/app/installations/${inst.id}/access_tokens`, jwt, {
      repositories: [repo.split("/")[1]],
      permissions: { checks: "write" },
    })
  ).data;
  appTokenCache = tok.token;
  return appTokenCache;
}

const output = (r) => ({ title: r.title, summary: r.summary.slice(0, 60000) });
const poster = {
  async start(sha) {
    const res = await request("POST", `/repos/${repo}/check-runs`, await appToken(), {
      name: policy.check_name,
      head_sha: sha,
      status: "in_progress",
      output: { title: "重算中", summary: "aiwork-gate 正在重新判定;没算完之前不放行。" },
    });
    return res.data.id;
  },
  async finish(sha, result, id) {
    const body = { status: result.status, output: output(result) };
    if (result.status === "completed") body.conclusion = result.conclusion;
    await request("PATCH", `/repos/${repo}/check-runs/${id}`, await appToken(), body);
  },
};

const event = JSON.parse(readFileSync(env.GITHUB_EVENT_PATH, "utf8"));
await gate({
  repo,
  event,
  policy,
  api,
  poster,
  fuse,
  log: (line) => {
    console.log(line);
    if (env.GITHUB_STEP_SUMMARY) appendFileSync(env.GITHUB_STEP_SUMMARY, `${line}\n\n`);
  },
});
