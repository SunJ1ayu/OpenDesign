// QA-执行试点的「操作录像」:主 agent 在真界面上把验收流程走一遍,每一步留截图 + 页面无障碍文本,
// 给 QA 腿(只读、跑不了浏览器)照着验收清单挑毛病,也给主裁对照 ZCode 亲看。**不是判据**,不进 run-all。
// 台面同 tests/e2e/model_settings.e2e.mjs:假外壳(应答重启 + prepare_gateway)+ 本机假厂商;**无外网出口**。
// 跑法(仓根):node tracks/opendesign-zcode-model-settings/evidence/qa-exec/tour.mjs
import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from "node:fs";
import { createServer } from "node:net";
import { createServer as createHttpServer } from "node:http";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..", "..", "..");
const { launchBrowser, waitConnected } = await import(join(ROOT, "tests", "e2e", "helpers.mjs"));
const { WS_STUB_BASE } = await import(join(ROOT, "tests", "e2e", "_ws-stub.mjs"));
const PY = process.env.PY || "/root/.venvs/design-studio/bin/python";
const PORT = 8859;
const OUT = HERE;
const MIMO_KEY = "tp-qa-tour-mimo-0123456789abcdef";
const DS_KEY = "sk-qa-tour-deepseek-0123456789ab";
const CUSTOM_KEY = "sk-qa-tour-custom-0123456789abcd";

const STUB = () => {
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
      setTimeout(() => { this.readyState = StubWS.OPEN; this.onopen?.({}); this._emit({ event: "ready", chat_id: "chat-qa" }); }, 10);
    }
    send() {}
  }
  window.WebSocket = StubWS;
};

const tmp = mkdtempSync(join(tmpdir(), "ds-qa-tour-"));
const dsRoot = join(tmp, "ds");
const home = join(tmp, "home");
const cfgPath = join(home, ".nanobot", "config.json");
mkdirSync(join(dsRoot, "projects", "20260701 王女士 翡翠湾 3#1801"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
mkdirSync(join(home, ".openDesign"), { recursive: true });
mkdirSync(dirname(cfgPath), { recursive: true });
const template = readFileSync(join(ROOT, "config", "nanobot.config.windows.jsonc"), "utf8")
  .split("\n").filter((ln) => !/^\s*\/\//.test(ln)).join("\n");
writeFileSync(cfgPath, JSON.stringify(JSON.parse(template), null, 2));

const HELLO = "OpenDesign.ds_shell_core.lock.v1\n";
const fakeShell = createServer((sock) => {
  let buf = "";
  sock.on("data", (b) => {
    buf += b.toString("utf8");
    if (buf.startsWith(HELLO) && buf.slice(HELLO.length).includes("\n")) {
      if (buf.slice(HELLO.length).split("\n")[0] === "RESTART-BACKEND") {
        sock.end("OK RESTART-BACKEND\n");
        setTimeout(() => spawnSync(PY, ["-c", `
import sys; sys.path.insert(0, ${JSON.stringify(join(ROOT, "bin"))})
import ds_credential
ds_credential.prepare_gateway(${JSON.stringify(home)}, ${JSON.stringify(cfgPath)})
`]), 1500);
      } else sock.end("OK\n");
    }
  });
});
await new Promise((r) => fakeShell.listen(0, "127.0.0.1", r));
const fakeVendor = createHttpServer((req, res) => {
  let raw = "";
  req.on("data", (b) => { raw += b; });
  req.on("end", () => {
    const body = JSON.parse(raw || "{}");
    const ok = req.headers.authorization === `Bearer ${CUSTOM_KEY}` && body.model === "gpt-4.1-mini";
    res.writeHead(ok ? 200 : 404, { "Content-Type": "application/json" });
    res.end(JSON.stringify(ok ? { choices: [{ message: { role: "assistant", content: "ok" } }] } : { error: { message: "model not found" } }));
  });
});
await new Promise((r) => fakeVendor.listen(0, "127.0.0.1", r));
const VENDOR_BASE = `http://127.0.0.1:${fakeVendor.address().port}/v1`;

const srv = spawn(PY, [join(ROOT, "bin", "ds_web.py")], {
  env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT), DS_NANOBOT_CONFIG: cfgPath, HOME: home,
         USERPROFILE: home, DS_LLM_KEY: "", DS_SHELL_LOCK_PORT: String(fakeShell.address().port),
         DS_WEB_DIST: join(ROOT, "web", "dist") },
  stdio: "ignore",
});
const base = `http://127.0.0.1:${PORT}`;
for (let i = 0; ; i++) {
  try { await fetch(`${base}/api/health`); break; } catch { if (i > 75) throw new Error("ds_web 起不来"); await new Promise((r) => setTimeout(r, 200)); }
}

const steps = [];
let n = 0;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function shot(page, title, note, { aria = true } = {}) {
  n += 1;
  const id = String(n).padStart(2, "0");
  await sleep(350);
  await page.screenshot({ path: join(OUT, `${id}.jpg`), type: "jpeg", quality: 72 });
  // 读屏树会吐出密码框里**正在输入的值** ⇒ 输入框里有 key 的那一步不取文本
  const text = aria ? String(await page.locator("body").ariaSnapshot().catch(() => "(取不到)")) : "(这一步输入框里有 key,不取读屏文本)";
  // 台面的临时目录会出现在「常规 · 数据与备份」里:换成占位(工件不许引用会话临时目录)
  steps.push({ id, title, note, url: page.url().replace(base, ""), aria: text.split(tmp).join("<临时目录>") });
  console.log(`  ${id} ${title}`);
}

const browser = await launchBrowser();
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.addInitScript(WS_STUB_BASE);
  await page.addInitScript(STUB);
  const MS = '[data-ui="model-settings"]';
  const detail = (id) => page.locator(`${MS} [data-ui="ms-detail"][data-provider="${id}"]`);

  await page.goto(`${base}/#/`, { waitUntil: "domcontentloaded" });
  await page.locator(MS).waitFor({ timeout: 15000 });
  await shot(page, "首次打开(一把 key 都没有)", "自动进「设置 · 模型设置」,右边是第一家 MiMo");

  await detail("mimo").locator('[data-ui="ms-key"]').fill(MIMO_KEY);
  await shot(page, "填 MiMo 的 key(还没点保存)", "输入框是密码框;「显示」只管正在输入的这把", { aria: false });
  await detail("mimo").locator('[data-ui="ms-key-save"]').click();
  await page.locator('[data-ui="ms-notice"]').waitFor();
  await shot(page, "MiMo 保存后", "提示正在重启后台;左栏 MiMo 圆点在重启完成前是黄的(未就绪)");
  await page.waitForFunction(() => document.querySelector('[data-provider="mimo"] [data-provider-status="ready"]'), null, { timeout: 15000 }).catch(() => {});
  await shot(page, "后台重启完成", "MiMo 变成就绪(绿点),状态句「在用 · 已存 …」");

  await page.locator('[data-ui="settings-toggle"]').click();
  await page.locator(".home-pane").waitFor({ state: "visible" });
  await waitConnected(page, ".home-pane");
  await shot(page, "返回工作区(首页)", "输入框右下角是模型按钮");
  const chip = '.home-pane .chat-card [data-ui="chat-model"]';
  await page.locator(chip).click();
  await page.locator('.home-pane [data-ui="chat-model-menu"]').waitFor();
  await shot(page, "点模型按钮", "向上弹;每家一行(当前那家 ✓ 和 ›),底行「管理模型」");
  await page.locator('.home-pane [data-ui="chat-model-vendor"][data-provider="mimo"]').hover();
  await page.locator('[data-ui="chat-model-sub"][data-provider="mimo"]').waitFor();
  await shot(page, "移到 MiMo", "向右弹出 MiMo 的模型(含 v2.6-pro / v2.6-flash),当前那个打勾");
  await page.locator('[data-ui="chat-model-sub"][data-provider="mimo"] [data-model-id="mimo-v2.6-pro"]').click();
  await sleep(800);
  await shot(page, "选了 mimo-v2.6-pro", "菜单收起,按钮上的字换成新模型");

  await page.locator(chip).click();
  await page.locator('.home-pane [data-ui="chat-model-manage"]').click();
  await page.locator(MS).waitFor();
  await shot(page, "点「管理模型」", "进设置页模型设置,落在当前那家 MiMo");
  await detail("mimo").locator('[data-ui="ms-add-model"]').click();
  await page.locator('[data-ui="ms-model-dialog"]').waitFor();
  await shot(page, "添加模型弹窗", "模型 ID + 上下文窗口");
  await page.locator('[data-ui="ms-model-id"]').fill("mimo v2.7");
  await page.locator('[data-ui="ms-dialog-save"]').click();
  await page.locator('[data-ui="ms-dialog-error"]').waitFor();
  await shot(page, "填错模型 ID(带空格)", "弹窗里说人话,不新增");
  await page.locator('[data-ui="ms-model-id"]').fill("mimo-v2.7-preview");
  await page.locator('[data-ui="ms-model-ctx"]').fill("262144");
  await page.locator('[data-ui="ms-dialog-save"]').click();
  await page.locator('[data-ui="ms-model-dialog"]').waitFor({ state: "hidden" });
  await shot(page, "加好了 mimo-v2.7-preview", "列表多一行,上下文 26.2万,有「删除」;内置模型没有「删除」");

  await page.locator(`${MS} [data-ui="ms-nav-item"][data-provider="deepseek"]`).click();
  await detail("deepseek").waitFor();
  await shot(page, "选 DeepSeek(还没填)", "状态句「还没填 API Key」,有「获取 API Key」链接");
  await detail("deepseek").locator('[data-ui="ms-key"]').fill(DS_KEY);
  await detail("deepseek").locator('[data-ui="ms-key-save"]').click();
  await page.locator('[data-ui="ms-notice"]').waitFor();
  await shot(page, "存 DeepSeek 的 key", "当前模型不变;提示正在重启后台");
  await page.waitForFunction(() => document.querySelector('[data-provider="deepseek"] [data-provider-status="ready"]'), null, { timeout: 15000 }).catch(() => {});
  await detail("deepseek").locator('[data-ui="ms-enable"]').click();
  await sleep(600);
  await shot(page, "禁用 DeepSeek", "圆点变灰,状态句「已禁用 …」,末四位还在");
  await detail("deepseek").locator('[data-ui="ms-enable"]').click();
  await sleep(600);
  await page.locator(`${MS} [data-ui="ms-nav-item"][data-provider="mimo"]`).click();
  await detail("mimo").locator('[data-ui="ms-enable"]').click();
  await page.locator('[data-ui="ms-notice"]').waitFor();
  await shot(page, "想禁用正在用的 MiMo", "拒绝并说为什么,开关不动");

  await page.locator(`${MS} [data-ui="ms-add-provider"]`).click();
  await page.locator('[data-ui="ms-provider-form"]').waitFor();
  await shot(page, "添加供应商表单", "名称 / Base URL / API Key / API 格式(只读)/ 每行一个模型");
  await page.locator('[data-ui="ms-pf-name"]').fill("冒充小米");
  await page.locator('[data-ui="ms-pf-base"]').fill("https://token-plan-cn.xiaomimimo.com/v1");
  await page.locator('[data-ui="ms-pf-models"]').fill("gpt-4.1-mini");
  await page.locator('[data-ui="ms-pf-save"]').click();
  await page.locator('[data-ui="ms-pf-error"]').waitFor();
  await shot(page, "Base URL 填成小米的", "拒收并说明");
  await page.locator('[data-ui="ms-pf-name"]').fill("公司中转");
  await page.locator('[data-ui="ms-pf-base"]').fill(VENDOR_BASE);
  await page.locator('[data-ui="ms-pf-key"]').fill(CUSTOM_KEY);
  await page.locator('[data-ui="ms-pf-models"]').fill("gpt-4.1-mini\nclaude-lite");
  await page.locator('[data-ui="ms-pf-save"]').click();
  await page.locator('[data-ui="ms-provider-form"]').waitFor({ state: "hidden" });
  await shot(page, "加好了「公司中转」", "左栏「自定义供应商」下多一家;右边是它的详情(名称、Base URL 可改,格式只读)");
  const cid = await page.locator(`${MS} [data-ui="ms-group"][data-group="custom"] [data-ui="ms-nav-item"]`).getAttribute("data-provider");
  await detail(cid).locator('[data-ui="ms-model"][data-model="gpt-4.1-mini"] [data-ui="ms-test"]').click();
  await page.waitForFunction(() => /成功|失败/.test(document.querySelector('[data-ui="ms-test-result"]')?.textContent || ""), null, { timeout: 15000 }).catch(() => {});
  await shot(page, "点「测试」(gpt-4.1-mini)", "不等重启就能测,显示连接成功");
  await detail(cid).locator('[data-ui="ms-model"][data-model="claude-lite"] [data-ui="ms-test"]').click();
  await page.waitForFunction(() => /失败/.test(document.querySelector('[data-ui="ms-test-result"]')?.textContent || ""), null, { timeout: 15000 }).catch(() => {});
  await shot(page, "点「测试」(claude-lite,假厂商没有这个模型)", "失败给可读原因");
  await sleep(2500);

  await page.locator('[data-ui="settings-toggle"]').click();
  await page.locator(".home-pane").waitFor({ state: "visible" });
  await page.locator(chip).click();
  await page.locator('.home-pane [data-ui="chat-model-menu"]').waitFor();
  await page.locator(`.home-pane [data-ui="chat-model-vendor"][data-provider="${cid}"]`).hover().catch(() => {});
  await sleep(400);
  await shot(page, "换模型菜单(三家)", "MiMo ✓、DeepSeek、公司中转;移到公司中转弹出它的两个模型");
  await page.keyboard.press("Escape");

  await page.locator(".side-footer .side-row").click();
  await page.locator('[data-ui="settings-general"]').waitFor();
  await shot(page, "设置 · 常规", "原来设置弹层里的各项;浏览器里显示版本与发布页");

  await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
  await page.locator(".ws-pane").waitFor({ state: "visible" });
  await waitConnected(page, ".ws-pane").catch(() => {});
  const wsChip = '.ws-pane [data-ui="chat-model"]';
  if (await page.locator(wsChip).isVisible().catch(() => false)) {
    await page.locator(wsChip).click();
    await page.locator('.ws-pane [data-ui="chat-model-vendor"][data-provider="mimo"]').hover().catch(() => {});
    await sleep(400);
    await shot(page, "项目页右栏的换模型菜单", "按钮贴着窗口右边:子菜单右边放不下时应翻到左边");
    await page.keyboard.press("Escape");
  }

  await page.setViewportSize({ width: 1024, height: 700 });
  await page.goto(`${base}/#/settings/models?provider=mimo`, { waitUntil: "domcontentloaded" });
  await page.locator(MS).waitFor();
  await shot(page, "窄窗口(1024×700)· 模型设置", "看左右两栏、按钮是否挤坏");
} finally {
  await browser.close();
  srv.kill("SIGKILL");
  fakeShell.close();
  fakeVendor.close();
  rmSync(tmp, { recursive: true, force: true });
}

const md = ["# QA-执行 操作录像(主 agent 在真界面上走一遍;截图 NN.jpg 同目录)", "",
  "台面:真 ds_web + 当前 web/dist;假外壳应答重启(1.5 秒后起好);本机假厂商(只认 gpt-4.1-mini)。key 都是假的。", ""];
for (const s of steps) {
  md.push(`## ${s.id} ${s.title}`, "", `- 地址:\`${s.url}\``, `- 这一步要看的:${s.note}`, `- 截图:${s.id}.jpg`, "",
    "页面无障碍文本(读屏看到的):", "", "```", s.aria.slice(0, 6000), "```", "");
}
writeFileSync(join(OUT, "tour.md"), md.join("\n"));
for (const k of [MIMO_KEY, DS_KEY, CUSTOM_KEY]) {
  if (md.join("\n").includes(k) || md.join("\n").includes(k.slice(0, 12))) { console.error("🔴 录像文本里出现了 key"); process.exit(3); }
}
console.log(`录像 ${steps.length} 步 → ${join(OUT, "tour.md")}`);
process.exit(0);
