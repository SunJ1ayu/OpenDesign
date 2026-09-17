// track opendesign-auto-update-countdown e2e:打开软件时那条倒计时横幅,在业主眼前到底发生了什么。
// 真 chromium + 真 ds_web(不需要 gateway);`/api/update/check` 与 `/api/update/apply` 用 page.route 拦成替身。
// 主 agent 亲写,执行腿逐字节 off-limits。段名与问法的唯一权威在该 track 的 design.md(AC-A~F)。
//
// 🔴 为什么必须有这一份:ac1~ac8 只问「函数返回哪几个字」,au1~au12 只问「后端怎么答」。
//    业主怕的两件事 —— **点了取消它还是装了**、**不是打开软件那次也弹倒计时** —— 全在 App 的接线里,
//    单元判据一条都问不出来(0.91 窗口栏整块没画出来时 12 条判据全绿,是同一种盲区)。
//
// 视口用真窗口的尺寸:默认 1280×860,最小 960×640(bin/ds_shell.py create_window)—— 1440 宽里看得见 ≠ 业主窗口里看得见(攻题 #15)。
//
// 跑法:node tests/e2e/auto_update_countdown.e2e.mjs(自起 ds_web 于 8846;要等几轮 10 秒倒计时,约 1 分半)
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
let srvExited = null;
srv.on("exit", (code) => { srvExited = code; });
for (let i = 0; ; i++) {
  if (srvExited !== null) throw new Error(`ds_web 起来就退出了(rc=${srvExited}):${PORT} 端口被占?`);
  try {
    const h = await (await fetch(`${base}/api/health`)).json();
    // 攻题 #19:固定端口上答话的可能是别的 ds_web(旧 dist)⇒ 必须是本次起的这一个。
    if (h.ds_root !== dsRoot) throw new Error(`${PORT} 上答话的不是本次起的 ds_web(ds_root=${h.ds_root})`);
    break;
  } catch (e) {
    if (String(e).includes("不是本次起的")) throw e;
    if (i > 50) throw new Error("ds_web 起不来");
    await new Promise((r) => setTimeout(r, 200));
  }
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
  auto_update: { eligible: true, why_not: null, recent_failure: false },
};
const TRIED = { ...ELIGIBLE, auto_update: { eligible: false, why_not: "attempted", recent_failure: false } };
const JUST_FAILED = { ...ELIGIBLE, auto_update: { eligible: false, why_not: "attempted", recent_failure: true } };
const LATEST_ALREADY = {
  current: "0.99.0", update_available: false, latest: "0.99.0", asset: null, notes: "", error: null,
  release_url: null, auto_update: { eligible: false, why_not: "no_update", recent_failure: false },
};
const STARTED = { ok: true, stage: "started", error: null, latest: "0.99.0" };
const DEFAULT_VIEW = { width: 1280, height: 860 };
const SMALLEST_VIEW = { width: 960, height: 640 };

/**
 * 开一页。`checks` 是依次回给 `/api/update/check` 的回包(用完了就一直回最后一个);回包也可以是
 * `(url) => Promise<body>`(用来把某一次请求挂住)。`applyReply` 是 `/api/update/apply` 的回包,
 * `"abort"` ⇒ 请求整个掐断。记下每一次请求的时刻、URL 与 apply 的请求体。
 */
async function openPage(browser, { checks, applyReply = STARTED, autoCheckOff = false, view = DEFAULT_VIEW }) {
  const page = await browser.newPage({ viewport: view });
  const log = { checks: 0, checkUrls: [], applies: [], view };
  if (autoCheckOff) {
    await page.addInitScript(() => {
      try { localStorage.setItem("ds.prefs.update", JSON.stringify({ "update.autoCheck": false })); }
      catch { /* 读不到就读不到,前提检查会抓住 */ }
    });
  }
  await page.route("**/api/update/check*", async (route) => {
    const i = log.checks++;
    log.checkUrls.push(route.request().url());
    let body = checks[Math.min(i, checks.length - 1)];
    if (typeof body === "function") body = await body(route.request().url());
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.route("**/api/update/apply*", (route) => {
    let body = null;
    try { body = JSON.parse(route.request().postData() || "null"); } catch { body = "<not json>"; }
    log.applies.push({ at: Date.now(), method: route.request().method(), body });
    if (applyReply === "abort") return route.abort();
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(applyReply) });
  });
  await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
  await page.locator(".side-footer .side-row").waitFor({ timeout: 15000 });
  return { page, log };
}

const banner = (page) => page.locator('[data-ui="auto-update-banner"]');
const bannerText = async (page) => (await banner(page).innerText()).replace(/\s+/g, " ");
const isAuto = (a) => !!a && a.method === "POST" && !!a.body && a.body.auto === true;

/** 横幅真在业主眼前:可见、不透明、整块落在视口里、中心点上确实是它(没被别的层盖住)、不在设置弹层里。 */
async function bannerOnScreen(page, view) {
  const b = banner(page);
  if (await b.count() !== 1) return false;
  if (!(await b.isVisible())) return false;
  const box = await b.boundingBox();
  if (!box || box.width <= 0 || box.height <= 0) return false;
  if (box.x < 0 || box.y < 0 || box.x + box.width > view.width || box.y + box.height > view.height) return false;
  return await b.evaluate((el) => {
    if (el.closest(".settings-pop")) return false;
    for (let n = el; n; n = n.parentElement) {
      if (Number(getComputedStyle(n).opacity) < 0.5) return false;
    }
    const r = el.getBoundingClientRect();
    const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    return !!hit && el.contains(hit);
  });
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

  await step("AC-A 打开时查到可自动更新的新版 ⇒ 眼前出现倒计时,约 10 秒后恰好发一次自动更新", async () => {
    const { page, log } = await openPage(browser, { checks: [ELIGIBLE] });
    check(await until(() => log.checks > 0, 15000), "前提:打开页面后真的自动查了一次更新");
    check(await until(() => bannerOnScreen(page, log.view), 5000),
      "查到之后 5 秒内,不翻任何菜单就看得见倒计时横幅(1280×860,没被盖住)");
    const shownAt = Date.now();
    const t1 = await bannerText(page);
    expect(t1.includes("0.99.0"), `横幅没说是哪一版:「${t1}」`);
    expect(/自动更新/.test(t1), `横幅没说会自动更新:「${t1}」`);
    const n1 = Number((t1.match(/(\d+)\s*秒/) || [])[1]);
    expect(n1 >= 9 && n1 <= 10, `横幅一出来显示的秒数应当是 10(读到时可能刚跳成 9):「${t1}」`);
    expect(await page.locator('[data-ui="auto-update-banner"] [data-ui="auto-update-cancel"]').count() === 1,
      "倒计时横幅上没有取消按钮");
    await sleep(2500);
    const t2 = await bannerText(page);
    const n2 = Number((t2.match(/(\d+)\s*秒/) || [])[1]);
    expect(Number.isFinite(n2) && n2 < n1, `秒数没在往下走:「${t1}」→「${t2}」`);
    check(await until(() => log.applies.length > 0, 14000), "倒计时走完了,没发更新请求");
    // 攻题 #5:导出的常量是 10、字在跳,真正的定时器却是 3 秒 —— 量横幅出现到请求到达的真实间隔。
    const waited = log.applies[0].at - shownAt;
    expect(waited >= 8500 && waited <= 12000,
      `横幅出现到自动更新请求之间应当约 10 秒,实测 ${waited}ms —— 业主以为有 10 秒可以取消`);
    await sleep(3000);
    expect(log.applies.length === 1, `应当恰好一次更新请求,实际 ${log.applies.length} 次`);
    expect(isAuto(log.applies[0]),
      `自动更新请求必须是 POST 且请求体 auto 为 true(服务端靠它二次把关、记账):${JSON.stringify(log.applies[0])}`);
    // applyLabel:请求中「正在更新,OpenDesign 会自动关掉再重新打开」,已开始「OpenDesign 会自动关掉再重新打开」。
    expect(await until(async () => (await bannerOnScreen(page, log.view)) &&
      /关掉|重新打开/.test(await bannerText(page)), 3000),
      "请求发出去之后,横幅没告诉业主软件会自己关掉再打开(他得知道窗口为什么要消失)");
    expect(log.checks === 1, `打开一次软件应当只自动查一次更新,实际 ${log.checks} 次`);
    await page.close();
  });

  // 下面几段都要"等过一轮倒计时" ⇒ 并排跑;分两批,本机只有 2G 内存,七个页面一起开会被系统杀进程。
  await Promise.all([
    step("AC-B 最小窗口里点取消 ⇒ 横幅收起;之后手动检查、开关自动检查、网络恢复、窗口切回来,都不许再自动更新", async () => {
      const { page, log } = await openPage(browser, { checks: [ELIGIBLE], view: SMALLEST_VIEW });
      check(await until(() => bannerOnScreen(page, log.view), 15000),
        "前提:960×640(真窗口的最小尺寸)里倒计时横幅在眼前、没被盖住");
      await page.locator('[data-ui="auto-update-banner"] [data-ui="auto-update-cancel"]').click();
      expect(await until(async () => !(await bannerOnScreen(page, log.view)), 2000), "点了取消,横幅还在");
      // 攻题 #8:取消只清了定时器、没记住「这次打开已取消」⇒ 下一次状态刷新又活过来。
      await page.evaluate(() => {
        window.dispatchEvent(new Event("online"));
        document.dispatchEvent(new Event("visibilitychange"));
        window.dispatchEvent(new Event("focus"));
      });
      await openSettings(page);
      await page.locator('.settings-pop button:has-text("检查更新")').click();
      const toggle = page.locator('.settings-pop button:has-text("打开时自动检查")');
      await toggle.click();
      await toggle.click();
      check(await until(() => log.checks >= 3, 10000), `前提:取消之后又查了两次更新(实际共 ${log.checks} 次)`);
      await sleep(14000);
      const autos = log.applies.filter(isAuto).length;
      expect(autos === 0, `🔴 点了取消,之后还是自动发了 ${autos} 次更新请求 —— 业主最不能接受的一种`);
      expect(log.applies.length === 0, `取消之后发了 ${log.applies.length} 次更新请求`);
      expect(!(await bannerOnScreen(page, log.view)), "取消之后倒计时横幅又冒出来了");
      await page.close();
    }),

    step("AC-C 这个版本早就自动试过 ⇒ 不出横幅、不请求;设置里说清楚可以手动点", async () => {
      const { page, log } = await openPage(browser, { checks: [TRIED] });
      check(await until(() => log.checks > 0, 15000), "前提:打开页面后真的自动查了一次更新");
      await sleep(14000);
      expect(!(await bannerOnScreen(page, log.view)), "早就自动试过的版本,打开时又出横幅了(每次打开都说一遍)");
      expect(log.applies.length === 0, `自动试过的版本又发了 ${log.applies.length} 次更新请求 —— 正是业主怕的循环`);
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

    step("AC-C2 刚自动更新失败、被换回旧版重新打开 ⇒ 横幅说一次(不倒计时、不请求),能关掉", async () => {
      const { page, log } = await openPage(browser, { checks: [JUST_FAILED] });
      check(await until(() => log.checks > 0, 15000), "前提:打开页面后真的自动查了一次更新");
      expect(await until(() => bannerOnScreen(page, log.view), 5000),
        "🔴 自动更新刚失败、软件被换回旧版重新打开,眼前却什么都没有 —— 业主以为已经更新好了");
      if (await banner(page).count() === 1) {
        const t = await bannerText(page);
        expect(t.includes("0.99.0") && /不会再自动/.test(t), `横幅没说是哪一版、没说不会再自动试:「${t}」`);
        expect(!/\d+\s*秒后/.test(t), `失败说明上居然在倒计时:「${t}」`);
        expect(await page.locator('[data-ui="auto-update-banner"] [data-ui="auto-update-cancel"]').count() === 0,
          "失败说明上有「取消」—— 没有要取消的东西");
      }
      await sleep(14000);
      expect(log.applies.length === 0, `刚失败的版本又发了 ${log.applies.length} 次更新请求`);
      const dismiss = page.locator('[data-ui="auto-update-banner"] [data-ui="auto-update-dismiss"]');
      expect(await dismiss.count() === 1, "失败说明上没有关闭按钮");
      if (await dismiss.count() === 1) {
        await dismiss.click();
        expect(await until(async () => !(await bannerOnScreen(page, log.view)), 2000), "点了关闭,横幅还在");
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
      await sleep(14000);
      expect(!(await bannerOnScreen(page, log.view)), "手动「检查更新」也弹了倒计时");
      expect(log.applies.length === 0, `手动「检查更新」之后自己发了 ${log.applies.length} 次更新请求`);
      await page.close();
    }),

  ]);
  await Promise.all([
    step("AC-F 打开时自动检查是关的;中途打开开关、那次查到新版 ⇒ 不倒计时", async () => {
      const { page, log } = await openPage(browser, { checks: [ELIGIBLE], autoCheckOff: true });
      await sleep(3000);
      check(log.checks === 0, `前提:自动检查关着时打开页面不该查(实际查了 ${log.checks} 次)`);
      await openSettings(page);
      await page.locator('.settings-pop button:has-text("打开时自动检查")').click();
      check(await until(() => log.checks >= 1, 10000), "前提:打开开关之后查了一次");
      await sleep(14000);
      expect(!(await bannerOnScreen(page, log.view)), "中途打开自动检查开关也弹了倒计时(那不是打开软件)");
      expect(log.applies.length === 0, `中途打开开关之后自己发了 ${log.applies.length} 次更新请求`);
      await page.close();
    }),

    // (攻题 #9「打开时那次还没回来、手动先查到新版」这里不设段:查更新进行中「检查更新」按钮本来就是灰的
    //  —— Sidebar `disabled={updateState === "checking"}` —— 业主在界面上造不出这个先后,判据 09-17 实跑超时证实。)
    step("AC-H 倒计时中业主自己点了「更新」⇒ 只有他点的那一次,倒计时停下,走完也不再自动发", async () => {
      const { page, log } = await openPage(browser, { checks: [ELIGIBLE] });
      check(await until(() => bannerOnScreen(page, log.view), 15000), "前提:倒计时横幅出现了");
      await openSettings(page);
      const btn = page.locator('.settings-pop [data-ui="update-apply"]');
      check(await until(async () => await btn.count() === 1, 3000), "前提:设置里有「更新」按钮");
      await btn.click();
      check(await until(() => log.applies.length === 1, 3000), "前提:手动更新请求发出去了");
      expect(await until(async () => (await banner(page).count()) === 0 || !/\d+\s*秒后/.test(await bannerText(page)), 2000),
        "业主已经手动开始更新了,横幅还在倒计时");
      await sleep(14000);
      expect(log.applies.length === 1, `应当只有手动那一次请求,实际 ${log.applies.length} 次`);
      expect(!isAuto(log.applies[0]), `手动点的请求被标成了自动:${JSON.stringify(log.applies[0])}`);
      await page.close();
    }),
  ]);

  await step("AC-D 自动更新失败 ⇒ 横幅上说人话(不只藏在设置里),能关掉;请求整个没回来 ⇒ 也要说,但不说「不会再自动」", async () => {
    const [d1, d2] = await Promise.all([
      openPage(browser, { checks: [ELIGIBLE], applyReply: { ok: false, stage: "download", error: "HTTP 502" } }),
      openPage(browser, { checks: [ELIGIBLE], applyReply: "abort" }),
    ]);
    for (const { page, log } of [d1, d2]) {
      check(await until(() => bannerOnScreen(page, log.view), 15000), "前提:倒计时横幅出现了");
    }
    for (const { log } of [d1, d2]) {
      check(await until(() => log.applies.length === 1, 14000), "前提:倒计时走完发了自动更新");
    }
    expect(await until(async () => (await bannerOnScreen(d1.page, d1.log.view)) &&
      /下载/.test(await bannerText(d1.page)), 5000),
      "下载失败了,横幅上没说(业主等着软件自己关掉重开,什么都不会发生)");
    const t = await bannerText(d1.page);
    expect(!/stage|download|HTTP 502|sha256/i.test(t), `横幅把内部词甩给了业主:「${t}」`);
    const dismiss = d1.page.locator('[data-ui="auto-update-banner"] [data-ui="auto-update-dismiss"]');
    expect(await dismiss.count() === 1, "失败说明上没有关闭按钮");
    if (await dismiss.count() === 1) {
      await dismiss.click();
      expect(await until(async () => !(await bannerOnScreen(d1.page, d1.log.view)), 2000), "点了关闭,横幅还在");
    }
    expect(await until(async () => (await bannerOnScreen(d2.page, d2.log.view)) &&
      (await bannerText(d2.page)).length > 0 && !/\d+\s*秒后/.test(await bannerText(d2.page)), 5000),
      "自动更新请求整个没回来,横幅上什么都没说(或者还停在倒计时)");
    const t2 = await bannerText(d2.page);
    expect(!/不会再自动/.test(t2), `请求没回来,不知道服务端记没记账,却说「不会再自动」:「${t2}」`);
    await d1.page.close();
    await d2.page.close();
  });
} finally {
  if (browser) await browser.close();
  srv.kill("SIGTERM");
  rmSync(tmp, { recursive: true, force: true });
}

console.log(failures === 0 ? "\n全部通过" : `\n${failures} 条没过`);
process.exit(failures === 0 ? 0 : 1);
