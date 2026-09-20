// 启动更新 e2e（历史文件名保留）。
//
// 规格沿革 —— 这份卷子的前提被业主改过两次,都不是我自己改的:
//   2026-09-17 取消倒计时:查到新版就立即更新,更新完再进工作区。
//   2026-09-19 取消"启动查更新"(track opendesign-startup-not-blocked-by-update):
//     业主原话「现在每次打开都会弹出正在检测更新,这严重拖慢了我们开软件的速度啊」
//     「不应该让用户看到这个界面才对啊,应该是有更新才显示和进度条,没更新就跟平时打开软件一样对不对」。
//     实测:0.98.7 打开软件干等 20.1 秒(收据 tracks/opendesign-startup-not-blocked-by-update/evidence/)。
//
// 🔴 **改这份卷子的规矩**:本次只搬前提、一条断言都没删。
//    原来由"启动那次查更新"送达的东西(回滚说明、已试过的版本、查不到更新),
//    现在由**手动/后台查更新**送达 —— 断言原样保留,只换触发点;
//    而"启动路径上不许联网"这件事反而被钉得更死(AC-A/AC-A0 的 log.checks === 0,
//    外加单测 sg1/sg5 与 su_net1~3)。
//    删断言和搬断言的区别在证据方向:搬,要说得出新位置问得出同一件事,且重新红检过。
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8846;
const KEY = "翡翠湾-1801";

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
// 盘上已经备好、校验过的新版(后端 startup_decision 的唯一一条 install 路)。
const READY = { action: "install", reason: "ready", version: "0.99.0",
                path: "C:\\Users\\x\\AppData\\Local\\OpenDesign\\pending\\OpenDesign-Setup-0.99.0.exe" };
const ENTER = { action: "enter", reason: "no_state" };
// 与 tests/test_update_ui.mjs 的 NO_MORE_AUTO 同一套说法(攻题二 #11:认意思不认字面)。
const NO_MORE_AUTO = /不会再自动|不再自动|以后只能手动|之后只能手动/;
const DEFAULT_VIEW = { width: 1280, height: 860 };
const SMALLEST_VIEW = { width: 960, height: 640 };

/**
 * 开一页。`checks` 是依次回给 `/api/update/check` 的回包(用完了就一直回最后一个);回包也可以是
 * `(url) => Promise<body>`(用来把某一次请求挂住)。`applyReply` 是 `/api/update/apply` 的回包,
 * `"abort"` ⇒ 请求整个掐断。记下每一次请求的时刻、URL 与 apply 的请求体。
 */
async function openPage(browser, { checks, applyReply = STARTED, autoCheckOff = false, view = DEFAULT_VIEW,
                                   startup = { action: "enter", reason: "no_state" } }) {
  const page = await browser.newPage({ viewport: view });
  const log = { checks: 0, checkUrls: [], applies: [], startups: 0, view };
  await page.addInitScript(() => {
    window.__workspaceMounted = false;
    new MutationObserver(() => {
      if (document.querySelector('.home-pane, .ws-pane, .side-footer')) window.__workspaceMounted = true;
    }).observe(document, { childList: true, subtree: true });
  });
  if (autoCheckOff) {
    await page.addInitScript(() => {
      try { localStorage.setItem("ds.prefs.update", JSON.stringify({ "update.autoCheck": false })); }
      catch { /* 读不到就读不到,前提检查会抓住 */ }
    });
  }
  // 🔴 规格变更(track opendesign-startup-not-blocked-by-update):启动**不再查更新**,
  //    只问这个本地端点"盘上有没有已经下好、校验过的新版"。默认没有 ⇒ 立刻进工作区。
  //    `startup` 可以是:回包对象 / "500" / "garbage" / "abort" / 函数(收第几次调用,
  //    用来模拟"装完重启后盘上已经没有待装包了")/ 返回 Promise 的函数(挂住,测上限)。
  await page.route("**/api/update/startup*", async (route) => {
    log.startups += 1;
    const body = typeof startup === "function" ? await startup(log.startups) : startup;
    if (body === "hang") return;                      // 永不回应
    if (body === "abort") return route.abort();
    if (body === "500") return route.fulfill({ status: 500, contentType: "application/json", body: "{}" });
    if (body === "garbage") return route.fulfill({ status: 200, contentType: "application/json",
                                                   body: "<这不是 json>" });
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.route("**/api/update/check*", async (route) => {
    const i = log.checks++;
    log.checkUrls.push(route.request().url());
    let body = checks[Math.min(i, checks.length - 1)];
    if (typeof body === "function") body = await body(route.request().url());
    if (body === "abort") return route.abort();
    if (body === "hang") return;
    log.checkedAt = Date.now();
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.route("**/api/update/apply*", async (route) => {
    let body = null;
    try { body = JSON.parse(route.request().postData() || "null"); } catch { body = "<not json>"; }
    log.applies.push({ at: Date.now(), method: route.request().method(), body });
    const reply = typeof applyReply === "function" ? await applyReply() : applyReply;
    if (reply === "abort") return route.abort();
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(reply) });
  });
  await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
  await page.locator("#root > div").waitFor({ timeout: 15000 });
  return { page, log };
}

const banner = (page) => page.locator('[data-ui="auto-update-banner"]');
const bannerText = async (page) => (await banner(page).innerText()).replace(/\s+/g, " ");
const isAuto = (a) => !!a && a.method === "POST" && !!a.body && a.body.auto === true;

/** 横幅真在业主眼前:可见、不透明、整块落在视口里、中心点上确实是它(没被别的层盖住)、不在设置弹层里。
 *  攻题二 #10:横幅容器可以合法地设 `pointer-events:none`(只让按钮可点),那样 elementFromPoint 会穿过它 ——
 *  命中测试时临时把横幅子树的 pointer-events 打开,问的是「视觉上有没有被盖住」,测完原样恢复。 */
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
    const nodes = [el, ...el.querySelectorAll("*")];
    const saved = nodes.map((n) => [n.style.getPropertyValue("pointer-events"), n.style.getPropertyPriority("pointer-events")]);
    nodes.forEach((n) => n.style.setProperty("pointer-events", "auto", "important"));
    try {
      const r = el.getBoundingClientRect();
      const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      return !!hit && el.contains(hit);
    } finally {
      nodes.forEach((n, i) => {
        if (saved[i][0]) n.style.setProperty("pointer-events", saved[i][0], saved[i][1]);
        else n.style.removeProperty("pointer-events");
      });
    }
  });
}

async function openSettings(page) {
  await page.locator(".side-footer .side-row").waitFor({ timeout: 15000 });
  if (await page.locator(".settings-pop").count() === 0) {
    await page.locator(".side-footer .side-row").click();
  }
  await page.locator(".settings-pop").waitFor({ timeout: 5000 });
}

const startup = (page) => page.locator('[data-ui="startup-update"]');
const workspace = (page) => page.locator('.side-footer .side-row');
const deferred = () => {
  let resolve;
  const promise = new Promise((r) => { resolve = r; });
  return { promise, resolve };
};

/** 手动查一次更新(启动不再查了,所以想拿到查更新的结果就得自己点)。 */
async function manualCheck(page, log, expected) {
  await openSettings(page);
  await page.locator('.settings-pop button:has-text("检查更新")').click();
  expect(await until(() => log.checks === expected), `手动检查没有发出(期望第 ${expected} 次)`);
}

/** 关掉设置弹层 —— 横幅的"真在业主眼前"要在没有弹层遮挡时问。 */
async function closeSettings(page) {
  await page.keyboard.press("Escape");
  // 🔴 `count()` 回的是 Promise —— 不 await 就是拿 Promise 跟数字比,恒假。
  //    这个洞第一版我自己写进来了,红检里表现成"设置弹层关不掉"这种假发现。
  expect(await until(async () => (await page.locator(".settings-pop").count()) === 0, 3000), "设置弹层关不掉");
}

let browser = null;
try {
  browser = await launchBrowser();
  await step("AC-A 盘上已备好新版 ⇒ 打开就装(零查更新、无倒计时),交棒后等新窗口", async () => {
    const applied = deferred();
    const { page, log } = await openPage(browser, {
      checks: [LATEST_ALREADY], applyReply: () => applied.promise, view: SMALLEST_VIEW,
      startup: (n) => (n === 1 ? READY : ENTER),   // 装完重启后,盘上那个包已经用掉了
    });
    try {
      expect(await until(() => startup(page).isVisible()), "正在装备好的新版,却没有启动页");
      expect(await workspace(page).count() === 0, "还没装完工作区已经出现");
      const fired = await until(() => log.applies.length === 1, 2500);
      expect(fired, "盘上已备好新版却没有立即开始安装");
      if (fired) expect(isAuto(log.applies[0]), "启动更新必须是自动请求");
      expect(log.checks === 0, "🔴 启动路径上发生了查更新请求 —— 本单要根除的就是它");
      expect(!await page.evaluate(() => window.__workspaceMounted), "更新完成前工作区曾被挂载");
      expect(await page.locator('[data-ui="auto-update-cancel"]').count() === 0, "启动更新还在显示取消倒计时按钮");
      const text = await startup(page).innerText().catch(() => "");
      expect(/0\.99\.0/.test(text) && /更新/.test(text), "启动页没说正在更新到哪一版(版本就在启动回包里)");
      expect(!/秒后|倒计时/.test(text), "启动页还在显示倒计时");
      const box = await startup(page).boundingBox();
      expect(box && box.x >= 0 && box.y >= 0 && box.x + box.width <= 960 && box.y + box.height <= 640,
        "启动页在最小窗口内不完整");
      applied.resolve(STARTED);
      await sleep(700);
      expect(await startup(page).isVisible(), "接力程序刚启动就进入了旧版工作区");
      expect(await workspace(page).count() === 0, "更新交棒后提前进入了旧版工作区");
      expect(log.applies.length === 1 && log.checks === 0, "启动更新被重复触发");
      // 成功重启后的新页面:盘上已经没有待装的包 ⇒ 正常进工作区,不再装一遍。
      await page.reload({ waitUntil: "domcontentloaded" });
      expect(await until(() => workspace(page).isVisible()), "更新后重新打开没有进入工作区");
      expect(await startup(page).count() === 0, "新版启动后仍被启动页挡住");
      expect(log.applies.length === 1, "新版重新打开还在自动更新");
    } finally {
      applied.resolve(STARTED); await page.close();
    }
  });

  await step("AC-A0 盘上没有备好的新版 ⇒ 打开软件一次网都不联,直接进工作区", async () => {
    // 🔴 业主投诉的就是这一条:线上**确实有**新版(ELIGIBLE),启动也不许去查。
    const { page, log } = await openPage(browser, { checks: [ELIGIBLE] });
    expect(await until(() => workspace(page).isVisible()), "没有待装的包却没能进工作区");
    expect(await startup(page).count() === 0, "没有东西要装,却还被启动页挡着");
    expect(log.startups === 1, "启动没有问本地状态接口");
    expect(log.checks === 0, "🔴 启动路径上又去查更新了 —— 这正是「每次打开都弹正在检测更新」");
    expect(log.applies.length === 0, "没有备好的包却发起了安装");
    await page.close();
  });

  await step("AC-B 启动接口回什么坏东西都要能进软件", async () => {
    for (const s of [ENTER, "500", "garbage", "abort", null, {}, [], { action: "INSTALL" }, { reason: "ready" }]) {
      const { page, log } = await openPage(browser, { checks: [LATEST_ALREADY], startup: s });
      const what = JSON.stringify(s);
      expect(await until(() => workspace(page).isVisible()), `启动接口回 ${what} 时没能进工作区`);
      expect(await startup(page).count() === 0, `启动接口回 ${what} 时卡在启动页`);
      expect(log.applies.length === 0, `启动接口回 ${what} 时发起了安装`);
      await page.close();
    }
  });

  await step("AC-C 已自动试过的版本不再自动更新,手动出口仍可用", async () => {
    const { page, log } = await openPage(browser, { checks: [TRIED] });
    await manualCheck(page, log, 1);
    expect(await until(async () => (await page.locator('[data-ui="auto-update-why-not"]').count()) === 1),
      "查到已试过的版本,却没有解释可以手动更新");
    expect(/手动/.test(await page.locator('[data-ui="auto-update-why-not"]').innerText()), "没有解释可手动更新");
    expect(log.applies.length === 0, "已尝试的版本又发起自动更新");
    await page.locator('[data-ui="update-apply"]').click();
    expect(await until(() => log.applies.length === 1), "手动更新没有发出请求");
    expect(!isAuto(log.applies[0]), "手动更新被错误标记为自动");
    await page.close();
  });

  await step("AC-C2 上次自动更新失败回滚 ⇒ 进旧版并给出可见说明,不再自动重试", async () => {
    const { page, log } = await openPage(browser, { checks: [JUST_FAILED] });
    expect(await until(() => workspace(page).isVisible()), "回滚后不能进入旧版");
    await manualCheck(page, log, 1);     // 说明改由查更新送达:启动已经不查了
    await closeSettings(page);
    expect(await until(() => bannerOnScreen(page, log.view)), "回滚后缺少可见的失败说明");
    const text = await bannerText(page);
    expect(text.includes("0.99.0") && NO_MORE_AUTO.test(text), "回滚提示没说明版本及不再自动重试");
    await page.locator('[data-ui="auto-update-dismiss"]').click();
    expect(await banner(page).count() === 0, "失败提示不能关闭");
    expect(log.applies.length === 0, "回滚后又自动重试");
    await page.close();
  });

  await step("AC-D 启动安装失败 ⇒ 进旧版、提示原因,结果未知时不虚称不会再试", async () => {
    for (const reply of [{ ok: false, stage: "download", error: "HTTP 502" }, "abort",
      { ok: false, stage: "auto_unrecorded", error: "write failed" }]) {
      const { page, log } = await openPage(browser, { checks: [LATEST_ALREADY], applyReply: reply,
        startup: (n) => (n === 1 ? READY : ENTER) });
      expect(await until(() => log.applies.length === 1, 2500), "备好的新版没有在启动时开始安装");
      expect(await until(() => workspace(page).isVisible()), "更新失败后仍挡住工作区");
      expect(await until(() => bannerOnScreen(page, log.view)), "更新失败没有可见的提示");
      const text = await bannerText(page);
      expect(!/HTTP 502|write failed/.test(text), "失败提示泄露内部错误");
      if (reply === "abort" || reply.stage === "auto_unrecorded") {
        expect(!NO_MORE_AUTO.test(text), "未确认记账却承诺不会再自动更新");
      }
      await page.evaluate(() => {
        window.dispatchEvent(new Event("online")); window.dispatchEvent(new Event("focus"));
        document.dispatchEvent(new Event("visibilitychange"));
      });
      await sleep(500);
      expect(log.applies.length === 1, "更新失败后自动重复请求");
      expect(log.checks === 0, "装失败之后又在启动路径上查更新");
      await page.locator('[data-ui="auto-update-dismiss"]').click();
      expect(await banner(page).count() === 0, "失败提示不能关闭");
      await page.close();
    }
  });

  await step("AC-E 使用中手动检查发现新版不会打断工作", async () => {
    const { page, log } = await openPage(browser, { checks: [ELIGIBLE] });
    await manualCheck(page, log, 1);
    await sleep(700);
    expect(log.applies.length === 0, "手动检查之后自己发了更新请求");
    expect(await workspace(page).isVisible(), "手动检查打断了工作区");
    await page.close();
  });

  await step("AC-F 关闭自动检查可进入软件,中途开启只查不装", async () => {
    const { page, log } = await openPage(browser, { checks: [ELIGIBLE], autoCheckOff: true });
    await openSettings(page);
    expect(log.checks === 0, "关闭自动检查后启动仍查更新");
    expect(log.startups === 0, "关闭自动检查后启动仍去问了更新状态");
    await page.locator('.settings-pop button:has-text("打开时自动检查")').click();
    check(await until(() => log.checks === 1), "中途开启没有检查更新");
    await sleep(700);
    expect(log.applies.length === 0, "中途开启自动检查之后自己发了更新请求");
    expect(await workspace(page).isVisible(), "中途开启开关打断了工作区");
    await page.close();
  });

  await step("AC-G 启动接口挂住 ⇒ 有界进入工作区,迟到的回包不打断工作", async () => {
    // 原来这条问的是"查更新无响应时 35 秒内要放人进来";现在启动根本不联网,
    // 同一件事改问本地读的上限(500ms 量级),**更严**。
    const answered = deferred();
    const { page, log } = await openPage(browser, { checks: [LATEST_ALREADY], startup: () => answered.promise });
    try {
      expect(await until(() => workspace(page).isVisible(), 8000),
        "启动接口一直不回,软件就再也打不开了(上限该是几百毫秒量级)");
      expect(await startup(page).count() === 0, "启动接口不回时卡在启动页");
      answered.resolve(READY);
      await sleep(700);
      expect(log.applies.length === 0, "迟到的启动回包触发了安装,打断了正在用软件的人");
      expect(log.checks === 0, "启动路径上查更新了");
    } finally {
      answered.resolve(ENTER); await page.close();
    }
  });

  await step("AC-G2 手动查更新失败 ⇒ 设置里留下失败状态,不装聋", async () => {
    const { page, log } = await openPage(browser, { checks: ["abort"] });
    expect(await until(() => workspace(page).isVisible()), "没能进工作区");
    await manualCheck(page, log, 1);
    expect(await until(async () => /查不到更新/.test(await page.locator('.settings-pop').innerText())),
      "查更新失败却没有保留失败状态");
    await page.close();
  });

  await step("AC-H 启动安装失败后手动更新可重试,且不会再次触发自动请求", async () => {
    const { page, log } = await openPage(browser, { checks: [ELIGIBLE],
      applyReply: { ok: false, stage: "download", error: "unavailable" },
      startup: (n) => (n === 1 ? READY : ENTER) });
    expect(await until(() => log.applies.length === 1, 2500), "前提:启动安装已经失败");
    await manualCheck(page, log, 1);
    await page.locator('[data-ui="update-apply"]').click();
    expect(await until(() => log.applies.length === 2), "自动失败后手动更新没有发出");
    expect(!isAuto(log.applies[1]), "失败后手动更新被标为自动");
    await sleep(700);
    expect(log.applies.length === 2, "手动重试后又发了额外更新请求");
    await page.close();
  });
} finally {
  if (browser) await browser.close();
  srv.kill("SIGTERM");
  rmSync(tmp, { recursive: true, force: true });
}
console.log(failures === 0 ? "\n全部通过" : `\n${failures} 条没过`);
process.exit(failures === 0 ? 0 : 1);
