// 项目页右侧面板 e2e(照 ZCode Side Pane)—— 真 chromium + 真 ds_web(聊天走不通也没关系,不需要网关)。
//
// 业主:"待办事项的图墙和项目助手也可以参考一下 zcode 的向右侧展开的设计" → 选了「项目页」:
// 变更记录占主位,「图片 · 文件」和「项目助手」收进右侧一块面板,标签切换,可收起、可拖宽。
//
// 覆盖:
//   P1 默认:面板开着、停在「图片 · 文件」;开关 aria-expanded=true
//   P2 收起:面板整块隐藏、变更记录铺满;项目助手的聊天**仍挂着**(keep-mounted);刷新后仍是收起
//   P3 标签:点「项目助手」切过去;键盘 ← / → 在两个标签间切(roving tabindex,只有选中的能 Tab 到)
//   P4 拖左边缘调宽:变宽、夹在 65% 以内,刷新后宽度还在
//   P5 🔴 在「图片 · 文件」里点「登记参考图」(往项目助手发话)⇒ 面板自动切到「项目助手」
//
// 跑法:node tests/e2e/side_pane.e2e.mjs(自起 ds_web 于 8863)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8863;

const tmp = mkdtempSync(join(tmpdir(), "spane-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
mkdirSync(join(ws, "云栖别墅"), { recursive: true });
writeFileSync(join(dsRoot, "projects", "翡翠湾.md"), "# 翡翠湾\n\n- 阶段:方案\n\n## 变更\n- [待确认] 客厅吊顶改平顶(2026-09-20)\n");
writeFileSync(join(dsRoot, "config", "workspace.json"), JSON.stringify({ root: ws, projects: { 翡翠湾: "云栖别墅" } }));
// 已配 key 的机器(否则 App 一打开就跳去模型设置页,同 workspace_picker.e2e.mjs 夹具)
const home = join(tmp, "home");
const nbCfg = join(home, ".nanobot", "config.json");
mkdirSync(join(home, ".openDesign"), { recursive: true });
writeFileSync(join(home, ".openDesign", "key.txt"), "sk-e2e-side-pane\n");
mkdirSync(join(home, ".nanobot"), { recursive: true });
const template = readFileSync(join(ROOT, "config", "nanobot.config.windows.jsonc"), "utf8")
  .split("\n").filter((ln) => !/^\s*\/\//.test(ln)).join("\n");
writeFileSync(nbCfg, JSON.stringify(JSON.parse(template), null, 2));

let failures = 0;
let browser = null;
let srv = null;
const step = async (label, fn) => {
  console.log(`\n== ${label}`);
  try { await fn(); } catch (e) { failures += 1; console.log(`  not ok - ${label}: ${e.message}`); }
};

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
  const page = await browser.newPage({ viewport: { width: 1440, height: 860 } });
  await page.route("**/api/update/**", (r) => r.fulfill({ status: 200, body: "{}" }));
  await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
  const pane = page.locator('[data-ui="side-pane"]');
  const toggle = page.locator('[data-ui="side-pane-toggle"]');
  const tabFiles = page.locator('[data-ui="side-pane-tab-files"]');
  const tabAsst = page.locator('[data-ui="side-pane-tab-assistant"]');
  await toggle.waitFor({ timeout: 15000 });
  const box = (loc) => loc.evaluate((e) => { const b = e.getBoundingClientRect(); return { l: b.left, r: b.right, w: b.width }; });

  await step("P1 默认开着、停在「图片 · 文件」", async () => {
    check(await pane.isVisible(), "面板可见");
    check(await toggle.getAttribute("aria-expanded") === "true", "开关 aria-expanded=true");
    check(await tabFiles.getAttribute("aria-selected") === "true", "选中的是「图片 · 文件」");
    check(await page.locator("#spane-panel-files").isVisible(), "图片 · 文件那页可见");
    check(!(await page.locator("#spane-panel-assistant").isVisible()), "项目助手那页隐藏");
    check(await page.locator(".chatcol").count() === 1, "项目助手的聊天已经挂着(没切过去也在)");
  });

  await step("P2 收起:整块隐藏、变更记录铺满;聊天仍挂着;刷新后仍收起", async () => {
    const mainBefore = await box(page.locator(".ws-main"));
    await toggle.click();
    check(!(await pane.isVisible()), "面板收起");
    check(await toggle.getAttribute("aria-expanded") === "false", "开关 aria-expanded=false");
    const mainAfter = await box(page.locator(".ws-main"));
    check(mainAfter.w > mainBefore.w + 200, `变更记录变宽铺满(${Math.round(mainBefore.w)} → ${Math.round(mainAfter.w)})`);
    check(await page.locator(".chatcol").count() === 1, "收起后项目助手的聊天仍挂着(keep-mounted)");
    await page.reload({ waitUntil: "domcontentloaded" });
    await toggle.waitFor({ timeout: 15000 });
    check(await toggle.getAttribute("aria-expanded") === "false" && !(await pane.isVisible()), "刷新后仍是收起");
    await toggle.click();
    check(await pane.isVisible(), "再点展开");
  });

  await step("P3 标签:点「项目助手」切过去;键盘 ← / → 切;只有选中的那个能 Tab 到", async () => {
    await tabAsst.click();
    check(await tabAsst.getAttribute("aria-selected") === "true", "点了切到「项目助手」");
    check(await page.locator("#spane-panel-assistant").isVisible() && !(await page.locator("#spane-panel-files").isVisible()),
      "项目助手那页可见、图片 · 文件那页隐藏");
    check(await tabAsst.getAttribute("tabindex") === "0" && await tabFiles.getAttribute("tabindex") === "-1", "roving tabindex");
    await tabAsst.focus();
    await page.keyboard.press("ArrowLeft");
    check(await tabFiles.getAttribute("aria-selected") === "true", "← 回到「图片 · 文件」");
    check(await page.evaluate(() => document.activeElement?.dataset.ui) === "side-pane-tab-files", "焦点跟着移过去");
    await page.keyboard.press("ArrowRight");
    check(await tabAsst.getAttribute("aria-selected") === "true", "→ 到「项目助手」");
    await tabFiles.click();
  });

  await step("P4 拖左边缘调宽,夹在 65% 以内,刷新后宽度还在", async () => {
    const host = await box(page.locator(".ws-pane"));
    const before = await box(pane);
    const h = page.locator('[data-ui="side-pane-resize"]');
    const hb = await h.boundingBox();
    await page.mouse.move(hb.x + hb.width / 2, hb.y + hb.height / 2);
    await page.mouse.down();
    await page.mouse.move(hb.x - 150, hb.y + hb.height / 2, { steps: 5 });
    await page.mouse.up();
    const after = await box(pane);
    check(after.w > before.w + 100, `往左拖变宽(${Math.round(before.w)} → ${Math.round(after.w)})`);
    // 再往左拖到底:不超过 65%
    const hb2 = await h.boundingBox();
    await page.mouse.move(hb2.x + 2, hb2.y + 20);
    await page.mouse.down();
    await page.mouse.move(host.l + 10, hb2.y + 20, { steps: 5 });
    await page.mouse.up();
    const max = await box(pane);
    check(max.w <= host.w * 0.65 + 2, `最宽不超过 65%(${Math.round(max.w)} / ${Math.round(host.w)})`);
    await page.reload({ waitUntil: "domcontentloaded" });
    await pane.waitFor({ timeout: 15000 });
    const kept = await box(pane);
    check(Math.abs(kept.w - max.w) <= 2, `刷新后宽度还在(${Math.round(max.w)} → ${Math.round(kept.w)})`);
  });

  await step("P5 🔴 在「图片 · 文件」里点「登记参考图」(往项目助手发话)⇒ 自动切到「项目助手」", async () => {
    await tabFiles.click();
    check(await tabFiles.getAttribute("aria-selected") === "true", "前提:停在「图片 · 文件」");
    const reg = page.locator('[data-ui="empty-reg-ref"]');
    await reg.waitFor({ timeout: 10000 });
    await reg.click();
    await page.waitForFunction(() =>
      document.querySelector('[data-ui="side-pane-tab-assistant"]')?.getAttribute("aria-selected") === "true",
      null, { timeout: 5000 });
    check(await page.locator("#spane-panel-assistant").isVisible(), "项目助手那页可见 —— 发出去的话业主看得见");
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
