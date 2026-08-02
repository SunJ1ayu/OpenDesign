// track opendesign-frontend-p3-polish e2e:修改单 §I 第二轮六条的**行为面**契约
// (真 chromium + 真 ds_web,无 gateway——未连接态即可覆盖 I1/I2/I3/I4/I6)。
//
// 覆盖:
//   I1 图墙「来源」chip 云 → 描边下拉(单选过滤 + × 清除)
//   I2 未建档页「建档」= 主按钮(.btn-primary)
//   I3 列宽重分配:伴随列 ~400px / 助手列 ~300px
//   I4 「最近更新」行可点:白名单内 .dwg → 真开该文件;.bat → 退化为开所在文件夹
//      (DS_OPEN_CMD 注入记录脚本,断言启动器实际收到的路径——永不真开程序)
//   I6 侧栏项目名:括号开头显括号后内容,title 兜全名
// I5(助手头部降噪 + 退出登录收进 … 菜单)需已连接态 → 归真 gateway/真机验收。
// 纯样式项(颜色/圆角/两行截断的视觉)不在此断言,归 verify 亲读 diff。
//
// 跑法:node tests/e2e/frontend_p3_polish.e2e.mjs(自起 ds_web 于 8795)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync, readFileSync, existsSync, chmodSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8795;

// ── 夹具 ────────────────────────────────────────────────────────────────────
const tmp = mkdtempSync(join(tmpdir(), "fp3-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");
const projA = "翡翠湾-1801";
const folderA = "20260601 平湖 翡翠湾 3#1801";
// I6:括号开头的长编号名(未建档行,直接由工作区发现)
const folderParen = "(20260612)周宁 云栖佳苑 12#1802";
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "refs"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
writeFileSync(join(dsRoot, "projects", `${projA}.md`), `# ${projA}

- 业主: [[李四]]
- 阶段: 施工跟进
- 当前状态: 等瓦工进场

## 变更记录
- [待确认] C1 2026-07-15 【玄关】玄关柜改高

## 沟通日志

---
最后更新: 2026-07-15
`);
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64");
mkdirSync(join(ws, folderA, "03-CAD"), { recursive: true });
mkdirSync(join(ws, folderA, "06-效果图"), { recursive: true });
mkdirSync(join(ws, folderParen), { recursive: true });
// I4 素材:白名单内 .dwg(应真开文件)+ 白名单外 .bat(应退化为开文件夹)
// mtime 拉开,保证两者都稳定落进「最近更新」且顺序确定
const dwgPath = join(ws, folderA, "03-CAD", "平面图.dwg");
const batPath = join(ws, folderA, "03-CAD", "跑批.bat");
writeFileSync(dwgPath, "DWG");
writeFileSync(batPath, "@echo off");
// I1 素材:「来源」= 顶层类目(GalleryItem.group,相册卡底部显示的就是它),
// 所以夹具必须跨**两个顶层类目**才谈得上来源过滤——只造一个类目会把断言逼成
// 相册粒度的错误语义(2026-07-20 收货闸③实抓,已修夹具而非改语义)。
mkdirSync(join(ws, folderA, "06-效果图", "定稿"), { recursive: true });
mkdirSync(join(ws, folderA, "06-效果图", "初稿"), { recursive: true });
mkdirSync(join(ws, folderA, "02-参考图"), { recursive: true });
writeFileSync(join(ws, folderA, "06-效果图", "定稿", "客厅.png"), PNG);
writeFileSync(join(ws, folderA, "06-效果图", "初稿", "餐厅.png"), PNG);
writeFileSync(join(ws, folderA, "02-参考图", "沙发.png"), PNG);
writeFileSync(join(dsRoot, "config", "workspace.json"), JSON.stringify({
  root: ws, projectsDir: ".",
  projects: { [projA]: folderA },
}));

// ── DS_OPEN_CMD:记录脚本(启动器替身,永不真开程序)──────────────────────
const openLog = join(tmp, "open.log");
const openCmd = join(tmp, "record-open.sh");
writeFileSync(openCmd, `#!/bin/sh\nprintf '%s\\n' "$1" >> ${JSON.stringify(openLog)}\n`);
chmodSync(openCmd, 0o755);
const openedPaths = () =>
  (existsSync(openLog) ? readFileSync(openLog, "utf-8") : "")
    .split("\n").map((s) => s.trim()).filter(Boolean);

// ── 起 ds_web ───────────────────────────────────────────────────────────────
const srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
  env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT), DS_OPEN_CMD: openCmd },
  stdio: ["ignore", "inherit", "inherit"],
});
const base = `http://127.0.0.1:${PORT}`;
for (let i = 0; ; i++) {
  try { await fetch(`${base}/api/health`); break; }
  catch { if (i > 50) throw new Error("ds_web 起不来"); await new Promise((r) => setTimeout(r, 200)); }
}

/** 等启动器日志出现 n 条(异步 Popen,给它一点时间)。 */
async function waitOpened(n, timeoutMs = 5000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    if (openedPaths().length >= n) return openedPaths();
    await new Promise((r) => setTimeout(r, 100));
  }
  return openedPaths();
}

let failures = 0;
let browser = null;
try {
  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  await page.goto(base, { waitUntil: "domcontentloaded" });

  // ── I6:侧栏项目名(括号开头 → 显括号后内容;title 兜全名)──────────────
  const parenRow = page.locator(`.proj-list .proj-row[title*="${folderParen}"]`).first();
  await parenRow.waitFor({ timeout: 10000 });
  const nmTxt = (await parenRow.locator(".nm").innerText()).trim();
  check(nmTxt === "周宁 云栖佳苑 12#1802",
    `I6 侧栏名显括号后内容(实际:${nmTxt})`);
  const nmTitle = await parenRow.getAttribute("title");
  check(nmTitle.includes(folderParen), "I6 title 含完整原名");

  // ── 进 projA 工作区 ────────────────────────────────────────────────────
  await page.locator(`.proj-list .proj-row:has-text("${projA}")`).first().click();
  await page.locator(".change-row").first().waitFor({ timeout: 10000 });

  // ── I3:列宽重分配(伴随列 ~400 / 助手列 ~300)────────────────────────
  const asideW = await page.locator(".aside").evaluate((el) => el.getBoundingClientRect().width);
  const chatW = await page.locator(".chatcol").evaluate((el) => el.getBoundingClientRect().width);
  check(Math.abs(asideW - 400) <= 2, `I3 伴随列 ≈400px(实际 ${asideW})`);
  check(Math.abs(chatW - 300) <= 2, `I3 助手列 ≈300px(实际 ${chatW})`);

  // ── I4:「最近更新」行可点 ────────────────────────────────────────────
  const recentRows = page.locator('[data-ui="recent-row"]');
  await recentRows.first().waitFor({ timeout: 10000 });
  const n = await recentRows.count();
  check(n >= 2, `I4 最近更新至少两行(实际 ${n})`);
  for (let i = 0; i < n; i++) {
    const tag = await recentRows.nth(i).evaluate((el) => el.tagName.toLowerCase());
    check(tag === "button", `I4 第 ${i} 行是可点 button(实际 ${tag})`);
  }
  const dwgRow = page.locator('[data-ui="recent-row"]:has-text("平面图.dwg")').first();
  check((await dwgRow.getAttribute("title")).includes("03-CAD/平面图.dwg"),
    "I4 title 显完整 类目/文件名");

  // 白名单内 .dwg → 启动器收到该文件本身
  await dwgRow.click();
  let opened = await waitOpened(1);
  check(opened.length === 1, `I4 点 .dwg 触发一次启动(实际 ${opened.length})`);
  check(opened[0] === dwgPath, `I4 .dwg 开的是文件本身(实际 ${opened[0]})`);

  // 白名单外 .bat → 退化为开所在文件夹,**绝不开 .bat 本身**
  const batRow = page.locator('[data-ui="recent-row"]:has-text("跑批.bat")').first();
  await batRow.click();
  opened = await waitOpened(2);
  check(opened.length === 2, `I4 点 .bat 触发一次启动(实际 ${opened.length})`);
  check(opened[1] === join(ws, folderA, "03-CAD"),
    `I4 .bat 退化为开所在文件夹(实际 ${opened[1]})`);
  check(!opened.includes(batPath), "I4 .bat 本身绝不允许被启动");

  // 嵌套文件(设计师的 定稿/初稿 子目录是常态):必须开到真实嵌套路径,
  // 而不是 类目/文件名(2026-07-20 subkimi 抓的规格级缺陷,三份 oracle 原都漏测)
  const nestedRow = page.locator('[data-ui="recent-row"]:has-text("客厅.png")').first();
  check((await nestedRow.getAttribute("title")).includes("06-效果图/定稿/客厅.png"),
    "I4 嵌套行 title 显完整嵌套 rel");
  await nestedRow.click();
  opened = await waitOpened(3);
  check(opened.length === 3, `I4 点嵌套 .png 触发一次启动(实际 ${opened.length})`);
  check(opened[2] === join(ws, folderA, "06-效果图", "定稿", "客厅.png"),
    `I4 嵌套文件开的是真实嵌套路径(实际 ${opened[2]})`);

  // ── I1:图墙「来源」= 描边下拉,不是 chip 云 ──────────────────────────
  // 直接走路由进图墙:本段验的是「来源」下拉的形态,不是入口(「图墙 →」小字
  // 2026-07-28 按用户要求删掉;入口另有 inbox_pad_gallery.e2e.mjs 钉)。
  await page.evaluate(() => { window.location.hash = "#/gallery"; });
  await page.locator(".gallery-page").waitFor({ timeout: 10000 });
  const srcSel = page.locator('[data-ui="gallery-source"]');
  await srcSel.waitFor({ timeout: 10000 });
  check(await srcSel.evaluate((el) => el.tagName.toLowerCase()) === "select",
    "I1 「来源」是 select 下拉");
  const chipRows = await page.locator(".g-chiprow").allInnerTexts();
  check(!chipRows.some((t) => t.trim().startsWith("来源")),
    "I1 顶部「来源」chip 云已移除");
  // 「来源」= 顶层类目(不是相册/子文件夹):两个类目 + 「全部来源」= 3 项
  const opts = (await srcSel.locator("option").allInnerTexts()).map((t) => t.trim());
  check(opts.length === 3, `I1 下拉 = 全部来源 + 2 个顶层类目(实际 ${opts.length} 项:${opts})`);
  check(opts.includes("06-效果图") && opts.includes("02-参考图"),
    `I1 选项是顶层类目而非子文件夹(实际 ${opts})`);
  check(!opts.some((t) => t === "定稿" || t === "初稿"),
    `I1 子文件夹「定稿/初稿」不该出现在来源里(实际 ${opts})`);

  // ── I2:未建档页「建档」= 主按钮 ──────────────────────────────────────
  await page.locator(`.proj-list .proj-row[title*="${folderParen}"]`).first().click();
  const regBtn = page.locator('.create-proj-form button').last();
  await regBtn.waitFor({ timeout: 10000 });
  const cls = await regBtn.getAttribute("class");
  check(cls.includes("btn-primary"), `I2 建档=主按钮 .btn-primary(实际 class="${cls}")`);
} catch (e) {
  failures++;
  console.error(String(e));
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}
console.log(failures === 0 ? "FRONTEND-P3-POLISH E2E: ALL PASS" : `FRONTEND-P3-POLISH E2E: ${failures} FAIL`);
process.exit(failures === 0 ? 0 : 1);
