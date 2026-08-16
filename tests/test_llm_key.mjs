// T4 oracle:界面里填大模型 key 的**纯逻辑层**(web/src/llmKey.ts)。
// 主 agent 亲写;执行腿对本文件逐字节 off-limits(改这份 = 改考卷)。
// track opendesign-key-onboarding,design.md 第二/三/四节。
//
// 跑法:node --test tests/test_llm_key.mjs(Node 22+,原生 strip-types)
//
// ── 后端契约(T2/T3 已交付并各自有判据,见 tests/test_ds_web_credential.py)──
//   GET  /api/llm/credential → 200 {configured, provider, hint,
//                                   providers:[{id,label,model}]}
//   POST /api/llm/credential {provider,key} → 200 {configured, provider, hint, restart}
//                                           → 400 {error:"人话"}
//   restart ∈ {"requested","manual"}。**"manual" = 网关没被重启,得业主自己动手。**
//
// ── 这份考卷问什么(对着 design 那节「这个 oracle 能被什么骗过」写的)────────
//   a*  契约:发到哪、发了什么、回来是什么形状
//   b*  厂商清单**只能来自后端**(骗法四:两边各硬编码一份,就会一起错)
//   c*  key 不许在前端留下任何副本(骗法一的前端那一半)
//   d*  重启那句话不许撒谎(骗法三:manual 必须说"请重启",requested 不许说)
//
// ⚠️ 判据先行时它红在 ERR_MODULE_NOT_FOUND 上 —— 那种红只证明"没有就会响",
//    **不证明"写错了会响"**(08-14 实证)。实现落地后必须另跑一轮定点变异。
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import {
  CREDENTIAL_PATH,
  fetchKeyStatus,
  saveKey,
  restartNotice,
} from "../web/src/llmKey.ts";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const SRC = join(ROOT, "web", "src", "llmKey.ts");

// 一把长得像真 key 的串:够长(过 _hint 的 12 字符线)、好在文本里搜。
const KEY = "sk-oracle-1234567890-ABCDEFGH-9999";

// ---- 替身 ---------------------------------------------------------------

/** 记录型 fetch:handler(url, init, n) 按第 n 次调用出剧本。 */
function recFetch(handler) {
  const calls = [];
  const fn = async (url, init = {}) => {
    calls.push({ url: String(url), init });
    return handler(String(url), init, calls.length);
  };
  fn.calls = calls;
  return fn;
}

const jsonRes = (status, body = {}) => ({
  status,
  ok: status >= 200 && status < 300,
  json: async () => body,
});

const STATUS_EMPTY = {
  configured: false,
  provider: null,
  hint: null,
  providers: [
    { id: "mimo", label: "MiMo(小米)", model: "mimo-v2.5" },
    { id: "deepseek", label: "DeepSeek 官方", model: "deepseek-v4-flash" },
  ],
};

// ---- a* 契约 -------------------------------------------------------------

test("a1 状态用 GET 拉,打在约定的那条路径上,不带 body", async () => {
  const f = recFetch(() => jsonRes(200, STATUS_EMPTY));
  await fetchKeyStatus(f);
  assert.equal(f.calls.length, 1);
  const { url, init } = f.calls[0];
  assert.equal(url, CREDENTIAL_PATH);
  assert.equal(CREDENTIAL_PATH, "/api/llm/credential"); // 路径写错 = 整条链断
  assert.ok(!init.method || init.method.toUpperCase() === "GET", `方法应是 GET,实为 ${init.method}`);
  assert.equal(init.body, undefined);
});

test("a2 状态原样透出(configured/provider/hint/providers 四样都不许丢)", async () => {
  const body = {
    configured: true, provider: "deepseek", hint: "sk-o…9999",
    providers: STATUS_EMPTY.providers,
  };
  const st = await fetchKeyStatus(recFetch(() => jsonRes(200, body)));
  assert.equal(st.configured, true);
  assert.equal(st.provider, "deepseek");
  assert.equal(st.hint, "sk-o…9999");
  assert.deepEqual(st.providers, STATUS_EMPTY.providers);
});

test("a3 保存用 POST,provider 和 key 都在 body 里,**key 不许进 URL**", async () => {
  const f = recFetch(() => jsonRes(200, { configured: true, provider: "mimo",
                                          hint: "sk-o…9999", restart: "manual" }));
  await saveKey(f, "mimo", KEY);
  assert.equal(f.calls.length, 1);
  const { url, init } = f.calls[0];
  assert.equal(init.method?.toUpperCase(), "POST");
  // URL 会进 access log / 浏览器历史 / Referer —— key 落在这儿就等于漏了。
  assert.ok(!url.includes(KEY), `key 出现在 URL 里:${url}`);
  assert.ok(!url.includes("key="), `URL 带了 key 参数:${url}`);
  const sent = JSON.parse(init.body);
  assert.equal(sent.provider, "mimo");
  assert.equal(sent.key, KEY);
});

test("a4 保存成功:回 ok + 后端给的状态与 restart", async () => {
  const f = recFetch(() => jsonRes(200, { configured: true, provider: "mimo",
                                          hint: "sk-o…9999", restart: "requested" }));
  const r = await saveKey(f, "mimo", KEY);
  assert.equal(r.ok, true);
  assert.equal(r.configured, true);
  assert.equal(r.provider, "mimo");
  assert.equal(r.hint, "sk-o…9999");
  assert.equal(r.restart, "requested");
});

test("a5 后端拒绝(400):把**它的**人话原样端出来,不许自己另编一句", async () => {
  const f = recFetch(() => jsonRes(400, { error: "API key 里有中文或特殊字符,请检查是不是复制多了" }));
  const r = await saveKey(f, "mimo", "中文key");
  assert.equal(r.ok, false);
  // 要的是"后端那句话到得了业主眼前",不是"一个字都不许多" ——
  // 实现加个「保存失败:」前缀完全合理,逐字相等会把它冤枉掉。
  assert.ok(r.error.includes("API key 里有中文或特殊字符,请检查是不是复制多了"),
            `后端的人话没端出来:${r.error}`);
});

test("a6 服务不可达(fetch 抛)不许静默成功,也不许把 key 带进错误里", async () => {
  const boom = async () => { throw new TypeError("Failed to fetch"); };
  const r = await saveKey(boom, "mimo", KEY);
  assert.equal(r.ok, false, "网络炸了却报成功 = 业主以为存上了");
  assert.ok(r.error && r.error.length > 0, "得给一句能读的话");
  assert.ok(!JSON.stringify(r).includes(KEY), "错误对象里带了 key 原文");
});

test("a7 500 之类也走失败路,不许当成 200 解读", async () => {
  const r = await saveKey(recFetch(() => jsonRes(500, {})), "mimo", KEY);
  assert.equal(r.ok, false);
});

// ---- b* 厂商清单只能来自后端 ----------------------------------------------

test("b1 厂商是后端说了算:没听过的厂商也照样透出、照样能提交", async () => {
  // 后端换了厂商表(将来加第三家 / 改端点),前端不该有自己的白名单。
  const acme = { id: "acme", label: "Acme 云", model: "acme-1" };
  const st = await fetchKeyStatus(recFetch(() => jsonRes(200, { ...STATUS_EMPTY, providers: [acme] })));
  assert.deepEqual(st.providers, [acme]);

  const f = recFetch(() => jsonRes(200, { configured: true, provider: "acme",
                                          hint: "sk-o…9999", restart: "manual" }));
  const r = await saveKey(f, "acme", KEY);
  assert.equal(r.ok, true, "前端自带白名单就会把后端的新厂商挡在外面");
  assert.equal(JSON.parse(f.calls[0].init.body).provider, "acme");
});

// ---- c* key 不许在前端留副本 ----------------------------------------------

test("c1 保存成功后,返回值里不含 key 原文", async () => {
  const f = recFetch(() => jsonRes(200, { configured: true, provider: "mimo",
                                          hint: "sk-o…9999", restart: "manual" }));
  const r = await saveKey(f, "mimo", KEY);
  assert.ok(!JSON.stringify(r).includes(KEY), "返回值把 key 带回来了");
});

test("c2 后端要是把 key 回显了,前端也不许原样端出去", async () => {
  // 反向验:这条防的是"上游漏了、前端当传声筒"。后端有 h4 咬着,这儿是纵深。
  const f = recFetch(() => jsonRes(200, { configured: true, provider: "mimo", hint: "sk-o…9999",
                                          restart: "manual", key: KEY, echo: { apiKey: KEY } }));
  const r = await saveKey(f, "mimo", KEY);
  assert.ok(!JSON.stringify(r).includes(KEY), "上游回显了 key,前端照单全收");
});

// ---- d* 重启文案不许撒谎 ---------------------------------------------------

test("d1 manual = 得业主自己重启,那句话里必须有「重启」", () => {
  const s = restartNotice("manual");
  assert.ok(s && s.length > 0);
  assert.ok(/重启|重新启动|重新打开/.test(s), `manual 却没说要重启:${s}`);
});

test("d2 requested = 已经替他重启了,不许再叫他去重启", () => {
  const s = restartNotice("requested");
  assert.ok(s && s.length > 0);
  assert.ok(!s.includes("重启一下") && !s.includes("请重启"),
            `已经替他做了却还叫他动手:${s}`);
  assert.notEqual(s, restartNotice("manual"), "两种结果说同一句话 = 这个字段白读了");
});

test("d3 没见过的 restart 值往保守那边倒(宁可让他多点一下)", () => {
  for (const v of ["", "unknown", undefined, null]) {
    const s = restartNotice(v);
    assert.ok(s && /重启|重新启动|重新打开/.test(s),
              `restart=${JSON.stringify(v)} 时没有让业主自己重启:${s}`);
  }
});
