// track opendesign-owner-consent 判据 O12:**同意卡的错误码不许原样丢给业主看**。
// 主 agent 亲写。
//
// 为什么要有这条:同意闸这张卡是给**不写代码的业主**看的,而后端 `resolve_pending`
// 每加一个失败原因,前端如果没跟上,屏幕上出现的就是一行 `没能提交:stale_pending`。
// 08-11 我自己就刚踩了一次 —— 修 O10 时给后端加了 `stale_pending`,
// 前端只认识 `already_resolved`,业主看到的会是那个英文码。
//
// 形状:**码表从 `bin/ds_consent.py` 现取,不手抄**(手抄的表会烂,而且烂法是静默的
// —— 见同仓 `MUST_REALLY_RUN` 那段的教训)。这条闸问的是:
//   ① resolve 能回的每一个错误码,前端都有一句人话;
//   ② 那句人话里不许再出现英文码本身(否则等于没翻译);
//   ③ 这张表真的被用上了,而且**留着兜底分支**(apply 阶段还会冒出业务错误码,
//      那些不在本表管辖范围内,但也不能让界面白屏)。
//
// ⚠️ 它证明不了那句人话**写得对**(那要人眼看)。它只证明"没有漏翻译的口子"。
//
// 跑法:node --test tests/test_consent_messages.mjs
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const PY = readFileSync(join(ROOT, "bin", "ds_consent.py"), "utf-8");
const TSX = readFileSync(join(ROOT, "web", "src", "workspace", "ConsentCard.tsx"), "utf-8");

/** 真相源:`resolve_pending` 函数体里所有 `{"error": "..."}` 的码。 */
function backendCodes() {
  const start = PY.indexOf("def resolve_pending(");
  assert.notEqual(start, -1,
    "ds_consent.py 里找不到 resolve_pending —— 这条闸失去了真相源,先修它别绕过");
  const rest = PY.slice(start + 1);
  const end = rest.indexOf("\ndef ");
  const body = end === -1 ? rest : rest.slice(0, end);
  const codes = [...body.matchAll(/"error":\s*"([a-z_]+)"/g)].map((m) => m[1]);
  // 下界:抓不到几条就说明正则跟代码漂移了(空转的闸比没有闸更坏)。
  assert.ok(codes.length >= 5,
    `只从 resolve_pending 里抓到 ${codes.length} 个错误码,正则多半跟代码漂移了`);
  return [...new Set(codes)];
}

/** 前端的码 → 人话表。 */
function frontendMessages() {
  const m = TSX.match(/const ERR_MSG[^{]*\{([\s\S]*?)\n\};/);
  assert.ok(m, "ConsentCard.tsx 里没有 ERR_MSG 码表");
  const out = {};
  for (const e of m[1].matchAll(/(\w+):\s*"([^"]*)"/g)) out[e[1]] = e[2];
  return out;
}

test("O12a resolve 能回的每个错误码,业主都能看到一句人话", () => {
  const msgs = frontendMessages();
  const missing = backendCodes().filter((c) => !(c in msgs));
  assert.deepEqual(missing, [],
    `这些错误码前端没翻译,业主会看到英文码:${missing.join(", ")}`);
});

test("O12b 翻译过来的话里不许再出现英文码", () => {
  for (const [code, text] of Object.entries(frontendMessages())) {
    assert.ok(!/[A-Za-z]{3,}/.test(text),
      `${code} 的说明里还有英文(${text})—— 那等于没翻译`);
  }
});

test("O12c 码表真的被用上,而且留着兜底", () => {
  assert.ok(/ERR_MSG\[[^\]]+\]/.test(TSX), "ERR_MSG 定义了却没被用 —— 摆设");
  assert.ok(/ERR_MSG\[[^\]]+\]\s*\|\|/.test(TSX),
    "没有兜底分支:apply 阶段冒出的业务错误码不在本表里,不能让界面什么都不显示");
});
