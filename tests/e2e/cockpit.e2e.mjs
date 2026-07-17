// track opendesign-cockpit e2e:驾驶舱列 UI 事实(真 chromium + 真 ds_web,无需 gateway
// ——纯 GET 数据面,聊天不参与)。夹具自建临时 DS_ROOT + 工作区(含**非模板类目名**
// "渲染输出",判卷"照现状认");跑完自清理。
//
// 跑法:node tests/e2e/cockpit.e2e.mjs(自起 ds_web 于空闲端口)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8791;

// ── 夹具 ────────────────────────────────────────────────────────────────────
const tmp = mkdtempSync(join(tmpdir(), "cockpit-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");
const proj = "翡翠湾-1801";
const folder = "20260601 平湖 翡翠湾 3#1801";
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "refs"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
writeFileSync(join(dsRoot, "projects", `${proj}.md`), `# ${proj}

- 业主: [[李四]]
- 阶段: 施工跟进
- 当前状态: 等瓦工进场

## 变更记录
- [待确认] C1 2026-07-10 主卧衣柜改推拉门

## 沟通日志

---
最后更新: 2026-07-15
`);
// 非模板类目名 + 常规类目;PNG 魔数即可(浏览器 img 失败也不影响 DOM 断言)
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64");
mkdirSync(join(ws, folder, "渲染输出"), { recursive: true });
mkdirSync(join(ws, folder, "01-资料"), { recursive: true });
writeFileSync(join(ws, folder, "渲染输出", "客厅.png"), PNG);
writeFileSync(join(ws, folder, "01-资料", "户型.txt"), "x");
writeFileSync(join(dsRoot, "config", "workspace.json"), JSON.stringify({
  root: ws, projectsDir: ".", projects: { [proj]: folder },
}));

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

let failures = 0;
let browser = null;
try {
  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(base, { waitUntil: "domcontentloaded" });

  // ① 侧栏点开项目 → 驾驶舱速览块:阶段/业主/当前状态/相对时间
  await page.locator(`.proj-list .proj-row:has-text("${proj}")`).first().click();
  await page.locator(".cockpit-brief").waitFor({ timeout: 10000 });
  const brief = await page.locator(".cockpit-brief").innerText();
  check(brief.includes("施工跟进"), "速览:阶段 chip");
  check(brief.includes("李四"), "速览:业主已剥 [[ ]]");
  check(brief.includes("等瓦工进场"), "速览:当前状态一句话");

  // ② 类目行:非模板类目名可见(照现状认判卷)+ 活跃度列
  const rows = page.locator(".cat-row");
  await rows.first().waitFor({ timeout: 10000 });
  const rowText = (await rows.allInnerTexts()).join("\n");
  check(rowText.includes("渲染输出"), "类目:非模板名『渲染输出』上屏");
  check(rowText.includes("01-资料"), "类目:常规名并存");
  check(rowText.includes("今天"), "类目:活跃度相对时间上屏");

  // ③ 项目图 tab:图片来自任意类目(零 06-效果图 耦合),类目小标
  await page.locator('.seg .opt:has-text("项目图")').click();
  await page.locator(".thumb-grid .thumb").first().waitFor({ timeout: 10000 });
  const tag = await page.locator(".thumb .tag").first().innerText();
  check(tag.includes("渲染输出"), "项目图:非模板类目的图上屏+类目小标");

  // ④ 图墙常驻入口(<4 张图也可达)→ GalleryPage
  await page.locator(".gallery-link").click();
  await page.locator(".gallery-page, .gallery-grid, .gallery-empty").first()
    .waitFor({ timeout: 10000 });
  check(page.url().includes("#/gallery"), "图墙:常驻入口可达(图少也能进)");
} catch (e) {
  failures++;
  console.error(String(e));
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}
console.log(failures === 0 ? "COCKPIT E2E: ALL PASS" : `COCKPIT E2E: ${failures} FAIL`);
process.exit(failures === 0 ? 0 : 1);
