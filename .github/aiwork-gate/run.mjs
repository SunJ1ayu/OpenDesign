// aiwork 放行关卡的流程:校验策略 → 先占位 → 读数据 → 判 → 写回结论。网络与 App 令牌由 main.mjs 注入。
//
// 失败处理的原则:head 上**任何时候都不能留着一条过时的 success**。
//   · 策略不全(比如缺 App ID)→ 在读任何数据、发任何检查之前就抛错;
//   · 占位:能从事件本身知道提交号时,先在那个提交上发一条 in_progress,把旧结论压掉,再去读 API;
//     占位都发不出去(App 令牌坏了)→ 抛错,运行失败,不读数据;
//   · 之后任何一步出错(查 PR 号、读 PR、收集、判定)→ 把占位改成 failure(G8);
//   · 运行被取消或超时 → 占位停在 in_progress,同样挡着,不会被当成通过。

import { collect } from "./collect.mjs";
import { decide } from "./decide.mjs";

export function validatePolicy(p) {
  const bad = [];
  if (typeof p?.check_name !== "string" || !p.check_name) bad.push("check_name");
  if (!Number.isInteger(p?.gate_app_id) || p.gate_app_id <= 0) bad.push("gate_app_id");
  if (typeof p?.owner !== "string" || !p.owner) bad.push("owner");
  if (!p?.builders || typeof p.builders !== "object" || !Object.keys(p.builders).length) bad.push("builders");
  if (typeof p?.reviewer_bot !== "string" || !p.reviewer_bot.endsWith("[bot]")) bad.push("reviewer_bot");
  if (typeof p?.ci?.workflow_path !== "string" || typeof p?.ci?.event !== "string") bad.push("ci");
  if (!Array.isArray(p?.judging_surface) || !Array.isArray(p?.high)) bad.push("judging_surface/high");
  if (bad.length) throw new Error(`.aiwork/policy.json 不完整或不合法:${bad.join("、")}`);
}

const PR_EVENTS = new Set(["pull_request", "pull_request_review", "pull_request_target"]);

// 从事件本身拿"判哪个 PR、哪个提交",不发请求。lookupSha:事件没带 PR 号,要按提交号去查。
export function targetsFromEvent(eventName, event) {
  if (eventName === "pull_request_target") {
    return { targets: [{ number: event.pull_request.number, sha: event.pull_request.head.sha }], lookupSha: null, skip: null };
  }
  if (eventName === "workflow_run") {
    const run = event.workflow_run;
    if (!PR_EVENTS.has(run.event)) return { targets: [], lookupSha: null, skip: `触发它的是 ${run.event},与 PR 无关` };
    const listed = (run.pull_requests ?? []).map((p) => ({ number: p.number, sha: run.head_sha }));
    return listed.length ? { targets: listed, lookupSha: null, skip: null } : { targets: [], lookupSha: run.head_sha, skip: null };
  }
  return { targets: [], lookupSha: null, skip: `不支持的事件 ${eventName}` };
}

const g8 = (message) => ({ status: "completed", conclusion: "failure", title: "不放行:数据不全(G8)", summary: `读 GitHub 数据出错,按失败处理:\n\n${message}` });
const closed = (number) => ({ status: "completed", conclusion: "failure", title: `PR #${number} 已不是 open,不判`, summary: "PR 已关闭或已合并。" });
const moved = (head) => ({ status: "completed", conclusion: "failure", title: "这个提交已不是 PR 的 head", summary: `PR 已推进到 \`${head}\`,结论在那个提交上。` });

export async function gate({ repo, eventName, event, policy, api, poster, log = () => {} }) {
  validatePolicy(policy);
  const plan = targetsFromEvent(eventName, event);
  if (plan.skip) {
    log(plan.skip);
    return [];
  }

  let targets = [];
  for (const t of plan.targets) targets.push({ ...t, id: await poster.start(t.sha) });

  if (plan.lookupSha) {
    const id = await poster.start(plan.lookupSha);
    let prs;
    try {
      prs = await api.get(`/repos/${repo}/commits/${plan.lookupSha}/pulls`);
      if (!Array.isArray(prs)) throw new Error("返回的不是列表");
    } catch (e) {
      await poster.finish(plan.lookupSha, g8(`按提交号查 PR 失败:${e.message}`), id);
      return [];
    }
    const open = prs.filter((p) => p.state === "open" && p.head?.sha === plan.lookupSha);
    if (!open.length) {
      await poster.finish(plan.lookupSha, { status: "completed", conclusion: "failure", title: "这个提交不是任何开着的 PR 的 head", summary: "" }, id);
      return [];
    }
    targets = open.map((p, i) => ({ number: p.number, sha: plan.lookupSha, id: i === 0 ? id : null }));
    for (const t of targets) if (t.id === null) t.id = await poster.start(t.sha);
  }

  const results = [];
  for (const t of targets) {
    let facts;
    try {
      facts = await collect(api, repo, t.number, policy);
    } catch (e) {
      await poster.finish(t.sha, g8(e.message), t.id);
      results.push({ number: t.number, sha: t.sha, title: g8("").title });
      continue;
    }
    if (facts.pr.state !== "open") {
      await poster.finish(t.sha, closed(t.number), t.id);
      continue;
    }
    let result;
    try {
      result = decide(facts, policy);
    } catch (e) {
      result = g8(`判定出错:${e.message}`);
    }
    const head = facts.pr.head_sha;
    if (head === t.sha) {
      await poster.finish(head, result, t.id);
    } else {
      await poster.finish(t.sha, moved(head), t.id);
      await poster.finish(head, result, await poster.start(head));
    }
    log(`PR #${t.number} @ ${head.slice(0, 7)}:${result.title}\n${result.summary}`);
    results.push({ number: t.number, sha: head, title: result.title, summary: result.summary });
  }
  return results;
}
