// 判据:输入框里那颗模型按钮的纯逻辑(track opendesign-composer-model-picker)。
// 编号权威表在 tracks/opendesign-composer-model-picker/design.md(前缀 mp)。
// 跑法:node --test tests/test_model_picker.mjs
//
// **此刻应该全红** —— web/src/chat/modelPicker.ts 还不存在。
// 界面长什么样、点了是否真发出请求,归 tests/e2e/model_picker.e2e.mjs;这里只钉"菜单里该有什么"。
import { test } from "node:test";
import assert from "node:assert/strict";
import { modelMenuItems, modelChipLabel, readModelsResponse, SWITCH_PROVIDER_LABEL } from "../web/src/chat/modelPicker.ts";

const MIMO = {
  provider: "mimo",
  label: "MiMo(小米)",
  current: "mimo-v2.5",
  models: [{ id: "mimo-v2.5", label: "mimo-v2.5" }, { id: "mimo-v2.5-pro", label: "mimo-v2.5-pro" }],
};

test("mp1 当前厂商的模型一行一个、当前那行打勾,分组标题说清是哪家的 key", () => {
  const items = modelMenuItems(MIMO);
  assert.equal(items[0].kind, "group");
  assert.match(items[0].label, /MiMo\(小米\)/);
  const models = items.filter((i) => i.kind === "model");
  assert.deepEqual(models.map((m) => m.id), ["mimo-v2.5", "mimo-v2.5-pro"]);
  assert.deepEqual(models.map((m) => m.active), [true, false]);
});

test("mp2 最后一项恒为「换厂商 / 换 key…」,前面有分隔线", () => {
  const items = modelMenuItems(MIMO);
  assert.equal(items.at(-1).kind, "switch");
  assert.equal(items.at(-1).label, SWITCH_PROVIDER_LABEL);
  assert.equal(SWITCH_PROVIDER_LABEL, "换厂商 / 换 key…");
  assert.equal(items.at(-2).kind, "sep");
});

test("mp3 没有可选模型(没配 key / 认不出厂商 / 读不到)⇒ 只剩「换厂商 / 换 key…」一项", () => {
  for (const resp of [null, { provider: null, label: null, current: null, models: [] }]) {
    const items = modelMenuItems(resp);
    assert.deepEqual(items.map((i) => i.kind), ["switch"], JSON.stringify(resp));
  }
});

test("mp4 当前模型不在目录里 ⇒ 没有哪一行打勾(不许谎称选中了某一个)", () => {
  const items = modelMenuItems({ ...MIMO, current: "some-other-model" });
  assert.equal(items.filter((i) => i.kind === "model" && i.active).length, 0);
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
