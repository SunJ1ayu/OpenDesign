// 判据:每家厂商各存各的 key —— 前端纯逻辑层(track opendesign-per-vendor-keys,前缀 pv)。
// 主 agent 亲写。设计在 tracks/opendesign-per-vendor-keys/design.md。
// 跑法:node --test tests/test_per_vendor_ui.mjs
//
// 这里只钉"菜单里该有什么、点了发什么";真浏览器 + 真 ds_web 走一遍归 tests/e2e/per_vendor_keys.e2e.mjs。
// 09-24 移植(track opendesign-zcode-model-settings,verify.md 对照表):pv1~pv4 改问两级树 modelMenuTree;
// pv6 / pv7(旧 key 卡片每行的状态与说法)由 tests/test_model_settings_ui.mjs 的 ms1 / ms4 接替。
//
// 最要紧的一条是 pv2:**点哪一行,就把哪一家发给后端**。
// 模型名今天两家不重名,但"靠名字反查厂商"是一条会随目录悄悄失效的前提 ——
// 让前端把厂商带上,后端就不必猜。
import { test } from "node:test";
import assert from "node:assert/strict";
import { modelMenuTree, readModelsResponse, modelSelectBody, MANAGE_MODELS_LABEL }
  from "../web/src/chat/modelPicker.ts";

const MIMO_MODELS = [{ id: "mimo-v2.5", label: "mimo-v2.5" }, { id: "mimo-v2.5-pro", label: "mimo-v2.5-pro" }];
const DS_MODELS = [{ id: "deepseek-v4-flash", label: "deepseek-v4-flash" }, { id: "deepseek-v4-pro", label: "deepseek-v4-pro" }];
const TWO = {
  provider: "deepseek", label: "DeepSeek 官方", current: "deepseek-v4-pro", models: DS_MODELS,
  groups: [
    { provider: "mimo", label: "MiMo(小米)", models: MIMO_MODELS },
    { provider: "deepseek", label: "DeepSeek 官方", models: DS_MODELS },
  ],
};

test("pv1 两家都活着:每家一行(没模型的那家不列);只有当前那家打勾,子菜单里只有「当前厂商的当前模型」打勾", () => {
  const t = modelMenuTree({ ...TWO, groups: [...TWO.groups, { provider: "kimi", label: "Kimi", models: [] }] });
  assert.deepEqual(t.vendors.map((v) => v.provider), ["mimo", "deepseek"]);
  assert.match(t.vendors[0].label, /MiMo\(小米\)/);
  assert.match(t.vendors[1].label, /DeepSeek 官方/);
  assert.deepEqual(t.vendors.map((v) => v.active), [false, true]);
  const active = t.vendors.flatMap((v) => v.models).filter((m) => m.active);
  assert.deepEqual(active.map((m) => [m.provider, m.id]), [["deepseek", "deepseek-v4-pro"]]);
  assert.equal(t.manage.label, MANAGE_MODELS_LABEL);
  assert.equal(t.manage.provider, "deepseek");
});

test("pv2 每一行都带着自己的厂商;点了发给后端的是 {model, provider}", () => {
  const models = modelMenuTree(TWO).vendors.flatMap((v) => v.models);
  assert.deepEqual(models.map((m) => m.provider), ["mimo", "mimo", "deepseek", "deepseek"]);
  assert.deepEqual(modelSelectBody(models[1]), { model: "mimo-v2.5-pro", provider: "mimo" });
  assert.deepEqual(modelSelectBody(models[2]), { model: "deepseek-v4-flash", provider: "deepseek" });
});

test("pv3 同一个模型名出现在两家里:只有当前那家(厂商行和它的模型)打勾(不许靠名字判断选中)", () => {
  const dup = {
    ...TWO, provider: "mimo", current: "shared-model",
    groups: [
      { provider: "mimo", label: "MiMo(小米)", models: [{ id: "shared-model", label: "shared-model" }] },
      { provider: "deepseek", label: "DeepSeek 官方", models: [{ id: "shared-model", label: "shared-model" }] },
    ],
  };
  const t = modelMenuTree(dup);
  assert.deepEqual(t.vendors.filter((v) => v.active).map((v) => v.provider), ["mimo"]);
  assert.deepEqual(t.vendors.flatMap((v) => v.models).filter((m) => m.active).map((m) => m.provider), ["mimo"]);
});

test("pv4 老后端(没有 groups):照旧只列当前这一家,行为与今天一致", () => {
  const old = { provider: "mimo", label: "MiMo(小米)", current: "mimo-v2.5", models: MIMO_MODELS };
  const t = modelMenuTree(readModelsResponse(200, old));
  assert.deepEqual(t.vendors.map((v) => v.provider), ["mimo"]);
  assert.deepEqual(t.vendors[0].models.map((m) => m.provider), ["mimo", "mimo"]);
});

test("pv5 读回包:groups 原样保留;形状不对 ⇒ null(与 mp6 同一个严格度)", () => {
  assert.deepEqual(readModelsResponse(200, TWO).groups, TWO.groups);
  assert.equal(readModelsResponse(200, { ...TWO, groups: "nope" }), null);
  assert.equal(readModelsResponse(200, { ...TWO, groups: [{ provider: 1, label: "x", models: [] }] }), null);
  assert.equal(readModelsResponse(200, { ...TWO, groups: [{ provider: "x", label: "x", models: [{ id: 2 }] }] }), null);
});
