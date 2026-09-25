// QA 执行的「真界面操作录像」(track opendesign-key-restart):主 agent 在**真管家 + 真网关 + 真工作台 + 真 chromium** 上
// 把业主的操作走一遍,每一步留截图 + 页面文字 + 当时的事实(网关 PID、厂商收到的 key 末几位)。**不是判据**,不进 run-all。
// 补的是两家 QA 判卷同指的缺口:云 Windows probe-5 直调接口、没开浏览器;e2e 的聊天是替身 —— 真界面 + 真后台没人亲眼看过。
//
// 台面:本机按出货包形状摆一份(<包>/ds 是仓库某次提交的 git archive,<包>/python/python.exe 是包一层 venv python 的小脚本,
// 让子进程也带上探针的 sitecustomize:把目录里 MiMo / DeepSeek 的端点改到本机假厂商)。两家假厂商只认对的 key,别的回 401;
// 用户消息里带「慢慢」时 MiMo 分 6 段、每段隔 1.5 秒流式回。零外网:代理变量指向没人听的端口。
//
// 跑法(仓根):node tracks/opendesign-key-restart/evidence/qa-exec/tour.mjs <包目录>
import { spawn, spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync, rmSync } from "node:fs";
import { createServer } from "node:http";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import { mkdtempSync } from "node:fs";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..", "..", "..");
const { launchBrowser, waitConnected, waitSendable } = await import(join(ROOT, "tests", "e2e", "helpers.mjs"));
const PKG = process.argv[2];
if (!PKG) { console.error("用法:tour.mjs <包目录>"); process.exit(2); }
const PY = join(PKG, "python", "python.exe");
const K1 = "tp-tour-mimo-one-0123456789", K2 = "tp-tour-mimo-two-9876543210", WRONG = "tp-tour-mimo-WRONG-000000000";
const DS_KEY = "sk-tour-deepseek-0123456789ab";

// ── 两家假厂商 ──
function fakeVendor(name, accept) {
  const hits = [];
  const srv = createServer((req, res) => {
    let raw = "";
    req.on("data", (b) => { raw += b; });
    req.on("end", async () => {
      let body = {};
      try { body = JSON.parse(raw || "{}"); } catch { /* 坏包 */ }
      const auth = req.headers.authorization || "";
      hits.push({ auth: auth.slice(-6), model: body.model, at: Date.now() });
      if (!accept.some((k) => auth === `Bearer ${k}`)) {
        res.writeHead(401, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: { message: "Invalid API key", type: "invalid_request_error" } }));
        return;
      }
      const last = [...(body.messages || [])].reverse().find((m) => m.role === "user");
      const lastText = typeof last?.content === "string" ? last.content : JSON.stringify(last?.content ?? "");
      const slow = lastText.includes("慢慢");
      const parts = slow ? [`我是${name},`, "这是一段", "慢慢写出来的", "回复,", "一共六段,", "写完了。"] : [`我是${name}。`];
      const now = Math.floor(Date.now() / 1000);
      if (body.stream) {
        res.writeHead(200, { "Content-Type": "text/event-stream" });
        for (const [i, p] of parts.entries()) {
          if (slow && i) await new Promise((r) => setTimeout(r, 1500));
          res.write(`data: ${JSON.stringify({ id: "x", object: "chat.completion.chunk", created: now, model: body.model,
            choices: [{ index: 0, delta: i ? { content: p } : { role: "assistant", content: p }, finish_reason: null }] })}\n\n`);
        }
        res.write(`data: ${JSON.stringify({ id: "x", object: "chat.completion.chunk", created: now, model: body.model,
          choices: [{ index: 0, delta: {}, finish_reason: "stop" }] })}\n\n`);
        res.end("data: [DONE]\n\n");
        return;
      }
      if (slow) await new Promise((r) => setTimeout(r, 7500));
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ id: "x", object: "chat.completion", created: now, model: body.model,
        choices: [{ index: 0, finish_reason: "stop", message: { role: "assistant", content: parts.join("") } }],
        usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 } }));
    });
  });
  return new Promise((r) => srv.listen(0, "127.0.0.1", () =>
    r({ name, hits, srv, base: `http://127.0.0.1:${srv.address().port}/v1` })));
}
const mimo = await fakeVendor("MiMo", [K1, K2]);
const ds = await fakeVendor("DeepSeek", [DS_KEY]);

// ── 业主的机器:数据目录 + 配置 + 第一把 key ──
const app = mkdtempSync(join(tmpdir(), "ds-key-tour-"));
const home = join(app, "OpenDesign", "UserData");
mkdirSync(join(home, ".nanobot"), { recursive: true });
mkdirSync(join(home, ".openDesign"), { recursive: true });
const prep = spawnSync(PY, ["-c", `
import json, sys; sys.path.insert(0, ${JSON.stringify(join(PKG, "ds", "bin"))})
import ds_credential
cfg = ds_credential.load_jsonc(${JSON.stringify(join(PKG, "ds", "config", "nanobot.config.windows.jsonc"))})
cfg["providers"]["custom"]["apiBase"] = ${JSON.stringify(mimo.base)}
ws = cfg.setdefault("channels", {}).setdefault("websocket", {})
ws.update(enabled=True, host="127.0.0.1", token="tour-kouling", websocketRequiresToken=True, allowFrom=["*"])
json.dump(cfg, open(${JSON.stringify(join(home, ".nanobot", "config.json"))}, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
`], { encoding: "utf-8" });
if (prep.status !== 0) { console.error(prep.stderr); process.exit(1); }
writeFileSync(join(home, ".openDesign", "key.txt"), K1 + "\n");

const dead = "http://127.0.0.1:9";
const host = spawn(PY, [join(PKG, "ds", "bin", "ds_host.py")], {
  env: { ...process.env, LOCALAPPDATA: app, PYTHONIOENCODING: "utf-8",
         PROBE_VENDOR_BASES: JSON.stringify({ mimo: mimo.base, deepseek: ds.base }),
         HTTP_PROXY: dead, HTTPS_PROXY: dead, http_proxy: dead, https_proxy: dead,
         NO_PROXY: "127.0.0.1,localhost", no_proxy: "127.0.0.1,localhost" },
  stdio: ["pipe", "pipe", "inherit"],
});
const first = await new Promise((r) => host.stdout.once("data", (b) => r(String(b))));
const web = JSON.parse(first.split("\n")[0]).web_port;
const base = `http://127.0.0.1:${web}`;
const wsPort = JSON.parse(spawnSync("cat", [join(home, ".nanobot", "config.json")], { encoding: "utf-8" }).stdout).channels.websocket.port;
const gwPid = () => (spawnSync("ss", ["-ltnpH", `sport = :${wsPort}`], { encoding: "utf-8" }).stdout.match(/pid=(\d+)/) || [])[1] || null;

const OUT = HERE;
const lines = ["# QA 执行 · 真界面操作录像(track opendesign-key-restart)", "",
  `台面:真管家 + 真网关(经 ds_gateway.py)+ 真工作台 + 真 chromium;包 = ${PKG}(见同目录 README)。每步:截图 NN.jpg + 页面文字 + 当时的事实。`, ""];
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
  const text = (await page.locator("body").innerText().catch(() => "")).replace(/\n{2,}/g, "\n").slice(0, 1500);
  lines.push(`## ${nn}. ${title}`, "", `截图:${nn}.jpg`, "");
  for (const [k, v] of Object.entries(facts)) lines.push(`- ${k}:${typeof v === "string" ? v : JSON.stringify(v)}`);
  lines.push("", "页面文字(截取):", "```", text, "```", "");
  console.log(`[${nn}] ${title} ${JSON.stringify(facts)}`);
}
const chipText = () => page.locator(`${pane} [data-ui="chat-model"]`).innerText().catch(() => "(没有换模型按钮)");
const lastAi = () => page.locator(`${pane} .msg-ai:not(.thinking)`).last().innerText().catch(() => "");
const aiCount = () => page.locator(`${pane} .msg-ai:not(.thinking)`).count();
const hitsNow = () => ({ MiMo: mimo.hits.map((h) => h.auth), DeepSeek: ds.hits.map((h) => h.auth) });
async function send(text) {
  const before = await aiCount();
  await page.locator(`${pane} textarea`).fill(text);
  await waitSendable(page, pane, 30000);          // 发送键要有字才亮:先填再等
  await page.locator(`${pane} .send-btn`).click();
  const t0 = Date.now();
  while (Date.now() - t0 < 90000) {
    if ((await aiCount()) > before && (await page.locator(`${pane} .msg-ai.streaming, ${pane} .msg-ai.thinking`).count()) === 0) break;
    await page.waitForTimeout(300);
  }
  await page.waitForTimeout(500);
}
async function toSettings(provider) {
  await page.locator('[data-ui="settings-toggle"]:visible').click();
  await page.locator('[data-ui="settings-nav-models"]').click();
  await page.locator(`[data-ui="ms-nav-item"][data-provider="${provider}"]`).click();
  await page.locator(`[data-ui="ms-detail"][data-provider="${provider}"]`).waitFor({ timeout: 8000 });
}
async function saveKey(key) {
  await page.locator('[data-ui="ms-key"]:visible').fill(key);
  await page.locator('[data-ui="ms-key-save"]:visible').click();
  await page.locator('[data-ui="ms-notice"]:visible').waitFor({ timeout: 8000 });
  await page.waitForTimeout(800);
  return page.locator('[data-ui="ms-notice"]:visible').innerText().catch(() => "");
}
async function backToChat() {
  await page.locator('[data-ui="settings-toggle"]:visible').click();
  await page.locator(pane).waitFor({ state: "visible", timeout: 8000 });
  await page.waitForTimeout(1500);
}
async function pick(provider, model) {
  await page.locator(`${pane} [data-ui="chat-model"]`).click();
  const menu = `${pane} [data-ui="chat-model-menu"]`;
  await page.locator(menu).waitFor({ state: "visible", timeout: 5000 });
  await page.locator(`${menu} [data-ui="chat-model-vendor"][data-provider="${provider}"]`).hover();
  await page.locator(`[data-ui="chat-model-sub"][data-provider="${provider}"] [data-model-id="${model}"]`).click();
  await page.waitForTimeout(800);
}

let failed = null;
try {
  const pid0 = gwPid();
  await page.goto(`${base}/#/`, { waitUntil: "domcontentloaded" });
  await page.locator(pane).waitFor({ state: "visible", timeout: 20000 });
  await waitConnected(page, pane, 60000);
  await step("打开软件:聊天连上,右下角换模型按钮在", { 按钮: await chipText(), 网关PID: pid0 });

  await send("你好");
  await step("发「你好」", { 回复: await lastAi(), 厂商收到: hitsNow() });

  await toSettings("deepseek");
  const n1 = await saveKey(DS_KEY);
  await step("设置 → 模型设置 → DeepSeek → 粘 key → 保存", { 提示: n1, 网关PID: gwPid() });

  await backToChat();
  await step("返回工作区:聊天还连着吗、按钮还在吗", { 按钮: await chipText(), 有没有连接不上: /连接不上/.test(await page.locator(pane).innerText()), 网关PID: gwPid() });

  await send("存完 DeepSeek,我没换模型");
  await step("不换模型再发一句(应仍是小米)", { 回复: await lastAi(), 厂商收到: hitsNow() });

  await pick("deepseek", "deepseek-v4-pro");
  await step("右下角换到 DeepSeek v4-pro", { 按钮: await chipText() });
  await send("换到 DeepSeek 之后");
  await step("发一句(应是 DeepSeek)", { 回复: await lastAi(), 厂商收到: hitsNow() });

  await toSettings("mimo");
  const n2 = await saveKey(WRONG);
  await step("设置 → MiMo → 故意存一把错的 key", { 提示: n2 });
  await backToChat();
  await pick("mimo", "mimo-v2.5");
  await send("小米 key 填错了之后");
  await step("切回小米发一句(key 是错的,应看到看得懂的失败)", { 回复: await lastAi(), 按钮: await chipText(), 厂商收到: hitsNow() });

  await toSettings("mimo");
  const n3 = await saveKey(K2);
  await step("设置 → MiMo → 改成一把对的新 key", { 提示: n3 });
  await backToChat();
  await send("改好 key 之后");
  await step("马上再发一句(应是小米、新 key)", { 回复: await lastAi(), 厂商收到: hitsNow() });

  // 回复写到一半去存 key
  const before = await aiCount();
  await page.locator(`${pane} textarea`).fill("请慢慢说一段话");
  await waitSendable(page, pane, 30000);
  await page.locator(`${pane} .send-btn`).click();
  await page.waitForTimeout(3500);
  await step("发一句要慢慢写的,正在写", { 正在写: await page.locator(`${pane} .msg-ai.streaming`).count() > 0 });
  await toSettings("deepseek");
  const n4 = await saveKey(DS_KEY);
  await step("写到一半时去设置存 DeepSeek 的 key", { 提示: n4 });
  await backToChat();
  const t0 = Date.now();
  while (Date.now() - t0 < 60000) {
    if ((await aiCount()) > before && (await page.locator(`${pane} .msg-ai.streaming, ${pane} .msg-ai.thinking`).count()) === 0) break;
    await page.waitForTimeout(300);
  }
  await step("回到聊天:那段回复写完了吗", { 回复: await lastAi(), 按钮: await chipText(), 网关PID: gwPid(), 开头PID: pid0 });
} catch (e) {
  failed = e;
  lines.push("## 中断", "", "```", String(e?.stack || e), "```");
  try { await step("中断时的画面"); } catch { /* 截不了 */ }
}
lines.push("## 页面级 JS 报错", "", consoleErr.length ? consoleErr.map((x) => `- ${x}`).join("\n") : "无", "");
writeFileSync(join(OUT, "tour.md"), lines.join("\n"));
await browser.close();
try { host.stdin.write('{"cmd":"quit"}\n'); } catch { /* 已经没了 */ }
await new Promise((r) => setTimeout(r, 3000));
try { host.kill("SIGKILL"); } catch { /* 已经没了 */ }
mimo.srv.close(); ds.srv.close();
rmSync(app, { recursive: true, force: true });
if (failed) { console.error(failed); process.exit(1); }
console.log(`录完 ${n} 步 → ${join(OUT, "tour.md")}`);
process.exit(0);
