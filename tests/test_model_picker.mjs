// 判据:输入框里那颗模型按钮的纯逻辑(track opendesign-composer-model-picker;09-24 起照 ZCode 两级弹框,
// track opendesign-zcode-model-settings)。编号权威表在 tracks/opendesign-composer-model-picker/design.md(前缀 mp)。
// 跑法:node --test tests/test_model_picker.mjs
//
// 界面长什么样、点了是否真发出请求,归 tests/e2e/model_picker.e2e.mjs;这里只钉"菜单里该有什么"。
// 09-24 移植(verify.md 对照表):mp1~mp4 从一维 modelMenuItems 改问两级树 modelMenuTree ——
// 每家一行(当前那家 ✓)→ 向右弹出这家模型(当前 ✓)→ 底行「管理模型」(接替「换厂商 / 换 key…」)。性质一条不丢。
import { test } from "node:test";
import assert from "node:assert/strict";
import { modelMenuTree, modelChipLabel, readModelsResponse, MANAGE_MODELS_LABEL } from "../web/src/chat/modelPicker.ts";

const MIMO = {
  provider: "mimo",
  label: "MiMo(小米)",
  current: "mimo-v2.5",
  models: [{ id: "mimo-v2.5", label: "mimo-v2.5" }, { id: "mimo-v2.5-pro", label: "mimo-v2.5-pro" }],
};

test("mp1 当前厂商一行(说清是哪家)、打勾;向右弹出的这家模型一行一个、当前那行打勾", () => {
  const t = modelMenuTree(MIMO);
  assert.equal(t.vendors.length, 1);
  const v = t.vendors[0];
  assert.equal(v.provider, "mimo");
  assert.match(v.label, /MiMo\(小米\)/);
  assert.equal(v.active, true);
  assert.deepEqual(v.models.map((m) => m.id), ["mimo-v2.5", "mimo-v2.5-pro"]);
  assert.deepEqual(v.models.map((m) => m.active), [true, false]);
});

test("mp2 底行恒为「管理模型」,落到当前那家的设置", () => {
  assert.equal(MANAGE_MODELS_LABEL, "管理模型");
  const t = modelMenuTree(MIMO);
  assert.equal(t.manage.label, MANAGE_MODELS_LABEL);
  assert.equal(t.manage.provider, "mimo");
});

test("mp3 没有可选模型(没配 key / 认不出厂商 / 读不到)⇒ 一家都不列,只剩「管理模型」", () => {
  for (const resp of [null, { provider: null, label: null, current: null, models: [] }]) {
    const t = modelMenuTree(resp);
    assert.deepEqual(t.vendors, [], JSON.stringify(resp));
    assert.equal(t.manage.label, MANAGE_MODELS_LABEL);
    assert.equal(t.manage.provider, null, "没有当前那家就不许编一家出来");
  }
});

test("mp4 当前模型不在目录里 ⇒ 没有哪一行打勾,厂商行也不勾(不许谎称选中了某一个)", () => {
  const t = modelMenuTree({ ...MIMO, current: "some-other-model" });
  assert.equal(t.vendors.flatMap((v) => v.models).filter((m) => m.active).length, 0);
  assert.equal(t.vendors.filter((v) => v.active).length, 0);
});

test("mp5 按钮上的字:优先接口回的 current,读不到退回网关报的模型名,都没有写「选择模型」", () => {
  assert.equal(modelChipLabel(MIMO, "gateway-said"), "mimo-v2.5");
  assert.equal(modelChipLabel(null, "gateway-said"), "gateway-said");
  assert.equal(modelChipLabel({ ...MIMO, current: null }, "gateway-said"), "gateway-said");
  assert.equal(modelChipLabel(null, undefined), "选择模型");
});

test("mp6 读接口回包不许崩:非 200 / 形状不对 ⇒ null", () => {
  assert.deepEqual(readModelsResponse(200, MIMO), MIMO);
  assert.equal(readModelsResponse(500, MIMO), null);
  assert.equal(readModelsResponse(200, null), null);
  assert.equal(readModelsResponse(200, "oops"), null);
  assert.equal(readModelsResponse(200, { ...MIMO, models: "not-array" }), null);
  assert.equal(readModelsResponse(200, { ...MIMO, models: [{ id: 3 }] }), null);
});
