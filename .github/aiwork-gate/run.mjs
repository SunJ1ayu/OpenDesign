// aiwork 放行关卡的流程。网络与 App 令牌由 main.mjs 注入;判定在 decide.mjs,读数据在 collect.mjs。
//
// 只守三件事:
//   · **关卡的结论只取决于 GitHub 上的现状,与是哪个事件叫醒它无关**:每次运行把所有开着的 PR 全重算一遍,
//     事件只是门铃。不从事件推"该算哪个 PR、写到哪个提交"—— 那条路上漏过好几次(没带 PR 的事件、旧提交、合并提交)。
//   · **同一时间只有一次运行**(workflow 的并发组是一个固定名字、不取消正在跑的;排队的只留最新一个,它开始时读到的
//     一定不比被它顶掉的旧一些)。所以同一提交上后写的结论一定出自后读的数据,不会有慢一步的旧运行盖掉新结论,
//     也用不着猜 GitHub 在同名检查里按什么取"最新"(后发的一定后写完)。
//   · **一个提交上的结论 = 以它为 head 的所有开着的 PR 的结论合在一起;读不全就不放行(G8)。**
//     检查和保险丝都挂在提交上;同一提交可以是几个 PR 的 head,目标分支不同 ⇒ 改动、要求都不同。
//
// 一次运行:
//   1. 列出所有开着的 PR,按 head 提交分组;
//   2. 先在每个 head 上占位(保险丝 pending + App 检查 in_progress),再读任何 PR 的数据 ——
//      半路死掉,没算完的提交也停在 in_progress / pending,不会留着上一次的结论;
//   3. 每个 head:把以它为 head 的 PR 全判一遍,合成一个结论写一次(App 先写,保险丝跟着)。
//
// 两道信号:App 检查(分支规则只认它,PR 冒充不了)+ 保险丝(GITHUB_TOKEN 发的 commit status `aiwork-gate/fuse`,
// 不靠 App 私钥)。只有 App 自己改得动它发过的检查 —— App 私钥坏了,旧 success 就一直挂着,这时靠保险丝挡。
// 保险丝谁有写权限的 workflow 都能拨,所以只能多挡、不能单独放行:转真拦截时两道都设为必过。
//   · 每个提交要么写上这次算出的结论,要么保险丝 failure(App 发不出占位 / 写不回结论、策略不合法);
//   · 连开着的 PR 都列不出来 → 不知道该挡哪些提交,至少把叫醒这次运行的那个提交的保险丝拨到 failure;
//   · 运行被取消或超时 → 占位停在 in_progress、保险丝停在 pending,同样挡着;下一次运行全部重算。

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

const g8 = (message) => ({ status: "completed", conclusion: "failure", title: "不放行:数据不全(G8)", summary: `读 GitHub 数据出错,按失败处理:\n\n${message}` });
const moved = { status: "completed", conclusion: "failure", title: "这个提交已不是开着的 PR 的 head", summary: "列出 PR 之后它又推进或关闭了;新的 head 由它的事件叫醒的下一次运行来算。" };

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

// 叫醒这次运行的那个提交:只在连开着的 PR 都列不出来时用
const eventSha = (event) => event?.pull_request?.head?.sha ?? event?.workflow_run?.head_sha ?? null;

export async function gate({ repo, event, policy, api, poster, fuse, log = () => {} }) {
  const errors = [];
  // 拨到 failure 是最后一道保底:它自己再出错也只记日志,不盖掉原本的错误
  const blow = async (sha, why) => {
    try {
      await fuse.set(sha, "failure", why);
    } catch (e) {
      log(`保险丝也拨不动(${sha.slice(0, 7)}):${e.message}`);
    }
  };

  // 1. 所有开着的 PR,按 head 提交分组
  const heads = new Map();
  try {
    for (const pr of await paginate(api, `/repos/${repo}/pulls?state=open&per_page=100`)) {
      const sha = pr.head?.sha;
      if (typeof sha !== "string" || !SHA_RE.test(sha)) throw new Error(`PR #${pr.number} 的 head 不是提交号`);
      if (!heads.has(sha)) heads.set(sha, []);
      heads.get(sha).push(pr.number);
    }
  } catch (e) {
    const sha = eventSha(event);
    if (typeof sha === "string" && SHA_RE.test(sha)) await blow(sha, "列不出开着的 PR,这个提交上的旧结论作废");
    throw e;
  }

  try {
    validatePolicy(policy);
  } catch (e) {
    for (const sha of heads.keys()) await blow(sha, "关卡策略不合法,这个提交上的旧结论作废");
    throw e;
  }

  // 2. 先在每个 head 上占位,再读任何 PR 的数据
  const ids = new Map();
  for (const sha of heads.keys()) {
    try {
      await fuse.set(sha, "pending", "重算中,算完之前不放行");
    } catch (e) {
      log(`保险丝拨不到 pending(${sha.slice(0, 7)}):${e.message};App 检查照发,算完还会再拨一次`);
    }
    try {
      ids.set(sha, await poster.start(sha));
    } catch (e) {
      await blow(sha, "关卡 App 发不出检查,这个提交上的旧结论作废");
      errors.push(e);
    }
  }

  // 3. 每个 head:以它为 head 的 PR 全判一遍,合成一个结论写一次
  const results = [];
  for (const [sha, numbers] of heads) {
    if (!ids.has(sha)) continue;
    let result;
    try {
      const verdicts = [];
      for (const n of numbers) {
        const facts = await collect(api, repo, n, policy);
        if (facts.pr.state !== "open" || facts.pr.head_sha !== sha) continue; // 列出之后又推进 / 关了
        let r;
        try {
          r = decide(facts, policy);
        } catch (e) {
          r = g8(`判定出错:${e.message}`);
        }
        verdicts.push({ number: n, r });
      }
      result = verdicts.length ? combine(verdicts) : moved;
    } catch (e) {
      result = g8(e.message);
    }
    try {
      await poster.finish(sha, result, ids.get(sha));
    } catch (e) {
      await blow(sha, "关卡 App 写不回结论,这个提交上的旧结论作废");
      errors.push(e);
      continue;
    }
    try {
      await fuse.set(sha, fuseState(result), result.title);
    } catch (e) {
      errors.push(e);
    }
    log(`${sha.slice(0, 7)}:${result.title}\n${result.summary}`);
    results.push({ sha, title: result.title, summary: result.summary });
  }
  if (errors.length) throw errors[0];
  return results;
}
