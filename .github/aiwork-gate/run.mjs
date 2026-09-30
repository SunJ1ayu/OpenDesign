// aiwork 放行关卡的流程。网络与 App 令牌由 main.mjs 注入;判定在 decide.mjs,读数据在 collect.mjs。
//
// 只守两件事:
//   · **一个提交上的结论 = 以它为 head 的所有开着的 PR 的结论合在一起;读不全就不放行。**
//   · **一个提交上以最新的那条关卡检查为准。** 每次运行先在提交上占位(新的一条检查),再读数据 ⇒ 最新那条
//     检查背后的数据也最新。GitHub 对同名检查只认最新的一条;保险丝也照这一条走,不看"谁最后写"——
//     几次运行同时算同一个提交(并发组按事件分,管不住运行时才知道的 head),慢一步的旧运行写完也盖不掉新结论。
// 检查和保险丝都挂在提交上,不是 PR 上(同一提交可以是几个 PR 的 head,目标分支不同 ⇒ 改动、要求都不同)。
//
// 一次运行:
//   1. 在事件的提交上先占位(保险丝 pending + App 检查 in_progress),压掉旧结论,再去读任何数据;
//   2. 定下涉及哪些 PR:事件带了就用,没带就按提交、再按分支查;
//   3. 读每个 PR 当前的 head(读不到就按事件说的算:还在事件的提交上);
//   4. 涉及的每个提交(事件的提交 + 各 PR 当前的 head):把以它为 head 的开着的 PR 全判一遍,合成一个结论写一次;
//      一个都没有(PR 推进了 / 关了)→ 它上面判 failure。
// 任何一步读不全 → 那个提交判 G8 failure。
//
// 两道信号:App 检查(分支规则只认它,PR 冒充不了)+ 保险丝(GITHUB_TOKEN 发的 commit status `aiwork-gate/fuse`,
// 不靠 App 私钥)。只有 App 自己改得动它发过的检查 —— App 私钥坏了,旧 success 就一直挂着,这时靠保险丝挡。
// 保险丝谁有写权限的 workflow 都能拨,所以只能多挡、不能单独放行:转真拦截时两道都设为必过。
//   · 占位:先拨保险丝(不靠 App 私钥),再发 App 检查;App 发不出去 → 保险丝 failure,抛错,不读数据;
//   · 写回:App 先写结论,保险丝再跟这个提交上最新的那条检查;App 写不回 / 读不回 → 保险丝 failure;
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
  // 以某个提交为 head(或含这个提交)的 PR;列表一律翻页取全,取不全就抛错(G8)
  const prsOnCommit = (sha) => paginate(api, `/repos/${repo}/commits/${sha}/pulls?per_page=100`);
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
  // 这个提交上最新的那条关卡检查:本 App、本检查名里 id 最大的。自己那条一定在(列表慢半拍也算上它)
  const latestCheck = async (sha, mine) => {
    const runs = await paginate(api, `/repos/${repo}/commits/${sha}/check-runs?check_name=${encodeURIComponent(policy.check_name)}&app_id=${policy.gate_app_id}&filter=all&per_page=100`, "check_runs");
    const newer = runs.filter((r) => r.app?.id === policy.gate_app_id && r.name === policy.check_name && r.id > mine.id);
    if (!newer.length) return mine;
    const c = newer.reduce((x, y) => (y.id > x.id ? y : x));
    return { id: c.id, state: fuseState(c), title: c.output?.title ?? "" };
  };
  // 保险丝跟最新的那条检查走;拨完再看一眼,最新那条在这期间变了(更新的运行占了位 / 写回了)就再跟一次
  const follow = async (sha, result) => {
    const mine = { id: ids.get(sha), state: fuseState(result), title: result.title };
    let seen = null;
    for (let round = 0; round < 10; round++) {
      const now = await latestCheck(sha, mine);
      if (seen && now.id === seen.id && now.state === seen.state) return;
      await fuse.set(sha, now.state, now.title);
      seen = now;
    }
    throw new Error(`提交 ${sha.slice(0, 7)} 上的关卡检查一直在变,保险丝跟不上`);
  };
  const finish = async (sha, result) => {
    try {
      await poster.finish(sha, result, ids.get(sha));
      await follow(sha, result);
    } catch (e) {
      await blow(sha, "关卡检查写不回 / 读不回,这个提交上的旧结论作废");
      throw e;
    }
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
      const prs = await prsOnCommit(plan.sha);
      if (plan.lookupHead) prs.push(...(await paginate(api, `/repos/${repo}/pulls?state=open&head=${encodeURIComponent(plan.lookupHead)}&per_page=100`)));
      numbers = [...new Set(prs.filter((p) => p.state === "open").map((p) => p.number))];
    } catch (e) {
      await finish(plan.sha, g8(`按提交号 / 分支查 PR 失败:${e.message}`));
      return [];
    }
  }

  // 3. 每个 PR 当前的 head;读不到就按事件说的算(还在事件的提交上),第 4 步收集时再读不到就是 G8
  const commits = new Map([[plan.sha, new Set()]]);
  for (const n of numbers) {
    let head = plan.sha;
    try {
      const pr = await api.get(`/repos/${repo}/pulls/${n}`);
      if (pr?.state !== "open") continue;
      if (typeof pr.head?.sha !== "string" || !SHA_RE.test(pr.head.sha)) throw new Error("head 不是提交号");
      head = pr.head.sha;
    } catch (e) {
      log(`读 PR #${n} 失败,按事件的提交算:${e.message}`);
    }
    if (!commits.has(head)) commits.set(head, new Set());
    commits.get(head).add(n);
  }

  // 4. 涉及的每个提交:以它为 head 的开着的 PR 全判一遍,写一次
  const results = [];
  for (const [sha, known] of commits) {
    await placeholder(sha);
    let result;
    try {
      const listed = await prsOnCommit(sha);
      const all = new Set([...known, ...listed.filter((p) => p.state === "open" && p.head?.sha === sha).map((p) => p.number)]);
      const verdicts = [];
      for (const n of all) {
        const facts = await collect(api, repo, n, policy);
        if (facts.pr.state !== "open" || facts.pr.head_sha !== sha) continue; // 已关闭 / 已推进
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
    await finish(sha, result);
    log(`${sha.slice(0, 7)}:${result.title}\n${result.summary}`);
    results.push({ sha, title: result.title, summary: result.summary });
  }
  return results;
}
