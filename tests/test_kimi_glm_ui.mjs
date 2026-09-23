// 判据:key 卡片上的「获取 API Key」链接(track opendesign-kimi-glm-vendors,前缀 ku)。主 agent 亲写,判据先单独 commit。
// 跑法:node --test tests/test_kimi_glm_ui.mjs
//
// 链接地址只由后端厂商表给(tests/test_kimi_glm_vendors.py k2/k6 钉值),前端不另抄一份;
// 前端要做的:① 只收 https(后端被改坏时不渲染一个 javascript: 链接)② 按下拉里选中的那家显示 ③ 在外部浏览器开。
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fetchKeyStatus } from "../web/src/llmKey.ts";

const fetchOf = (body) => async () => ({ status: 200, json: async () => body });
const P = (id, extra = {}) => ({ id, label: id.toUpperCase(), model: `${id}-m`, ...extra });

test("ku1 厂商行带上 keyUrl;缺了也照样认得出这家(老后端)", async () => {
  const st = await fetchKeyStatus(fetchOf({
    configured: false, providers: [P("kimi", { keyUrl: "https://platform.kimi.com/console/api-keys" }), P("mimo")],
  }));
  assert.deepEqual(st.providers.map((p) => p.id), ["kimi", "mimo"]);
  assert.equal(st.providers[0].keyUrl, "https://platform.kimi.com/console/api-keys");
  assert.equal(st.providers[1].keyUrl ?? null, null);
});

test("ku2 🔴 非 https 的 keyUrl 一律丢掉(不渲染 javascript:/http:/相对路径)", async () => {
  const bad = ["javascript:alert(1)", "http://bigmodel.cn/x", "/api/x", "  ", 42, "https//no-colon"];
  const st = await fetchKeyStatus(fetchOf({
    configured: false, providers: bad.map((u, i) => P(`v${i}`, { keyUrl: u })),
  }));
  assert.equal(st.providers.length, bad.length, "坏链接不该让整行厂商消失");
  for (const p of st.providers) assert.equal(p.keyUrl ?? null, null, `${p.id} 收下了 ${p.keyUrl}`);
});

test("ku3 卡片按选中厂商显示「获取 API Key」外链,在新窗口开、不带来源", () => {
  const src = readFileSync(new URL("../web/src/LlmKeyCard.tsx", import.meta.url), "utf8");
  const at = src.indexOf('data-ui="llm-key-link"');
  assert.ok(at >= 0, "卡片上没有获取 key 的链接");
  const tag = src.slice(src.lastIndexOf("<a", at), src.indexOf(">", at) + 1);
  assert.match(tag, /href=\{selected\.keyUrl\}/, "链接要跟着下拉里选中的那家走");
  assert.match(tag, /target="_blank"/);
  assert.match(tag, /rel="noreferrer"/);
  const around = src.slice(Math.max(0, at - 300), at + 300);
  assert.match(around, /selected\?\.keyUrl\s*&&/, "没有链接的厂商不该画一个空链接");
  assert.match(around, /获取/, "链接要说人话:获取 … API Key");
});
