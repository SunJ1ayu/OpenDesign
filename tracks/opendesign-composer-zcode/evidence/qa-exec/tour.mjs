// QA 执行的「真界面操作录像」(track opendesign-composer-zcode):主 agent 在**真管家 + 真网关 + 真工作台 + 真 chromium** 上
// 按七家 QA 设计的 P0 把输入框五条走一遍,每一步留截图 + 页面文字 + 当时的事实。**不是判据**,不进 run-all。
// 补的是判据够不着的:e2e 的网关是替身,这里是真 nanobot 网关收 `/stop`、真掐断厂商的流、真回放。
//
// 台面(照 opendesign-chat-error-visible 的 tour.mjs):本机按出货形状摆一份(<包>/ds = 仓库某次提交的 git archive bin config web/dist;
// <包>/python/python.exe = 包一层 venv python 的小脚本)。主槽 MiMo 的 apiBase 指到本机假厂商;回法由本脚本现场切换(MODE)。
// 零外网:导入 tests/e2e/helpers.mjs 即进无出口网络命名空间;代理变量另指向没人听的端口。
//
// 跑法(仓根):node tracks/opendesign-composer-zcode/evidence/qa-exec/tour.mjs <包目录>
import { spawn, spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync, rmSync, mkdtempSync, readFileSync, existsSync, readdirSync } from "node:fs";
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

// ── 假厂商:ok = 一句话;slow = 60 段、每段 0.3 秒(约 18 秒说完);think = 先想 8 秒再慢慢说;
//    quota / glmquota = 探针里的真厂商欠费原文(看 Q3′ 的小字标签)
let MODE = "ok";
const BODIES = {
  quota: [402, { error: { message: "Insufficient Balance", type: "unknown_error", param: null, code: "invalid_request_error" } }],
  glmquota: [429, { error: { code: "1113", message: "余额不足或无可用资源包,请充值。" } }],
};
const hits = [];
const vendor = createServer((req, res) => {
  let raw = "";
  req.on("data", (b) => { raw += b; });
  req.on("end", () => {
    let body = {};
    try { body = JSON.parse(raw || "{}"); } catch { /* 坏包 */ }
    const hit = { mode: MODE, path: req.url, at: Date.now(), sent: 0, cutByClient: false };
    hits.push(hit);
    if (BODIES[MODE]) {
      const [code, b] = BODIES[MODE];
      res.writeHead(code, { "Content-Type": "application/json" });
      res.end(JSON.stringify(b));
      return;
    }
    const now = Math.floor(Date.now() / 1000);
    const chunk = (delta, fin = null) => `data: ${JSON.stringify({ id: "x", object: "chat.completion.chunk", created: now,
      model: body.model, choices: [{ index: 0, delta, finish_reason: fin }] })}\n\n`;
    const slow = MODE === "slow" || MODE === "think";
    const parts = slow ? Array.from({ length: 60 }, (_, i) => `第${i}段。`) : ["我是 MiMo,正常回复。"];
    if (!body.stream) {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ id: "x", object: "chat.completion", created: now, model: body.model,
        choices: [{ index: 0, finish_reason: "stop", message: { role: "assistant", content: parts.join("") } }],
        usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 } }));
      return;
    }
    res.writeHead(200, { "Content-Type": "text/event-stream" });
    res.on("close", () => { if (!res.writableEnded) hit.cutByClient = true; });
    let i = 0;
    const tick = () => {
      if (res.destroyed) return;
      if (i >= parts.length) { res.write(chunk({}, "stop")); res.end("data: [DONE]\n\n"); return; }
      res.write(chunk(i === 0 ? { role: "assistant", content: parts[i] } : { content: parts[i] }));
      hit.sent = ++i;
      setTimeout(tick, slow ? 300 : 0);
    };
    setTimeout(tick, MODE === "think" ? 8000 : 0);
  });
});
await new Promise((r) => vendor.listen(0, "127.0.0.1", r));
const vendorBase = `http://127.0.0.1:${vendor.address().port}/v1`;

// ── 业主的机器:数据目录 + 配置 + MiMo 一把 key;另存一把 Kimi、加一家名字又长又带括号的自定义供应商(看按钮上的厂商名)──
const app = mkdtempSync(join(tmpdir(), "ds-composer-tour-"));
const home = join(app, "OpenDesign", "UserData");
mkdirSync(join(home, ".nanobot"), { recursive: true });
mkdirSync(join(home, ".openDesign"), { recursive: true });
const cfgPath = join(home, ".nanobot", "config.json");
// 先放 MiMo 的 key:加自定义供应商要求先有一把内置厂商的 key(产品规矩 NEED_BUILTIN_KEY)
writeFileSync(join(home, ".openDesign", "key.txt"), "tp-qa-tour-mimo-0123456789\n");
const prep = spawnSync(PY, ["-c", `
import json, sys; sys.path.insert(0, ${JSON.stringify(join(PKG, "ds", "bin"))})
import ds_credential
cfg = ds_credential.load_jsonc(${JSON.stringify(join(PKG, "ds", "config", "nanobot.config.windows.jsonc"))})
cfg["providers"]["custom"]["apiBase"] = ${JSON.stringify(vendorBase)}
ws = cfg.setdefault("channels", {}).setdefault("websocket", {})
ws.update(enabled=True, host="127.0.0.1", token="tour-kouling", websocketRequiresToken=True, allowFrom=["*"])
json.dump(cfg, open(${JSON.stringify(cfgPath)}, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
pid = ds_credential.add_custom_provider(${JSON.stringify(home)}, ${JSON.stringify(cfgPath)}, label="王工工作室(备用中转)线路",
    api_base=${JSON.stringify(vendorBase.replace("/v1", "/relay/v1"))}, models=["relay-chat-v1"], key="sk-qa-tour-relay-0123456789", multi=True)
print("custom provider:", pid)
`], { encoding: "utf-8" });
if (prep.status !== 0) { console.error(prep.stderr); process.exit(1); }

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
const lines = ["# QA 执行 · 真界面操作录像(track opendesign-composer-zcode)", "",
  `台面:真管家 + 真网关 + 真工作台 + 真 chromium;包 = 本机按出货形状摆的一份(${process.env.TOUR_PKG_FROM || "ds 来自哪次提交:未注明"})。`,
  "主槽 MiMo 指到本机假厂商,回法按步骤切换(slow = 60 段每段 0.3 秒;think = 先想 8 秒)。每步:截图 NN.jpg + 页面文字 + 当时的事实。",
  "读屏文字不含悬停提示与图标;需要时事实里另记 aria-label / title。", ""];
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
const ta = (scope) => page.locator(`${scope} textarea`);
const bubbles = (scope) => page.locator(`${scope} .msg-ai:not(.thinking)`);
const notes = (scope) => page.locator(`${scope} [data-ui="chat-system-note"]`).allInnerTexts();
const userBubbles = (scope) => page.locator(`${scope} .msg-user`).allInnerTexts();
const btnState = async (scope) => ({
  发送键: await page.locator(`${scope} .send-btn`).count(),
  停止键: await page.locator(`${scope} .stop-btn`).count(),
  输入框可用: !(await ta(scope).isDisabled().catch(() => true)),
});
async function sendAndWait(scope, text, timeout = 90000) {
  await ta(scope).fill(text);
  await waitSendable(page, scope, 30000);
  await page.locator(`${scope} .send-btn`).click();
  const t0 = Date.now();
  await page.locator(`${scope} .stop-btn`).waitFor({ timeout: 5000 }).catch(() => {});
  while (Date.now() - t0 < timeout && (await page.locator(`${scope} .stop-btn`).count()) > 0) await page.waitForTimeout(300);
  await page.waitForTimeout(600);
  return Date.now() - t0;
}
async function sendNoWait(scope, text) {
  await ta(scope).fill(text);
  await waitSendable(page, scope, 30000);
  await page.locator(`${scope} .send-btn`).click();
  await page.locator(`${scope} .stop-btn`).waitFor({ timeout: 5000 });
}
async function clickStopAndTime(scope) {
  const t0 = Date.now();
  await page.locator(`${scope} .stop-btn`).click();
  while (Date.now() - t0 < 15000 && (await page.locator(`${scope} .send-btn`).count()) === 0) await page.waitForTimeout(100);
  return Date.now() - t0;
}

let failed = null;
try {
  await page.goto(`${base}/#/`, { waitUntil: "domcontentloaded" });
  await page.locator(pane).waitFor({ state: "visible", timeout: 20000 });
  await waitConnected(page, pane, 60000);
  const chip = page.locator(`${pane} [data-ui="chat-model"]`);
  await page.waitForFunction(() => /·/.test(document.querySelector('.home-pane [data-ui="chat-model"]')?.textContent || ""),
    null, { timeout: 15000 }).catch(() => {});
  await step("打开软件的首页(问候语按本机时间;占位字;输入框下面那一排)", {
    本机时间: new Date().toLocaleTimeString("zh-CN"), 问候语: await page.locator(`${pane} .home-greet`).innerText(),
    占位字: await ta(pane).getAttribute("placeholder"), 模型按钮: await chip.innerText(), 模型按钮悬停: await chip.getAttribute("title"),
    发送键读屏名: await page.locator(`${pane} .send-btn`).getAttribute("aria-label"),
    "模型接口原样(/api/llm/models 的 provider/label/current)": await page.evaluate(async () => {
      const r = await (await fetch("/api/llm/models")).json();
      return { provider: r.provider, label: r.label, current: r.current, groups: (r.groups || []).map((g) => g.provider) };
    }),
    说明: "录像台子把主槽的地址改指到本机假厂商,后台按地址认不出是 MiMo ⇒ provider 为空 ⇒ 按钮按设计退回只写模型名;业主机器上地址是真的" });

  await page.locator(`${pane} [data-ui="composer-plus"]`).click();
  await page.waitForTimeout(300);
  await step("点「+」", { 菜单项: await page.locator(`${pane} [data-ui="composer-menu"] [role="menuitem"]`).allInnerTexts() });
  await page.keyboard.press("Escape");

  await ta(pane).fill("客厅墙面改成暖灰");
  await page.locator(`${pane} [data-ui="composer-plus"]`).click();
  await page.locator(`${pane} [data-ui="composer-menu"] [role="menuitem"]`, { hasText: "记一下" }).click();
  await page.waitForTimeout(300);
  await step("先打了「客厅墙面改成暖灰」,再「+」→「记一下」", { 输入框: await ta(pane).inputValue(),
    光标位置: await ta(pane).evaluate((el) => `${el.selectionStart}/${el.value.length}`) });
  await page.locator(`${pane} [data-ui="composer-plus"]`).click();
  await page.locator(`${pane} [data-ui="composer-menu"] [role="menuitem"]`, { hasText: "找参考图" }).click();
  await page.waitForTimeout(300);
  await step("接着「+」→「找参考图」(换开头,不叠两个)", { 输入框: await ta(pane).inputValue() });

  await ta(pane).fill("");
  await ta(pane).type("/");
  await page.waitForTimeout(300);
  await step("清空后打 /", { 技能表: await page.locator(`${pane} [data-ui="slash-menu"] [role="option"]`).allInnerTexts() });
  await ta(pane).type("账本");
  await page.waitForTimeout(300);
  await step("接着打「账本」(按关键词筛)", { 技能表: await page.locator(`${pane} [data-ui="slash-menu"] [role="option"]`).allInnerTexts() });
  await ta(pane).press("Enter");
  await page.waitForTimeout(300);
  await step("按 Enter", { 输入框: await ta(pane).inputValue(), 技能表还在: await page.locator(`${pane} [data-ui="slash-menu"]`).count() });
  await ta(pane).fill("");
  await ta(pane).type("、");
  await page.waitForTimeout(300);
  await step("清空后打「、」(中文标点模式下按 / 键打出来的就是它)", {
    技能表: await page.locator(`${pane} [data-ui="slash-menu"] [role="option"]`).allInnerTexts() });
  await ta(pane).press("Escape");
  await page.waitForTimeout(200);
  await step("按 Esc", { 输入框: await ta(pane).inputValue(), 技能表还在: await page.locator(`${pane} [data-ui="slash-menu"]`).count() });
  await ta(pane).fill("");

  // ── 停止:真网关收 /stop ──
  MODE = "slow";
  await sendNoWait(pane, "讲个长故事");
  await page.waitForFunction(() => /第3段/.test(document.querySelector(".home-pane .msg-ai.streaming")?.textContent || ""), null, { timeout: 30000 });
  await step("回复中(假厂商慢慢吐字):输入框下面那颗键", { ...(await btnState(pane)),
    停止键读屏名: await page.locator(`${pane} .stop-btn`).getAttribute("aria-label") });
  const hitSlow = hits.at(-1);
  const tStop = await clickStopAndTime(pane);
  await page.waitForTimeout(1500);
  await step("点 ■ 停止", { "从点下到 ↑ 回来毫秒": tStop, ...(await btnState(pane)), 系统小字: await notes(pane),
    用户气泡: await userBubbles(pane), 最后一条回答: await bubbles(pane).last().innerText().catch(() => ""),
    假厂商那边: `送出 ${hitSlow.sent}/60 段,被网关掐断: ${hitSlow.cutByClient}` });
  const sentAtStop = hitSlow.sent;
  await page.waitForTimeout(3000);
  await step("停下 3 秒后(确认真的不再出字)", { 假厂商又送了几段: hitSlow.sent - sentAtStop,
    最后一条回答: await bubbles(pane).last().innerText().catch(() => "") });

  MODE = "ok";
  const tAgain = await sendAndWait(pane, "还在吗");
  await step("停完马上再发一句", { 等了毫秒: tAgain, 最后一条回答: await bubbles(pane).last().innerText().catch(() => ""), ...(await btnState(pane)) });

  MODE = "think";
  await sendNoWait(pane, "想一想再说");
  await page.waitForTimeout(2000);
  await step("还在「正在思考」、一个字都没出", { ...(await btnState(pane)), 思考动画: await page.locator(`${pane} .msg-ai.thinking`).count() });
  const tThinkStop = await clickStopAndTime(pane);
  await page.waitForTimeout(1500);
  await step("这时点 ■", { "从点下到 ↑ 回来毫秒": tThinkStop, ...(await btnState(pane)), 系统小字: await notes(pane),
    思考动画: await page.locator(`${pane} .msg-ai.thinking`).count(), 助手气泡数: await bubbles(pane).count() });

  // ── 三栏:首页在说,项目助手也在说,只停项目栏 ──
  const cr = await fetch(`${base}/api/projects/create`, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project: "翡翠湾-1801" }) });
  if (!cr.ok) throw new Error(`夹具:建项目失败 HTTP ${cr.status} ${await cr.text()}`);
  MODE = "slow";
  await sendNoWait(pane, "首页这边讲个长故事");
  const homeHit = hits.at(-1);
  await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
  await page.reload({ waitUntil: "domcontentloaded" });
  const proj = page.locator(".proj-row", { hasText: "翡翠湾-1801" }).first();
  await proj.click({ timeout: 20000 });
  await waitConnected(page, ".chatcol", 60000);
  await step("项目页右栏(窄):输入框下面那一排", { 模型按钮: await page.locator('.chatcol [data-ui="chat-model"]').innerText(),
    发送键在: await page.locator(".chatcol .send-btn").count() });
  // 重载会断掉首页那一轮 —— 首页那条要在重载之后另起
  MODE = "slow";
  await sendNoWait(".chatcol", "项目这边也讲一个");
  const projHit = hits.at(-1);
  await page.waitForTimeout(2000);
  await step("项目栏在回复", { ...(await btnState(".chatcol")) });
  const tProjStop = await clickStopAndTime(".chatcol");
  await page.waitForTimeout(1000);
  await step("只停项目栏", { "从点下到 ↑ 回来毫秒": tProjStop, 项目栏: await btnState(".chatcol"), 项目栏小字: await notes(".chatcol"),
    项目栏那一路被掐断: projHit.cutByClient, "首页那一路(重载前起的)":`送出 ${homeHit.sent}/60,被掐断 ${homeHit.cutByClient}` });

  await page.goto(`${base}/#/`, { waitUntil: "domcontentloaded" });
  await page.locator(pane).waitFor({ state: "visible", timeout: 8000 });
  await waitConnected(page, pane, 60000);
  await sendNoWait(pane, "首页再讲一个长的");
  const homeHit2 = hits.at(-1);
  await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
  await page.locator(".chatcol").waitFor({ state: "visible", timeout: 8000 });
  await sendNoWait(".chatcol", "项目这边再讲一个");
  const projHit2 = hits.at(-1);
  await page.waitForTimeout(1500);
  await clickStopAndTime(".chatcol");
  const homeSentAtProjStop = homeHit2.sent;
  await page.waitForTimeout(3000);
  await page.goto(`${base}/#/`, { waitUntil: "domcontentloaded" });
  await page.locator(pane).waitFor({ state: "visible", timeout: 8000 });
  await step("两栏同时在说,只停项目栏,切回首页(不重载)", { 首页: await btnState(pane),
    首页那一路: `停项目栏时送出 ${homeSentAtProjStop}/60,3 秒后 ${homeHit2.sent}/60,被掐断 ${homeHit2.cutByClient}`,
    项目栏那一路被掐断: projHit2.cutByClient });
  const t1 = Date.now();
  while (Date.now() - t1 < 30000 && (await page.locator(`${pane} .stop-btn`).count()) > 0) await page.waitForTimeout(300);
  await step("首页那一条自己说完", { ...(await btnState(pane)), 最后一条回答结尾: (await bubbles(pane).last().innerText().catch(() => "")).slice(-20) });

  // ── 重开软件,从侧栏点回第一段(停过两次的那段)──
  const liveNotes = await notes(pane);
  await page.reload({ waitUntil: "domcontentloaded" });
  await waitConnected(page, pane, 60000);
  const histRows = await page.locator(".hist-row").allInnerTexts();
  await step("重开软件后的侧栏历史", { 侧栏历史: histRows });
  const row = page.locator(".hist-row", { hasText: "讲个长故事" }).first();
  if (await row.count()) {
    await row.click();
    await page.waitForTimeout(3000);
    await step("点回「讲个长故事」那段(走网关回放)", { 系统小字: await notes(pane), 实时时的系统小字: liveNotes,
      有没有英文系统句: (await page.locator(`${pane} .msg-ai`).allInnerTexts()).some((t) => /Stopped|No active task/.test(t)),
      用户气泡: await userBubbles(pane) });
  } else {
    await step("侧栏里没有「讲个长故事」那段(被新对话挤出了 —— 第 3 件侧栏要解决的)", { 侧栏历史: histRows });
  }

  // ── Q3′:出错小字的标签 ──
  MODE = "quota";
  await sendAndWait(pane, "欠费的情况");
  MODE = "glmquota";
  await sendAndWait(pane, "GLM 余额不足的情况");
  await step("两种欠费:网关改写过的(DeepSeek 402)与厂商原话(GLM 1113)", {
    小字: await page.locator(`${pane} [data-ui="chat-model-error-raw"]`).allInnerTexts() });
  MODE = "ok";

  // ── 模型按钮(放在最后:台子里主槽认不出是 MiMo,换走就换不回来):Kimi(设置页存 key、打开启用)→ 自己加的长名字供应商 ──
  await page.locator('[data-ui="settings-toggle"]:visible').click();
  await page.locator('[data-ui="settings-nav-models"]').click();
  await page.locator('[data-ui="ms-nav-item"][data-provider="kimi"]').click();
  await page.locator('[data-ui="ms-detail"][data-provider="kimi"]').waitFor({ timeout: 8000 });
  await page.locator('[data-ui="ms-key"]:visible').fill("sk-qa-tour-kimi-0123456789");
  await page.locator('[data-ui="ms-key-save"]:visible').click();
  await page.waitForTimeout(1500);
  const sw = page.locator('[data-ui="ms-enable"]:visible');
  if ((await sw.getAttribute("aria-checked")) !== "true") { await sw.click(); await page.waitForTimeout(1500); }
  await page.locator('[data-ui="settings-toggle"]:visible').click();
  await page.locator(pane).waitFor({ state: "visible", timeout: 8000 });
  await chip.click();
  await page.locator(`${pane} [data-ui="chat-model-menu"]`).waitFor({ timeout: 5000 });
  const kimiRow = page.locator(`${pane} [data-ui="chat-model-menu"] .item`, { hasText: "Kimi" }).first();
  await kimiRow.hover();
  await page.waitForTimeout(500);
  await step("打开模型菜单,指到 Kimi 按量", { 菜单: await page.locator(`${pane} [data-ui="chat-model-menu"]`).innerText() });
  const sub = page.locator('[data-ui="chat-model-sub"] .item').first();
  if (await sub.count()) await sub.click(); else await kimiRow.click();
  await page.waitForTimeout(1500);
  await step("换成 Kimi 的一个模型", { 模型按钮: await chip.innerText(), 模型按钮悬停: await chip.getAttribute("title") });
  await chip.click();
  const relayRow = page.locator(`${pane} [data-ui="chat-model-menu"] .item`, { hasText: "王工" }).first();
  await relayRow.hover();
  await page.waitForTimeout(500);
  await page.locator('[data-ui="chat-model-sub"] .item').first().click();
  await page.waitForTimeout(1500);
  await step("换成自己加的供应商「王工工作室(备用中转)线路」(名字长、带括号)", { 模型按钮: await chip.innerText(),
    模型按钮悬停: await chip.getAttribute("title") });
  await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
  await page.locator(".proj-row", { hasText: "翡翠湾-1801" }).first().click({ timeout: 20000 });
  await waitConnected(page, ".chatcol", 60000);
  await page.waitForTimeout(1000);
  const card = await page.locator(".chatcol .chat-card").boundingBox();
  const up = await page.locator(".chatcol .send-btn").boundingBox();
  await step("项目页右栏(窄)里,长名字的模型按钮", { 模型按钮: await page.locator('.chatcol [data-ui="chat-model"]').innerText(),
    "↑ 整个在卡里": !!(card && up && up.x + up.width <= card.x + card.width + 0.5) });
  MODE = "ok";
  const tRelay = await sendAndWait(".chatcol", "用这家说一句");
  await step("用这家发一句", { 等了毫秒: tRelay, 最后一条回答: await bubbles(".chatcol").last().innerText().catch(() => "") });

  // ── 待办小框、技能页 ──
  await page.goto(`${base}/#/todos`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1500);
  await step("待办页右边的小输入框(这单不动它)", { 占位字: await page.locator('[data-ui="rail-ask"]').getAttribute("placeholder").catch(() => "(没找到)"),
    发送键: await page.locator('[data-ui="rail-send"]').innerText().catch(() => "(没找到)") });
  await page.goto(`${base}/#/skills`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1000);
  await step("技能页", { 卡片: await page.locator(".skill-card .nm").allInnerTexts() });
  await page.locator(".skill-card", { hasText: "找参考图" }).click();
  await page.waitForTimeout(1500);
  await step("点「找参考图」卡片", { 首页输入框: await ta(pane).inputValue().catch(() => "") });
} catch (e) {
  failed = e;
  lines.push("## 中断", "", "```", String(e?.stack || e), "```");
  try { await step("中断时的画面"); } catch { /* 截不了 */ }
}
lines.push("## 假厂商收到的请求", "", "```",
  JSON.stringify(hits.map((h) => ({ mode: h.mode, sent: h.sent, cut: h.cutByClient }))), "```", "");
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
