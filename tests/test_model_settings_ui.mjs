// 判据:设置页 · 模型设置的纯逻辑(track opendesign-zcode-model-settings,前缀 ms)。主 agent 亲写,判据先单独 commit。
// 跑法:node --test tests/test_model_settings_ui.mjs
//
// 接替旧 key 卡片的纯逻辑判据(ku1~ku3、pv6、pv7)—— 性质一条不丢,问的对象换成新页面的数据层:
//   · 「获取 API Key」只收 https(ku2);没有链接的厂商不画空链接(ku3)
//   · 每家状态四种说法不许混:在用 / 就绪 / 已保存等重启 / 没填(pv7),另加 ZCode 的「已禁用」
//   · 形状不对的行丢掉、不让整页崩(pv6)
// 需求空白的主裁定见 tracks/opendesign-zcode-model-settings/evidence/acceptance-cases.md Q1~Q9。
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  readProvidersResponse, providerStatus, providerStateText, navGroups, contextLabel,
  settingsRoute, settingsHash, PROVIDERS_PATH,
} from "../web/src/settings/modelSettings.ts";

const M = (id, o = {}) => ({ id, label: id, builtin: true, contextWindow: null, ...o });
const P = (id, o = {}) => ({
  id, label: id.toUpperCase(), kind: "builtin", apiBase: `https://${id}.example/v1`, keyUrl: `https://${id}.example/keys`,
  configured: false, hint: null, live: false, active: false, pending: false, enabled: true, models: [M(`${id}-a`)], ...o,
});
const VIEW = {
  providers: [P("mimo", { configured: true, hint: "tp-o…0123", live: true, active: true }), P("deepseek"),
              P("c_1", { kind: "custom", keyUrl: null, label: "我的中转" })],
  current: { provider: "mimo", model: "mimo-a" }, multi: true,
};

test("ms1 读回包:正常原样;非 200 / 形状不对 ⇒ null;坏的一行丢掉、不拖垮整页(pv6)", () => {
  assert.equal(PROVIDERS_PATH, "/api/llm/providers");
  const v = readProvidersResponse(200, VIEW);
  assert.deepEqual(v.providers.map((p) => p.id), ["mimo", "deepseek", "c_1"]);
  assert.deepEqual(v.current, { provider: "mimo", model: "mimo-a" });
  assert.equal(v.multi, true);
  assert.equal(readProvidersResponse(500, VIEW), null);
  assert.equal(readProvidersResponse(200, { providers: "x" }), null);
  const junk = readProvidersResponse(200, { ...VIEW, providers: [{ id: 3 }, VIEW.providers[0], "x"] });
  assert.deepEqual(junk.providers.map((p) => p.id), ["mimo"]);
});

test("ms2 🔴「获取 API Key」只收 https;坏链接不让整行厂商消失(ku1/ku2)", () => {
  const bad = ["javascript:alert(1)", "http://bigmodel.cn/x", "/api/x", "  ", 42, "https//no-colon"];
  const v = readProvidersResponse(200, { ...VIEW, providers: bad.map((u, i) => P(`v${i}`, { keyUrl: u })) });
  assert.equal(v.providers.length, bad.length);
  for (const p of v.providers) assert.equal(p.keyUrl, null, `${p.id} 收下了坏链接`);
  assert.equal(readProvidersResponse(200, VIEW).providers[0].keyUrl, "https://mimo.example/keys");
});

test("ms3 状态点三态(照 ZCode):已禁用 > 就绪(key 在、后台拿到)> 未就绪(没填或等重启)", () => {
  assert.equal(providerStatus(P("x", { configured: true, live: true })), "ready");
  assert.equal(providerStatus(P("x", { configured: true, pending: true })), "unavailable");
  assert.equal(providerStatus(P("x")), "unavailable");
  assert.equal(providerStatus(P("x", { configured: true, live: true, enabled: false })), "disabled");
});

test("ms4 每家一句话:在用 / 就绪 / 已保存等重启 / 没填 / 已禁用 —— 五种说法不许混(pv7)", () => {
  const t = [
    providerStateText(P("x", { configured: true, hint: "sk-o…cdef", live: true, active: true })),
    providerStateText(P("x", { configured: true, hint: "sk-o…cdef", live: true })),
    providerStateText(P("x", { configured: true, hint: "sk-o…cdef", pending: true })),
    providerStateText(P("x")),
    providerStateText(P("x", { configured: true, hint: "sk-o…cdef", live: true, enabled: false })),
  ];
  assert.equal(new Set(t).size, 5, t.join(" | "));
  assert.match(t[0], /在用/);
  assert.match(t[1], /cdef/);
  assert.match(t[2], /重启/, "等重启那一家必须说清要等后台重启");
  assert.doesNotMatch(t[3], /…/, "没填的不许出现首尾提示");
  assert.match(t[4], /禁用/);
});

test("ms5 左栏两组:内置供应商(照后端顺序)/ 自定义供应商(没有也要有这一组,「添加供应商」挂在它下面)", () => {
  const g = navGroups(readProvidersResponse(200, VIEW));
  assert.deepEqual(g.map((x) => [x.id, x.title]), [["builtin", "内置供应商"], ["custom", "自定义供应商"]]);
  assert.deepEqual(g[0].items.map((p) => p.id), ["mimo", "deepseek"]);
  assert.deepEqual(g[1].items.map((p) => p.id), ["c_1"]);
  const none = navGroups(readProvidersResponse(200, { ...VIEW, providers: VIEW.providers.slice(0, 2) }));
  assert.deepEqual(none[1].items, []);
});

test("ms6 上下文长度按「万」显示(ZCode 行内那个小标签);没有就不显示", () => {
  assert.equal(contextLabel(262144), "26.2万");
  assert.equal(contextLabel(128000), "12.8万");
  assert.equal(contextLabel(1000000), "100万");
  assert.equal(contextLabel(null), "");
});

test("ms7 设置页路由:#/settings ⇒ 常规;#/settings/models?provider=kimi ⇒ 模型设置并选中 kimi;来回一致", () => {
  assert.deepEqual(settingsRoute("#/settings"), { section: "general", provider: null });
  assert.deepEqual(settingsRoute("#/settings/models"), { section: "models", provider: null });
  assert.deepEqual(settingsRoute("#/settings/models?provider=kimi"), { section: "models", provider: "kimi" });
  assert.equal(settingsRoute("#/workspace"), null);
  assert.equal(settingsHash("models", "kimi"), "#/settings/models?provider=kimi");
  assert.deepEqual(settingsRoute(settingsHash("models", "c_1")), { section: "models", provider: "c_1" });
});

test("ms8 被环境变量供着的那一家 writable=false 原样透出(界面据此禁用输入并说明,H1);老后端没这个字段 ⇒ 当可写", () => {
  const v = readProvidersResponse(200, { ...VIEW, providers: [P("mimo", { writable: false }), P("deepseek")] });
  assert.deepEqual(v.providers.map((p) => p.writable), [false, true]);
});
