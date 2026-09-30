// aiwork 放行关卡的收集部分:从 GitHub API 读判定要的事实。只读,不执行、不检出 PR 的代码。
// G8 失败即拒:任何一次请求出错、分页没取完、条数对不上,都抛错,由 run.mjs 判 failure。

const MAX_PAGES = 30;

// api:{ get(path) → JSON, getPage(pathOrUrl) → { data, next }, graphql(query, variables) → data };真实实现在 main.mjs,测试里用替身。
// 响应自带 total_count 的(如 workflow_runs),取到的条数必须等于它:少一条可能正好是最新那次失败的运行。
export async function paginate(api, path, key) {
  const out = [];
  let url = path;
  let expected = null;
  for (let page = 0; page < MAX_PAGES; page++) {
    const { data, next } = await api.getPage(url);
    const items = key ? data?.[key] : data;
    if (!Array.isArray(items)) throw new Error(`${path}:第 ${page + 1} 页不是列表`);
    if (key && page === 0 && Number.isInteger(data.total_count)) expected = data.total_count;
    out.push(...items);
    if (!next) {
      if (expected !== null && out.length !== expected) {
        throw new Error(`${path}:条数对不上,取到 ${out.length} 条,接口说有 ${expected} 条`);
      }
      return out;
    }
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
  // 同一 PR 在同一提交上可能跑过几次(重开 PR、手动重跑):认最后开始的那次执行。
  // 重跑沿用原来的运行号、只更新 run_started_at,所以不能按运行号排(按运行号,旧运行重跑失败会被较新的成功盖住)
  const mine = ciRuns
    .filter((r) => (r.pull_requests ?? []).some((p) => p.number === prNumber))
    .sort((a, b) => String(b.run_started_at ?? "").localeCompare(String(a.run_started_at ?? "")) || b.id - a.id);
  if (!mine.length) {
    return ciRuns.length
      ? { state: "failure", detail: `这个提交上有 ${ciRuns.length} 次 ci.yml 运行,但都没关联到 PR #${prNumber}` }
      : { state: "missing", detail: "没有 ci.yml 的运行" };
  }
  const run = mine[0];
  // created_at 是触发这次运行的事件的时间;重跑(re-run)沿用当时的合并提交,所以不看 run_started_at
  const at = { created_at: run.created_at ?? null };
  if (run.status !== "completed") return { state: "pending", detail: `运行 ${run.id} 状态 ${run.status}`, ...at };
  if (run.conclusion === "success") return { state: "success", detail: `运行 ${run.id}`, ...at };
  return { state: "failure", detail: `结论 ${run.conclusion}(运行 ${run.html_url ?? run.id})`, ...at };
}

// 从 PR 的事件里取两样时间:
//   · 最后一次改目标分支:改了目标,PR 的 CI 不会自己重跑(ci.yml 不订阅 edited),旧的 CI 测的是旧目标;
//   · 每条评审被撤销的时刻:评审接口只给提交时间,被撤销的评审按反对算,反对的时刻是撤销那一刻。
export async function collectPrEvents(api, repo, prNumber) {
  const events = await paginate(api, `/repos/${repo}/issues/${prNumber}/events?per_page=100`);
  const times = events.filter((e) => e.event === "base_ref_changed").map((e) => e.created_at).sort();
  const dismissedAt = new Map();
  for (const e of events) {
    if (e.event !== "review_dismissed" || e.dismissed_review?.review_id == null) continue;
    const id = e.dismissed_review.review_id;
    if (!dismissedAt.has(id) || dismissedAt.get(id) < e.created_at) dismissedAt.set(id, e.created_at);
  }
  return { base_changed_at: times.at(-1) ?? null, dismissedAt };
}

// 每条评审发出之后有没有被改写过、何时改写(REST 不给,只有 GraphQL 的 lastEditedAt 有)。
// 评审机器人的结论写在正文里:正文被改写过,就不再是它当时写下的结论(有写权限的人也可能改别人的评审)。
const REVIEW_EDITS = `query($owner: String!, $name: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $name) { pullRequest(number: $number) { reviews(first: 100, after: $after) {
    totalCount pageInfo { hasNextPage endCursor } nodes { databaseId submittedAt lastEditedAt } } } } }`;

export async function collectReviewEdits(api, repo, prNumber) {
  const [owner, name] = repo.split("/");
  const seen = new Set();
  const editedAt = new Map();
  let after = null;
  for (let page = 0; page < MAX_PAGES; page++) {
    const conn = (await api.graphql(REVIEW_EDITS, { owner, name, number: prNumber, after }))?.repository?.pullRequest?.reviews;
    if (!conn || !Array.isArray(conn.nodes)) throw new Error(`PR #${prNumber} 的评审改写记录读不出`);
    for (const n of conn.nodes) {
      seen.add(n.databaseId);
      if (n.submittedAt && n.lastEditedAt && n.lastEditedAt > n.submittedAt) editedAt.set(n.databaseId, n.lastEditedAt);
    }
    if (!conn.pageInfo?.hasNextPage) {
      if (seen.size !== conn.totalCount) throw new Error(`PR #${prNumber} 的评审改写记录条数对不上,取到 ${seen.size} 条,接口说有 ${conn.totalCount} 条`);
      return { seen, editedAt };
    }
    after = conn.pageInfo.endCursor;
  }
  throw new Error(`PR #${prNumber} 的评审改写记录超过 ${MAX_PAGES} 页还没取完`);
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
  const { base_changed_at, dismissedAt } = await collectPrEvents(api, repo, pr.number);
  const edits = await collectReviewEdits(api, repo, pr.number);
  for (const r of reviews) {
    r.dismissed_at = r.state === "DISMISSED" ? dismissedAt.get(r.id) ?? null : null;
    if (r.state === "DISMISSED" && !r.dismissed_at) throw new Error(`评审 #${r.id}(${r.login})被撤销,但 PR 事件里找不到撤销时间`);
    if (!edits.seen.has(r.id)) throw new Error(`评审 #${r.id}(${r.login})在改写记录里找不到`);
    r.edited_at = edits.editedAt.get(r.id) ?? null;
  }

  const sameRepo = pr.head.repo?.full_name === repo;
  const pushes = sameRepo
    ? await collectPushes(api, repo, pr.head.ref, headSha)
    : { covers_head: false, actors: [] };

  return {
    pr: { number: pr.number, state: pr.state, head_sha: headSha },
    files,
    reviews,
    ci,
    base_changed_at,
    pushes,
  };
}
