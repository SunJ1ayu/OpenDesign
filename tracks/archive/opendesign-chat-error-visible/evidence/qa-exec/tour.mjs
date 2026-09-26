// QA 执行的「真界面操作录像」(track opendesign-chat-error-visible):主 agent 在**真管家 + 真网关 + 真工作台 + 真 chromium** 上
// 按 QA 设计(Grok 26 条)把业主会碰到的出错走一遍,每一步留截图 + 页面文字 + 当时的事实。**不是判据**,不进 run-all。
// 补的是判据够不着的:e2e 的网关是替身,这里是真 nanobot 网关、真出错路径(含它自己的重试)。
//
// 台面:本机按出货形状摆一份(<包>/ds = 仓库某次提交的 git archive bin config web/dist;<包>/python/python.exe = 包一层 venv python 的小脚本)。
// 主槽 MiMo 的 apiBase 指到本机假厂商;假厂商的回法由本脚本现场切换(MODE)。报错体用本单探针抓到的真厂商原文。
// 零外网:导入 tests/e2e/helpers.mjs 即进无出口网络命名空间;代理变量另指向没人听的端口。
//
// 跑法(仓根):node tracks/opendesign-chat-error-visible/evidence/qa-exec/tour.mjs <包目录>
import { spawn, spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync, rmSync, mkdtempSync, readFileSync } from "node:fs";
import { createServer } from "node:http";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..", "..", "..");
const { launchBrowser, waitConnected, waitSendable } = await import(join(ROOT, "tests", "e2e", "helpers.mjs"));
const PKG = process.argv[2];
if (!PKG) { console.error("用法:tour.mjs <包目录>"); process.exit(2); }
const PY = join(PKG, "python", "python.exe");

// ── 假厂商:回法由 MODE 决定(报错体 = 探针里的真厂商原文)──
let MODE = "ok";
const BODIES = {
  "401": [401, { error: { message: "Invalid API Key", param: "Please provide valid API Key", code: "401", type: "invalid_key" } }],
  quota: [402, { error: { message: "Insufficient Balance", type: "unknown_error", param: null, code: "invalid_request_error" } }],
  glmquota: [429, { error: { code: "1113", message: "余额不足或无可用资源包,请充值。" } }],
  rate: [429, { error: { message: "Rate limit reached for requests", type: "rate_limit_error" } }],
  "500": [500, { error: { message: "internal server error", type: "server_error" } }],
  weird: [400, { error: { message: "Invalid image data", type: "invalid_request_error" } }],
};
const hits = [];
const vendor = createServer((req, res) => {
  let raw = "";
  req.on("data", (b) => { raw += b; });
  req.on("end", () => {
    let body = {};
    try { body = JSON.parse(raw || "{}"); } catch { /* 坏包 */ }
    hits.push({ mode: MODE, at: Date.now() });
    if (MODE === "down") { req.socket.destroy(); return; }   // 连上就断 = 网关眼里「连不上」
    if (BODIES[MODE]) {
      const [code, b] = BODIES[MODE];
      res.writeHead(code, { "Content-Type": "application/json" });
      res.end(JSON.stringify(b));
      return;
    }
    const now = Math.floor(Date.now() / 1000);
    const text = "我是 MiMo,正常回复。";
    if (body.stream) {
      res.writeHead(200, { "Content-Type": "text/event-stream" });
      res.write(`data: ${JSON.stringify({ id: "x", object: "chat.completion.chunk", created: now, model: body.model,
        choices: [{ index: 0, delta: { role: "assistant", content: text }, finish_reason: null }] })}\n\n`);
      res.write(`data: ${JSON.stringify({ id: "x", object: "chat.completion.chunk", created: now, model: body.model,
        choices: [{ index: 0, delta: {}, finish_reason: "stop" }] })}\n\n`);
      res.end("data: [DONE]\n\n");
      return;
    }
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ id: "x", object: "chat.completion", created: now, model: body.model,
      choices: [{ index: 0, finish_reason: "stop", message: { role: "assistant", content: text } }],
      usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 } }));
  });
});
await new Promise((r) => vendor.listen(0, "127.0.0.1", r));
const vendorBase = `http://127.0.0.1:${vendor.address().port}/v1`;

// ── 业主的机器:数据目录 + 配置 + 一把 key ──
const app = mkdtempSync(join(tmpdir(), "ds-chaterr-tour-"));
const home = join(app, "OpenDesign", "UserData");
mkdirSync(join(home, ".nanobot"), { recursive: true });
mkdirSync(join(home, ".openDesign"), { recursive: true });
const prep = spawnSync(PY, ["-c", `
import json, sys; sys.path.insert(0, ${JSON.stringify(join(PKG, "ds", "bin"))})
import ds_credential
cfg = ds_credential.load_jsonc(${JSON.stringify(join(PKG, "ds", "config", "nanobot.config.windows.jsonc"))})
cfg["providers"]["custom"]["apiBase"] = ${JSON.stringify(vendorBase)}
ws = cfg.setdefault("channels", {}).setdefault("websocket", {})
ws.update(enabled=True, host="127.0.0.1", token="tour-kouling", websocketRequiresToken=True, allowFrom=["*"])
json.dump(cfg, open(${JSON.stringify(join(home, ".nanobot", "config.json"))}, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
`], { encoding: "utf-8" });
if (prep.status !== 0) { console.error(prep.stderr); process.exit(1); }
writeFileSync(join(home, ".openDesign", "key.txt"), "tp-qa-tour-mimo-0123456789\n");

const dead = "http://127.0.0.1:9";
const host = spawn(PY, [join(PKG, "ds", "bin", "ds_host.py")], {
  env: { ...process.env, LOCALAPPDATA: app, PYTHONIOENCODING: "utf-8",
         HTTP_PROXY: dead, HTTPS_PROXY: dead, http_proxy: dead, https_proxy: dead,
         NO_PROXY: "127.0.0.1,localhost", no_proxy: "127.0.0.1,localhost" },
  stdio: ["pipe", "pipe", "inherit"],
});
const first = await new Promise((r) => host.stdout.once("data", (b) => r(String(b))));
const web = JSON.parse(first.split("\n")[0]).web_port;
const base = `http://127.0.0.1:${web}`;

const OUT = HERE;
const lines = ["# QA 执行 · 真界面操作录像(track opendesign-chat-error-visible)", "",
  `台面:真管家 + 真网关 + 真工作台 + 真 chromium;包 = 本机按出货形状摆的一份(${process.env.TOUR_PKG_FROM || "ds 来自哪次提交:未注明"})。`,
  "主槽 MiMo 指到本机假厂商,回法按步骤切换(报错体 = 探针里的真厂商原文)。每步:截图 NN.jpg + 页面文字 + 当时的事实。", ""];
let n = 0;
const pane = ".home-pane";
const browser = await launchBrowser();
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
const consoleErr = [];
page.on("pageerror", (e) => consoleErr.push(String(e)));

async function step(title, facts = {}) {
  n += 1;
  const nn = String(n).padStart(2, "0");
  await page.screenshot({ path: join(OUT, `${nn}.jpg`), type: "jpeg", quality: 60 });
  const text = (await page.locator("body").innerText().catch(() => "")).replace(/\n{2,}/g, "\n").slice(0, 1800);
  lines.push(`## ${nn}. ${title}`, "", `截图:${nn}.jpg`, "");
  for (const [k, v] of Object.entries(facts)) lines.push(`- ${k}:${typeof v === "string" ? v : JSON.stringify(v)}`);
  lines.push("", "页面文字(截取):", "```", text, "```", "");
  console.log(`[${nn}] ${title} ${JSON.stringify(facts).slice(0, 300)}`);
}
const bubbles = (scope) => page.locator(`${scope} .msg-ai:not(.thinking)`);
const errs = (scope) => page.locator(`${scope} [data-ui="chat-model-error"]`);
const lastAi = (scope) => bubbles(scope).last().innerText().catch(() => "");
const errTexts = (scope) => errs(scope).allInnerTexts();
async function send(scope, text, timeout = 90000) {
  const before = await bubbles(scope).count();
  await page.locator(`${scope} textarea`).fill(text);
  await waitSendable(page, scope, 30000);
  await page.locator(`${scope} .send-btn`).click();
  const t0 = Date.now();
  while (Date.now() - t0 < timeout) {
    if ((await bubbles(scope).count()) > before &&
        (await page.locator(`${scope} .msg-ai.streaming, ${scope} .msg-ai.thinking`).count()) === 0) break;
    await page.waitForTimeout(300);
  }
  await page.waitForTimeout(600);
  return Date.now() - t0;
}
const sendable = async (scope) => {
  await page.locator(`${scope} textarea`).fill("试一下");
  const ok = await page.locator(`${scope} .send-btn:not([disabled])`).count() > 0;
  await page.locator(`${scope} textarea`).fill("");
  return ok;
};

let failed = null;
try {
  await page.goto(`${base}/#/`, { waitUntil: "domcontentloaded" });
  await page.locator(pane).waitFor({ state: "visible", timeout: 20000 });
  await waitConnected(page, pane, 60000);
  MODE = "ok";
  await send(pane, "你好");
  await step("打开软件,正常聊一句(基线:正常回复没有出错样式)", { 回复: await lastAi(pane), 出错说明条数: await errs(pane).count() });

  MODE = "401";
  const t401 = await send(pane, "帮我看看今天的待办");
  await step("E1 key 不对:发一句", { 等了毫秒: t401, 出错说明: await errTexts(pane), 还能发: await sendable(pane) });

  await page.locator('[data-ui="settings-toggle"]:visible').click();
  await page.waitForTimeout(800);
  await page.locator('[data-ui="settings-toggle"]:visible').click();
  await page.locator(pane).waitFor({ state: "visible", timeout: 8000 });
  await page.waitForTimeout(800);
  await step("E7 打开设置再回来", { 出错说明: await errTexts(pane) });

  await page.locator(".hist-row").first().click();
  await page.waitForTimeout(2500);
  await step("E8/故事B 从侧栏「历史对话」点回这段(走网关回放)", { 出错说明: await errTexts(pane),
    有没有英文原文当正文: (await page.locator(`${pane} .msg-ai:not([data-ui="chat-model-error"])`).allInnerTexts()).some((t) => /Error:|The AI provider/.test(t)) });

  MODE = "quota";
  await send(pane, "额度的情况");
  await step("E2 欠费 / 额度(DeepSeek 402 原文 → 网关换成固定英文)", { 最新出错说明: (await errTexts(pane)).at(-1) });

  MODE = "glmquota";
  await send(pane, "GLM 余额不足的情况");
  await step("E2b 额度(GLM 1113「余额不足」原文透传)", { 最新出错说明: (await errTexts(pane)).at(-1) });

  MODE = "rate";
  await page.locator(`${pane} textarea`).fill("限流的情况");
  await waitSendable(page, pane, 30000);
  const before = await bubbles(pane).count();
  await page.locator(`${pane} .send-btn`).click();
  await page.waitForTimeout(3000);
  await step("E19 限流:网关在自己重试的那几秒(应只有思考动画,不是空白)", { 思考动画: await page.locator(`${pane} .msg-ai.thinking`).count() });
  const t0 = Date.now();
  while (Date.now() - t0 < 60000 && (await bubbles(pane).count()) <= before) await page.waitForTimeout(300);
  await page.waitForTimeout(600);
  await step("E3 限流:重试完之后", { 等了毫秒: Date.now() - t0 + 3000, 最新出错说明: (await errTexts(pane)).at(-1) });

  MODE = "down";
  const tdown = await send(pane, "连不上的情况");
  await step("E4 连不上厂商", { 等了毫秒: tdown, 最新出错说明: (await errTexts(pane)).at(-1) });

  MODE = "500";
  await send(pane, "厂商出错的情况");
  await step("E5 厂商服务器出错", { 最新出错说明: (await errTexts(pane)).at(-1) });

  MODE = "weird";
  await send(pane, "认不出的错");
  await step("E6 认不出的错(invalid_request_error + 图片被拒)", { 最新出错说明: (await errTexts(pane)).at(-1) });

  MODE = "ok";
  const nErr = await errs(pane).count();
  await send(pane, "现在好了吗");
  await step("E9/E12 改好之后再发:正常回复,没有出错样式,出错说明条数不变", { 回复: await lastAi(pane),
    出错说明条数: `${nErr} → ${await errs(pane).count()}` });

  MODE = "401";
  await send(pane, "连发第一句");
  await send(pane, "连发第二句");
  await step("E13 key 错时连发两句:各有一条说明", { 出错说明条数: await errs(pane).count() });

  // E8 打开待办页再回首页(第 1 遍录像没走,QA 判卷 Q4)
  const homeLive = await errTexts(pane);
  await page.goto(`${base}/#/todos`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1200);
  await page.goto(`${base}/#/`, { waitUntil: "domcontentloaded" });
  await page.locator(pane).waitFor({ state: "visible", timeout: 8000 });
  await page.waitForTimeout(800);
  const homeBack = await errTexts(pane);
  await step("E8 打开待办页再回首页", { 出错说明条数: `${homeLive.length} → ${homeBack.length}`,
    逐条相同: JSON.stringify(homeLive) === JSON.stringify(homeBack) });

  // E24 / D6 真重开软件(整页重载)→ 点回首页这段(此时侧栏里它还在;第 1 遍录像在建项目之后才做,点进了待办那段)
  await page.reload({ waitUntil: "domcontentloaded" });
  await waitConnected(page, pane, 60000);
  const histRows = await page.locator(".hist-row").allInnerTexts();
  await page.locator(".hist-row").first().click({ timeout: 15000 });
  await page.waitForFunction((n) => document.querySelectorAll('.home-pane [data-ui="chat-model-error"]').length >= n,
    homeLive.length, { timeout: 20000 }).catch(() => {});
  await page.waitForTimeout(800);
  const homeReplay = await errTexts(pane);
  await step("E24/D6 重开软件,从侧栏点回首页这段(走网关回放):每一类出错说明都与实时逐条相同", {
    侧栏历史: histRows, 出错说明条数: `实时 ${homeLive.length} / 回放 ${homeReplay.length}`,
    逐条相同: JSON.stringify(homeLive) === JSON.stringify(homeReplay),
    有没有英文原文当正文: (await page.locator(`${pane} .msg-ai:not([data-ui="chat-model-error"])`).allInnerTexts()).some((t) => /Error:|The AI provider/.test(t)) });

  // E10 项目助手栏:当场 + 首页不冒出 + 切走再回来
  MODE = "401";
  const cr = await fetch(`${base}/api/projects/create`, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project: "翡翠湾-1801" }) });
  if (!cr.ok) throw new Error(`夹具:建项目失败 HTTP ${cr.status} ${await cr.text()}`);
  // 只改 # 是同一页内跳转,不重新拉项目列表 ⇒ 真重载
  await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
  await page.reload({ waitUntil: "domcontentloaded" });
  const proj = page.locator(".proj-row", { hasText: "翡翠湾-1801" }).first();
  await proj.click({ timeout: 20000 });
  await waitConnected(page, ".chatcol", 60000);
  const homeBefore = await errs(pane).count();
  await send(".chatcol", "这个项目的进度");
  const projLive = await errTexts(".chatcol");
  await step("E10 项目助手栏里出错(首页那栏不许跟着冒)", { 项目栏出错说明: projLive,
    首页出错条数: `${homeBefore} → ${await errs(pane).count()}` });
  await page.goto(`${base}/#/todos`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1200);
  await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
  await proj.click({ timeout: 20000 });
  await page.waitForTimeout(2500);
  const projBack = await errTexts(".chatcol");
  await step("E10b 项目栏:去待办页再回来、点回这个项目", { 出错说明条数: `${projLive.length} → ${projBack.length}`,
    逐条相同: JSON.stringify(projLive) === JSON.stringify(projBack) });

  // E11 待办页助手栏:右栏是单行「问一句」框 + 发送键,发出后展开成完整聊天
  await page.goto(`${base}/#/todos`, { waitUntil: "domcontentloaded" });
  const railChat = '[data-ui="rail-chat"]';
  await page.locator('[data-ui="rail-ask"]').fill("帮我排一下待办");
  await page.locator('[data-ui="rail-send"]').click();
  await page.locator(`${railChat} [data-ui="chat-model-error"]`).first().waitFor({ timeout: 60000 });
  await page.waitForTimeout(600);
  const railLive = await errTexts(railChat);
  await step("E11 待办页助手栏里出错", { 待办栏出错说明: railLive });
  await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1200);
  await page.goto(`${base}/#/todos`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1200);
  const railBack = await errTexts(railChat);
  await step("E11b 待办栏:去工作区再回待办页", { 出错说明条数: `${railLive.length} → ${railBack.length}`,
    逐条相同: JSON.stringify(railLive) === JSON.stringify(railBack),
    对话还展开着: await page.locator(`${railChat}:not(.route-hidden)`).count() > 0 });

  // E21 设置页:给未启用的一家存 key,看提示
  await page.locator('[data-ui="settings-toggle"]:visible').click();
  await page.locator('[data-ui="settings-nav-models"]').click();
  await page.locator('[data-ui="ms-nav-item"][data-provider="kimi"]').click();
  await page.locator('[data-ui="ms-detail"][data-provider="kimi"]').waitFor({ timeout: 8000 });
  const sw = page.locator('[data-ui="ms-enable"]:visible');
  if ((await sw.getAttribute("aria-checked")) === "true") { await sw.click(); await page.waitForTimeout(800); }
  await page.locator('[data-ui="ms-key"]:visible').fill("sk-qa-tour-kimi-0123456789");
  await page.locator('[data-ui="ms-key-save"]:visible').click();
  await page.locator('[data-ui="ms-notice"]:visible').waitFor({ timeout: 8000 }).catch(() => {});
  await page.waitForTimeout(800);
  await step("E21 给「未启用」的 Kimi 存 key:提示的叫法", {
    提示: await page.locator('[data-ui="ms-notice"]:visible').innerText().catch(() => "(没有提示)"),
    开关旁的字: await page.locator(".ms-switch-wrap .ms-muted:visible").innerText().catch(() => "") });
} catch (e) {
  failed = e;
  lines.push("## 中断", "", "```", String(e?.stack || e), "```");
  try { await step("中断时的画面"); } catch { /* 截不了 */ }
}
lines.push("## 假厂商收到的请求(按模式计数)", "", "```",
  JSON.stringify(hits.reduce((a, h) => ({ ...a, [h.mode]: (a[h.mode] || 0) + 1 }), {})), "```", "");
lines.push("## 页面级 JS 报错", "", consoleErr.length ? consoleErr.map((x) => `- ${x}`).join("\n") : "无", "");
writeFileSync(join(OUT, "tour.md"), lines.join("\n"));
await browser.close();
try { host.stdin.write('{"cmd":"quit"}\n'); } catch { /* 已经没了 */ }
await new Promise((r) => setTimeout(r, 3000));
try { host.kill("SIGKILL"); } catch { /* 已经没了 */ }
vendor.close();
rmSync(app, { recursive: true, force: true });
if (failed) { console.error(failed); process.exit(1); }
console.log(`录完 ${n} 步 → ${join(OUT, "tour.md")}`);
process.exit(0);
