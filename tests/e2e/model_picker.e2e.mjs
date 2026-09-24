// 判据:输入框里的模型按钮(track opendesign-composer-model-picker)的端到端。
// 真 chromium + 真 ds_web(自己的临时 nanobot 配置,**绝不碰机器上的真配置**)+ stub 掉 ws/bootstrap。
// 编号权威表在 tracks/opendesign-composer-model-picker/design.md。主 agent 亲写。
//
// 为什么必须有这一份(纯逻辑判据 mp 与后端判据 lm 接不住的):
//   modelPicker.ts 的菜单可以字字正确而 ChatPage 压根没渲染它;后端 POST 可以正确而按钮没调它;
//   按钮可以换了字而配置文件没变。这里问的是**业主眼前和盘上**到底发生了什么。
//
// 判据锁死的假绿路线:
//   ① 按钮换了字、后端没写 ⇒ 读配置文件本身。
//   ② 旧头部还在、只是多加了一个按钮 ⇒ 断言页面上没有 .chat-meta、没有「退出登录」。
//   ③ 重连中也挂着绿点 = 界面谎称已连接 ⇒ 掐断后断言按钮不出现(chat_reconnect 那条语义保留)。
//
// 09-24 起菜单照 ZCode 两级弹框(track opendesign-zcode-model-settings,旧→新对照在它的 verify.md):
//   ⑦ 改问「厂商行 ✓ + 底行管理模型」,并新增 ⑦b 子菜单在厂商行右边、⑦c 斜着移进子菜单不闪退(QA A23);
//   ⑧ 在子菜单里点;⑫「换厂商 / 换 key…」→「管理模型」进设置页这家。其余原样。
//
// 跑法:node tests/e2e/model_picker.e2e.mjs(自起 ds_web 于 8844;不需要 nanobot)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, waitConnected } from "./helpers.mjs";
import { WS_STUB_BASE } from "./_ws-stub.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8844;
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
    return origFetch(url, init);   // /api/llm/models、/api/llm/model 走真 ds_web
  };
  class StubWS extends window.__BaseStubWS {
    constructor(url) {
      super(url);
      window.__wsAll.push(this);
      setTimeout(() => {
        if (this.readyState === StubWS.CLOSED) return;
        if (window.__failConnect) {
          this.readyState = StubWS.CLOSED;
          this.onclose?.({ code: 1006, reason: "stub fail", wasClean: false });
          return;
        }
        this.readyState = StubWS.OPEN;
        this.onopen?.({});
        this._emit({ event: "ready", chat_id: `chat-mp-${window.__wsAll.length}` });
      }, 10);
    }
    send() { /* 这个场景不聊天 */ }
  }
  window.WebSocket = StubWS;
  window.__killAll = () => {
    window.__failConnect = true;
    for (const ws of window.__wsAll) {
      if (ws.readyState === StubWS.CLOSED) continue;
      ws.readyState = StubWS.CLOSED;
      ws.onclose?.({ code: 1006, reason: "stub kill", wasClean: false });
    }
  };
};

// ── 临时台面:数据根 / 家目录(带 key,免得 key 卡片自动弹出)/ nanobot 配置(出货模板,MiMo 形态)──
const tmp = mkdtempSync(join(tmpdir(), "ds-e2e-model-picker-"));
const dsRoot = join(tmp, "ds");
const home = join(tmp, "home");
const cfgPath = join(home, ".nanobot", "config.json");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
mkdirSync(join(tmp, "ws"), { recursive: true });
writeFileSync(join(dsRoot, "config", "workspace.json"), JSON.stringify({ root: join(tmp, "ws"), projects: {} }));
mkdirSync(join(home, ".openDesign"), { recursive: true });
writeFileSync(join(home, ".openDesign", "key.txt"), "sk-e2e-model-picker\n");
mkdirSync(dirname(cfgPath), { recursive: true });
const template = readFileSync(join(ROOT, "config", "nanobot.config.windows.jsonc"), "utf8")
  .split("\n").filter((ln) => !/^\s*\/\//.test(ln)).join("\n");
writeFileSync(cfgPath, JSON.stringify(JSON.parse(template), null, 2));
const modelPresetOnDisk = () => JSON.parse(readFileSync(cfgPath, "utf8")).agents.defaults.modelPreset;

const pane = ".home-pane";
const chip = `${pane} .chat-card [data-ui="chat-model"]`;
const menu = `${pane} [data-ui="chat-model-menu"]`;
let browser = null;
let srv = null;
try {
  check(modelPresetOnDisk() === "mimo-v2.5", "前置:临时配置里的默认模型是 mimo-v2.5");
  srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
    env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT), DS_NANOBOT_CONFIG: cfgPath,
           HOME: home, USERPROFILE: home },
    stdio: ["ignore", "inherit", "inherit"],
  });
  const base = `http://127.0.0.1:${PORT}`;
  for (let i = 0; ; i++) {
    try { await fetch(`${base}/api/health`); break; }
    catch {
      if (i > 50) throw new Error("ds_web 起不来");
      await new Promise((r) => setTimeout(r, 200));
    }
  }

  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  const errs = [];
  page.on("pageerror", (e) => errs.push(String(e)));
  const posts = [];
  page.on("request", (r) => { if (r.method() === "POST" && r.url().includes("/api/llm/model")) posts.push(r.url()); });
  await page.addInitScript(WS_STUB_BASE);
  await page.addInitScript(STUB);
  await page.goto(`${base}/#/`, { waitUntil: "domcontentloaded" });
  await page.locator(pane).waitFor({ state: "visible", timeout: 10000 });
  await waitConnected(page, pane);

  // ── 位置与去掉的东西 ────────────────────────────────────────────────────
  check(await until(async () => (await page.locator(chip).innerText()).includes("mimo-v2.5")),
    "① 连上后,输入卡里出现模型按钮,写着当前模型 mimo-v2.5");
  const chipBox = await page.locator(chip).boundingBox();
  const sendBox = await page.locator(`${pane} .chat-card .send-btn`).boundingBox();
  check(chipBox && sendBox && chipBox.x + chipBox.width <= sendBox.x + 1 && Math.abs(
    (chipBox.y + chipBox.height / 2) - (sendBox.y + sendBox.height / 2)) < 12,
  "② 按钮在发送键左边、同一行(业主拍板的位置)");
  check(await page.locator(".chat-meta").count() === 0, "③ 左上角「已连接 · 模型名」那一行没了");
  check(!(await page.locator("body").innerText()).includes("退出登录"), "④ 页面上没有「退出登录」");

  // ── 菜单 ──────────────────────────────────────────────────────────────
  await page.locator(chip).click();
  check(await until(() => page.locator(menu).isVisible(), 5000), "⑤ 点按钮弹出菜单");
  const menuBox = await page.locator(menu).boundingBox();
  const chipBox2 = await page.locator(chip).boundingBox();
  check(menuBox && chipBox2 && menuBox.y + menuBox.height <= chipBox2.y + 1, "⑥ 菜单向上弹(在按钮上方)");
  const menuText = await page.locator(menu).innerText();
  const vendor = page.locator(`${menu} [data-ui="chat-model-vendor"][data-provider="mimo"]`);
  check(menuText.includes("MiMo") && menuText.includes("管理模型") && !menuText.includes("换厂商")
        && await vendor.getAttribute("data-selected") === "true",
    "⑦ 菜单里是厂商一行(MiMo,当前那家打勾)和底行「管理模型」;旧的「换厂商 / 换 key…」没了");
  const sub = page.locator(`[data-ui="chat-model-sub"][data-provider="mimo"]`);
  await vendor.hover();
  check(await until(() => sub.isVisible(), 5000), "⑦a 移到厂商行 ⇒ 弹出这家的模型");
  const vBox = await vendor.boundingBox();
  const sBox = await sub.boundingBox();
  check(vBox && sBox && sBox.x >= vBox.x + vBox.width - 8, "⑦b 模型子菜单在厂商行右边(照 ZCode 向右弹)");
  // ⑦c QA A23:从厂商行**斜着**移进子菜单(途中擦过菜单里别的行)子菜单不许闪退。
  //     09-24 判据修:① 第一版用多元素 locator 取 innerText,Playwright 严格模式必抛 ⇒ 这一问恒红、问不出东西;
  //     ② 第一版轨迹从厂商行右沿直进子菜单,一行都没擦过 ⇒ 问不到"擦过别的行会不会收"。
  //     现在:从厂商行左侧出发、瞄子菜单**最后一行**(轨迹必然往下擦过底行「管理模型」),先证明真擦过了,
  //     再等过宽限期(>200ms)看子菜单还在 —— 等不够就问不出"过一会儿才收"。
  const lastItem = sub.locator("[data-model-id]").last();
  const tBox = await lastItem.boundingBox();
  await page.evaluate(() => {
    window.__crossedManage = false;
    document.querySelector('[data-ui="chat-model-manage"]')
      ?.addEventListener("mouseenter", () => { window.__crossedManage = true; }, { once: true });
  });
  if (vBox && tBox) {
    await page.mouse.move(vBox.x + 20, vBox.y + vBox.height / 2);
    await page.mouse.move(tBox.x + tBox.width / 2, tBox.y + tBox.height / 2, { steps: 16 });
  }
  const crossed = await page.evaluate(() => window.__crossedManage === true);
  check(crossed, "⑦c 前提:轨迹确实擦过了底行「管理模型」(没擦过 = 下一问问不出东西)");
  await page.waitForTimeout(450);
  check(crossed && await sub.isVisible() && (await sub.locator("[data-model-id]").count()) > 0
        && (await page.locator(`${menu} [data-ui="chat-model-sub"] [data-model-id="mimo-v2.5"]`).getAttribute("aria-checked")) === "true",
    "⑦c 斜着移进子菜单(擦过别的行)不闪退,过了宽限期还在;当前模型那行打勾");
  const target = page.locator(`[data-ui="chat-model-sub"][data-provider="mimo"] [data-model-id="mimo-v2.5-pro"]`);

  // ── 选中 ⇒ 真写配置 ⇒ 按钮换字 ────────────────────────────────────────
  await target.click();
  check(await until(() => modelPresetOnDisk() === "mimo-v2.5-pro", 8000), "⑧ 选 mimo-v2.5-pro ⇒ 盘上的配置真的改了");
  check(posts.length === 1, `⑨ 恰好发出一次 POST /api/llm/model(实际 ${posts.length})`);
  check(await until(async () => (await page.locator(chip).innerText()).includes("mimo-v2.5-pro"), 8000),
    "⑩ 按钮上的字变成 mimo-v2.5-pro");
  check(!(await page.locator(menu).isVisible()), "⑪ 选完菜单收起");

  // ── ⑯ 项目页右栏(窄):长模型名不许把「发送」挤出输入卡、不许把「记一下」挤成两行 ─────────
  //     09-24 QA-执行录像第 24 步主裁亲看抓到:当前模型换成 mimo-v2.5-pro / v2.6-pro 这类长名字后,
  //     右栏输入卡里「发送」被切掉一半、「记一下」折成两行。此刻按钮上正是长名字(⑩)。
  await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
  await page.locator(".ws-pane").waitFor({ state: "visible", timeout: 10000 });
  await waitConnected(page, ".ws-pane");
  const wsCard = page.locator(".ws-pane .chat-card").first();
  const cardBox = await wsCard.boundingBox();
  const sendWs = await wsCard.locator(".send-btn").boundingBox();
  const noteWs = await wsCard.locator(".tool-chip").first().boundingBox();
  const chipWs = await wsCard.locator('[data-ui="chat-model"]').boundingBox();
  check(cardBox && sendWs && sendWs.x >= cardBox.x && sendWs.x + sendWs.width <= cardBox.x + cardBox.width + 0.5
        && noteWs && noteWs.height <= 30 && chipWs && chipWs.x + chipWs.width <= sendWs.x + 1,
    `⑯ 右栏输入卡:「发送」整个在卡里、「记一下」一行、模型按钮不压「发送」(卡 ${JSON.stringify(cardBox)} 发送 ${JSON.stringify(sendWs)} 记一下 ${JSON.stringify(noteWs)})`);
  await page.goto(`${base}/#/`, { waitUntil: "domcontentloaded" });
  await page.locator(chip).waitFor({ state: "visible", timeout: 10000 });

  // ── 管理模型 ⇒ 设置页 · 模型设置,落在当前那家 ────────────────────────
  await page.locator(chip).click();
  await page.locator(menu).waitFor({ state: "visible", timeout: 5000 });
  await page.locator(`${menu} [data-ui="chat-model-manage"]`).click();
  check(await until(() => page.locator('[data-ui="model-settings"] [data-ui="ms-detail"][data-provider="mimo"]').isVisible(), 5000)
        && /#\/settings\/models/.test(page.url()),
    "⑫ 「管理模型」打开设置页的模型设置,右边是当前那家(MiMo)");
  await page.locator('[data-ui="settings-toggle"]:visible').click();
  await page.locator(chip).waitFor({ state: "visible", timeout: 5000 });

  // ── 断线 ⇒ 按钮不许挂着 ────────────────────────────────────────────────
  await page.evaluate(() => window.__killAll());
  check(await until(() => page.locator(`${pane} [data-ui="chat-reconnecting"]`).isVisible(), 8000),
    "⑬ 前置:掐断后出现「正在重连」");
  check(!(await page.locator(chip).isVisible()), "⑭ 重连中模型按钮不出现(不许谎称已连接)");

  check(errs.length === 0, `⑮ 全程没有页面级 JS 报错${errs.length ? ":" + errs[0] : ""}`);
} catch (e) {
  console.error("FAIL(异常):", e);
  failures += 1;
} finally {
  if (browser) await browser.close();
  if (srv) srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}

console.log(failures === 0 ? "\nALL PASS" : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
