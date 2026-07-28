// track opendesign-stage-history e2e:P2 队列三条的**行为面**契约
// (真 chromium + 真 ds_web,无 gateway —— 三条都在未连接态可达)。
//
// 覆盖:
//   #7 切阶段:stage-chip 可点 → 下拉列**后端下发**的词表 → 选中后
//      **markdown 档案里真的改了**,UI 回显新阶段(不是只改了个 span)
//   #8 参考图标签/备注就地改:图墙 lightbox 里改标签 →
//      **refs-index.md 里真的改了**,且「来源/文件/用于」三段逐字节不变;
//      工作区图(不在索引里)**不给编辑入口**
//   #9 变更修改历史:改过的行出「改过 N 次」,展开能看到日期 + 原文
//
// 断言原则:UI 事实 + **落盘事实**(读回 markdown / 索引),不断言样式细节。
//
// 跑法:node tests/e2e/stage_history.e2e.mjs(自起 ds_web 于 8796)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8796;

// ── 夹具 ────────────────────────────────────────────────────────────────────
const tmp = mkdtempSync(join(tmpdir(), "stagehist-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");
const projA = "翡翠湾-1801";
const folderA = "20260601 平湖 翡翠湾 3#1801";
const projMd = join(dsRoot, "projects", `${projA}.md`);
const indexMd = join(dsRoot, "refs-index.md");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "refs", "奶油风", "客厅"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
mkdirSync(join(ws, folderA, "06-效果图"), { recursive: true });

// #9 素材:C1 改过两次(`## 变更历史` 段的留痕格式 = edit_change 写侧口径),
// C2 一次没改过(用来钉住"没历史就不出入口")
writeFileSync(projMd, `# ${projA}

- 业主: [[李四]]
- 阶段: 方案深化
- 当前状态: 等瓦工进场

## 变更记录
- [待确认] C1 2026-07-15 【主卧】灯位右移 30cm
- [进行中] C2 2026-07-16 玄关柜改高

## 变更历史
- C1 改于 2026-07-17｜原:灯位右移
- C1 改于 2026-07-18｜原:灯位右移 20cm
- C1 备注:业主口头确认过

---
最后更新: 2026-07-18
`);

const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64");
writeFileSync(join(dsRoot, "refs", "奶油风", "客厅", "a.jpg"), PNG);
writeFileSync(join(ws, folderA, "06-效果图", "客厅.png"), PNG);

// #8 素材:一条挂在本项目上的索引条目(格式 = add_ref 写侧口径)
writeFileSync(indexMd, `# 参考图索引

- [r1] 奶油风|客厅 | 来源:小红书 | 文件:refs/奶油风/客厅/a.jpg | 用于:${projA} | 备注:弧形吊顶

---
最后更新: 2026-07-18
`);
writeFileSync(join(dsRoot, "refs-vocab.md"), `# 风格词表

## 风格
- 奶油风
- 侘寂风
`);
writeFileSync(join(dsRoot, "config", "workspace.json"), JSON.stringify({
  root: ws, projectsDir: ".", projects: { [projA]: folderA },
}));

const readMd = () => readFileSync(projMd, "utf-8");
const readIndex = () => readFileSync(indexMd, "utf-8");
const refLine = () => readIndex().split("\n").find((l) => l.startsWith("- [r1] "));
const seg = (prefix) => (refLine().split(" | ").find((s) => s.startsWith(prefix)) ?? "");

// ── 起 ds_web ───────────────────────────────────────────────────────────────
const srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
  env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT) },
  stdio: ["ignore", "inherit", "inherit"],
});
const base = `http://127.0.0.1:${PORT}`;
for (let i = 0; ; i++) {
  try { await fetch(`${base}/api/health`); break; }
  catch { if (i > 50) throw new Error("ds_web 起不来"); await new Promise((r) => setTimeout(r, 200)); }
}

/** 轮询盘上文件,等写落地(针孔是同步的,但 UI→请求→落盘仍有毫秒级窗口)。 */
async function waitFor(fn, label, timeoutMs = 8000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    if (fn()) return true;
    await new Promise((r) => setTimeout(r, 120));
  }
  throw new Error(`FAIL: 等不到落盘 —— ${label}`);
}

let failures = 0;
let browser = null;
try {
  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  await page.goto(base, { waitUntil: "domcontentloaded" });
  await page.locator(`.proj-list .proj-row:has-text("${projA}")`).first().click();
  await page.locator(".change-row").first().waitFor({ timeout: 10000 });

  // ── #7 切阶段 ─────────────────────────────────────────────────────────
  const chip = page.locator('[data-ui="stage-chip"]').first();
  await chip.waitFor({ timeout: 10000 });
  check((await chip.innerText()).trim() === "方案深化", "#7 chip 初始显示盘上的阶段");
  const chipTag = await chip.evaluate((el) => el.tagName.toLowerCase());
  check(chipTag === "button", `#7 stage-chip 必须可点(实际 <${chipTag}>)`);

  await chip.click();
  const menu = page.locator('[data-ui="stage-menu"]');
  await menu.waitFor({ timeout: 5000 });
  const opts = (await menu.locator('[data-ui="stage-option"]').allInnerTexts())
    .map((t) => t.trim());
  check(opts.length === 11, `#7 下拉列出全部 11 个阶段(实际 ${opts.length}:${opts})`);
  check(opts[0] === "洽谈" && opts[opts.length - 1] === "售后",
    `#7 词表顺序 = 后端下发的顺序(实际 ${opts})`);

  await menu.locator('[data-ui="stage-option"]', { hasText: "施工图" }).first().click();
  await waitFor(() => readMd().includes("- 阶段: 施工图"), "#7 阶段写进 markdown");
  check(!readMd().split("## 变更记录")[0].includes("方案深化"),
    "#7 头部不许残留旧阶段");
  check(readMd().includes("- [待确认] C1 2026-07-15 【主卧】灯位右移 30cm"),
    "#7 改阶段不许碰变更行");
  await page.locator('[data-ui="stage-chip"]:has-text("施工图")').first()
    .waitFor({ timeout: 8000 });
  check(true, "#7 UI 回显新阶段");

  // esc 关菜单(与 p3-polish 的 … 菜单同规矩)
  await page.locator('[data-ui="stage-chip"]').first().click();
  await menu.waitFor({ timeout: 5000 });
  await page.keyboard.press("Escape");
  await menu.waitFor({ state: "detached", timeout: 5000 });
  check(true, "#7 esc 关闭阶段下拉");

  // ── #9 变更修改历史 ────────────────────────────────────────────────────
  const rowC1 = page.locator('.change-row:has-text("灯位右移 30cm")').first();
  const rowC2 = page.locator('.change-row:has-text("玄关柜改高")').first();
  const histBtn = rowC1.locator('[data-ui="history-toggle"]');
  await histBtn.waitFor({ timeout: 8000 });
  check((await histBtn.innerText()).includes("改过 2 次"),
    `#9 折叠态显示改过次数(实际 ${(await histBtn.innerText()).trim()})`);
  check((await rowC2.locator('[data-ui="history-toggle"]').count()) === 0,
    "#9 没改过的行不出历史入口");
  check((await rowC1.innerText()).includes("业主口头确认过"),
    "#9 备注也要显示出来(后端早就返回了)");

  await histBtn.click();
  const entries = rowC1.locator('[data-ui="history-entry"]');
  await entries.first().waitFor({ timeout: 5000 });
  const texts = (await entries.allInnerTexts()).map((t) => t.trim());
  check(texts.length === 2, `#9 展开列出两条(实际 ${texts.length})`);
  check(texts[0].includes("原:灯位右移") && texts[0].includes("7月17日"),
    `#9 首条 = 日期 + 原文(实际 ${texts[0]})`);
  check(texts[1].includes("原:灯位右移 20cm"),
    `#9 时序保持后端顺序(实际 ${texts[1]})`);
  await histBtn.click();
  check((await rowC1.locator('[data-ui="history-entry"]').count()) === 0,
    "#9 再点收起");

  // ── #8 参考图标签/备注就地改(图墙 lightbox)───────────────────────────
  // 直接走路由进图墙:本段验的是 lightbox 里改标签/备注,不是入口(「图墙 →」小字
  // 2026-07-28 按用户要求删掉;入口另有 inbox_pad_gallery.e2e.mjs 钉)。
  await page.evaluate(() => { window.location.hash = "#/gallery"; });
  await page.locator(".gallery-page").waitFor({ timeout: 10000 });
  // 相册墙:参考图库那册只有一张 → 点封面直接放大(既有语义,p2-polish 定的)
  await page.locator('.gallery-page .g-cell:has(.g-cap .g:text-is("参考"))')
    .first().click();
  await page.locator(".g-light").waitFor({ timeout: 8000 });
  const editor = page.locator('[data-ui="ref-edit"]');
  await editor.waitFor({ timeout: 8000 });
  check((await editor.locator('[data-ui="ref-style-option"]').count()) >= 2,
    "#8 风格选项来自后端下发的词表(至少奶油风/侘寂风两项)");
  check((await page.locator('[data-ui="ref-note-input"]').inputValue()) === "弧形吊顶",
    "#8 备注回填当前值");

  await editor.locator('[data-ui="ref-style-option"]', { hasText: "侘寂风" })
    .first().click();
  await page.locator('[data-ui="ref-note-input"]').fill("改成平顶");
  await page.locator('[data-ui="ref-save"]').first().click();
  await waitFor(() => refLine().includes("备注:改成平顶"), "#8 备注写进索引");
  check(refLine().startsWith("- [r1] 侘寂风|客厅 ") ||
        refLine().startsWith("- [r1] 奶油风,侘寂风|客厅 "),
    `#8 风格标签落盘(实际 ${refLine()})`);
  check(seg("来源:") === "来源:小红书", `#8 来源段逐字节不变(实际 ${seg("来源:")})`);
  check(seg("文件:") === "文件:refs/奶油风/客厅/a.jpg",
    `#8 文件段逐字节不变(实际 ${seg("文件:")})`);
  check(seg("用于:") === `用于:${projA}`, `#8 用于段逐字节不变(实际 ${seg("用于:")})`);

  // 工作区图(不在索引里)→ 没有编辑入口
  await page.keyboard.press("Escape");
  await page.locator(".g-light").waitFor({ state: "detached", timeout: 5000 });
  const wsCell = page.locator('.gallery-page .g-cell:has(.g-cap .g:text-is("06-效果图"))')
    .first();
  check((await wsCell.count()) === 1,
    "#8 夹具:图墙里应有工作区那册(06-效果图/客厅.png)");
  await wsCell.click();
  await page.locator(".g-light").waitFor({ timeout: 8000 });
  check((await page.locator('[data-ui="ref-edit"]').count()) === 0,
    "#8 工作区图不给标签编辑入口(它不在索引里)");
} catch (e) {
  failures++;
  console.error(String(e));
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}
console.log(failures === 0 ? "STAGE-HISTORY E2E: ALL PASS" : `STAGE-HISTORY E2E: ${failures} FAIL`);
process.exit(failures === 0 ? 0 : 1);
