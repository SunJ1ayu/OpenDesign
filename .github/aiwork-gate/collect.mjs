// aiwork 放行关卡的收集部分:从 GitHub API 读判定要的事实。只读,不执行、不检出 PR 的代码。
// G8 失败即拒:任何一次请求出错、分页没取完、条数对不上,都抛错,由 main.mjs 判 failure。

const MAX_PAGES = 30;

// api:{ get(path) → JSON, getPage(pathOrUrl) → { data, next } };真实实现在 main.mjs,测试里用替身。
export async function paginate(api, path, key) {
  const out = [];
  let url = path;
  for (let page = 0; page < MAX_PAGES; page++) {
    const { data, next } = await api.getPage(url);
    const items = key ? data?.[key] : data;
    if (!Array.isArray(items)) throw new Error(`${path}:第 ${page + 1} 页不是列表`);
    out.push(...items);
    if (!next) return out;
    url = next;
  }
  throw new Error(`${path}:超过 ${MAX_PAGES} 页还没取完`);
}

function stripRef(workflowPath) {
  return String(workflowPath ?? "").replace(/@.*$/, "");
}

// 同一个提交可能同时是别的 PR 的 head(基线不同,合并结果就不同):只认明确关联到本 PR 的那次运行。
export async function collectCi(api, repo, headSha, policy, prNumber) {
  const runs = await paginate(
    api,
    `/repos/${repo}/actions/runs?head_sha=${headSha}&event=${policy.ci.event}&per_page=100`,
    "workflow_runs",
  );
  const ciRuns = runs.filter((r) => stripRef(r.path) === policy.ci.workflow_path && r.head_sha === headSha);
  const mine = ciRuns
    .filter((r) => (r.pull_requests ?? []).some((p) => p.number === prNumber))
    .sort((a, b) => b.id - a.id);
  if (!mine.length) {
    return ciRuns.length
      ? { state: "failure", detail: `这个提交上有 ${ciRuns.length} 次 ci.yml 运行,但都没关联到 PR #${prNumber}` }
      : { state: "missing", detail: "没有 ci.yml 的运行" };
  }
  const run = mine[0];
  if (run.status !== "completed") return { state: "pending", detail: `运行 ${run.id} 状态 ${run.status}` };
  if (run.conclusion === "success") return { state: "success", detail: `运行 ${run.id}` };
  return { state: "failure", detail: `结论 ${run.conclusion}(运行 ${run.html_url ?? run.id})` };
}

const PUSH_TYPES = new Set(["push", "force_push", "branch_creation"]);

// 只看分支这一世:从最新往回数,数到最近一次建分支为止;遇到删分支就停(那之前是上一世)。
export async function collectPushes(api, repo, headRef, headSha) {
  const acts = await paginate(
    api,
    `/repos/${repo}/activity?ref=${encodeURIComponent(`refs/heads/${headRef}`)}&direction=desc&per_page=100`,
  );
  const sorted = [...acts].sort((a, b) =>
    a.timestamp === b.timestamp ? b.id - a.id : a.timestamp < b.timestamp ? 1 : -1,
  );
  const life = [];
  for (const a of sorted) {
    if (a.activity_type === "branch_deletion") break;
    life.push(a);
    if (a.activity_type === "branch_creation") break;
  }
  const pushes = life.filter((a) => PUSH_TYPES.has(a.activity_type));
  return {
    covers_head: pushes.some((a) => a.after === headSha),
    actors: pushes.map((a) => a.actor?.login ?? "(已注销账号)"),
  };
}

export async function collect(api, repo, prNumber, policy) {
  const pr = await api.get(`/repos/${repo}/pulls/${prNumber}`);
  const headSha = pr.head.sha;

  const fileEntries = await paginate(api, `/repos/${repo}/pulls/${prNumber}/files?per_page=100`);
  if (fileEntries.length !== pr.changed_files) {
    throw new Error(`改动文件取到 ${fileEntries.length} 个,PR 说有 ${pr.changed_files} 个`);
  }
  const files = [...new Set(fileEntries.flatMap((f) => [f.filename, f.previous_filename].filter(Boolean)))];

  const reviews = (await paginate(api, `/repos/${repo}/pulls/${prNumber}/reviews?per_page=100`)).map((r) => ({
    id: r.id,
    login: r.user?.login ?? null,
    type: r.user?.type ?? null,
    state: r.state,
    commit_id: r.commit_id,
    body: r.body ?? "",
    submitted_at: r.submitted_at ?? "",
  }));

  const ci = await collectCi(api, repo, headSha, policy, pr.number);

  const sameRepo = pr.head.repo?.full_name === repo;
  const pushes = sameRepo
    ? await collectPushes(api, repo, pr.head.ref, headSha)
    : { covers_head: false, actors: [] };

  return {
    pr: { number: pr.number, state: pr.state, head_sha: headSha, head_ref: pr.head.ref, base_ref: pr.base.ref },
    files,
    reviews,
    ci,
    pushes,
  };
}
