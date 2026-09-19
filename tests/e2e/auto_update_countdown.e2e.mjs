// 启动更新 e2e（历史文件名保留）：用户 2026-09-17 明确取消倒计时，更新完再进入工作区。
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
// 与 tests/test_update_ui.mjs 的 NO_MORE_AUTO 同一套说法(攻题二 #11:认意思不认字面)。
const NO_MORE_AUTO = /不会再自动|不再自动|以后只能手动|之后只能手动/;
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

let browser = null;
try {
  browser = await launchBrowser();
  await step("AC-A 检查前不进入工作区；发现新版立即更新，成功交棒后等新窗口", async () => {
    const checked = deferred();
    const applied = deferred();
    const { page, log } = await openPage(browser, {
      checks: [() => checked.promise, LATEST_ALREADY], applyReply: () => applied.promise, view: SMALLEST_VIEW,
    });
    try {
      expect(await until(() => startup(page).isVisible()), "检查更新时应显示启动页");
      expect(await workspace(page).count() === 0, "检查更新结束前工作区已经出现");
      checked.resolve(ELIGIBLE);
      const fired = await until(() => log.applies.length === 1, 2500);
      expect(fired, "查到新版后没有立即发起自动更新（仍在等倒计时）");
      if (fired) {
        expect(log.applies[0].at - log.checkedAt < 2500, "查到新版后仍有额外等待");
        expect(isAuto(log.applies[0]), "启动更新必须是自动请求");
      }
      expect(await startup(page).isVisible(), "更新进行中没有启动页");
      expect(!await page.evaluate(() => window.__workspaceMounted), "更新完成前工作区曾被挂载");
      expect(await page.locator('[data-ui="auto-update-cancel"]').count() === 0, "启动更新还在显示取消倒计时按钮");
      const text = await startup(page).innerText().catch(() => "");
      expect(/0\.99\.0/.test(text) && /更新/.test(text), "启动页应显示正在更新的版本");
      expect(!/秒后|倒计时/.test(text), "启动页还在显示倒计时");
      const box = await startup(page).boundingBox();
      expect(box && box.x >= 0 && box.y >= 0 && box.x + box.width <= 960 && box.y + box.height <= 640,
        "启动页在最小窗口内不完整");
      applied.resolve(STARTED);
      await sleep(700);
      expect(await startup(page).isVisible(), "接力程序刚启动就进入了旧版工作区");
      expect(await workspace(page).count() === 0, "更新交棒后提前进入了旧版工作区");
      expect(log.applies.length === 1 && log.checks === 1, "启动更新被重复触发");
      // 成功重启后的新页面已经是最新版，可以进入软件。
      await page.reload({ waitUntil: "domcontentloaded" });
      expect(await until(() => workspace(page).isVisible()), "更新后重新打开没有进入工作区");
      expect(await startup(page).count() === 0, "新版启动后仍被启动页挡住");
      expect(log.applies.length === 1, "新版重新打开还在自动更新");
    } finally {
      checked.resolve(ELIGIBLE); applied.resolve(STARTED); await page.close();
    }
  });

  await step("AC-B 没有新版、断网或不可自动更新时正常进入软件", async () => {
    for (const info of [LATEST_ALREADY, "abort", null, { ...LATEST_ALREADY, error: "网络不可用" },
      { ...ELIGIBLE, auto_update: { eligible: false, why_not: "no_shell" } },
      { ...ELIGIBLE, asset: null }]) {
      const { page, log } = await openPage(browser, { checks: [info] });
      expect(await until(() => workspace(page).isVisible()), `未更新时没有进入工作区: ${JSON.stringify(info)}`);
      expect(await startup(page).count() === 0, "无需更新却卡在启动页");
      expect(log.applies.length === 0, "没有可自动安装的版本却发起了更新");
      await page.close();
    }
  });

  await step("AC-C 已自动试过的版本不再自动更新，手动出口仍可用", async () => {
    const { page, log } = await openPage(browser, { checks: [TRIED] });
    await openSettings(page);
    expect(log.applies.length === 0, "已尝试的版本又发起自动更新");
    expect(/手动/.test(await page.locator('[data-ui="auto-update-why-not"]').innerText()), "没有解释可手动更新");
    await page.locator('[data-ui="update-apply"]').click();
    expect(await until(() => log.applies.length === 1), "手动更新没有发出请求");
    expect(!isAuto(log.applies[0]), "手动更新被错误标记为自动");
    await page.close();
  });

  await step("AC-C2 回滚后进入旧版并显示失败说明，不再次更新", async () => {
    const { page, log } = await openPage(browser, { checks: [JUST_FAILED] });
    expect(await until(() => workspace(page).isVisible()), "回滚后不能进入旧版");
    expect(await until(() => bannerOnScreen(page, log.view)), "回滚后缺少可见的失败说明");
    const text = await bannerText(page);
    expect(text.includes("0.99.0") && NO_MORE_AUTO.test(text), "回滚提示没说明版本及不再自动重试");
    await page.locator('[data-ui="auto-update-dismiss"]').click();
    expect(await banner(page).count() === 0, "失败提示不能关闭");
    expect(log.applies.length === 0, "回滚后又自动重试");
    await page.close();
  });

  await step("AC-D 更新失败后进入旧版，提示原因，结果未知时不虚称不会再试", async () => {
    for (const reply of [{ ok: false, stage: "download", error: "HTTP 502" }, "abort",
      { ok: false, stage: "auto_unrecorded", error: "write failed" }]) {
      const { page, log } = await openPage(browser, { checks: [ELIGIBLE], applyReply: reply });
      expect(await until(() => log.applies.length === 1, 2500), "启动更新没有立即发起");
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
      await page.locator('[data-ui="auto-update-dismiss"]').click();
      expect(await banner(page).count() === 0, "失败提示不能关闭");
      await page.close();
    }
  });

  await step("AC-E 使用中手动检查发现新版不会打断工作", async () => {
    const { page, log } = await openPage(browser, { checks: [LATEST_ALREADY, ELIGIBLE] });
    await openSettings(page);
    await page.locator('.settings-pop button:has-text("检查更新")').click();
    check(await until(() => log.checks === 2), "手动检查未发出");
    await sleep(700);
    expect(log.applies.length === 0, "手动检查之后自己发了更新请求");
    expect(await workspace(page).isVisible(), "手动检查打断了工作区");
    await page.close();
  });

  await step("AC-F 关闭自动检查可进入软件，中途开启只查不装", async () => {
    const { page, log } = await openPage(browser, { checks: [ELIGIBLE], autoCheckOff: true });
    await openSettings(page);
    expect(log.checks === 0, "关闭自动检查后启动仍查更新");
    await page.locator('.settings-pop button:has-text("打开时自动检查")').click();
    check(await until(() => log.checks === 1), "中途开启没有检查更新");
    await sleep(700);
    expect(log.applies.length === 0, "中途开启自动检查之后自己发了更新请求");
    expect(await workspace(page).isVisible(), "中途开启开关打断了工作区");
    await page.close();
  });

  await step("AC-G 检查无响应时有界进入旧版，迟到的新版结果不打断工作", async () => {
    const checked = deferred();
    const { page, log } = await openPage(browser, { checks: [() => checked.promise] });
    try {
      expect(await until(() => startup(page).isVisible()), "等待检查时缺少启动页");
      expect(await workspace(page).count() === 0, "检查未结束就提前开放工作区");
      expect(await until(() => workspace(page).isVisible(), 40000), "检查一直无响应时无法进入旧版");
      checked.resolve(ELIGIBLE);
      await sleep(700);
      expect(log.applies.length === 0, "检查超时后迟到的回包触发了更新");
      await openSettings(page);
      expect(/查不到更新/.test(await page.locator('.settings-pop').innerText()), "检查超时却没有保留失败状态");
    } finally {
      checked.resolve(ELIGIBLE);
      await page.close();
    }
  });

  await step("AC-H 自动失败后手动更新可重试，且不会再次触发自动请求", async () => {
    const { page, log } = await openPage(browser, { checks: [ELIGIBLE],
      applyReply: { ok: false, stage: "download", error: "unavailable" } });
    await openSettings(page);
    check(log.applies.length === 1, "前提：自动更新已经失败");
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
