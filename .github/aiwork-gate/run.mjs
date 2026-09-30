// aiwork 放行关卡的流程。网络与 App 令牌由 main.mjs 注入;判定在 decide.mjs,读数据在 collect.mjs。
//
// 只守一件事:**一个提交上的结论 = 以它为 head 的所有开着的 PR 的结论合在一起;读不全就不放行。**
// 检查和保险丝都挂在提交上,不是 PR 上(同一提交可以是几个 PR 的 head,目标分支不同 ⇒ 改动、要求都不同)。
//
// 一次运行:
//   1. 在事件的提交上先占位(保险丝 pending + App 检查 in_progress),压掉旧结论,再去读任何数据;
//   2. 定下涉及哪些 PR:事件带了就用,没带就按提交、再按分支查;
//   3. 读每个 PR 当前的 head;
//   4. 每个 head 提交:把以它为 head 的开着的 PR 全判一遍,合成一个结论,写一次;
//   5. 事件的提交若已不是任何开着的 PR 的 head(PR 推进了 / 关了),它上面判 failure。
// 任何一步读不全 → 那个提交判 G8 failure;连 PR 都读不到,就无从知道当前 head,只能在事件的提交上判。
//
// 两道信号:App 检查(分支规则只认它,PR 冒充不了)+ 保险丝(GITHUB_TOKEN 发的 commit status `aiwork-gate/fuse`,
// 不靠 App 私钥)。只有 App 自己改得动它发过的检查 —— App 私钥坏了,旧 success 就一直挂着,这时靠保险丝挡。
// 保险丝谁有写权限的 workflow 都能拨,所以只能多挡、不能单独放行:转真拦截时两道都设为必过。
//   · 占位:先拨保险丝(不靠 App 私钥),再发 App 检查;App 发不出去 → 保险丝 failure,抛错,不读数据;
//   · 写回:App 先写结论,保险丝再跟着结论走;App 写不回 → 保险丝 failure;
//   · 策略不合法 → 不读数据、不发检查,只把事件提交的保险丝拨到 failure;
//   · 运行被取消或超时 → 占位停在 in_progress、保险丝停在 pending,同样挡着。

import { collect, paginate } from "./collect.mjs";
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
const SHA_RE = /^[0-9a-f]{40}$/;
const fuseState = (r) => (r.status !== "completed" ? "pending" : r.conclusion === "success" ? "success" : "failure");

const PR_EVENTS = new Set(["pull_request", "pull_request_review", "pull_request_target"]);

// 从事件本身拿"哪个提交、哪些 PR",不发请求。numbers 为空时,要按提交(再按分支 lookupHead)去查。
export function targetsFromEvent(eventName, event) {
  if (eventName === "pull_request_target") {
    return { sha: event.pull_request.head.sha, numbers: [event.pull_request.number], lookupHead: null, skip: null };
  }
  if (eventName === "workflow_run") {
    const run = event.workflow_run;
    if (!PR_EVENTS.has(run.event)) return { sha: null, numbers: [], lookupHead: null, skip: `触发它的是 ${run.event},与 PR 无关` };
    const owner = run.head_repository?.owner?.login;
    const lookupHead = owner && run.head_branch ? `${owner}:${run.head_branch}` : null;
    return { sha: run.head_sha, numbers: (run.pull_requests ?? []).map((p) => p.number), lookupHead, skip: null };
  }
  return { sha: null, numbers: [], lookupHead: null, skip: `不支持的事件 ${eventName}` };
}

const g8 = (message) => ({ status: "completed", conclusion: "failure", title: "不放行:数据不全(G8)", summary: `读 GitHub 数据出错,按失败处理:\n\n${message}` });
const notHead = { status: "completed", conclusion: "failure", title: "这个提交已不是任何开着的 PR 的 head", summary: "PR 已推进或已关闭;结论在各 PR 当前的 head 上。" };

// 几个 PR 的结论合成一个:有一个不放行就不放行,有一个在等就等,全都放行才放行。
function combine(verdicts) {
  if (verdicts.length === 1) return verdicts[0].r;
  const pick =
    verdicts.find((v) => v.r.status === "completed" && v.r.conclusion !== "success") ??
    verdicts.find((v) => v.r.status !== "completed") ??
    verdicts[0];
  const list = verdicts.map((v) => `- PR #${v.number}:${v.r.title}`).join("\n");
  return {
    ...pick.r,
    title: `PR #${pick.number}:${pick.r.title}`,
    summary: `${pick.r.summary}\n\n---\n这个提交是 ${verdicts.length} 个开着的 PR 的 head(检查挂在提交上,全都放行才放行):\n${list}`,
  };
}

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
  const ids = new Map();
  const placeholder = async (sha) => {
    if (ids.has(sha)) return ids.get(sha);
    try {
      await fuse.set(sha, "pending", "重算中,算完之前不放行");
    } catch (e) {
      log(`保险丝拨不到 pending(${sha.slice(0, 7)}):${e.message};App 检查照发,最后还会再拨一次`);
    }
    try {
      ids.set(sha, await poster.start(sha));
    } catch (e) {
      await blow(sha, "关卡 App 发不出检查,这个提交上的旧结论作废");
      throw e;
    }
    return ids.get(sha);
  };
  const finish = async (sha, result) => {
    try {
      await poster.finish(sha, result, ids.get(sha));
    } catch (e) {
      await blow(sha, "关卡 App 写不回结论,这个提交上的旧结论作废");
      throw e;
    }
    await fuse.set(sha, fuseState(result), result.title);
  };

  try {
    validatePolicy(policy);
  } catch (e) {
    await blow(plan.sha, "关卡策略不合法,这个提交上的旧结论作废");
    throw e;
  }

  // 1. 先在事件的提交上占位
  await placeholder(plan.sha);

  // 2. 涉及哪些 PR
  let numbers = plan.numbers;
  if (!numbers.length) {
    try {
      const prs = await api.get(`/repos/${repo}/commits/${plan.sha}/pulls`);
      if (!Array.isArray(prs)) throw new Error("按提交查 PR 返回的不是列表");
      if (plan.lookupHead) {
        const byBranch = await api.get(`/repos/${repo}/pulls?state=open&head=${encodeURIComponent(plan.lookupHead)}&per_page=100`);
        if (!Array.isArray(byBranch)) throw new Error("按分支查 PR 返回的不是列表");
        prs.push(...byBranch);
      }
      numbers = [...new Set(prs.filter((p) => p.state === "open").map((p) => p.number))];
    } catch (e) {
      await finish(plan.sha, g8(`按提交号 / 分支查 PR 失败:${e.message}`));
      return [];
    }
  }

  // 3. 每个 PR 当前的 head
  const heads = new Map();
  let readError = null;
  for (const n of numbers) {
    try {
      const pr = await api.get(`/repos/${repo}/pulls/${n}`);
      if (pr?.state !== "open") continue;
      const head = pr.head?.sha;
      if (typeof head !== "string" || !SHA_RE.test(head)) throw new Error("head 不是提交号");
      if (!heads.has(head)) heads.set(head, new Set());
      heads.get(head).add(n);
    } catch (e) {
      readError ??= `读 PR #${n} 失败:${e.message}`;
    }
  }

  // 4. 每个 head 提交:以它为 head 的开着的 PR 全判一遍,写一次
  const results = [];
  for (const [head, known] of heads) {
    await placeholder(head);
    let result;
    try {
      const listed = await paginate(api, `/repos/${repo}/commits/${head}/pulls?per_page=100`);
      const all = new Set([...known, ...listed.filter((p) => p.state === "open" && p.head?.sha === head).map((p) => p.number)]);
      const verdicts = [];
      for (const n of all) {
        const facts = await collect(api, repo, n, policy);
        if (facts.pr.state !== "open" || facts.pr.head_sha !== head) continue; // 算的时候已关闭 / 推进
        let r;
        try {
          r = decide(facts, policy);
        } catch (e) {
          r = g8(`判定出错:${e.message}`);
        }
        verdicts.push({ number: n, r });
      }
      result = verdicts.length ? combine(verdicts) : notHead;
    } catch (e) {
      result = g8(e.message);
    }
    await finish(head, result);
    log(`${head.slice(0, 7)}:${result.title}\n${result.summary}`);
    results.push({ sha: head, title: result.title, summary: result.summary });
  }

  // 5. 事件的提交已不是任何开着的 PR 的 head
  if (!heads.has(plan.sha)) await finish(plan.sha, readError ? g8(readError) : notHead);
  return results;
}
