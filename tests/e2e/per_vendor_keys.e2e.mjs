// 判据:每家厂商各存各的 key,端到端(track opendesign-per-vendor-keys)。
// 真 chromium + 真 ds_web + 一个**假外壳**(只会应答重启暗号、并替外壳做 prepare_gateway 那一步)。
// 主 agent 亲写。设计:tracks/opendesign-per-vendor-keys/design.md。
//
// 09-24 移植到照 ZCode 的新界面(track opendesign-zcode-model-settings;旧→新对照在它的 verify.md):
// 旧 key 卡片 → 设置页「模型设置」;一维菜单 → 两级弹框;「换厂商 / 换 key…」→「管理模型」。
// **C2 语义按业主定的 D4 改了**:存别家的 key 不换当前模型(照 ZCode),原来是"存完就换过去"。
//
// 业主视角的一整趟:
//   A 已经配过 MiMo:菜单里只有 MiMo 一家;「管理模型」进设置页,MiMo「在用 + 末四位」,DeepSeek「还没填」
//   B 在设置页选 DeepSeek、粘 key、保存 ⇒ MiMo 的 key **原样还在**;DeepSeek 的 key 落进它自己的文件
//   C 外壳重启网关(这里是假外壳做 prepare_gateway)之后:菜单出现两家,勾仍在 MiMo(存 key 不换当前模型,D4)
//   D 在菜单里点 MiMo 的模型、再点 DeepSeek 的模型 ⇒ **配置文件真的变了**,而且指向对的那一家(不是只换了按钮上的字)
//   E 两把 key 都不许出现在页面文本 / 无障碍树 / 控制台里
//
// 它问不出:运行中的网关下一句真的换了(→ tests/test_per_vendor_live.py);外壳本体接没接上(→ 真机)。
//
// 跑法:node tests/e2e/per_vendor_keys.e2e.mjs(自起 ds_web 于 8848;不需要 nanobot 网关)
import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, existsSync, rmSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, waitConnected } from "./helpers.mjs";
import { WS_STUB_BASE } from "./_ws-stub.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8848;
const PY = process.env.PY || "/root/.venvs/design-studio/bin/python";
const MIMO_KEY = "tp-e2e-pv-mimo-0123456789abcdef";
const DS_KEY = "sk-e2e-pv-deepseek-0123456789ab";
let failures = 0;

async function until(fn, timeoutMs = 15000, stepMs = 200) {
  const t0 = Date.now();
  for (;;) {
    try { if (await fn()) return true; } catch { /* 还没出现 */ }
    if (Date.now() - t0 > timeoutMs) return false;
    await new Promise((r) => setTimeout(r, stepMs));
  }
}
function check(ok, label) {
  if (ok) console.log(`  ok   - ${label}`);
  else { console.log(`  FAIL - ${label}`); failures += 1; }
}

// 期望值的唯一出处是后端目录(不在判据里另抄一份端点/模型名)
const catRaw = spawnSync(PY, ["-c", `
import sys, json; sys.path.insert(0, ${JSON.stringify(join(ROOT, "bin"))})
import ds_credential
print(json.dumps(ds_credential.PROVIDERS, ensure_ascii=False))
`], { encoding: "utf-8" });
const CATALOG = JSON.parse(catRaw.stdout || "{}");
if (!CATALOG.mimo || !CATALOG.deepseek) {
  console.error("读不到后端厂商目录:", catRaw.stderr);
  process.exit(1);
}

const STUB = () => {
  window.__wsAll = [];
  const origFetch = window.fetch;
  window.fetch = (url, init) => {
    const u = String(url);
    if (u.includes("/api/chat/bootstrap")) {
      return Promise.resolve(new Response(JSON.stringify(
        { token: "stub-token", ws_path: "/ws", expires_in: 600, model_name: "mimo-v2.5" }),
        { status: 200, headers: { "Content-Type": "application/json" } }));
    }
    if (u.includes("/thread")) return Promise.resolve(new Response("not found", { status: 404 }));
    return origFetch(url, init);
  };
  class StubWS extends window.__BaseStubWS {
    constructor(url) {
      super(url);
      window.__wsAll.push(this);
      setTimeout(() => {
        this.readyState = StubWS.OPEN;
        this.onopen?.({});
        this._emit({ event: "ready", chat_id: `chat-pv-${window.__wsAll.length}` });
      }, 10);
    }
    send() { /* 这个场景不聊天 */ }
  }
  window.WebSocket = StubWS;
};

// ── 台面 ──
const tmp = mkdtempSync(join(tmpdir(), "ds-e2e-per-vendor-"));
const dsRoot = join(tmp, "ds");
const home = join(tmp, "home");
const cfgPath = join(home, ".nanobot", "config.json");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
mkdirSync(join(tmp, "ws"), { recursive: true });
writeFileSync(join(dsRoot, "config", "workspace.json"), JSON.stringify({ root: join(tmp, "ws"), projects: {} }));
mkdirSync(join(home, ".openDesign"), { recursive: true });
writeFileSync(join(home, ".openDesign", "key.txt"), MIMO_KEY + "\n");
mkdirSync(dirname(cfgPath), { recursive: true });
const template = readFileSync(join(ROOT, "config", "nanobot.config.windows.jsonc"), "utf8")
  .split("\n").filter((ln) => !/^\s*\/\//.test(ln)).join("\n");
writeFileSync(cfgPath, JSON.stringify(JSON.parse(template), null, 2));
const readCfg = () => JSON.parse(readFileSync(cfgPath, "utf8"));
const dsKeyFile = join(home, ".openDesign", "keys", "deepseek.txt");

// ── 假外壳:认暗号、回「OK RESTART-BACKEND」,然后做外壳起网关时的那一步(prepare_gateway)──
const HELLO = "OpenDesign.ds_shell_core.lock.v1\n";
const restarts = [];
const fakeShell = createServer((sock) => {
  let buf = "";
  sock.on("data", (b) => {
    buf += b.toString("utf8");
    if (buf.startsWith(HELLO) && buf.slice(HELLO.length).includes("\n")) {
      const verb = buf.slice(HELLO.length).split("\n")[0];
      if (verb === "RESTART-BACKEND") {
        sock.end("OK RESTART-BACKEND\n");
        // 真外壳重启网关要花时间:故意晚 1.5 秒才「起好」,让存完那一刻卡片必然处在「待重启」
        setTimeout(() => {
        const r = spawnSync(PY, ["-c", `
import sys; sys.path.insert(0, ${JSON.stringify(join(ROOT, "bin"))})
import ds_credential
extra = ds_credential.prepare_gateway(${JSON.stringify(home)}, ${JSON.stringify(cfgPath)})
print(sorted(extra))
`], { encoding: "utf-8" });
        restarts.push({ rc: r.status, out: (r.stdout || "").trim(), err: (r.stderr || "").trim() });
        }, 1500);
      } else {
        sock.end("OK\n");
      }
    }
  });
});
await new Promise((r) => fakeShell.listen(0, "127.0.0.1", r));
const lockPort = fakeShell.address().port;

const pane = ".home-pane";
const chip = `${pane} .chat-card [data-ui="chat-model"]`;
const menu = `${pane} [data-ui="chat-model-menu"]`;
let browser = null;
let srv = null;
try {
  srv = spawn(PY, [join(ROOT, "bin", "ds_web.py")], {
    env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT), DS_NANOBOT_CONFIG: cfgPath,
           HOME: home, USERPROFILE: home, DS_LLM_KEY: "", DS_SHELL_LOCK_PORT: String(lockPort),
           DS_WEB_DIST: join(ROOT, "web", "dist") },
    stdio: ["ignore", "inherit", "inherit"],
  });
  const base = `http://127.0.0.1:${PORT}`;
  for (let i = 0; ; i++) {
    try { await fetch(`${base}/api/health`); break; }
    catch {
      if (i > 75) throw new Error("ds_web 起不来");
      await new Promise((r) => setTimeout(r, 200));
    }
  }

  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  const consoleLines = [];
  page.on("console", (m) => consoleLines.push(m.text()));
  page.on("pageerror", (e) => consoleLines.push(String(e)));
  await page.addInitScript(WS_STUB_BASE);
  await page.addInitScript(STUB);
  await page.goto(`${base}/#/`, { waitUntil: "domcontentloaded" });
  await page.locator(pane).waitFor({ state: "visible", timeout: 10000 });
  await waitConnected(page, pane);

  // 第 1 轮 K1:菜单打开时先用手上的旧数据画、再用打开那一下拉到的新数据重画。
  // 读在两者之间就是时序性红 ⇒ **等打开那次 /api/llm/models 回包落地、且菜单里的家数与回包一致**再读。
  const twoFrames = () => page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  const vendorRow = (id) => page.locator(`${menu} [data-ui="chat-model-vendor"][data-provider="${id}"]`);
  const openMenu = async () => {
    const fresh = page.waitForResponse((r) => r.url().includes("/api/llm/models"), { timeout: 8000 });
    await page.locator(chip).click();
    const body = await (await fresh).json().catch(() => ({}));
    const want = Array.isArray(body.groups) && body.groups.length ? body.groups.length : 1;
    await page.locator(menu).waitFor({ state: "visible", timeout: 5000 });
    await until(async () => (await page.locator(`${menu} [data-ui="chat-model-vendor"]`).count()) === want, 5000);
    await twoFrames();
  };
  // 两级弹框:每家一行,移上去才向右弹出这家的模型 ⇒ 逐家悬停,把子菜单里的行读出来
  const vendorsInMenu = async () => {
    await openMenu();
    const rows = await page.locator(`${menu} [data-ui="chat-model-vendor"]`).evaluateAll(
      (els) => els.map((e) => [e.getAttribute("data-provider"), e.innerText, e.getAttribute("data-selected")]));
    const models = [];
    for (const [id] of rows) {
      await vendorRow(id).hover();
      const sub = page.locator(`[data-ui="chat-model-sub"][data-provider="${id}"]`);
      await sub.waitFor({ state: "visible", timeout: 5000 });
      models.push(...await sub.locator("[data-model-id]").evaluateAll(
        (els) => els.map((e) => [e.getAttribute("data-provider"), e.getAttribute("data-model-id"),
                                 e.getAttribute("aria-checked")])));
    }
    return { labels: rows.map((r) => r[1]), selected: rows.filter((r) => r[2] === "true").map((r) => r[0]), models };
  };
  const closeMenu = async () => {
    if (await page.locator(menu).isVisible()) await page.keyboard.press("Escape");
  };

  // ── A ──
  const a = await vendorsInMenu();
  check(a.labels.length === 1 && /MiMo/.test(a.labels[0]), `A1 只配了 MiMo:菜单只有 MiMo 一家(实际 ${JSON.stringify(a.labels)})`);
  check(a.models.length > 0 && a.models.every(([p]) => p === "mimo"), `A2 每一行都标着厂商 mimo(实际 ${JSON.stringify(a.models)})`);
  await page.locator(`${menu} [data-ui="chat-model-manage"]`).click();
  const ms = '[data-ui="model-settings"]';
  check(await until(() => page.locator(ms).isVisible(), 5000)
        && await until(() => page.locator('[data-ui="ms-detail"][data-provider="mimo"]').isVisible(), 5000),
    "A3 「管理模型」打开模型设置,落在当前那家(MiMo)");
  const navItem = (id) => page.locator(`${ms} [data-ui="ms-nav-item"][data-provider="${id}"]`);
  const stateOf = async (id) => {
    if (!(await page.locator(`[data-ui="ms-detail"][data-provider="${id}"]`).isVisible())) {
      await navItem(id).click();
      await page.locator(`[data-ui="ms-detail"][data-provider="${id}"]`).waitFor({ timeout: 5000 });
    }
    return page.locator(`[data-ui="ms-detail"][data-provider="${id}"] [data-ui="ms-state"]`).innerText().catch(() => "");
  };
  check(await until(async () => (await navItem("mimo").count()) === 1 && (await navItem("deepseek").count()) === 1, 5000),
    "A4 左栏两家各一行");
  const mimoRow = await stateOf("mimo");
  check(/在用/.test(mimoRow) && mimoRow.includes(MIMO_KEY.slice(-4)), `A5 MiMo:在用 + 末四位(实际「${mimoRow}」)`);
  const dsRow0 = await stateOf("deepseek");
  // 🔴 「没有末四位」在那一行根本不存在时也成立 ⇒ 先要求它有字(第一版就是这么假绿的)
  check(dsRow0.trim().length > 0 && !dsRow0.includes("…") && !dsRow0.includes(DS_KEY.slice(-4)),
    `A6 DeepSeek 在、且没有末四位(还没填)(实际「${dsRow0}」)`);

  // ── B ──
  check(await page.locator('[data-ui="ms-detail"][data-provider="deepseek"]').isVisible(), "B1 点左栏 DeepSeek ⇒ 右边是 DeepSeek 的详情");
  await page.locator('[data-ui="ms-key"]:visible').fill(DS_KEY);
  await page.locator('[data-ui="ms-key-save"]:visible').click();
  check(await until(() => page.locator('[data-ui="ms-notice"]:visible').isVisible(), 8000), "B2 保存后有提示");
  // B7 要问的是「页面自己跟上」,前提是存完那一刻它**确实**处在「等重启」—— 先把前提钉住。
  check(await until(async () => /重启/.test(await stateOf("deepseek")), 1200),
    `B2b 存完那一刻 DeepSeek 写着要等后台重启(实际「${await stateOf("deepseek")}」)`);
  check(readFileSync(join(home, ".openDesign", "key.txt"), "utf8").trim() === MIMO_KEY, "B3 MiMo 的 key 原样还在");
  check(existsSync(dsKeyFile) && readFileSync(dsKeyFile, "utf8").trim() === DS_KEY, "B4 DeepSeek 的 key 落进它自己的文件");
  check(await until(() => restarts.length > 0, 8000), `B5 保存之后请了外壳重启网关(假外壳收到 ${restarts.length} 次)`);
  check(restarts.every((r) => r.rc === 0), `B6 外壳那一步(prepare_gateway)没出错:${JSON.stringify(restarts)}`);
  // 第 1 轮 G5:页面一直开着,后台起好之后它要自己跟上,不许一直写着「等重启」
  check(await until(async () => !/重启/.test(await stateOf("deepseek"))
                     && (await navItem("deepseek").locator('[data-provider-status="ready"]').count()) === 1, 15000),
    `B7 页面开着不动:后台起好后 DeepSeek 自己变成「就绪」(实际「${await stateOf("deepseek")}」)`);

  // ── C ──
  await page.locator('[data-ui="settings-toggle"]:visible').click();
  await until(async () => !(await page.locator(ms).isVisible()), 3000);
  await page.locator(`${pane} .chat-card`).waitFor({ state: "visible", timeout: 5000 });
  const c = await vendorsInMenu();
  check(c.labels.length === 2 && /MiMo/.test(c.labels.join()) && /DeepSeek/.test(c.labels.join()),
    `C1 网关拿到 key 之后菜单出现两家(实际 ${JSON.stringify(c.labels)})`);
  const checked = c.models.filter(([, , on]) => on === "true");
  check(checked.length === 1 && checked[0][0] === "mimo" && checked[0][1] === CATALOG.mimo.model
        && JSON.stringify(c.selected) === '["mimo"]',
    `C2 存 DeepSeek 的 key 没换当前模型:勾仍在 MiMo(D4,照 ZCode)(实际打勾 ${JSON.stringify(checked)} / 厂商行 ${JSON.stringify(c.selected)})`);

  // ── D ──
  const pick = async (provider, model) => {
    if (!(await page.locator(menu).isVisible())) await openMenu();
    await vendorRow(provider).hover();
    const item = page.locator(`[data-ui="chat-model-sub"][data-provider="${provider}"] [data-model-id="${model}"]`);
    await item.waitFor({ state: "visible", timeout: 5000 });
    await item.click();
    return until(() => readCfg().agents.defaults.modelPreset === model, 8000);
  };
  const entryFor = (cfg, apiBase) => (cfg.providers.custom?.apiBase === apiBase ? "custom"
    : Object.entries(cfg.providers).find(([n, p]) => n !== "custom" && p?.apiBase === apiBase)?.[0]);
  check(await pick("deepseek", "deepseek-v4-pro"), "D1 点 DeepSeek 的 pro ⇒ 配置里的当前模型真的变了");
  let cfg = readCfg();
  check(cfg.model_presets["deepseek-v4-pro"]?.provider === entryFor(cfg, CATALOG.deepseek.apiBase),
    `D2 它指向 DeepSeek 的端点(预设 provider=${cfg.model_presets["deepseek-v4-pro"]?.provider})`);
  check(await until(async () => (await page.locator(chip).innerText()).includes("deepseek-v4-pro"), 5000), "D3 按钮上的字跟着变");
  check(await pick("mimo", "mimo-v2.5-pro"), "D4 再点 MiMo 的 pro ⇒ 配置里的当前模型真的变了");
  cfg = readCfg();
  check(cfg.model_presets["mimo-v2.5-pro"]?.provider === entryFor(cfg, CATALOG.mimo.apiBase),
    `D5 它指向 MiMo 的端点(预设 provider=${cfg.model_presets["mimo-v2.5-pro"]?.provider})`);
  check(readFileSync(join(home, ".openDesign", "key.txt"), "utf8").trim() === MIMO_KEY
        && readFileSync(dsKeyFile, "utf8").trim() === DS_KEY, "D6 换模型没碰任何 key 文件");

  // ── E ──
  await closeMenu();
  const html = await page.content();
  const aria = JSON.stringify(await page.locator("body").ariaSnapshot().catch(() => ""));
  for (const [name, k] of [["MiMo", MIMO_KEY], ["DeepSeek", DS_KEY]]) {
    for (const [where, text] of [["页面 HTML", html], ["无障碍树", aria], ["控制台", consoleLines.join("\n")]]) {
      check(!text.includes(k) && !text.includes(k.slice(0, 12)), `E ${name} 的 key 没出现在${where}里`);
    }
  }
  check(!JSON.stringify(readCfg()).includes(DS_KEY) && !JSON.stringify(readCfg()).includes(MIMO_KEY), "E 配置文件里没有 key 原文");
} catch (e) {
  console.log(`  FAIL - 场景本身崩了:${e?.stack || e}`);
  failures += 1;
} finally {
  try { await browser?.close(); } catch { /* 已经关了 */ }
  try { srv?.kill("SIGKILL"); } catch { /* 已经没了 */ }
  fakeShell.close();
  rmSync(tmp, { recursive: true, force: true });
}
console.log(failures ? `\n${failures} 条红` : "\n全绿");
process.exit(failures ? 1 : 0);
