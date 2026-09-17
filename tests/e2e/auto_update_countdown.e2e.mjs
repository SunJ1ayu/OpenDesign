// track opendesign-auto-update-countdown e2e:打开软件时那条倒计时横幅,在业主眼前到底发生了什么。
// 真 chromium + 真 ds_web(不需要 gateway);`/api/update/check` 与 `/api/update/apply` 用 page.route 拦成替身。
// 主 agent 亲写,执行腿逐字节 off-limits。段名与问法的唯一权威在该 track 的 design.md(AC-A~F)。
//
// 🔴 为什么必须有这一份:ac1~ac8 只问「函数返回哪几个字」,au1~au12 只问「后端怎么答」。
//    业主怕的两件事 —— **点了取消它还是装了**、**不是打开软件那次也弹倒计时** —— 全在 App 的接线里,
//    单元判据一条都问不出来(0.91 窗口栏整块没画出来时 12 条判据全绿,是同一种盲区)。
//
// 跑法:node tests/e2e/auto_update_countdown.e2e.mjs(自起 ds_web 于 8846;要等几轮 10 秒倒计时,约 1 分钟)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8846;
const KEY = "翡翠湾-1801";
const SECONDS = 10;            // 与 update.ts 的 AUTO_UPDATE_SECONDS 同值(ac1 钉着那一边)
const PAST_COUNTDOWN = (SECONDS + 4) * 1000;

const tmp = mkdtempSync(join(tmpdir(), "auto-update-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");
const home = join(tmp, "home");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
mkdirSync(join(ws, "00-收件箱"), { recursive: true });
// HOME 隔离 + 一把假 key:否则"还没配 key"的卡片会自动弹出来,遮罩吃掉所有点击(tests/e2e/README.md)。
mkdirSync(join(home, ".openDesign"), { recursive: true });
writeFileSync(join(home, ".openDesign", "key.txt"), "sk-e2e-fixture\n");
writeFileSync(join(dsRoot, "projects", `${KEY}.md`), `# ${KEY}

- 业主: [[王女士]]
- 阶段: 施工跟进

## 变更记录

## 沟通日志

---
最后更新: 2026-09-17
`);
writeFileSync(join(dsRoot, "config", "workspace.json"),
  JSON.stringify({ root: ws, projectsDir: ".", projects: {} }));

const srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
  env: { ...process.env, HOME: home, USERPROFILE: home,
         DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT) },
  stdio: ["ignore", "inherit", "inherit"],
});
const base = `http://127.0.0.1:${PORT}`;
for (let i = 0; ; i++) {
  try { await fetch(`${base}/api/health`); break; }
  catch { if (i > 50) throw new Error("ds_web 起不来"); await new Promise((r) => setTimeout(r, 200)); }
}

let failures = 0;
async function step(name, fn) {
  console.log(`\n== ${name}`);
  try { await fn(); } catch (e) { failures++; console.error(`[${name}] ${String(e)}`); }
}
function expect(cond, label) {
  if (cond) { console.log(`  ok - ${label}`); return; }
  failures++;
  console.error(`  FAIL: ${label}`);
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function until(fn, ms = 10000) {
  const t0 = Date.now();
  for (;;) {
    if (await fn()) return true;
    if (Date.now() - t0 > ms) return false;
    await sleep(100);
  }
}

const ASSET = { name: "OpenDesign-Setup-0.99.0.exe", url: "https://x/y", size: 46000000,
                digest: "sha256:" + "ab".repeat(32) };
const ELIGIBLE = {
  current: "0.98.6", update_available: true, latest: "0.99.0", asset: ASSET,
  notes: "## 这一版改了什么\n\n打开软件发现新版会自动更新", error: null,
  release_url: "https://github.com/SunJ1ayu/OpenDesign/releases/tag/win-installer-0.99.0",
  auto_update: { eligible: true, why_not: null },
};
const TRIED = { ...ELIGIBLE, auto_update: { eligible: false, why_not: "attempted" } };
const LATEST_ALREADY = {
  current: "0.99.0", update_available: false, latest: "0.99.0", asset: null, notes: "", error: null,
  release_url: null, auto_update: { eligible: false, why_not: "no_update" },
};
const STARTED = { ok: true, stage: "started", error: null, latest: "0.99.0" };

/**
 * 开一页。`checks` 是依次回给 `/api/update/check` 的回包(用完了就一直回最后一个);
 * `applyReply` 是 `/api/update/apply` 的回包。记下每一次 apply 的请求体。
 * `autoCheckOff` ⇒ 在页面脚本跑之前把「打开时自动检查」存成关。
 */
async function openPage(browser, { checks, applyReply = STARTED, autoCheckOff = false }) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const log = { checks: 0, applies: [] };
  if (autoCheckOff) {
    await page.addInitScript(() => {
      try { localStorage.setItem("ds.prefs.update", JSON.stringify({ "update.autoCheck": false })); }
      catch { /* 读不到就读不到,前提检查会抓住 */ }
    });
  }
  await page.route("**/api/update/check*", (route) => {
    const body = checks[Math.min(log.checks, checks.length - 1)];
    log.checks++;
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.route("**/api/update/apply*", (route) => {
    let body = null;
    try { body = JSON.parse(route.request().postData() || "null"); } catch { body = "<not json>"; }
    log.applies.push({ method: route.request().method(), body });
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(applyReply) });
  });
  await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
  await page.locator(".side-footer .side-row").waitFor({ timeout: 15000 });
  return { page, log };
}

const banner = (page) => page.locator('[data-ui="auto-update-banner"]');

/** 横幅真在业主眼前:可见、有尺寸、落在视口里、**不在设置弹层里**(业主不翻菜单)。 */
async function bannerOnScreen(page) {
  const b = banner(page);
  if (await b.count() !== 1) return false;
  if (!(await b.isVisible())) return false;
  const box = await b.boundingBox();
  if (!box || box.width <= 0 || box.height <= 0) return false;
  if (box.x + box.width <= 0 || box.y + box.height <= 0 || box.x >= 1440 || box.y >= 900) return false;
  const inSettings = await b.evaluate((el) => !!el.closest(".settings-pop"));
  return !inSettings;
}

async function openSettings(page) {
  if (await page.locator(".settings-pop").count() === 0) {
    await page.locator(".side-footer .side-row").click();
  }
  await page.locator(".settings-pop").waitFor({ timeout: 5000 });
}

let browser = null;
try {
  browser = await launchBrowser();

  await step("AC-A 打开时查到可自动更新的新版 ⇒ 眼前出现倒计时,走完恰好发一次自动更新", async () => {
    const { page, log } = await openPage(browser, { checks: [ELIGIBLE] });
    check(await until(() => log.checks > 0, 15000), "前提:打开页面后真的自动查了一次更新");
    check(await until(() => bannerOnScreen(page), 5000),
      "查到之后 5 秒内,不翻任何菜单就看得见倒计时横幅");
    const t1 = (await banner(page).innerText()).replace(/\s+/g, " ");
    expect(t1.includes("0.99.0"), `横幅没说是哪一版:「${t1}」`);
    expect(/自动更新/.test(t1), `横幅没说会自动更新:「${t1}」`);
    const n1 = Number((t1.match(/(\d+)\s*秒/) || [])[1]);
    await sleep(2500);
    const t2 = (await banner(page).innerText()).replace(/\s+/g, " ");
    const n2 = Number((t2.match(/(\d+)\s*秒/) || [])[1]);
    expect(Number.isFinite(n1) && Number.isFinite(n2) && n2 < n1,
      `秒数没在往下走:「${t1}」→「${t2}」`);
    expect(log.applies.length === 0, "倒计时还没走完就发了更新请求");
    expect(await until(() => log.applies.length > 0, PAST_COUNTDOWN), "倒计时走完了,没发更新请求");
    await sleep(3000);
    expect(log.applies.length === 1, `应当恰好一次更新请求,实际 ${log.applies.length} 次`);
    const a = log.applies[0] || {};
    expect(a.method === "POST" && a.body && a.body.auto === true,
      `自动更新请求必须是 POST 且请求体 auto 为 true(服务端靠它二次把关、记账):${JSON.stringify(a)}`);
    // applyLabel:请求中「正在更新,OpenDesign 会自动关掉再重新打开」,已开始「OpenDesign 会自动关掉再重新打开」。
    expect(await until(async () => (await bannerOnScreen(page)) &&
      /关掉|重新打开/.test(await banner(page).innerText()), 3000),
      "请求发出去之后,横幅没告诉业主软件会自己关掉再打开(他得知道窗口为什么要消失)");
    await page.close();
  });

  // 下面四段都是"等过倒计时,什么都不该发生" ⇒ 并排跑,省三轮 10 秒。
  await Promise.all([
    step("AC-B 点取消 ⇒ 横幅收起,这次打开不再发更新请求", async () => {
      const { page, log } = await openPage(browser, { checks: [ELIGIBLE] });
      check(await until(() => bannerOnScreen(page), 15000), "前提:倒计时横幅出现了");
      await page.locator('[data-ui="auto-update-banner"] [data-ui="auto-update-cancel"]').click();
      expect(await until(async () => !(await bannerOnScreen(page)), 2000), "点了取消,横幅还在");
      await sleep(PAST_COUNTDOWN);
      expect(log.applies.length === 0,
        `🔴 点了取消,还是发了 ${log.applies.length} 次更新请求 —— 业主最不能接受的一种`);
      expect(!(await bannerOnScreen(page)), "取消之后横幅又冒出来了");
      await page.close();
    }),

    step("AC-C 这个版本自动试过 ⇒ 不倒计时、不请求;设置里说清楚可以手动点", async () => {
      const { page, log } = await openPage(browser, { checks: [TRIED] });
      check(await until(() => log.checks > 0, 15000), "前提:打开页面后真的自动查了一次更新");
      await sleep(PAST_COUNTDOWN);
      expect(!(await bannerOnScreen(page)), "自动试过的版本又弹倒计时了 —— 正是业主怕的循环");
      expect(log.applies.length === 0, `自动试过的版本又发了 ${log.applies.length} 次更新请求`);
      await openSettings(page);
      const hint = page.locator('.settings-pop [data-ui="auto-update-why-not"]');
      expect(await until(async () => await hint.count() === 1, 3000),
        "设置里没有解释为什么这一版不再自动更新(蓝点亮着、却不自动,业主会以为坏了)");
      if (await hint.count() === 1) {
        const s = await hint.innerText();
        expect(/手动/.test(s), `解释里没告诉业主可以手动更新:「${s}」`);
      }
      await page.close();
    }),

    step("AC-E 打开时已是最新;之后手动点「检查更新」查到新版 ⇒ 不倒计时(那不是打开软件)", async () => {
      const { page, log } = await openPage(browser, { checks: [LATEST_ALREADY, ELIGIBLE] });
      check(await until(() => log.checks === 1, 15000), "前提:打开时自动查了一次");
      await sleep(1500);
      await openSettings(page);
      await page.locator('.settings-pop button:has-text("检查更新")').click();
      check(await until(() => log.checks >= 2, 10000), "前提:手动检查真的发出去了");
      await sleep(PAST_COUNTDOWN);
      expect(!(await bannerOnScreen(page)), "手动「检查更新」也弹了倒计时");
      expect(log.applies.length === 0, `手动「检查更新」之后自己发了 ${log.applies.length} 次更新请求`);
      await page.close();
    }),

    step("AC-F 打开时自动检查是关的;中途打开开关、那次查到新版 ⇒ 不倒计时", async () => {
      const { page, log } = await openPage(browser, { checks: [ELIGIBLE], autoCheckOff: true });
      await sleep(3000);
      check(log.checks === 0, `前提:自动检查关着时打开页面不该查(实际查了 ${log.checks} 次)`);
      await openSettings(page);
      await page.locator('.settings-pop button:has-text("打开时自动检查")').click();
      check(await until(() => log.checks >= 1, 10000), "前提:打开开关之后查了一次");
      await sleep(PAST_COUNTDOWN);
      expect(!(await bannerOnScreen(page)), "中途打开自动检查开关也弹了倒计时(那不是打开软件)");
      expect(log.applies.length === 0, `中途打开开关之后自己发了 ${log.applies.length} 次更新请求`);
      await page.close();
    }),
  ]);

  await step("AC-D 自动更新失败 ⇒ 横幅上说人话(不只藏在设置里),能关掉", async () => {
    const { page, log } = await openPage(browser, {
      checks: [ELIGIBLE],
      applyReply: { ok: false, stage: "download", error: "HTTP 502" },
    });
    check(await until(() => bannerOnScreen(page), 15000), "前提:倒计时横幅出现了");
    check(await until(() => log.applies.length === 1, PAST_COUNTDOWN), "前提:倒计时走完发了自动更新");
    expect(await until(async () => (await bannerOnScreen(page)) &&
      /下载/.test(await banner(page).innerText()), 5000),
      "下载失败了,横幅上没说(业主等着软件自己关掉重开,什么都不会发生)");
    const t = await banner(page).innerText();
    expect(!/stage|download|HTTP 502|sha256/i.test(t), `横幅把内部词甩给了业主:「${t}」`);
    const dismiss = page.locator('[data-ui="auto-update-banner"] [data-ui="auto-update-dismiss"]');
    expect(await dismiss.count() === 1, "失败说明上没有关闭按钮");
    if (await dismiss.count() === 1) {
      await dismiss.click();
      expect(await until(async () => !(await bannerOnScreen(page)), 2000), "点了关闭,横幅还在");
    }
    await page.close();
  });
} finally {
  if (browser) await browser.close();
  srv.kill("SIGTERM");
  rmSync(tmp, { recursive: true, force: true });
}

console.log(failures === 0 ? "\n全部通过" : `\n${failures} 条没过`);
process.exit(failures === 0 ? 0 : 1);
