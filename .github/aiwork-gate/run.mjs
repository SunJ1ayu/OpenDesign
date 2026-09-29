// aiwork 放行关卡的流程:校验策略 → 先占位 → 读数据 → 判 → 写回结论。网络与 App 令牌由 main.mjs 注入。
//
// 失败处理的原则:head 上**任何时候都不能留着一条过时的 success**。
//   · 两道信号:App 发的检查(分支规则只认它,PR 冒充不了)+ 保险丝(GITHUB_TOKEN 发的 commit status
//     `aiwork-gate/fuse`,不靠 App 私钥)。只有 App 自己改得动它发的检查 —— App 私钥坏了,旧 success 就一直挂着,
//     这时靠保险丝挡。保险丝谁有写权限的 workflow 都能拨,所以它只能多挡、不能单独放行:转真拦截时两道都设为必过;
//   · 策略不全(比如缺 App ID)→ 不读数据、不发检查,把事件里那个提交的保险丝拨到 failure,抛错;
//   · 占位:能从事件本身知道提交号时,先把那个提交的保险丝拨到 pending,再发一条 in_progress 的 App 检查
//     把旧结论压掉,再去读 API;App 检查发不出去(私钥坏了)→ 保险丝 failure,抛错,不读数据;
//   · 之后任何一步出错(查 PR 号、读 PR、收集、判定)→ 把占位改成 failure(G8);App 写不回 → 保险丝 failure;
//   · App 把结论写回之后,保险丝才跟着结论走(success / failure / pending);
//   · 运行被取消或超时 → 占位停在 in_progress、保险丝停在 pending,同样挡着,不会被当成通过。

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

export const FUSE_CONTEXT = "aiwork-gate/fuse";
const fuseState = (r) => (r.status !== "completed" ? "pending" : r.conclusion === "success" ? "success" : "failure");

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

export async function gate({ repo, eventName, event, policy, api, poster, fuse, log = () => {} }) {
  const plan = targetsFromEvent(eventName, event);
  if (plan.skip) {
    log(plan.skip);
    return [];
  }

  // 拨到 failure 是最后一道保底:它自己再出错也只记日志,不盖掉原本的错误
  const blow = async (sha, why) => {
    try {
      await fuse.set(sha, "failure", why);
    } catch (e) {
      log(`保险丝也拨不动(${sha.slice(0, 7)}):${e.message}`);
    }
  };
  const start = async (sha) => {
    try {
      await fuse.set(sha, "pending", "重算中,算完之前不放行");
    } catch (e) {
      log(`保险丝拨不到 pending(${sha.slice(0, 7)}):${e.message};App 检查照发,最后还会再拨一次`);
    }
    try {
      return await poster.start(sha);
    } catch (e) {
      await blow(sha, "关卡 App 发不出检查,这个提交上的旧结论作废");
      throw e;
    }
  };
  const finish = async (sha, result, id) => {
    try {
      await poster.finish(sha, result, id);
    } catch (e) {
      await blow(sha, "关卡 App 写不回结论,这个提交上的旧结论作废");
      throw e;
    }
    await fuse.set(sha, fuseState(result), result.title);
  };

  try {
    validatePolicy(policy);
  } catch (e) {
    for (const sha of new Set([...plan.targets.map((t) => t.sha), plan.lookupSha].filter(Boolean))) {
      await blow(sha, "关卡策略不合法,这个提交上的旧结论作废");
    }
    throw e;
  }

  let targets = [];
  for (const t of plan.targets) targets.push({ ...t, id: await start(t.sha) });

  if (plan.lookupSha) {
    const id = await start(plan.lookupSha);
    let prs;
    try {
      prs = await api.get(`/repos/${repo}/commits/${plan.lookupSha}/pulls`);
      if (!Array.isArray(prs)) throw new Error("返回的不是列表");
    } catch (e) {
      await finish(plan.lookupSha, g8(`按提交号查 PR 失败:${e.message}`), id);
      return [];
    }
    const open = prs.filter((p) => p.state === "open" && p.head?.sha === plan.lookupSha);
    if (!open.length) {
      await finish(plan.lookupSha, { status: "completed", conclusion: "failure", title: "这个提交不是任何开着的 PR 的 head", summary: "" }, id);
      return [];
    }
    targets = open.map((p, i) => ({ number: p.number, sha: plan.lookupSha, id: i === 0 ? id : null }));
    for (const t of targets) if (t.id === null) t.id = await start(t.sha);
  }

  const results = [];
  for (const t of targets) {
    let facts;
    try {
      facts = await collect(api, repo, t.number, policy);
    } catch (e) {
      await finish(t.sha, g8(e.message), t.id);
      results.push({ number: t.number, sha: t.sha, title: g8("").title });
      continue;
    }
    if (facts.pr.state !== "open") {
      await finish(t.sha, closed(t.number), t.id);
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
      await finish(head, result, t.id);
    } else {
      await finish(t.sha, moved(head), t.id);
      await finish(head, result, await start(head));
    }
    log(`PR #${t.number} @ ${head.slice(0, 7)}:${result.title}\n${result.summary}`);
    results.push({ number: t.number, sha: head, title: result.title, summary: result.summary });
  }
  return results;
}
