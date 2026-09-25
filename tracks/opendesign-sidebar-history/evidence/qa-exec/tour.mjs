// QA 执行的「真界面操作录像」(track opendesign-sidebar-history):主 agent 在**真管家 + 真网关 + 真工作台 + 真 chromium** 上
// 按七家 QA 设计的 P0 把侧栏「历史对话 + 项目」走一遍,每一步留截图 + 侧栏文字 + 当时的事实。**不是判据**,不进 run-all。
// 补的是判据够不着的:e2e 的会话列表 / 碰过的项目 / 置顶改名都是替身,这里是真网关写的对话文件、助手真调项目工具
// (假厂商按话发工具调用,网关真去执行、真写项目档案)、ds_web 真写 sidebar.json、真关掉管家再开。
//
// 台面(照 opendesign-composer-zcode 的 tour.mjs):本机按出货形状摆一份(<包>/ds = 仓库某次提交的 git archive bin config web/dist;
// <包>/python/python.exe = 包一层 venv python 的小脚本)。主槽的 apiBase 指到本机假厂商。
// 业主机器上的旧对话用「种」的:照网关对话文件的格式在 sessions/ 里写 30 段更早的对话(有的碰过项目)。
// 零外网:导入 tests/e2e/helpers.mjs 即进无出口网络命名空间;代理变量另指向没人听的端口。
//
// 跑法(仓根):node tracks/opendesign-sidebar-history/evidence/qa-exec/tour.mjs <包目录>
import { spawn, spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync, rmSync, mkdtempSync, readFileSync, existsSync } from "node:fs";
import { createServer } from "node:http";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..", "..", "..");
const { launchBrowser, waitConnected, waitSendable } = await import(join(ROOT, "tests", "e2e", "helpers.mjs"));
const PKG = process.argv[2];
if (!PKG) { console.error("用法:tour.mjs <包目录>"); process.exit(2); }
const PY = join(PKG, "python", "python.exe");

// ── 假厂商:按用户的话决定回什么;要动项目的,先回工具调用(网关真去执行),拿到工具结果再回一句话 ──
const textOf = (c) => (typeof c === "string" ? c : Array.isArray(c)
  ? c.filter((p) => p && p.type === "text").map((p) => p.text).join("") : JSON.stringify(c ?? ""));
const hits = [];
function plan(ask) {
  let m;
  if ((m = ask.match(/给(\S+?)记一笔[::](\S+)/))) return [{ name: "append_change", args: { project: m[1], content: m[2] } }];
  if (ask.includes("两个项目一起推进")) {
    return [{ name: "append_change", args: { project: "翡翠湾-1801", content: "餐厅吊灯换款" } },
            { name: "set_stage", args: { project: "滨江-12F", stage: "平面方案" } }];
  }
  if (ask.includes("把老宅改名成老宅翻新")) return [{ name: "rename_project", args: { old: "老宅", new: "老宅翻新" } }];
  if (ask.includes("临时样板间这个项目删掉")) return [{ name: "delete_project", args: { project: "临时样板间" } }];
  if ((m = ask.match(/【当前项目:([^】]+)】帮我看看档案/))) return [{ name: "read_project", args: { name: m[1] } }];
  return null;
}
const vendor = createServer((req, res) => {
  let raw = "";
  req.on("data", (b) => { raw += b; });
  req.on("end", () => {
    let body = {};
    try { body = JSON.parse(raw || "{}"); } catch { /* 坏包 */ }
    const msgs = body.messages || [];
    const sysText = textOf(msgs.find((x) => x.role === "system")?.content);
    const last = msgs[msgs.length - 1] || {};
    const ask = textOf([...msgs].reverse().find((x) => x.role === "user")?.content);
    let text = "好的。";
    let tools = null;
    let kind = "chat";
    if (sysText.includes("short, neutral chat titles")) {
      // 网关给对话起名:取用户第一句(去掉项目前缀)前 14 个字 —— 录像里每段对话名字不同,好认
      kind = "title";
      const u = (ask.match(/User: ([\s\S]*?)(?:\nAssistant:|$)/)?.[1] ?? ask).replace(/^【当前项目:[^】]+】/, "").trim();
      text = u.slice(0, 14) || "未命名";
    } else if (last.role === "tool") {
      kind = "after-tool";
      text = `好的,处理完了:${textOf(last.content).slice(0, 60)}`;
    } else {
      tools = plan(ask);
    }
    hits.push({ kind, ask: ask.slice(-80), tools: tools ? tools.map((t) => `${t.name}(${JSON.stringify(t.args)})`) : [] });
    const now = Math.floor(Date.now() / 1000);
    const calls = tools?.map((t, i) => ({ index: i, id: `call_${now}_${i}`, type: "function",
      function: { name: `mcp_design-studio_${t.name}_tool`, arguments: JSON.stringify(t.args) } }));
    if (!body.stream) {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ id: "x", object: "chat.completion", created: now, model: body.model,
        choices: [{ index: 0, finish_reason: calls ? "tool_calls" : "stop",
          message: calls ? { role: "assistant", content: null, tool_calls: calls.map(({ index, ...c }) => c) }
                         : { role: "assistant", content: text } }],
        usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 } }));
      return;
    }
    res.writeHead(200, { "Content-Type": "text/event-stream" });
    const chunk = (delta, fin = null) => `data: ${JSON.stringify({ id: "x", object: "chat.completion.chunk", created: now,
      model: body.model, choices: [{ index: 0, delta, finish_reason: fin }] })}\n\n`;
    if (calls) {
      calls.forEach((c, i) => res.write(chunk(i === 0 ? { role: "assistant", tool_calls: [c] } : { tool_calls: [c] })));
      res.write(chunk({}, "tool_calls"));
    } else {
      res.write(chunk({ role: "assistant", content: text }));
      res.write(chunk({}, "stop"));
    }
    res.end("data: [DONE]\n\n");
  });
});
await new Promise((r) => vendor.listen(0, "127.0.0.1", r));
const vendorBase = `http://127.0.0.1:${vendor.address().port}/v1`;

// ── 业主的机器:数据目录(五个项目档案)+ 网关工作区里 30 段更早的对话 + 配置 + 一把 key ──
const app = mkdtempSync(join(tmpdir(), "ds-sidebar-tour-"));
const home = join(app, "OpenDesign", "UserData");
const data = join(app, "OpenDesign", "Data");
const sessDir = join(home, ".nanobot", "workspace", "sessions");
for (const d of [join(home, ".nanobot"), join(home, ".openDesign"), join(data, "projects"), sessDir]) mkdirSync(d, { recursive: true });
const PROJ = { "翡翠湾-1801": "施工跟进", "陈总办公室": "方案深化", "滨江-12F": "洽谈", "老宅": "平面方案", "临时样板间": "洽谈" };
for (const [p, st] of Object.entries(PROJ)) {
  writeFileSync(join(data, "projects", `${p}.md`),
    `# ${p}\n\n- 业主: [[李四]]\n- 阶段: ${st}\n\n## 变更记录\n\n## 沟通日志\n\n---\n最后更新: 2026-09-01\n`);
}
const localIso = (ms) => new Date(ms).toLocaleString("sv-SE").replace(" ", "T") + ".000000";
const DAY = 86400000;
const midnight = new Date(); midnight.setHours(0, 0, 0, 0);
// 元数据 updated_at 一律写「刚才」:网关默认每 15 分钟空闲压缩一次、每次都把它刷成当时(design P6),业主机器上就是这样;
// 真正的最后聊天时间在消息自带的 timestamp 里
const bumped = localIso(Date.now() - 60000);
const webuiDir = join(home, ".nanobot", "webui");
mkdirSync(webuiDir, { recursive: true });
function seed(title, whenMs, firstUser, tool = null) {
  const id = randomUUID();
  const at = localIso(whenMs);
  const rows = [{ _type: "metadata", key: `websocket:${id}`, created_at: at, updated_at: bumped,
                  metadata: { webui: true, title }, last_consolidated: 0 },
                { role: "user", content: firstUser, timestamp: at }];
  if (tool) {
    rows.push({ role: "assistant", content: "", timestamp: at, tool_calls: [{ id: "call_seed", type: "function",
      function: { name: `mcp_design-studio_${tool.name}_tool`, arguments: JSON.stringify(tool.args) } }] });
    rows.push({ role: "tool", tool_call_id: "call_seed", name: `mcp_design-studio_${tool.name}_tool`, content: "{\"ok\": true}", timestamp: at });
  }
  rows.push({ role: "assistant", content: "好的,记下了。", timestamp: at });
  writeFileSync(join(sessDir, `websocket_${id}.jsonl`), rows.map((r) => JSON.stringify(r)).join("\n") + "\n");
  return `websocket:${id}`;
}
seed("昨天的报价", midnight.getTime() - 3 * 3600000, "陈总办公室的报价单再核一遍",
  { name: "log_communication", args: { project: "陈总办公室", text: "报价单核对" } });
seed("昨天闲聊", midnight.getTime() - 5 * 3600000, "今天有点累");
seed("老宅水电改造", midnight.getTime() - 3 * DAY, "老宅厨房水电要改",
  { name: "append_change", args: { project: "老宅", content: "厨房水电改位" } });
seed("样板间软装", midnight.getTime() - 4 * DAY, "临时样板间软装清单",
  { name: "append_change", args: { project: "临时样板间", content: "软装清单" } });
// 一段被空闲压缩过的长对话:对话文件里只剩后面的闲聊(没有工具调用);早期给滨江-12F 记的账只在界面回放记录里(design P1′)
{
  const id = randomUUID();
  const at = localIso(midnight.getTime() - 9 * DAY);
  writeFileSync(join(sessDir, `websocket_${id}.jsonl`), [
    { _type: "metadata", key: `websocket:${id}`, created_at: at, updated_at: bumped, metadata: { webui: true, title: "滨江长对话" }, last_consolidated: 0 },
    { role: "user", content: "那就先这样", timestamp: at },
    { role: "assistant", content: "好的", timestamp: at },
  ].map((r) => JSON.stringify(r)).join("\n") + "\n");
  writeFileSync(join(webuiDir, `websocket_${id}.jsonl`), [
    { event: "user", chat_id: id, text: "滨江-12F 的卫生间墙砖换一下", turn_id: "t1", turn_phase: "user", turn_seq: 1 },
    { event: "message", chat_id: id, text: "", kind: "progress", turn_id: "t1", tool_events: [{ version: 1, phase: "end", call_id: "c1",
      name: "mcp_design-studio_append_change_tool", arguments: { project: "滨江-12F", content: "卫生间墙砖换款" }, result: "{\"ok\": true}", error: null, files: [], embeds: [] }] },
    { event: "turn_end", chat_id: id, turn_id: "t1", turn_phase: "complete", turn_seq: 3 },
  ].map((r) => JSON.stringify(r)).join("\n") + "\n");
}
for (let i = 1; i <= 26; i++) {
  const touch = i === 26 ? { name: "append_change", args: { project: "翡翠湾-1801", content: "最早那次改动" } } : null;
  seed(`很早的对话${String(i).padStart(2, "0")}`, midnight.getTime() - (5 + i) * DAY, `第 ${i} 段旧对话`, touch);
}

writeFileSync(join(home, ".openDesign", "key.txt"), "tp-qa-tour-mimo-0123456789\n");
const cfgPath = join(home, ".nanobot", "config.json");
const prep = spawnSync(PY, ["-c", `
import json, sys; sys.path.insert(0, ${JSON.stringify(join(PKG, "ds", "bin"))})
import ds_credential
cfg = ds_credential.load_jsonc(${JSON.stringify(join(PKG, "ds", "config", "nanobot.config.windows.jsonc"))})
cfg["providers"]["custom"]["apiBase"] = ${JSON.stringify(vendorBase)}
ws = cfg.setdefault("channels", {}).setdefault("websocket", {})
ws.update(enabled=True, host="127.0.0.1", token="tour-kouling", websocketRequiresToken=True, allowFrom=["*"])
json.dump(cfg, open(${JSON.stringify(cfgPath)}, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
`], { encoding: "utf-8" });
if (prep.status !== 0) { console.error(prep.stderr); process.exit(1); }

const dead = "http://127.0.0.1:9";
let host = null;
async function startHost() {
  host = spawn(PY, [join(PKG, "ds", "bin", "ds_host.py")], {
    env: { ...process.env, LOCALAPPDATA: app, PYTHONIOENCODING: "utf-8",
           HTTP_PROXY: dead, HTTPS_PROXY: dead, http_proxy: dead, https_proxy: dead,
           NO_PROXY: "127.0.0.1,localhost", no_proxy: "127.0.0.1,localhost" },
    stdio: ["pipe", "pipe", "inherit"],
  });
  const first = await new Promise((r) => host.stdout.once("data", (b) => r(String(b))));
  return JSON.parse(first.split("\n")[0]).web_port;
}
// 等端口真能再绑:用管家自己那套判断(ds_shell_core.port_free,不带 SO_REUSEADDR)。Linux 上刚断开的连接(TIME_WAIT)会让它判「占着」,
// 管家就把聊天端口顺延到 8766,而前端写死连 8765 ⇒ 页面连不上 —— 老问题,另报。Node 的 listen 自带 SO_REUSEADDR,拿它判会误以为空了(第 2 遍录像栽过)。
async function waitPortFree(port, timeoutMs = 150000) {
  const t0 = Date.now();
  for (;;) {
    const r = spawnSync(PY, ["-c", `import sys; sys.path.insert(0, ${JSON.stringify(join(PKG, "ds", "bin"))}); import ds_shell_core as c; sys.exit(0 if c.port_free(${port}) else 1)`]);
    if (r.status === 0 || Date.now() - t0 > timeoutMs) return Math.round((Date.now() - t0) / 1000);
    await new Promise((res) => setTimeout(res, 2000));
  }
}
async function quitHost() {
  try { host.stdin.write('{"cmd":"quit"}\n'); } catch { /* 已经没了 */ }
  const t0 = Date.now();
  while (host.exitCode === null && Date.now() - t0 < 15000) await new Promise((r) => setTimeout(r, 200));
  if (host.exitCode === null) { try { host.kill("SIGKILL"); } catch { /* 已经没了 */ } }
}
let base = `http://127.0.0.1:${await startHost()}`;

const OUT = HERE;
const lines = ["# QA 执行 · 真界面操作录像(track opendesign-sidebar-history)", "",
  `台面:真管家 + 真网关 + 真工作台 + 真 chromium;包 = 本机按出货形状摆的一份(${process.env.TOUR_PKG_FROM || "ds 来自哪次提交:未注明"})。`,
  "主槽指到本机假厂商:话里要动项目的(「给X记一笔:…」「两个项目一起推进」「把老宅改名成老宅翻新」「临时样板间这个项目删掉」、项目栏里「帮我看看档案」),",
  "假厂商先回**工具调用**,网关真去执行(真写项目档案),再回一句话;网关给对话起名时,假厂商回用户第一句的前 14 个字。",
  "开录前在网关的对话目录里照它的格式种了 30 段旧对话(昨天 2 段、更早 28 段;其中 4 段碰过项目:昨天的报价→陈总办公室、老宅水电改造→老宅、样板间软装→临时样板间、很早的对话26→翡翠湾-1801)。",
  "种的旧对话:元数据里的「更新时间」全写成录像开始前 1 分钟(模拟网关每 15 分钟一次的空闲压缩把它刷新),消息自带真实时间;另有一段「滨江长对话」(9 天前)被压缩过 ——",
  "对话文件里只剩最后两句闲聊,早期给滨江-12F 记账那一步只在界面回放记录里。种的旧对话没有完整的界面回放,点开时首页正文可能是空的(台子限制,不是这次改的)。",
  "「关掉再开」之前录像台子先等聊天端口 8765 释放(刚断开的连接会占它一阵;不等的话新聊天服务换了端口、页面连不上 —— 那是另一个老问题,另报)。",
  "五个项目:翡翠湾-1801(施工跟进)、陈总办公室(方案深化)、滨江-12F(洽谈)、老宅(平面方案)、临时样板间(洽谈)。",
  "每步:截图 NN.jpg + 侧栏文字 + 当时的事实。读屏文字不含悬停提示与图标;需要时事实里另记 aria-pressed / 悬停字。", ""];
let n = 0;
const pane = ".home-pane";
const browser = await launchBrowser();
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
const consoleErr = [];
page.on("pageerror", (e) => consoleErr.push(String(e)));
let dialogPlan = "accept";
const dialogs = [];
page.on("dialog", async (d) => { dialogs.push(d.message()); if (dialogPlan === "accept") await d.accept(); else await d.dismiss(); });

const side = page.locator("nav.side");
async function step(title, facts = {}) {
  n += 1;
  const nn = String(n).padStart(2, "0");
  await page.screenshot({ path: join(OUT, `${nn}.jpg`), type: "jpeg", quality: 60 });
  const text = (await side.innerText().catch(() => "")).replace(/\n{2,}/g, "\n").slice(0, 2200);
  lines.push(`## ${nn}. ${title}`, "", `截图:${nn}.jpg`, "");
  for (const [k, v] of Object.entries(facts)) lines.push(`- ${k}:${typeof v === "string" ? v : JSON.stringify(v)}`);
  lines.push("", "侧栏文字:", "```", text, "```", "");
  console.log(`[${nn}] ${title} ${JSON.stringify(facts).slice(0, 300)}`);
}
const rows = async (sel) => (await page.locator(`${sel} .hist-row`).allInnerTexts()).map((t) => t.split("\n")[0].trim());
const viewState = async () => ({
  按时间: await page.locator('[data-ui="side-view-time"]').getAttribute("aria-pressed").catch(() => null),
  按项目: await page.locator('[data-ui="side-view-project"]').getAttribute("aria-pressed").catch(() => null),
});
const sidebarFile = () => {
  const p = join(data, "config", "sidebar.json");
  return existsSync(p) ? JSON.parse(readFileSync(p, "utf-8")) : "(还没有这个文件)";
};
async function view(v) { await page.locator(`[data-ui="side-view-${v}"]`).click(); await page.waitForTimeout(300); }
async function expand(p) {
  const b = page.locator(`[data-ui="proj-expand"][data-project="${p}"]`);
  if (await b.count() === 0) return false;
  if ((await b.getAttribute("aria-expanded")) !== "true") await b.click();
  await page.waitForTimeout(200);
  return true;
}
async function projList(p) { return (await expand(p)) ? rows(`[data-ui="proj-sessions"][data-project="${p}"]`) : "(这个项目没有展开键 = 0 段对话)"; }
async function menu(rowSel, name, action) {
  const row = page.locator(`${rowSel} .hist-row`, { hasText: name }).first();
  await row.scrollIntoViewIfNeeded();
  await row.hover();
  await row.locator('[data-ui="hist-menu"]').click();
  await page.waitForTimeout(200);
  if (action) await page.locator(`[data-ui="hist-${action}"]`).click();
}
async function waitTurn(scope, timeout = 60000) {
  const t0 = Date.now();
  await page.locator(`${scope} .stop-btn`).waitFor({ timeout: 5000 }).catch(() => {});
  while (Date.now() - t0 < timeout && (await page.locator(`${scope} .stop-btn`).count()) > 0) await page.waitForTimeout(300);
  await page.waitForTimeout(1500);   // 等侧栏随回合收尾刷新
}
async function send(scope, text) {
  const ta = page.locator(`${scope} textarea`).first();
  await ta.fill(text);
  await waitSendable(page, scope, 30000);
  await page.locator(`${scope} .send-btn`).first().click();
  await waitTurn(scope);
}
const lastReply = async (scope) => (await page.locator(`${scope} .msg-ai:not(.thinking)`).last().innerText().catch(() => "")).slice(0, 160);
async function newChat() {
  await page.locator('[data-ui="side-new-chat"]').click();
  await page.waitForTimeout(500);
  await waitConnected(page, pane, 30000);
}
const projFile = (p) => { try { return readFileSync(join(data, "projects", `${p}.md`), "utf-8"); } catch { return "(没有这个档案)"; } };

let failed = null;
try {
  await page.goto(`${base}/#/`, { waitUntil: "domcontentloaded" });
  await page.locator(pane).waitFor({ state: "visible", timeout: 20000 });
  await waitConnected(page, pane, 60000);
  await page.locator('[data-ui="side-day"]').first().waitFor({ timeout: 20000 });
  await step("第一次打开软件(从没拨过视图)", { 视图按钮: await viewState(),
    分段小标: await page.locator('[data-ui="side-day"]').allInnerTexts(), 历史首屏行数: (await rows('[data-ui="side-history"]')).length,
    显示更多按钮: await page.locator('[data-ui="side-more"]').count() });

  let clicks = 0;
  while ((await page.locator('[data-ui="side-more"]').count()) > 0 && clicks < 10) {
    await page.locator('[data-ui="side-more"]').first().click();
    clicks += 1;
    await page.waitForTimeout(200);
  }
  const all = await rows('[data-ui="side-history"]');
  await page.locator('[data-ui="side-history"] .hist-row').last().scrollIntoViewIfNeeded();
  await step("一直点「显示更多」到按钮没了,滚到最下", { 点了几次: clicks, 历史行数: all.length, 最后三行: all.slice(-3),
    有没有重复: all.length !== new Set(all).size ? "有重复" : "没有",
    左下角设置在不在屏幕里: await page.locator('[data-ui="settings-toggle"]').isVisible() });

  await page.locator('[data-ui="side-history"] .hist-row', { hasText: "很早的对话26" }).first().click();
  await page.waitForTimeout(2500);
  await step("点最早那段「很早的对话26」", { 地址: await page.evaluate(() => location.hash),
    首页气泡: (await page.locator(`${pane} .msg-user, ${pane} .msg-ai`).allInnerTexts()).map((t) => t.slice(0, 40)) });
  await send(pane, "还在吗");
  await step("在这段里接着发「还在吗」", { 回复: await lastReply(pane), 今天这段: await rows('[data-ui="side-history"]').then((r) => r.slice(0, 3)),
    分段小标: await page.locator('[data-ui="side-day"]').allInnerTexts() });

  // ── 新对话第一句就让助手记账(侧栏开着「按项目」、翡翠湾展开着)──
  await view("project");
  await expand("翡翠湾-1801");
  await step("拨到「按项目」,展开翡翠湾-1801(还没发新对话)", { 视图按钮: await viewState(), 翡翠湾下: await projList("翡翠湾-1801"),
    "滨江下(那段被压缩过的长对话)": await projList("滨江-12F"),
    其他对话: await rows('[data-ui="side-other"]').then((r) => r.slice(0, 6)) });
  await newChat();
  await send(pane, "给翡翠湾-1801记一笔:主卧衣柜改推拉门");
  await step("新对话第一句「给翡翠湾-1801记一笔:主卧衣柜改推拉门」,等它记完(不刷新页面)", {
    回复: await lastReply(pane), 翡翠湾下: await projList("翡翠湾-1801"),
    其他对话前几条: await rows('[data-ui="side-other"]').then((r) => r.slice(0, 4)),
    "档案里有没有这笔": projFile("翡翠湾-1801").includes("主卧衣柜改推拉门") ? "有" : "没有",
    假厂商收到的工具调用: hits.filter((h) => h.tools.length).map((h) => h.tools).at(-1) });

  await newChat();
  await send(pane, "这周想把两个项目一起推进");
  await step("新对话「这周想把两个项目一起推进」(助手给翡翠湾记一笔 + 把滨江-12F 改到平面方案)", {
    回复: await lastReply(pane), 翡翠湾下: await projList("翡翠湾-1801"), 滨江下: await projList("滨江-12F"),
    滨江档案阶段: (projFile("滨江-12F").match(/- 阶段: (.+)/) || [])[1] });
  await view("time");
  await step("拨回「按时间」看这两段", { 今天: await rows('[data-ui="side-history"]').then((r) => r.slice(0, 4)),
    行上的项目小标: await page.locator('[data-ui="side-history"] .hist-row .hist-proj').allInnerTexts().then((t) => t.slice(0, 4)) });

  await newChat();
  await send(pane, "陈总办公室那边下周量房吗");
  await view("project");
  await step("新对话只嘴上提「陈总办公室」(助手没动项目),再看「按项目」", { 回复: await lastReply(pane),
    陈总办公室下: await projList("陈总办公室"), 其他对话前几条: await rows('[data-ui="side-other"]').then((r) => r.slice(0, 4)) });

  // ── 项目栏里的项目对话 ──
  await side.locator(".proj-row", { hasText: "陈总办公室" }).first().click();
  await page.waitForTimeout(1500);
  await waitConnected(page, ".ws-pane", 30000);
  await send(".ws-pane", "帮我看看档案");
  await step("点项目名「陈总办公室」进项目页,在右边项目助手里说「帮我看看档案」", { 地址: await page.evaluate(() => location.hash),
    项目助手回复: await lastReply(".ws-pane"), 陈总办公室下: await projList("陈总办公室") });
  await send(".ws-pane", "再记一下明天去量房");
  await step("在项目助手里再说一句(对话在变,侧栏开着「按项目」)", { 陈总办公室下: await projList("陈总办公室") });

  // ── 置顶 / 改名 ──
  await page.locator('[data-ui="side-new-chat"]').click();
  await page.waitForTimeout(800);
  await menu('[data-ui="proj-sessions"][data-project="翡翠湾-1801"]', "这周想把两个项目一起推进");
  await step("在翡翠湾下面那段「这周想把两个项目…」点「⋯」", {
    菜单: await page.locator('[data-ui="hist-pop"] [role="menuitem"]').allInnerTexts() });
  await page.locator('[data-ui="hist-pin"]').click();
  await page.waitForTimeout(600);
  await step("点「置顶」", { 已置顶: await rows('[data-ui="side-pinned"]'), 翡翠湾下: await projList("翡翠湾-1801"),
    滨江下: await projList("滨江-12F"), "盘上 sidebar.json": sidebarFile() });
  await menu('[data-ui="side-pinned"]', "这周想把两个项目", "rename");
  await page.locator('[data-ui="hist-rename-input"]').fill("给甲方的预算口径");
  await page.locator('[data-ui="hist-rename-input"]').press("Enter");
  await page.waitForTimeout(600);
  await step("「⋯」→「改名」,输入「给甲方的预算口径」回车", { 已置顶: await rows('[data-ui="side-pinned"]'),
    "盘上 sidebar.json": sidebarFile() });
  await menu('[data-ui="side-pinned"]', "给甲方的预算口径", "rename");
  await page.locator('[data-ui="hist-rename-input"]').fill("   ");
  await step("再改名:把名字清成只剩空格(还没回车)", { 输入框: JSON.stringify(await page.locator('[data-ui="hist-rename-input"]').inputValue()) });
  await page.locator('[data-ui="hist-rename-input"]').press("Enter");
  await page.waitForTimeout(600);
  await step("回车", { 已置顶: await rows('[data-ui="side-pinned"]'), "盘上 sidebar.json": sidebarFile() });
  await view("time");
  await step("「按时间」里看置顶那段", { 已置顶: await rows('[data-ui="side-pinned"]'), 今天: await rows('[data-ui="side-history"]').then((r) => r.slice(0, 5)) });
  await view("project");

  // ── 关掉软件再打开 ──
  const oldBase = base;
  await quitHost();
  const waited = await waitPortFree(8765);
  base = `http://127.0.0.1:${await startHost()}`;
  await page.goto(`${base}/#/`, { waitUntil: "domcontentloaded" });
  await waitConnected(page, pane, 60000);
  await page.locator('[data-ui="side-pinned"]').waitFor({ timeout: 20000 }).catch(() => {});
  await step("完全关掉软件(管家退出)再打开", { 前后地址: `${oldBase} → ${base}`, 等聊天端口释放了几秒: waited, 视图按钮: await viewState(),
    已置顶: await rows('[data-ui="side-pinned"]'),
    说明: "「按时间 | 按项目」记在浏览器存储里,按地址分;录像台子重开若换了端口就像换了一台浏览器(业主的桌面版地址固定,不受影响)" });
  await menu('[data-ui="side-pinned"]', "给甲方的预算口径", "pin");
  await page.waitForTimeout(600);
  await view("project");
  await step("「⋯」→「取消置顶」", { 已置顶: await page.locator('[data-ui="side-pinned"]').count() ? await rows('[data-ui="side-pinned"]') : "(置顶区没了)",
    翡翠湾下: await projList("翡翠湾-1801"), 滨江下: await projList("滨江-12F") });

  // ── 项目改名 / 删项目 ──
  await step("改名之前:老宅下面", { 老宅下: await projList("老宅") });
  await newChat();
  await send(pane, "把老宅改名成老宅翻新");
  await step("新对话「把老宅改名成老宅翻新」(助手真改名)", { 回复: await lastReply(pane),
    项目栏: await side.locator(".proj-row .nm").allInnerTexts(), 老宅翻新下: await projList("老宅翻新") });
  await step("删项目之前:临时样板间下面", { 临时样板间下: await projList("临时样板间") });
  await newChat();
  await send(pane, "临时样板间这个项目删掉吧,是建重复了");
  await step("新对话「临时样板间这个项目删掉吧」(助手真删,进回收站)", { 回复: await lastReply(pane),
    项目栏: await side.locator(".proj-row .nm").allInnerTexts(),
    "其他对话里有没有「样板间软装」": (await rows('[data-ui="side-other"]')).includes("样板间软装") ? "有" : "前几条里没有(可能要点显示更多)",
    其他对话前几条: await rows('[data-ui="side-other"]') });

  // ── 删除一段置顶 + 改过名、又碰过项目的对话 ──
  await menu('[data-ui="side-other"]', "陈总办公室那边下周量房吗", "pin");
  await page.waitForTimeout(500);
  await menu('[data-ui="side-pinned"]', "陈总办公室那边下周量房吗", "rename");
  await page.locator('[data-ui="hist-rename-input"]').fill("要删的这段");
  await page.locator('[data-ui="hist-rename-input"]').press("Enter");
  await page.waitForTimeout(500);
  await step("把「陈总办公室那边下周量房吗」置顶并改名「要删的这段」", { 已置顶: await rows('[data-ui="side-pinned"]'), "盘上 sidebar.json": sidebarFile() });
  dialogPlan = "dismiss";
  await menu('[data-ui="side-pinned"]', "要删的这段", "delete");
  await page.waitForTimeout(600);
  await step("「⋯」→「删除」,确认框点「取消」", { 确认框原文: dialogs.at(-1), 已置顶: await rows('[data-ui="side-pinned"]') });
  dialogPlan = "accept";
  await menu('[data-ui="side-pinned"]', "要删的这段", "delete");
  await page.waitForTimeout(1500);
  await view("time");
  let more = 0;
  while ((await page.locator('[data-ui="side-more"]').count()) > 0 && more < 10) { await page.locator('[data-ui="side-more"]').first().click(); more += 1; }
  const allNow = await rows('[data-ui="side-history"]');
  await step("再删一次,确认框点「确定」;然后「按时间」翻到底找它", { 确认框原文: dialogs.at(-1),
    已置顶: await page.locator('[data-ui="side-pinned"]').count() ? await rows('[data-ui="side-pinned"]') : "(置顶区没了)",
    按时间里还有没有: allNow.some((t) => t.includes("要删的这段") || t.includes("陈总办公室那边下周")) ? "还有" : "没有",
    "盘上 sidebar.json": sidebarFile() });

  // ── 原有的:分堆折叠、新建项目、点对话回首页接着聊 ──
  await view("project");
  const stageHead = side.locator('[data-ui="stage-group"] .grp-toggle').first();
  const stageName = await stageHead.innerText();
  await stageHead.click();
  await page.waitForTimeout(300);
  await step(`折叠第一个阶段堆「${stageName.split("\n")[0]}」`, { 项目栏: await side.locator(".proj-row .nm").allInnerTexts() });
  await stageHead.click();
  await page.waitForTimeout(300);
  await side.locator('.sect-add').click();
  await page.waitForTimeout(600);
  await step("再展开;点项目栏的「+」(新建项目)", { 地址: await page.evaluate(() => location.hash),
    首页输入框: await page.locator(`${pane} textarea`).first().inputValue() });
  await page.locator(`${pane} textarea`).first().fill("");
  await expand("翡翠湾-1801");
  await page.locator('[data-ui="proj-sessions"][data-project="翡翠湾-1801"] .hist-row', { hasText: "给翡翠湾-1801记一笔" }).first().click();
  await page.waitForTimeout(2500);
  await step("从「按项目」翡翠湾下面点回「给翡翠湾-1801记一笔…」那段", { 地址: await page.evaluate(() => location.hash),
    首页气泡: (await page.locator(`${pane} .msg-user, ${pane} .msg-ai`).allInnerTexts()).map((t) => t.slice(0, 50)) });
} catch (e) {
  failed = e;
  lines.push("## 中断", "", "```", String(e?.stack || e), "```");
  try { await step("中断时的画面"); } catch { /* 截不了 */ }
}
lines.push("## 假厂商收到的请求(起名 / 对话 / 工具之后)", "", "```", ...hits.map((h) => JSON.stringify(h)), "```", "");
lines.push("## 页面级 JS 报错", "", consoleErr.length ? consoleErr.map((x) => `- ${x}`).join("\n") : "无", "");
writeFileSync(join(OUT, "tour.md"), lines.join("\n"));
await browser.close();
await quitHost();
vendor.close();
rmSync(app, { recursive: true, force: true });
if (failed) { console.error(failed); process.exit(1); }
console.log(`录完 ${n} 步 → ${join(OUT, "tour.md")}`);
process.exit(0);
