// 外观切换 e2e —— 真 chromium + 真 ds_web。PR #5 审查:三个选项标了 role=radio,
// 却不能用方向键切、三个都进 Tab 顺序,与单选组交互不符。这里用真键盘走一遍。
//
// 覆盖:
//   T1 进设置页默认深色:<html data-theme=dark>,只有「深色」可 Tab 到(roving tabindex)
//   T2 键盘:→ 选中并聚焦「浅色」、页面立刻变浅;→ 跟随系统;→ 回到深色(循环);← / Home / End
//   T3 Tab 从单选组出去只要一下(不在三个选项之间逐个停)
//   T4 选了浅色后刷新:还是浅色(第一帧就是,不靠 React 再设)
//
// 跑法:node tests/e2e/theme_switch.e2e.mjs(自起 ds_web 于 8862)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8862;

const tmp = mkdtempSync(join(tmpdir(), "theme-e2e-"));
const dsRoot = join(tmp, "ds");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
// 已配 key 的机器(否则 App 一打开就跳去模型设置页,同 workspace_picker.e2e.mjs 夹具)
const home = join(tmp, "home");
const nbCfg = join(home, ".nanobot", "config.json");
mkdirSync(join(home, ".openDesign"), { recursive: true });
writeFileSync(join(home, ".openDesign", "key.txt"), "sk-e2e-theme\n");
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
  const page = await browser.newPage({ viewport: { width: 1300, height: 860 } });
  await page.route("**/api/update/**", (r) => r.fulfill({ status: 200, body: "{}" }));
  await page.goto(`${base}/#/settings/general`, { waitUntil: "domcontentloaded" });
  const group = page.locator('[data-ui="settings-appearance"] [role="radiogroup"]');
  await group.waitFor({ timeout: 15000 });
  const theme = () => page.evaluate(() => document.documentElement.dataset.theme);
  const checked = () => group.locator('[aria-checked="true"]').getAttribute("data-theme-opt");
  const focused = () => page.evaluate(() => document.activeElement?.getAttribute("data-theme-opt") ?? null);
  const tabbable = () => group.locator('[role="radio"][tabindex="0"]').evaluateAll((els) =>
    els.map((e) => e.getAttribute("data-theme-opt")));

  await step("T1 默认深色;只有选中的那一项进 Tab 顺序", async () => {
    check(await theme() === "dark", "默认深色");
    check(await checked() === "dark", "「深色」是选中的");
    const t = await tabbable();
    check(t.length === 1 && t[0] === "dark", `只有「深色」tabindex=0:${JSON.stringify(t)}`);
    check(await group.locator('[role="radio"][tabindex="-1"]').count() === 2, "另外两项 tabindex=-1");
  });

  await step("T2 真键盘:方向键移动并选中,页面随之变色;首尾循环;Home / End", async () => {
    // 从外观前面那个可聚焦的东西 Tab 进来 —— 落在选中的那一项上
    await page.locator('[data-ui="settings-nav-general"]').focus();
    for (let i = 0; i < 20 && (await focused()) === null; i++) await page.keyboard.press("Tab");
    check(await focused() === "dark", `Tab 进来落在选中的「深色」上(实际 ${await focused()})`);
    await page.keyboard.press("ArrowRight");
    check(await checked() === "light" && await focused() === "light", "→ 选中并聚焦「浅色」");
    check(await theme() === "light", "页面立刻变浅");
    check(JSON.stringify(await tabbable()) === '["light"]', "Tab 位跟着移到「浅色」");
    await page.keyboard.press("ArrowDown");
    check(await checked() === "system" && await focused() === "system", "↓ 到「跟随系统」");
    await page.keyboard.press("ArrowRight");
    check(await checked() === "dark", "→ 从最后一项回到第一项");
    await page.keyboard.press("ArrowLeft");
    check(await checked() === "system", "← 从第一项到最后一项");
    await page.keyboard.press("Home");
    check(await checked() === "dark" && await theme() === "dark", "Home 到「深色」");
    await page.keyboard.press("End");
    check(await checked() === "system", "End 到「跟随系统」");
    await page.keyboard.press("ArrowLeft");
    check(await checked() === "light", "← 回到「浅色」");
  });

  await step("T3 Tab 一下就离开单选组(不在三个选项之间逐个停)", async () => {
    await page.keyboard.press("Tab");
    const f = await focused();
    const inGroup = await page.evaluate(() =>
      !!document.activeElement?.closest('[data-ui="settings-appearance"] [role="radiogroup"]'));
    check(f === null && !inGroup, `Tab 之后焦点已不在外观单选组里(实际 ${f})`);
  });

  await step("T4 选了浅色后刷新,第一帧就是浅色", async () => {
    await page.reload({ waitUntil: "commit" });
    const early = await page.evaluate(() => document.documentElement.dataset.theme);
    check(early === "light", `刷新后 <html data-theme> 一开始就是 light(实际 ${early})`);
    await group.waitFor({ timeout: 15000 });
    check(await checked() === "light", "设置里显示的也是「浅色」");
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
