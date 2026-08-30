// 前端启动上报的 e2e(真 chromium + 真 ds_web)。主 agent 亲写。
//
// 🔴 **为什么非要真浏览器**:外壳那边的「首帧看门」靠前端回叫来判断"界面画出来了没有"。
//    如果这条链在真环境里断了,表现和白屏一模一样 ⇒ **每次开机都误报**。
//    而单元测试拿假对象一定绿(判据 s7/s8 在 Linux 上验的是外壳那一侧的逻辑,
//    验不了"网页真的会叫这一声")。design.md 的 oracle 表里就写着:
//    接得住它的只有真浏览器 + Windows 真截图,不是任何数量的单测。
//
// 自审时抓到的那条真 bug 也钉在这里(B 段):第一版 `reportFirstFrame()` 在
// `render()` 之后同步等两帧就下结论,而 React 18 的 render 是**异步**的 ——
// 健康启动会被报成"尺寸异常"、且永不报成功。
//
// 覆盖:
//   A 页面加载后,`report_startup` **真的被调用了**(桥在 pywebviewready 之后补发)
//   B 一定收到 `frontend.frame_submitted`,**且不许收到 frontend.error**
//   C 事件名都在白名单内(外壳那边会丢弃白名单外的,两边要对得上)
//
// 跑法:node tests/e2e/startup_report.e2e.mjs(自起 ds_web 于 8831)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { launchBrowser } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8831;

const tmp = mkdtempSync(join(tmpdir(), "startupreport-e2e-"));
const dsRoot = join(tmp, "ds");
mkdirSync(join(dsRoot, "config"), { recursive: true });
writeFileSync(join(dsRoot, "config", "workspace.json"),
  JSON.stringify({ root: join(tmp, "ws"), projectsDir: ".", projects: {} }));
mkdirSync(join(tmp, "ws"), { recursive: true });

const srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
  env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT) },
  stdio: ["ignore", "inherit", "inherit"],
});
const base = `http://127.0.0.1:${PORT}`;
for (let i = 0; ; i++) {
  try { await fetch(`${base}/api/health`); break; }
  catch { if (i > 50) throw new Error("ds_web 起不来"); await new Promise((r) => setTimeout(r, 200)); }
}

// 和 bin/ds_diag.py 的 UI_EVENTS 一致。对不上就是两边漂了。
const WHITELIST = new Set([
  "frontend.bundle_started", "frontend.react_committed",
  "frontend.frame_submitted", "frontend.error", "frontend.resource_failed",
]);

let failures = 0;
const expect = (cond, label) => {
  if (cond) { console.log(`  ok - ${label}`); return; }
  failures++; console.error(`  FAIL: ${label}`);
};

let browser = null;
try {
  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1280, height: 860 } });

  // 装一个假的 pywebview 桥 —— 在页面脚本之前注入,走的正是真实那条路
  // (外壳注入得比页面晚,所以还要派一次 pywebviewready 让缓存补发)。
  await page.addInitScript(() => {
    const seen = [];
    window.__seen = seen;
    window.pywebview = {
      api: {
        report_startup(event, detail) { seen.push([event, detail]); return Promise.resolve({ accepted: true }); },
        // 🔴 桩必须把前端会叫的方法**补全**:第一版只放了 report_startup,
        //    于是 WindowChrome 叫 window_state() 时页面真抛异常,B 段红在了
        //    我自己的桩上。报警器没错、桩不全 —— 记在这儿免得下个人再踩。
        window_state() { return Promise.resolve({ maximized: false }); },
        minimize() { return Promise.resolve(null); },
        toggle_maximize() { return Promise.resolve({ maximized: false }); },
        close_window() { return Promise.resolve(null); },
        begin_drag() { return Promise.resolve(null); },
        begin_resize() { return Promise.resolve(null); },
      },
    };
    // 模拟外壳"注入完成"的时机:页面已经跑了一会儿才派。
    setTimeout(() => window.dispatchEvent(new Event("pywebviewready")), 50);
  });

  await page.goto(`${base}/?shell=1`, { waitUntil: "domcontentloaded" });

  // 等 frame_submitted 或超时(比前端自己的帧预算宽,免得判据比被测物还急)
  await page.waitForFunction(
    () => (window.__seen || []).some(([e]) => e === "frontend.frame_submitted"),
    { timeout: 15000 },
  ).catch(() => {});

  const seen = await page.evaluate(() => window.__seen || []);
  const names = seen.map(([e]) => e);
  console.log(`\n== 收到的事件:${JSON.stringify(names)}`);

  console.log("\n== A 桥真的被调用了");
  expect(seen.length > 0,
    `report_startup 被叫到了(实测 ${seen.length} 次)—— 一次都没有 = 这条链在真环境里是断的`);

  console.log("\n== B 一定报出「画出来了」,且不许报错");
  expect(names.includes("frontend.frame_submitted"),
    `收到 frontend.frame_submitted —— 收不到的话外壳的首帧看门每次都会误报`);
  const errs = seen.filter(([e]) => e === "frontend.error");
  expect(errs.length === 0,
    `健康启动不许报 frontend.error(实测 ${JSON.stringify(errs)})`);

  console.log("\n== C 事件名和外壳白名单对得上");
  const stray = names.filter((n) => !WHITELIST.has(n));
  expect(stray.length === 0,
    `没有白名单外的事件名(实测 ${JSON.stringify(stray)})—— 有的话外壳会静默丢弃`);
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}

console.log(failures === 0 ? "\n全部通过" : `\n${failures} 条不通过`);
process.exit(failures === 0 ? 0 : 1);
