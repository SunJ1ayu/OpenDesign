// T4 oracle:界面里填大模型 key 的**纯逻辑层**。
// 主 agent 亲写;执行腿对本文件逐字节 off-limits(改这份 = 改考卷)。
// 原 track opendesign-key-onboarding(模块 web/src/llmKey.ts);09-24 起旧 key 卡片由照 ZCode 的「设置 · 模型设置」接替
// (track opendesign-zcode-model-settings),问的对象换成 web/src/settings/modelSettings.ts —— **每一条性质原样保留**,
// 对照表在那个 track 的 verify.md。
//
// 跑法:node --test tests/test_llm_key.mjs(Node 22+,原生 strip-types)
//
// ── 后端契约(判据 tests/test_ds_web_providers.py w1~w8)──────────────────
//   GET  /api/llm/providers → 200 {providers:[{id,label,configured,hint,writable,…,models}], current, multi}
//   POST /api/llm/providers/key {provider,key} → 200 同上 + restart
//                                            → 400 {error:"人话"}
//   restart ∈ {"requested","manual"}。**"manual" = 网关没被重启,得业主自己动手。**
//
// ── 这份考卷问什么 ────────────────────────────────────────────────────────
//   a*  契约:发到哪、发了什么、回来是什么形状
//   b*  厂商清单**只能来自后端**(两边各硬编码一份,就会一起错)
//   c*  key 不许在前端留下任何副本
//   d*  重启那句话不许撒谎(manual 必须说"请重启",requested 不许说)
//
// ⚠️ 判据先行时它红在 ERR_MODULE_NOT_FOUND 上 —— 那种红只证明"没有就会响",
//    **不证明"写错了会响"**(08-14 实证)。实现落地后跑 tests/mutation-llm-key.sh 定点变异。
import { test } from "node:test";
import assert from "node:assert/strict";

import {
  PROVIDERS_PATH,
  PROVIDER_KEY_PATH,
  CUSTOM_PROVIDER_PATH,
  fetchProviders,
  saveProviderKey,
  postSettings,
  restartNotice,
} from "../web/src/settings/modelSettings.ts";

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

const ROW = (id, o = {}) => ({
  id, label: id.toUpperCase(), kind: "builtin", apiBase: `https://${id}.example/v1`, keyUrl: null,
  configured: false, hint: null, live: false, active: false, pending: false, enabled: true, writable: true,
  models: [{ id: `${id}-a`, label: `${id}-a`, builtin: true, contextWindow: null }], ...o,
});
const VIEW_EMPTY = { providers: [ROW("mimo"), ROW("deepseek")], current: null, multi: true };
const saved = (o = {}) => ({
  providers: [ROW("mimo", { configured: true, hint: "sk-o…9999", pending: true }), ROW("deepseek")],
  current: null, multi: true, restart: "manual", ...o,
});

// ---- a* 契约 -------------------------------------------------------------

test("a1 状态用 GET 拉,打在约定的那条路径上,不带 body", async () => {
  const f = recFetch(() => jsonRes(200, VIEW_EMPTY));
  await fetchProviders(f);
  assert.equal(f.calls.length, 1);
  const { url, init } = f.calls[0];
  assert.equal(url, PROVIDERS_PATH);
  assert.equal(PROVIDERS_PATH, "/api/llm/providers"); // 路径写错 = 整条链断
  assert.ok(!init.method || init.method.toUpperCase() === "GET", `方法应是 GET,实为 ${init.method}`);
  assert.equal(init.body, undefined);
});

test("a2 状态原样透出(每家 configured/hint/writable 与当前在用都不许丢);读不到 ⇒ null 不抛", async () => {
  const body = {
    providers: [ROW("mimo"), ROW("deepseek", { configured: true, hint: "sk-o…9999", writable: false })],
    current: { provider: "deepseek", model: "deepseek-a" }, multi: false,
  };
  const st = await fetchProviders(recFetch(() => jsonRes(200, body)));
  const ds = st.providers.find((p) => p.id === "deepseek");
  assert.equal(ds.configured, true);
  assert.equal(ds.hint, "sk-o…9999");
  assert.equal(ds.writable, false);
  assert.deepEqual(st.current, { provider: "deepseek", model: "deepseek-a" });
  assert.equal(st.multi, false);
  assert.equal(await fetchProviders(async () => { throw new TypeError("Failed to fetch"); }), null);
  assert.equal(await fetchProviders(recFetch(() => jsonRes(500, {}))), null);
});

test("a3 保存用 POST,provider 和 key 都在 body 里,**key 不许进 URL**", async () => {
  const f = recFetch(() => jsonRes(200, saved()));
  await saveProviderKey(f, "mimo", KEY);
  assert.equal(f.calls.length, 1);
  const { url, init } = f.calls[0];
  assert.equal(url, PROVIDER_KEY_PATH);
  assert.equal(PROVIDER_KEY_PATH, "/api/llm/providers/key");
  assert.equal(init.method?.toUpperCase(), "POST");
  // URL 会进 access log / 浏览器历史 / Referer —— key 落在这儿就等于漏了。
  assert.ok(!url.includes(KEY), `key 出现在 URL 里:${url}`);
  assert.ok(!url.includes("key="), `URL 带了 key 参数:${url}`);
  const sent = JSON.parse(init.body);
  assert.equal(sent.provider, "mimo");
  assert.equal(sent.key, KEY);
});

test("a4 保存成功:回 ok + 后端给的新列表与 restart", async () => {
  const r = await saveProviderKey(recFetch(() => jsonRes(200, saved({ restart: "requested" }))), "mimo", KEY);
  assert.equal(r.ok, true);
  assert.equal(r.view.providers[0].configured, true);
  assert.equal(r.view.providers[0].hint, "sk-o…9999");
  assert.equal(r.restart, "requested");
});

test("a5 后端拒绝(400):把**它的**人话原样端出来,不许自己另编一句", async () => {
  const f = recFetch(() => jsonRes(400, { error: "API key 里有中文或特殊字符,请检查是不是复制多了" }));
  const r = await saveProviderKey(f, "mimo", "中文key");
  assert.equal(r.ok, false);
  // 要的是"后端那句话到得了业主眼前",不是"一个字都不许多"(加个「保存失败:」前缀完全合理)。
  assert.ok(r.error.includes("API key 里有中文或特殊字符,请检查是不是复制多了"),
            `后端的人话没端出来:${r.error}`);
});

test("a6 服务不可达(fetch 抛)不许静默成功,也不许把 key 带进错误里", async () => {
  const boom = async () => { throw new TypeError("Failed to fetch"); };
  const r = await saveProviderKey(boom, "mimo", KEY);
  assert.equal(r.ok, false, "网络炸了却报成功 = 业主以为存上了");
  assert.ok(r.error && r.error.length > 0, "得给一句能读的话");
  assert.ok(!JSON.stringify(r).includes(KEY), "错误对象里带了 key 原文");
});

test("a7 500 之类 / 200 但形状不对 也走失败路,不许当成成功解读", async () => {
  assert.equal((await saveProviderKey(recFetch(() => jsonRes(500, {})), "mimo", KEY)).ok, false);
  assert.equal((await saveProviderKey(recFetch(() => jsonRes(200, { providers: "x" })), "mimo", KEY)).ok, false);
});

test("a8 添加自定义供应商(带 key)走同一条纪律:POST、key 只在 body、回包不含 key", async () => {
  const f = recFetch(() => jsonRes(200, saved({ key: KEY })));
  const r = await postSettings(f, CUSTOM_PROVIDER_PATH,
    { op: "add", label: "中转", apiBase: "https://proxy.example/v1", models: ["gpt-x"], key: KEY }, KEY);
  assert.equal(CUSTOM_PROVIDER_PATH, "/api/llm/providers/custom");
  assert.equal(f.calls[0].init.method?.toUpperCase(), "POST");
  assert.ok(!f.calls[0].url.includes(KEY));
  assert.equal(JSON.parse(f.calls[0].init.body).key, KEY);
  assert.equal(r.ok, true);
  assert.ok(!JSON.stringify(r).includes(KEY), "回包把 key 带回来了");
});

// ---- b* 厂商清单只能来自后端 ----------------------------------------------

test("b1 厂商是后端说了算:没听过的厂商也照样透出、照样能提交", async () => {
  // 后端换了厂商表(加一家 / 改端点),前端不该有自己的白名单。
  const acme = ROW("acme", { label: "Acme 云" });
  const st = await fetchProviders(recFetch(() => jsonRes(200, { ...VIEW_EMPTY, providers: [acme] })));
  assert.deepEqual(st.providers.map((p) => [p.id, p.label]), [["acme", "Acme 云"]]);

  const f = recFetch(() => jsonRes(200, saved({ providers: [acme] })));
  const r = await saveProviderKey(f, "acme", KEY);
  assert.equal(r.ok, true, "前端自带白名单就会把后端的新厂商挡在外面");
  assert.equal(JSON.parse(f.calls[0].init.body).provider, "acme");
});

// ---- c* key 不许在前端留副本 ----------------------------------------------

test("c1 保存成功后,返回值里不含 key 原文", async () => {
  const r = await saveProviderKey(recFetch(() => jsonRes(200, saved())), "mimo", KEY);
  assert.ok(!JSON.stringify(r).includes(KEY), "返回值把 key 带回来了");
});

test("c2 后端要是把 key 回显了(多出来的字段、甚至塞进某家的末四位提示),前端也不许原样端出去", async () => {
  // 反向验:这条防的是"上游漏了、前端当传声筒"。后端有 w1/w5 咬着,这儿是纵深。
  const leaky = saved({ key: KEY, echo: { apiKey: KEY } });
  leaky.providers[1] = ROW("deepseek", { configured: true, hint: KEY, label: `DS ${KEY}` });
  const r = await saveProviderKey(recFetch(() => jsonRes(200, leaky)), "mimo", KEY);
  assert.ok(!JSON.stringify(r).includes(KEY), "上游回显了 key,前端照单全收");
  assert.ok(r.ok, "回显不等于保存失败:key 抹掉、其余照常");
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

test("d4 live = 网关在跑、下一句就用(track opendesign-key-restart):不提重启、不叫他动手", () => {
  const s = restartNotice("live");
  assert.ok(s && s.length > 0);
  assert.ok(!/重启|重新启动|重新打开|稍等/.test(s), `网关根本没动,却说在重启 / 叫他重开 / 叫他等:${s}`);
  assert.notEqual(s, restartNotice("manual"));
  assert.notEqual(s, restartNotice("requested"));
});

test("d5 live 存的不是正在用的那家 ⇒ 不许说「下一句就用它」(QA 设计 Grok Q1 / DeepSeek T14:存 key 不换当前模型)", () => {
  const other = restartNotice("live", false);
  assert.ok(!/下一句/.test(other), `存了另一家却暗示下一句就改走它:${other}`);
  assert.ok(/右下角/.test(other), `没告诉他去哪儿换到这家:${other}`);
  const same = restartNotice("live", true);
  assert.ok(/下一句/.test(same), `改的就是正在用的那家,却没说下一句就用新 key:${same}`);
  assert.equal(restartNotice("live"), other, "不知道是不是正在用的那家 ⇒ 用两种情况都成立的那句");
});

test("d6 live 存的是未启用的那家 ⇒ 不许说「右下角就能换」(第 1 轮评审 DeepSeek #1:菜单里藏着它),要说先启用", () => {
  const s = restartNotice("live", false, true);
  assert.ok(!/右下角就能换/.test(s), `未启用的那家不在换模型菜单里,却叫他去右下角换:${s}`);
  assert.ok(/启用/.test(s) && !/已禁用/.test(s), `没说要先启用(或用了界面上不用的词「已禁用」):${s}`);
  assert.equal(restartNotice("live", false), restartNotice("live", false, false), "没说未启用 ⇒ 与原来那句一样");
});

test("d7 未启用那句的叫法对得上开关旁实际显示的字「未启用 / 已启用」(track opendesign-chat-error-visible;key-restart QA 执行顺带发现)", () => {
  const s = restartNotice("live", false, true);
  assert.ok(!/打开「启用」/.test(s), `开关旁边根本没有「启用」这两个字的按钮:${s}`);
  assert.ok(/「未启用」/.test(s), `没用开关旁边实际显示的字「未启用」:${s}`);
});

test("d3 没见过的 restart 值往保守那边倒(宁可让他多点一下)", () => {
  // 09-24 加强:只查「有重启两个字」分不出两种说法 —— requested 那句也含「请手动重启」(08-16 四审加的兜底),
  // 把未知值倒向"正在自动重启"时这条照绿(红检 mutation-llm-key M5 漏网)。保守 = 与 manual 同一句。
  for (const v of ["", "unknown", undefined, null]) {
    const s = restartNotice(v);
    assert.ok(s && /重启|重新启动|重新打开/.test(s),
              `restart=${JSON.stringify(v)} 时没有让业主自己重启:${s}`);
    assert.equal(s, restartNotice("manual"), `restart=${JSON.stringify(v)} 时说成了已替他重启:${s}`);
  }
});
