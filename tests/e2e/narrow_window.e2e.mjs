// 窄窗不出横向滚动条(track opendesign-instant-ui,业主「顺手修」;主 agent 亲写,判据先单独 commit)。
//
// 现象(云 Windows 截图 e2-01-ui,0.98.9 起就有):窗口 1024 宽时,首页底部多一条横向滚动条,
// 输入框右边的「发送」被切掉一半。根因:`.workspace { min-width: 1260px }` —— 那是给项目页
// 三栏(变更 / 伴随 / 助手)的兜底,却加在了**所有页**上。
//
// 判据:1024×720(= 云 Windows 窗口)下,首页 / 待办 / 技能 / 图库 页面不比窗口宽,「发送」整个在窗口里;
// 项目页在 1280 宽(= 默认窗口宽)下不出滚动;项目页在 1024 宽下**照旧**出横向滚动 ——
// 那是刻意的兜底(三栏放不下时宁可滚动,不挤坏),这一条钉住「没顺手把它也拆了」。
//
// 跑法:node tests/e2e/narrow_window.e2e.mjs(自起 ds_web 于 8852,无 gateway)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8852;

const tmp = mkdtempSync(join(tmpdir(), "narrow-e2e-"));
const dsRoot = join(tmp, "ds");
const proj = "翡翠湾-1801";
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "refs"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
writeFileSync(join(dsRoot, "projects", `${proj}.md`), `# ${proj}

- 业主: [[李四]]
- 阶段: 施工跟进
- 当前状态: 等瓦工进场

## 变更记录
- [待确认] C1 2026-07-15 【玄关】玄关柜改高

## 沟通日志

---
最后更新: 2026-07-15
`);

const srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
  env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT) },
  stdio: ["ignore", "inherit", "inherit"],
});
const base = `http://127.0.0.1:${PORT}`;
for (let i = 0; ; i++) {
  try { await fetch(`${base}/api/health`); break; }
  catch { if (i > 50) throw new Error("ds_web 起不来"); await new Promise((r) => setTimeout(r, 200)); }
}

// 🔴 不能只量 document:html/body 都是 overflow:auto,滚动条可能出在 body 上,documentElement.scrollWidth 照样等于窗口宽
//    (第一版就这么假绿过四条)。量「根布局 .workspace 实际多宽」与各层 scrollWidth 取最大。
const overflow = (page) => page.evaluate(() => {
  const ws = document.querySelector(".workspace");
  const scroll = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth,
    ws ? Math.ceil(ws.getBoundingClientRect().width) : 0);
  return { scroll, client: window.innerWidth };
});

let failures = 0;
let browser = null;
try {
  browser = await launchBrowser();

  // ── 1024 宽:单栏页不许被撑宽 ────────────────────────────────────────
  const page = await browser.newPage({ viewport: { width: 1024, height: 720 } });
  await page.goto(`${base}/#/`, { waitUntil: "domcontentloaded" });
  await page.locator(".proj-list .proj-row").first().waitFor({ timeout: 10000 });
  for (const route of ["", "todos", "skills", "gallery"]) {
    await page.goto(`${base}/#/${route}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(800);
    const o = await overflow(page);
    check(o.scroll <= o.client + 1, `1024 宽 #/${route || "(首页)"} 不出横向滚动(内容 ${o.scroll} / 窗口 ${o.client})`);
  }
  await page.goto(`${base}/#/`, { waitUntil: "domcontentloaded" });
  const send = page.locator(".home-pane button", { hasText: "发送" }).first();
  await send.waitFor({ timeout: 10000 });
  const box = await send.boundingBox();
  check(!!box && box.x + box.width <= 1024, `1024 宽首页「发送」整个在窗口里(右边缘 ${box && Math.round(box.x + box.width)})`);

  // ── 项目页:1024 宽照旧兜底滚动(三栏不挤坏) ──────────────────────────
  await page.locator(".proj-list .proj-row").first().click();
  await page.waitForFunction(() => location.hash === "#/workspace", null, { timeout: 10000 });
  await page.waitForTimeout(800);
  const w = await overflow(page);
  check(w.scroll > w.client + 100, `1024 宽项目页照旧横向滚动兜底(内容 ${w.scroll} / 窗口 ${w.client})`);

  // ── 项目页:默认窗口宽 1280 下不出滚动 ───────────────────────────────
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.waitForTimeout(500);
  const w2 = await overflow(page);
  check(w2.scroll <= w2.client + 1, `1280 宽项目页不出横向滚动(内容 ${w2.scroll} / 窗口 ${w2.client})`);

  // ── 从项目页回首页:兜底要跟着撤掉(路由切换不是整页重载) ──────────────
  await page.setViewportSize({ width: 1024, height: 720 });
  await page.evaluate(() => { location.hash = "#/"; });
  await page.waitForTimeout(800);
  const h = await overflow(page);
  check(h.scroll <= h.client + 1, `从项目页切回首页后不再横向滚动(内容 ${h.scroll} / 窗口 ${h.client})`);
} catch (e) {
  failures++;
  console.error(String(e));
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}
console.log(failures === 0 ? "NARROW-WINDOW E2E: ALL PASS" : `NARROW-WINDOW E2E: ${failures} FAIL`);
process.exit(failures === 0 ? 0 : 1);
