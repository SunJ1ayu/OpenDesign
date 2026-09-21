// 判据:每家厂商各存各的 key —— 前端纯逻辑层(track opendesign-per-vendor-keys,前缀 pv)。
// 主 agent 亲写。设计在 tracks/opendesign-per-vendor-keys/design.md。
// 跑法:node --test tests/test_per_vendor_ui.mjs
//
// 这里只钉"菜单里该有什么、点了发什么、卡片每行说什么";
// 真浏览器 + 真 ds_web 走一遍归 tests/e2e/per_vendor_keys.e2e.mjs。
//
// 最要紧的一条是 pv2:**点哪一行,就把哪一家发给后端**。
// 模型名今天两家不重名,但"靠名字反查厂商"是一条会随目录悄悄失效的前提 ——
// 让前端把厂商带上,后端就不必猜。
import { test } from "node:test";
import assert from "node:assert/strict";
import { modelMenuItems, readModelsResponse, modelSelectBody, SWITCH_PROVIDER_LABEL }
  from "../web/src/chat/modelPicker.ts";
import { fetchKeyStatus, vendorStateText } from "../web/src/llmKey.ts";

const MIMO_MODELS = [{ id: "mimo-v2.5", label: "mimo-v2.5" }, { id: "mimo-v2.5-pro", label: "mimo-v2.5-pro" }];
const DS_MODELS = [{ id: "deepseek-v4-flash", label: "deepseek-v4-flash" }, { id: "deepseek-v4-pro", label: "deepseek-v4-pro" }];
const TWO = {
  provider: "deepseek", label: "DeepSeek 官方", current: "deepseek-v4-pro", models: DS_MODELS,
  groups: [
    { provider: "mimo", label: "MiMo(小米)", models: MIMO_MODELS },
    { provider: "deepseek", label: "DeepSeek 官方", models: DS_MODELS },
  ],
};

test("pv1 两家都活着:按厂商分组列出,只有「当前厂商的当前模型」那一行打勾", () => {
  const items = modelMenuItems(TWO);
  assert.deepEqual(items.map((i) => i.kind),
    ["group", "model", "model", "group", "model", "model", "sep", "switch"]);
  assert.match(items[0].label, /MiMo\(小米\)/);
  assert.match(items[3].label, /DeepSeek 官方/);
  const active = items.filter((i) => i.kind === "model" && i.active);
  assert.deepEqual(active.map((i) => [i.provider, i.id]), [["deepseek", "deepseek-v4-pro"]]);
  assert.equal(items.at(-1).label, SWITCH_PROVIDER_LABEL);
});

test("pv2 每一行都带着自己的厂商;点了发给后端的是 {model, provider}", () => {
  const items = modelMenuItems(TWO).filter((i) => i.kind === "model");
  assert.deepEqual(items.map((i) => i.provider), ["mimo", "mimo", "deepseek", "deepseek"]);
  assert.deepEqual(modelSelectBody(items[1]), { model: "mimo-v2.5-pro", provider: "mimo" });
  assert.deepEqual(modelSelectBody(items[2]), { model: "deepseek-v4-flash", provider: "deepseek" });
});

test("pv3 同一个模型名出现在两家里:只有当前那家的打勾(不许靠名字判断选中)", () => {
  const dup = {
    ...TWO, provider: "mimo", current: "shared-model",
    groups: [
      { provider: "mimo", label: "MiMo(小米)", models: [{ id: "shared-model", label: "shared-model" }] },
      { provider: "deepseek", label: "DeepSeek 官方", models: [{ id: "shared-model", label: "shared-model" }] },
    ],
  };
  const active = modelMenuItems(dup).filter((i) => i.kind === "model" && i.active);
  assert.deepEqual(active.map((i) => i.provider), ["mimo"]);
});

test("pv4 老后端(没有 groups):照旧只列当前这一家,行为与今天一致", () => {
  const old = { provider: "mimo", label: "MiMo(小米)", current: "mimo-v2.5", models: MIMO_MODELS };
  const parsed = readModelsResponse(200, old);
  const items = modelMenuItems(parsed);
  assert.deepEqual(items.map((i) => i.kind), ["group", "model", "model", "sep", "switch"]);
  assert.deepEqual(items.filter((i) => i.kind === "model").map((i) => i.provider), ["mimo", "mimo"]);
});

test("pv5 读回包:groups 原样保留;形状不对 ⇒ null(与 mp6 同一个严格度)", () => {
  assert.deepEqual(readModelsResponse(200, TWO).groups, TWO.groups);
  assert.equal(readModelsResponse(200, { ...TWO, groups: "nope" }), null);
  assert.equal(readModelsResponse(200, { ...TWO, groups: [{ provider: 1, label: "x", models: [] }] }), null);
  assert.equal(readModelsResponse(200, { ...TWO, groups: [{ provider: "x", label: "x", models: [{ id: 2 }] }] }), null);
});

test("pv6 卡片状态:每家一行透出来;老后端没有 vendors ⇒ 空数组,不崩", async () => {
  const vendors = [
    { id: "mimo", label: "MiMo(小米)", configured: true, hint: "tp-o…0123", live: true, active: false, pending: false },
    { id: "deepseek", label: "DeepSeek 官方", configured: true, hint: "sk-o…cdef", live: false, active: false, pending: true },
  ];
  const base = { configured: true, provider: "mimo", hint: "tp-o…0123", providers: [], source: "file", writable: true };
  const fetchWith = (body) => async () => ({ status: 200, json: async () => body });
  const st = await fetchKeyStatus(fetchWith({ ...base, vendors }));
  assert.deepEqual(st.vendors, vendors);
  const old = await fetchKeyStatus(fetchWith(base));
  assert.deepEqual(old.vendors, []);
  const junk = await fetchKeyStatus(fetchWith({ ...base, vendors: [{ id: 3 }, vendors[0], "x"] }));
  assert.deepEqual(junk.vendors, [vendors[0]], "形状不对的那几行应该被丢掉,不是整张卡片崩掉");
});

test("pv7 每一行说的话:在用 / 已配置 / 已保存等重启 / 没填 —— 四种状态四种说法,不许混", () => {
  const v = (o) => ({ id: "x", label: "X", configured: false, hint: null, live: false, active: false, pending: false, ...o });
  const active = vendorStateText(v({ configured: true, hint: "sk-o…cdef", live: true, active: true }));
  const idle = vendorStateText(v({ configured: true, hint: "sk-o…cdef", live: true }));
  const pending = vendorStateText(v({ configured: true, hint: "sk-o…cdef", pending: true }));
  const none = vendorStateText(v({}));
  assert.equal(new Set([active, idle, pending, none]).size, 4, [active, idle, pending, none].join(" | "));
  assert.match(active, /在用/);
  assert.match(pending, /重启/, "待重启那一行必须说清要等后台重启 —— 不说,业主会以为存了没用");
  assert.doesNotMatch(none, /…/, "没填的那一行不许出现末四位提示");
  assert.match(idle, /cdef/);
});
