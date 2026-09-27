// 业主手动选工作区 e2e —— track opendesign-workspace-picker。真 chromium + 真 ds_web。
//
// 以前工作区只能靠助手设;接好之后界面上没有地方换。现在:设置页「项目文件夹」/ 项目页「接入工作区」
// → 选文件夹(桌面版弹系统对话框,浏览器里手填)→ 预览三种摆法各认出几个项目 → 接入。
//
// 覆盖:
//   W1 浏览器里(没有外壳):设置页 → 手填路径 → 预览(有总夹时默认选它,写着认出几个、叫什么)→ 接入 →
//      配置真的写了、设置页那一行显示新路径
//   W2 桌面版:点「更换」直接弹系统对话框(替身返回一个没有总夹的文件夹)→ 默认选"直接放在这里"→ 接入
//   W3 桌面版:对话框里点了取消 ⇒ 什么都不改、弹窗关掉
//   W4 项目页「接入工作区」打开的是这个对话框,**不再**往聊天里发话
//   W5 (PR #4 审查)「01-项目」是软链接:预览说认出几个,接入后就是几个(以前预览 2、接入后 0)
//   W6 (PR #4 三审)手填路径看过 A 再改成 B:A 的预览作废、「接入」写的是 B;A 的慢请求晚回来也不盖掉 B
//
// 跑法:node tests/e2e/workspace_picker.e2e.mjs(自起 ds_web 于 8861)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync, existsSync, symlinkSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8861;

const tmp = mkdtempSync(join(tmpdir(), "wspick-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");          // 有「01-项目」总夹
const flat = join(tmp, "flat");      // 项目直接摆着
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
for (const p of ["01-项目/甲", "01-项目/乙", "2026/丙", "散项目"]) mkdirSync(join(ws, p), { recursive: true });
for (const p of ["戊", "己", "庚"]) mkdirSync(join(flat, p), { recursive: true });
writeFileSync(join(dsRoot, "projects", "翡翠湾.md"), "# 翡翠湾\n\n- 阶段:方案\n");
const cfgPath = join(dsRoot, "config", "workspace.json");
// 已配 key 的机器(否则 App 一打开就跳去模型设置页,同 chat_model_error.e2e.mjs 夹具)
const home = join(tmp, "home");
const nbCfg = join(home, ".nanobot", "config.json");
mkdirSync(join(home, ".openDesign"), { recursive: true });
writeFileSync(join(home, ".openDesign", "key.txt"), "sk-e2e-workspace-picker\n");
mkdirSync(join(home, ".nanobot"), { recursive: true });
const template = readFileSync(join(ROOT, "config", "nanobot.config.windows.jsonc"), "utf8")
  .split("\n").filter((ln) => !/^\s*\/\//.test(ln)).join("\n");
writeFileSync(nbCfg, JSON.stringify(JSON.parse(template), null, 2));

/** 桌面外壳替身:shellApi 认它所需的全套方法 + pickFolder(由 window.__pickResult 决定选了什么)。 */
const SHELL_STUB = () => {
  window.__pickCalls = [];
  window.__pickResult = null;
  const noop = () => Promise.resolve(null);
  window.odShell = {
    minimize: noop, toggleMaximize: () => Promise.resolve({ maximized: false }), close: noop,
    windowState: () => Promise.resolve({ maximized: false }), onWindowState: () => () => {},
    reportStartup: () => {},
    pickFolder: (d) => { window.__pickCalls.push(d ?? ""); return Promise.resolve(window.__pickResult); },
    update: { check: noop, install: noop, state: () => Promise.resolve({ phase: "idle" }), onState: () => () => {} },
  };
};

let failures = 0;
let browser = null;
let srv = null;
const step = async (label, fn) => {
  console.log(`\n== ${label}`);
  try { await fn(); } catch (e) { failures += 1; console.log(`  not ok - ${label}: ${e.message}`); }
};
const cfg = () => (existsSync(cfgPath) ? JSON.parse(readFileSync(cfgPath, "utf-8")) : null);

try {
  srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
    env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT), DS_NANOBOT_CONFIG: nbCfg,
           HOME: home, USERPROFILE: home },
    stdio: ["ignore", "inherit", "inherit"],
  });
  const base = `http://127.0.0.1:${PORT}`;
  for (let i = 0; ; i++) {
    try { await fetch(`${base}/api/health`); break; }
    catch { if (i > 50) throw new Error("ds_web 起不来"); await new Promise((r) => setTimeout(r, 200)); }
  }
  browser = await launchBrowser();

  await step("W1 浏览器里:设置页 → 手填路径 → 预览 → 接入", async () => {
    const page = await browser.newPage({ viewport: { width: 1300, height: 860 } });
    await page.route("**/api/update/**", (r) => r.fulfill({ status: 200, body: "{}" }));
    await page.goto(`${base}/#/settings/general`, { waitUntil: "domcontentloaded" });
    const row = page.locator('[data-ui="settings-workspace-root"]');
    await row.waitFor({ timeout: 15000 });
    check((await row.innerText()).includes("还没接入"), "没接时这一行说「还没接入」");
    await row.click();
    await page.locator('[data-ui="ws-picker-input"]').fill(ws);
    await page.locator('[data-ui="ws-picker"] button[type="submit"]').click();
    await page.locator('[data-ui="ws-picker-layout"]').first().waitFor({ timeout: 10000 });
    const sel = page.locator('[data-ui="ws-picker-layout"][aria-checked="true"]');
    check(await sel.getAttribute("data-layout") === "auto", "有「01-项目」总夹时默认选它");
    const selText = await sel.innerText();
    check(selText.includes("认出 2 个") && selText.includes("甲") && selText.includes("乙"),
      `写着认出几个、叫什么:${JSON.stringify(selText)}`);
    check((await page.locator('[data-ui="ws-picker"]').innerText()).includes("上传") ||
          (await page.locator('[data-ui="ws-picker"]').innerText()).includes("发给大模型"),
      "影响面写在对话框里(接入后助手能读这里的资料)");
    check(cfg() === null, "预览不写任何东西");
    await page.locator('[data-ui="ws-picker-apply"]').click();
    const done = page.locator('[data-ui="ws-picker-done"]');
    await done.waitFor({ timeout: 10000 });
    check((await done.innerText()).includes("认出 2 个项目"), "接入后告诉业主认出几个");
    const c = cfg();
    check(c && c.projectsDir === "01-项目", `配置真的写了:${JSON.stringify(c)}`);
    await page.locator('[data-ui="ws-picker"] .btn-primary').click();
    await page.waitForFunction(() => document.querySelector('[data-ui="settings-workspace-root"]')?.innerText.includes("更换"),
      null, { timeout: 8000 });
    check((await row.innerText()).includes("ws"), "设置页那一行显示新路径");
    await page.close();
  });

  await step("W2 桌面版:点「更换」直接弹系统对话框 → 没有总夹时默认「直接放在这里」→ 接入", async () => {
    const page = await browser.newPage({ viewport: { width: 1300, height: 860 } });
    await page.route("**/api/update/**", (r) => r.fulfill({ status: 200, body: "{}" }));
    await page.addInitScript(SHELL_STUB);
    await page.addInitScript((p) => { window.__pickResult = p; }, flat);
    // 把"现在接的是哪个文件夹"拖慢 1.2 秒:业主一进设置页就点「更换」的竞态,每次都复现
    // (以前对话框会从空路径打开 —— 云沙箱里这条偶发红过一次,就是它)
    await page.route("**/api/workspace/health", async (r) => {
      await new Promise((res) => setTimeout(res, 1200));
      await r.continue();
    });
    await page.goto(`${base}/#/settings/general`, { waitUntil: "domcontentloaded" });
    await page.locator('[data-ui="settings-workspace-root"]').click();
    // 加载中业主手快点「选择文件夹…」(PR #4 二审):按钮是灰的,点了也不弹;加载完只自动弹一次
    const choose = page.locator('[data-ui="ws-picker-choose"]');
    await choose.waitFor({ timeout: 5000 });
    check(await choose.isDisabled(), "当前文件夹还没拉到时「选择文件夹…」是灰的");
    await choose.click({ force: true, timeout: 2000 }).catch(() => {});
    check((await page.evaluate(() => window.__pickCalls)).length === 0, "加载中点了也不以空路径弹对话框");
    await page.locator('[data-ui="ws-picker-layout"]').first().waitFor({ timeout: 10000 });
    await page.waitForTimeout(400);
    check(await page.locator('[data-ui="ws-picker-input"]').count() === 0, "桌面版不让手填,用系统对话框");
    const calls = await page.evaluate(() => window.__pickCalls);
    check(calls.length === 1 && calls[0].endsWith("ws"), `对话框从现在的文件夹打开:${JSON.stringify(calls)}`);
    check(await page.locator('[data-layout="auto"]').count() === 0, "没有总夹时不列「都放在总夹里」");
    const sel = page.locator('[data-ui="ws-picker-layout"][aria-checked="true"]');
    check(await sel.getAttribute("data-layout") === "direct", "默认选「直接放在这个文件夹里」");
    await page.locator('[data-ui="ws-picker-apply"]').click();
    await page.locator('[data-ui="ws-picker-done"]').waitFor({ timeout: 10000 });
    const c = cfg();
    check(c && c.root.endsWith("flat") && c.projectsDir === ".", `换到新根、旧的「01-项目」没残留:${JSON.stringify(c)}`);
    await page.close();
  });

  await step("W3 桌面版:对话框里点取消 ⇒ 什么都不改、弹窗关掉", async () => {
    const before = readFileSync(cfgPath, "utf-8");
    const page = await browser.newPage({ viewport: { width: 1300, height: 860 } });
    await page.route("**/api/update/**", (r) => r.fulfill({ status: 200, body: "{}" }));
    await page.addInitScript(SHELL_STUB);          // __pickResult = null ⇒ 取消
    await page.goto(`${base}/#/settings/general`, { waitUntil: "domcontentloaded" });
    await page.locator('[data-ui="settings-workspace-root"]').click();
    await page.waitForTimeout(800);
    check(await page.locator('[data-ui="ws-picker"]').count() === 0, "弹窗关掉了");
    check(readFileSync(cfgPath, "utf-8") === before, "配置一个字节都没动");
    await page.close();
  });

  await step("W4 项目页「接入工作区」打开的是这个对话框,不再往聊天里发话", async () => {
    rmSync(cfgPath, { force: true });                  // 回到"还没接入"
    const page = await browser.newPage({ viewport: { width: 1300, height: 860 } });
    await page.route("**/api/update/**", (r) => r.fulfill({ status: 200, body: "{}" }));
    const wsFrames = [];
    page.on("websocket", (w) => w.on("framesent", (f) => wsFrames.push(String(f.payload))));
    await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
    const btn = page.locator('[data-ui="connect-workspace"]');
    await btn.waitFor({ timeout: 15000 });
    await btn.click();
    await page.locator('[data-ui="ws-picker"]').waitFor({ timeout: 5000 });
    check(true, "点了打开选文件夹对话框");
    check(!wsFrames.some((f) => f.includes("接进来")), "没有往聊天里发「把我的项目文件夹接进来」");
    await page.close();
  });
  await step("W5 「01-项目」是软链接:预览认出几个,接入后就是几个", async () => {
    const lnRoot = join(tmp, "linked");
    const real = join(lnRoot, "真实的项目夹");
    for (const p of ["辛", "壬"]) mkdirSync(join(real, p), { recursive: true });
    try {
      symlinkSync(real, join(lnRoot, "01-项目"), "dir");
    } catch (e) {
      console.log(`  (跳过:这台机器建不了软链接 —— ${e.code})`);
      return;
    }
    const page = await browser.newPage({ viewport: { width: 1300, height: 860 } });
    await page.route("**/api/update/**", (r) => r.fulfill({ status: 200, body: "{}" }));
    await page.goto(`${base}/#/settings/general`, { waitUntil: "domcontentloaded" });
    await page.locator('[data-ui="settings-workspace-root"]').click();
    await page.locator('[data-ui="ws-picker-input"]').fill(lnRoot);
    await page.locator('[data-ui="ws-picker"] button[type="submit"]').click();
    const sel = page.locator('[data-ui="ws-picker-layout"][aria-checked="true"]');
    await sel.waitFor({ timeout: 10000 });
    const selText = await sel.innerText();
    check(await sel.getAttribute("data-layout") === "auto" && selText.includes("「01-项目」"),
      `总夹名是根下那一项的名字「01-项目」,不是链接目标的名字:${JSON.stringify(selText)}`);
    check(selText.includes("认出 2 个"), "预览认出 2 个");
    await page.locator('[data-ui="ws-picker-apply"]').click();
    const done = page.locator('[data-ui="ws-picker-done"]');
    await done.waitFor({ timeout: 10000 });
    check((await done.innerText()).includes("认出 2 个项目"), `接入后也是 2 个:${JSON.stringify(await done.innerText())}`);
    await page.close();
  });
  await step("W6 (PR #4 三审)手填:看过 A 再改成 B ⇒ A 的预览作废;A 的请求晚回来也不盖掉 B", async () => {
    const page = await browser.newPage({ viewport: { width: 1300, height: 860 } });
    await page.route("**/api/update/**", (r) => r.fulfill({ status: 200, body: "{}" }));
    await page.goto(`${base}/#/settings/general`, { waitUntil: "domcontentloaded" });
    await page.locator('[data-ui="settings-workspace-root"]').click();
    const input = page.locator('[data-ui="ws-picker-input"]');
    const look = page.locator('[data-ui="ws-picker"] button[type="submit"]');
    const apply = page.locator('[data-ui="ws-picker-apply"]');
    const layouts = page.locator('[data-ui="ws-picker-layout"]');
    // ① 看过 A,改成 B 不点「看看」:A 的预览必须消失、「接入」不能点(以前点了写进去的是 A)
    await input.fill(ws);
    await look.click();
    await layouts.first().waitFor({ timeout: 10000 });
    await input.fill(flat);
    check(await layouts.count() === 0, "改了路径,旧预览就撤掉");
    check(await apply.isDisabled(), "改了路径没重新预览,「接入」点不了");
    await look.click();
    await layouts.first().waitFor({ timeout: 10000 });
    check((await page.locator('[data-ui="ws-picker"] [role="radiogroup"]').innerText()).includes("戊"),
      "重新预览的是 B");
    await apply.click();
    await page.locator('[data-ui="ws-picker-done"]').waitFor({ timeout: 10000 });
    const c = cfg();
    check(c && c.root.endsWith("flat"), `写进去的是 B,不是 A:${JSON.stringify(c && c.root)}`);
    await page.close();

    // ② A 的预览请求拖慢,期间改成 B 并预览:A 晚回来后界面上仍是 B
    const p2 = await browser.newPage({ viewport: { width: 1300, height: 860 } });
    await p2.route("**/api/update/**", (r) => r.fulfill({ status: 200, body: "{}" }));
    await p2.route("**/api/workspace/root/preview", async (r) => {
      if ((r.request().postData() || "").includes("flat")) return r.continue();
      await new Promise((res) => setTimeout(res, 1500));
      await r.continue();
    });
    await p2.goto(`${base}/#/settings/general`, { waitUntil: "domcontentloaded" });
    await p2.locator('[data-ui="settings-workspace-root"]').click();
    const in2 = p2.locator('[data-ui="ws-picker-input"]');
    const look2 = p2.locator('[data-ui="ws-picker"] button[type="submit"]');
    await in2.fill(ws);
    await look2.click();
    await in2.fill(flat);
    await look2.click();
    await p2.locator('[data-ui="ws-picker-layout"]').first().waitFor({ timeout: 10000 });
    await p2.waitForTimeout(2200);                   // 等 A 那条慢请求回来
    const txt = await p2.locator('[data-ui="ws-picker"] [role="radiogroup"]').innerText();
    check(txt.includes("戊") && !txt.includes("甲"), `晚回来的 A 没盖掉 B:${JSON.stringify(txt)}`);
    check(await p2.locator('[data-layout="auto"]').count() === 0, "没有 A 才有的「都放在总夹里」");
    await p2.close();
  });
} catch (e) {
  failures += 1;
  console.log(`  not ok - 场景中断: ${e.message}`);
} finally {
  if (browser) await browser.close();
  if (srv) srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}

console.log(failures === 0 ? "\nALL PASS" : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
