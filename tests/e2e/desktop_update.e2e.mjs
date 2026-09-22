// 更新一栏在**真页面上**长什么样(真 chromium + 真 ds_web + 假的 odShell)。主 agent 亲写,执行腿逐字节 off-limits。
// track opendesign-electron-shell,T3 攻题后补(`…-t4-attack.out` #5 #6 #14)。
//
// 为什么纯函数判据(test_desktop_ui.mjs du6~du9)不够:组件可以不用 `showRestart()`,自己写 `state.version && <button>` ——
// 下载到 37% 就冒出「重启以更新」,点了软件退出、安装器没来;`RESTART_HINT` 常量写对了、却没渲染出来。
// 这份 e2e 由测试往页面里**推**主进程那边会推的每一种状态,看 DOM 上真的出现了什么。
//
// 覆盖:
//   A 每一种状态下:「重启以更新」只在下好之后出现(整页任何地方,弹层开着也算);收起的「设置」行上那个按钮在;
//     圆点只在「下好了 / 下载失败」时亮;弹层里的说明不说假话;失败时有「重试」;下好时「约 2 分钟、别关机」看得见
//   B 点「重启以更新」⇒ 叫 odShell.update.install() 恰好一次;点「重试」⇒ 叫 odShell.update.check()
//   C 浏览器形态(没有 odShell):只有当前版本 + 发布页链接,没有重启/重试/检查更新
//   D(T4 收货补,主 agent 读 diff 发现):弹层里「检查更新」—— 旧版一直有这个按钮;设计 D 写的是「改接」+ `update.check()` 手动查,
//     我的任务书写成「旧的查更新…全部删掉」,执行腿连按钮一起删了。没查过 / 已是最新时在,点了只叫 check;
//     查着、下着、下好了不摆(没东西可查),出错时由「重试」顶(不摆两个做同一件事的按钮)
//
// 跑法:node tests/e2e/desktop_update.e2e.mjs(自起 ds_web 于 8850)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { launchBrowser } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8850;
const tmp = mkdtempSync(join(tmpdir(), "desktopupdate-e2e-"));
const dsRoot = join(tmp, "ds");
mkdirSync(join(dsRoot, "config"), { recursive: true });
mkdirSync(join(tmp, "ws"), { recursive: true });
writeFileSync(join(dsRoot, "config", "workspace.json"),
  JSON.stringify({ root: join(tmp, "ws"), projectsDir: ".", projects: {} }));

const srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
  env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT) },
  stdio: ["ignore", "inherit", "inherit"],
});
const base = `http://127.0.0.1:${PORT}`;
let version = null;
for (let i = 0; ; i++) {
  try { version = (await (await fetch(`${base}/api/health`)).json()).version; break; }
  catch { if (i > 50) throw new Error("ds_web 起不来"); await new Promise((r) => setTimeout(r, 200)); }
}

let failures = 0;
const expect = (cond, label) => {
  if (cond) { console.log(`  ok - ${label}`); return; }
  failures++; console.error(`  FAIL: ${label}`);
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const STATES = [
  ["idle", { phase: "idle" }],
  ["checking", { phase: "checking" }],
  ["latest", { phase: "latest" }],
  ["downloading", { phase: "downloading", version: "9.9.9", percent: 37 }],
  ["查不到", { phase: "error", error: "net::ERR_INTERNET_DISCONNECTED" }],
  ["下载失败", { phase: "error", error: "ECONNRESET", version: "9.9.9" }],
  ["downloaded", { phase: "downloaded", version: "9.9.9" }],
];

let browser = null;
try {
  browser = await launchBrowser();

  // ── A / B:外壳里,逐个状态推进去看 ───────────────────────────────────
  const page = await browser.newPage({ viewport: { width: 1280, height: 860 } });
  await page.addInitScript(() => {
    const calls = [];
    window.__calls = calls;
    let state = { phase: "idle" };
    const subs = [];
    window.__push = (s) => { state = s; subs.slice().forEach((cb) => cb(s)); };
    const ok = (v = null) => () => Promise.resolve(v);
    window.odShell = {
      minimize: ok(), toggleMaximize: ok({ maximized: false }), close: ok(),
      windowState: ok({ maximized: false }), onWindowState: () => () => {}, reportStartup: ok(true),
      update: {
        check: () => { calls.push("check"); return Promise.resolve(null); },
        install: () => { calls.push("install"); return Promise.resolve(true); },
        state: () => Promise.resolve(state),
        onState: (cb) => { subs.push(cb); return () => { const i = subs.indexOf(cb); if (i >= 0) subs.splice(i, 1); }; },
      },
    };
  });
  await page.goto(`${base}/?shell=1#/workspace`, { waitUntil: "domcontentloaded" });
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.locator("nav.side").waitFor({ state: "visible", timeout: 20000 });

  const visible = (sel) => page.locator(sel).first().isVisible().catch(() => false);
  const restartTextAnywhere = () => page.evaluate(() => [...document.querySelectorAll("body *")].some((el) => {
    if (el.children.length) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== "hidden" && /重启以更新/.test(el.textContent || "");
  }));
  const popOpen = async (want) => {
    const open = await visible("[data-ui=update-status]");
    if (open !== want) { await page.click("[data-ui=settings-toggle]", { timeout: 5000 }); await sleep(300); }
  };

  // 一段炸了(找不到钩子 / 超时)记成一条有名字的 FAIL,别让整份 e2e 崩成一行栈 —— 红要红在有名字的地方
  const guard = async (name, fn) => {
    try { await fn(); } catch (e) { failures++; console.error(`  FAIL: ${name} 炸了:${String(e).split("\n")[0]}`); }
  };
  for (const [name, st] of STATES) await guard(`A ${name}`, async () => {
    await page.evaluate((s) => window.__push(s), st);
    await sleep(400);
    const done = st.phase === "downloaded";
    const dlFail = st.phase === "error" && !!st.version;
    console.log(`\n== A ${name}`);
    await popOpen(false);
    expect(await visible("[data-ui=update-restart]") === done,
      `收起的「设置」行上「重启以更新」${done ? "在" : "不在"}`);
    expect(await visible("[data-ui=update-badge]") === (done || dlFail),
      `侧栏圆点${done || dlFail ? "亮" : "不亮"}`);
    await popOpen(true);
    const label = (await page.locator("[data-ui=update-status]").first().innerText().catch(() => "")).trim();
    expect(label.length > 0, `弹层里的更新一栏有话说:「${label}」`);
    if (st.phase === "error") {
      expect(!/已是最新|最新版/.test(label), `出错时不说已是最新:「${label}」`);
      expect(await visible("[data-ui=update-retry]"), "出错时有「重试」");
    } else {
      expect(!(await visible("[data-ui=update-retry]")), "没出错不摆「重试」");
    }
    const canCheck = st.phase === "idle" || st.phase === "latest";
    expect(await visible("[data-ui=update-check]") === canCheck,
      `弹层里「检查更新」${canCheck ? "在(没查过 / 已是最新时要能手动查)" : "不在"}`);
    expect(await restartTextAnywhere() === done,
      `整页(弹层开着)任何地方「重启以更新」这几个字${done ? "看得见" : "都不许出现"}`);
    // 复核:只看「整页有这两句」⇒ 页面别处本来就有时,提示没渲染也绿。改成**对照**:下好之前不许有、下好之后必须有。
    const hint = await page.evaluate(() => /2 ?分钟/.test(document.body.innerText) && /关机/.test(document.body.innerText));
    expect(hint === done, done ? "下好之后「约 2 分钟、期间别关机」真的渲染出来了"
                               : "还没下好,页面上不许已经有「约 2 分钟、期间别关机」(否则上一条问不出东西)");
  });

  await guard("B", async () => {
  console.log("\n== B 点下去叫到对的方法");
  await page.evaluate(() => { window.__calls.length = 0; });
  await popOpen(false);
  await page.click("[data-ui=update-restart]");
  await sleep(300);
  let calls = await page.evaluate(() => window.__calls.slice());
  expect(calls.filter((c) => c === "install").length === 1, `点「重启以更新」⇒ install 恰好一次(实测 ${JSON.stringify(calls)})`);
  await page.evaluate(() => { window.__calls.length = 0; window.__push({ phase: "error", error: "x", version: "9.9.9" }); });
  await sleep(300);
  await popOpen(true);
  await page.click("[data-ui=update-retry]");
  await sleep(300);
  calls = await page.evaluate(() => window.__calls.slice());
  expect(calls.includes("check") && !calls.includes("install"), `点「重试」⇒ 只叫 check(实测 ${JSON.stringify(calls)})`);

  console.log("\n== D 手动检查更新");
  await page.evaluate(() => { window.__calls.length = 0; window.__push({ phase: "latest" }); });
  await sleep(300);
  await popOpen(true);
  await page.click("[data-ui=update-check]");
  await sleep(300);
  calls = await page.evaluate(() => window.__calls.slice());
  expect(JSON.stringify(calls) === JSON.stringify(["check"]), `点「检查更新」⇒ 只叫 check 一次(实测 ${JSON.stringify(calls)})`);
  });
  await page.close();

  // ── C 浏览器形态 ────────────────────────────────────────────────────
  console.log("\n== C 浏览器里(没有更新器):当前版本 + 发布页链接");
  await guard("C", async () => {
  const p2 = await browser.newPage({ viewport: { width: 1280, height: 860 } });
  await p2.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
  await p2.reload({ waitUntil: "domcontentloaded" });
  await p2.locator("nav.side").waitFor({ state: "visible", timeout: 20000 });
  await p2.click("[data-ui=settings-toggle]");
  await sleep(400);
  const txt = await p2.locator("[data-ui=update-status]").first().innerText().catch(() => "");
  expect(txt.includes(version), `显示当前版本 ${version}(实测「${txt}」)`);
  const link = await p2.locator('a[href^="https://github.com/SunJ1ayu/OpenDesign/releases"]').count();
  expect(link >= 1, "有发布页链接");
  expect(await p2.locator("[data-ui=update-restart], [data-ui=update-retry], [data-ui=update-check]").count() === 0,
    "没有重启 / 重试 / 检查更新(浏览器里没有更新器)");
  await p2.close();
  });
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}

console.log(failures === 0 ? "\n全部通过" : `\n${failures} 条不通过`);
process.exit(failures === 0 ? 0 : 1);
