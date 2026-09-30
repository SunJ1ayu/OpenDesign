// aiwork 放行关卡的判定部分:只吃收集好的事实(collect.mjs)和策略(.aiwork/policy.json),不碰网络。
// 规则编号对应 SunJ1ayu/aiwork 的 WORKFLOW-MIGRATION-PLAN.md 第 2 节;对抗用例见 tests/test_aiwork_gate.mjs。
//
//   G1 CI:当前 head 上、来自 ci.yml 的那次运行成功,且是在最后一次改目标分支之后触发的 —— 业主批准也豁免不了
//   G2 判卷面:改了 CI / 测试入口 / 关卡自己 → 要业主批准
//   G3 评审:当前 head 上至少一条合格 PASS(aiwork-review 发的、完整、读过文件、家族不是任何 Builder 的家族)—— 豁免不了
//   G4 作者:这个分支上的每次推送都来自已知 Builder 账号,否则 UNKNOWN → 要业主批准
//   G5 当前 head 上任何一条 BLOCK → 要业主在最后一条 BLOCK 之后批准。BLOCK = aiwork-review 在当前 head 上发的、
//      除"格式完整且结论不是 BLOCK"以外的一切(BLOCK 结论、Request changes、正文结论行写 BLOCK、结论块看不懂),
//      或任何其他评审人在当前 head 上最后一次表态是 Request changes / 被撤销(撤销只要写权限,Builder 就有,
//      撤销抹不掉反对;被撤销的评审看不出原来是什么,一律按反对算,反对的时刻是撤销那一刻)
//   G6 high 路径:两个不同的非作者家族 PASS(豁免不了)+ 业主批准
//   G7 业主批准 = 业主在当前 head 上最后一次表态是 Approve;最后一次是 Request changes 或被撤销则一律不放行
//   G8 数据不全 → 由 collect.mjs 抛错,main.mjs 直接判 failure

const SHA_RE = /^[0-9a-f]{40}$/;
const VERDICTS = new Set(["PASS", "BLOCK", "NEEDS_MORE_INFO", "UNKNOWN"]);
const COMPLETENESS = new Set(["complete", "partial", "none"]);
const FAMILY_RE = /^[a-z][a-z0-9-]*$/;
// review-pr 的正文里有一行独占的 `Conclusion: …`(评审腿的原话);它写 BLOCK 而结论块不是 BLOCK,就是自相矛盾
const CONCLUSION_BLOCK_RE = /^[\s>*_#-]*Conclusion\s*[:：]\s*[*_]*\s*BLOCK\b/im;

export function globToRegExp(pattern) {
  let re = "";
  for (let i = 0; i < pattern.length; i++) {
    const c = pattern[i];
    if (c === "*" && pattern[i + 1] === "*") {
      re += ".*";
      i++;
    } else if (c === "*") {
      re += "[^/]*";
    } else {
      re += c.replace(/[.+?^${}()|[\]\\]/g, "\\$&");
    }
  }
  return new RegExp(`^${re}$`);
}

export function matchAny(patterns, path) {
  return patterns.some((p) => globToRegExp(p).test(path));
}

// 评审正文里恰好一个 ```json 块;字段不全或类型不对就不算这条评审的结论。
export function parseReviewBlock(body) {
  const blocks = [...String(body ?? "").matchAll(/```json[ \t]*\r?\n([\s\S]*?)\r?\n```/g)];
  if (blocks.length !== 1) return { ok: false, why: `结论块应恰好 1 个,实为 ${blocks.length} 个` };
  let v;
  try {
    v = JSON.parse(blocks[0][1]);
  } catch {
    return { ok: false, why: "结论块不是合法 JSON" };
  }
  if (!v || typeof v !== "object" || Array.isArray(v)) return { ok: false, why: "结论块不是对象" };
  if (!VERDICTS.has(v.verdict)) return { ok: false, why: `verdict 不认识:${JSON.stringify(v.verdict)}` };
  if (typeof v.head_sha !== "string" || !SHA_RE.test(v.head_sha)) return { ok: false, why: "head_sha 不是 40 位提交号" };
  if (typeof v.model !== "string" || !v.model.trim()) return { ok: false, why: "缺 model" };
  if (typeof v.family !== "string" || !FAMILY_RE.test(v.family)) return { ok: false, why: "family 不合格" };
  if (!COMPLETENESS.has(v.completeness)) return { ok: false, why: `completeness 不认识:${JSON.stringify(v.completeness)}` };
  if (!Array.isArray(v.files_read) || !v.files_read.every((f) => typeof f === "string" && f.length > 0)) {
    return { ok: false, why: "files_read 应是文件路径数组" };
  }
  return { ok: true, value: v };
}

// 作者:只看推送者(仓库活动记录里的 actor),commit 里写的作者名不作数。
export function authorOf(pushes, policy) {
  if (!pushes || !pushes.covers_head) {
    return { known: false, why: "活动记录里找不到把分支推到当前 head 的那次推送" };
  }
  const actors = [...new Set(pushes.actors)];
  if (actors.length === 0) return { known: false, why: "这个分支没有推送记录" };
  const strangers = actors.filter((a) => !Object.hasOwn(policy.builders, a));
  if (strangers.length) return { known: false, why: `有非 Builder 账号推送过:${strangers.join("、")}` };
  const families = [...new Set(actors.map((a) => policy.builders[a]))];
  if (families.length !== 1) return { known: false, why: `推送者分属多个家族:${families.join("、")}` };
  return { known: true, family: families[0], actors };
}

// aiwork-review 的一条评审算不算 BLOCK:算就返回原因(可为空串),不算返回 null。
// BLOCK 从宽认、PASS 从严认:Request changes、结论块写 BLOCK、正文结论行写 BLOCK、结论块看不懂(缺字段、
// 不止一个、不是 JSON、没有)都算 —— 看不出它想说什么,就当它反对(哪怕已被撤销)。
function blockReason(r, p) {
  if (r.state === "CHANGES_REQUESTED") return "";
  if (!p.ok) return `看不懂:${p.why}`;
  if (p.value.verdict === "BLOCK") return "";
  if (CONCLUSION_BLOCK_RE.test(r.body ?? "")) return "正文结论行写的是 BLOCK";
  return null;
}

const byTime = (a, b) => (a.submitted_at < b.submitted_at ? -1 : a.submitted_at > b.submitted_at ? 1 : a.id - b.id);

// 除 aiwork-review 以外,每个评审人在当前 head 上最后一次表态(COMMENTED 不算表态)。
function stancesOnHead(reviews, policy, head) {
  const last = new Map();
  for (const r of reviews) {
    if (r.commit_id !== head || r.login === policy.reviewer_bot) continue;
    if (!["APPROVED", "CHANGES_REQUESTED", "DISMISSED"].includes(r.state)) continue;
    const prev = last.get(r.login);
    if (!prev || byTime(prev, r) < 0) last.set(r.login, r);
  }
  return last;
}

export function decide(facts, policy) {
  const head = facts.pr.head_sha;
  const lines = [];
  const add = (ok, rule, text) => lines.push(`${ok ? "✅" : "❌"} ${rule} ${text}`);

  // G1
  const ci = facts.ci;
  const pending = ci.state === "pending" || ci.state === "missing";
  // 目标分支在这次 CI 之后改过:它测的是旧目标的合并结果。缺创建时间就当作旧的
  const baseMoved = ci.state === "success" && Boolean(facts.base_changed_at) && !(Date.parse(ci.created_at) > Date.parse(facts.base_changed_at));
  const ciOk = ci.state === "success" && !baseMoved;
  if (pending) {
    add(false, "G1", ci.state === "pending" ? "CI 还在跑,等它跑完再判" : "当前 head 上还没有 CI 运行");
  } else if (baseMoved) {
    add(false, "G1", `目标分支在这次 CI 之后改过(${facts.base_changed_at}),CI 测的是旧目标:推一个新提交,或关掉再重开 PR,让 CI 在新目标上重跑`);
  } else {
    add(ciOk, "G1", ciOk ? "CI(ci.yml)在当前 head 上通过" : `CI 没通过:${ci.detail}`);
  }

  // G4
  const author = authorOf(facts.pushes, policy);
  add(author.known, "G4", author.known ? `作者:${author.actors.join("、")}(${author.family})` : `作者 UNKNOWN:${author.why}`);

  // 评审
  const botReviews = facts.reviews.filter((r) => r.login === policy.reviewer_bot && r.type === "Bot");
  const onHead = botReviews.filter((r) => r.commit_id === head);
  const builderFamilies = new Set(Object.values(policy.builders));
  const passes = [];
  const blocks = [];
  const rejected = [];
  for (const r of onHead) {
    const p = parseReviewBlock(r.body);
    const why = blockReason(r, p);
    if (why !== null) {
      blocks.push({ id: r.id, at: r.submitted_at, family: p.ok ? p.value.family : "?", model: `${p.ok ? p.value.model : `评审 #${r.id}`}${why ? `,${why}` : ""}` });
      continue;
    }
    const v = p.value;
    if (v.head_sha !== head) {
      rejected.push(`评审 #${r.id}:结论写的是 ${v.head_sha.slice(0, 7)},不是当前 head`);
      continue;
    }
    if (v.verdict !== "PASS") {
      rejected.push(`评审 #${r.id}:结论是 ${v.verdict}`);
      continue;
    }
    if (r.state === "DISMISSED") {
      rejected.push(`评审 #${r.id}:已被撤销`);
      continue;
    }
    if (v.completeness !== "complete") {
      rejected.push(`评审 #${r.id}:不完整(${v.completeness})`);
      continue;
    }
    if (v.files_read.length === 0) {
      rejected.push(`评审 #${r.id}:没读任何文件`);
      continue;
    }
    // 作者 UNKNOWN 时也不能让 Builder 家族来审:谁推的说不清,就把所有 Builder 家族都当作者
    if (builderFamilies.has(v.family) || (author.known && v.family === author.family)) {
      rejected.push(`评审 #${r.id}:${v.family} 是 Builder 家族,不能审 Builder 的代码`);
      continue;
    }
    passes.push({ id: r.id, family: v.family, model: v.model });
  }
  const stale = botReviews.length - onHead.length;

  // 人的表态:业主单独看(G7);其他人最后一次表态不是 Approve 的,都算 BLOCK(G5)
  const stances = stancesOnHead(facts.reviews, policy, head);
  const ownerLast = [...stances.values()].find((r) => r.login === policy.owner && r.type === "User") ?? null;
  for (const [login, r] of stances) {
    if (login === policy.owner || r.state === "APPROVED") continue;
    // 被撤销的评审,反对的时刻是撤销那一刻;缺撤销时间就当它在最后(之前的批准豁免不了)
    const at = r.state === "DISMISSED" ? r.dismissed_at || "9999-12-31T23:59:59Z" : r.submitted_at;
    blocks.push({ id: r.id, at, family: "评审人", model: `${login}${r.state === "DISMISSED" ? "(被撤销的评审)" : " 要求修改"}` });
  }

  // G3
  const reviewOk = passes.length > 0;
  add(
    reviewOk,
    "G3",
    reviewOk
      ? `合格 PASS:${passes.map((p) => `${p.model}(${p.family})`).join("、")}`
      : `当前 head 上没有合格 PASS${stale ? `(另有 ${stale} 条评审针对旧提交,不算)` : ""}`,
  );
  for (const r of rejected) lines.push(`   · ${r}`);

  // G5
  const blocked = blocks.length > 0;
  if (blocked) add(false, "G5", `有 BLOCK:${blocks.map((b) => `${b.model}(${b.family})`).join("、")}`);

  // G2 / G6
  const judging = facts.files.filter((f) => matchAny(policy.judging_surface, f));
  const high = facts.files.filter((f) => matchAny(policy.high, f));
  if (judging.length) add(false, "G2", `改了判卷面:${judging.slice(0, 5).join("、")}${judging.length > 5 ? " 等" : ""}`);
  const families = [...new Set(passes.map((p) => p.family))];
  const highOk = !high.length || families.length >= 2;
  if (high.length) {
    add(highOk, "G6", `high 路径:${high.slice(0, 5).join("、")}${high.length > 5 ? " 等" : ""};不同家族 PASS ${families.length} 家(要 2 家)`);
  }

  // G7
  const approved = ownerLast?.state === "APPROVED";
  const ownerObjects = ownerLast !== null && !approved;
  const stance = { at: ownerLast?.submitted_at ?? "" };
  const lastBlockAt = blocks.map((b) => b.at).sort().at(-1) ?? "";
  // 批准要晚于最后一条 BLOCK:业主批准时还没看到的 BLOCK,不能被那次批准豁免
  const blockWaived = approved && stance.at > lastBlockAt;
  const needOwner = [];
  if (!author.known) needOwner.push("作者 UNKNOWN");
  if (judging.length) needOwner.push("改了判卷面");
  if (blocked) needOwner.push("有 BLOCK");
  if (high.length) needOwner.push("high 路径");
  const ownerOk = !ownerObjects && (!needOwner.length || (approved && (!blocked || blockWaived)));
  if (ownerObjects) add(false, "G7", ownerLast.state === "DISMISSED" ? "业主在当前 head 上的评审被撤销了,需要业主重新表态" : "业主在当前 head 上要求修改(Request changes)");
  else if (needOwner.length) {
    const why = !approved ? "还没有" : blocked && !blockWaived ? "批准早于最后一条 BLOCK,要在看过 BLOCK 之后再批准" : "已批准";
    add(ownerOk, "G7", `需要业主在当前 head 上批准(${needOwner.join("、")}):${why}`);
  }

  const verdictLine = (() => {
    if (!ciOk) return pending ? "等 CI" : baseMoved ? "不放行:目标分支改过,CI 要在新目标上重跑" : "不放行:CI 没通过";
    if (!reviewOk) return "不放行:缺合格评审";
    if (!highOk) return "不放行:high 路径要两家不同模型都 PASS";
    if (ownerObjects) return "不放行:业主要求修改";
    if (!ownerOk) return `等业主批准:${needOwner.join("、")}`;
    return "放行";
  })();
  const pass = verdictLine === "放行";
  return {
    status: pending ? "in_progress" : "completed",
    conclusion: pending ? null : pass ? "success" : "failure",
    title: verdictLine,
    summary: [`head \`${head}\``, "", ...lines].join("\n"),
    author,
    passes,
    blocks,
  };
}
