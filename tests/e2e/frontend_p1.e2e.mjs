// track opendesign-frontend-p1 e2e:三处"直接点"全链(真 chromium + 真 ds_web,
// 无需 gateway)。①变更正文就地编辑(既有 edit 针孔 new_text)②收件箱单条「跳过」
// (针孔⑧ amend:旧案 superseded、剩余重暂存、确认后落位)③项目↔文件夹关联下拉
// (针孔⑨ bind:写 workspace.json 显式映射)。夹具自建临时 DS_ROOT+工作区,跑完自清理。
//
// 跑法:node tests/e2e/frontend_p1.e2e.mjs(自起 ds_web 于 8793)
import { spawn, execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync, existsSync, readFileSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, check, expandInbox } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8793;

// ── 夹具 ────────────────────────────────────────────────────────────────────
const tmp = mkdtempSync(join(tmpdir(), "fp1-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");
const projA = "翡翠湾-1801";                       // 已映射:就地编辑 + 收件箱场景
const folderA = "20260601 平湖 翡翠湾 3#1801";
const projB = "山语城-902";                        // 已建档未映射:bind 场景
const folderB = "老宅翻新项目夹";                  // token 对不上 projB → 不会被自动绑
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "refs"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
writeFileSync(join(dsRoot, "projects", `${projA}.md`), `# ${projA}

- 业主: [[李四]]
- 阶段: 施工跟进

## 变更记录
- [待确认] C1 2026-07-15 玄关柜改高

## 沟通日志

---
最后更新: 2026-07-15
`);
writeFileSync(join(dsRoot, "projects", `${projB}.md`), `# ${projB}

- 业主: [[王五]]
- 阶段: 方案深化

## 变更记录

## 沟通日志

---
最后更新: 2026-07-14
`);
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64");
mkdirSync(join(ws, folderA, "01-资料"), { recursive: true });
mkdirSync(join(ws, folderB), { recursive: true });
mkdirSync(join(ws, "00-收件箱"), { recursive: true });
mkdirSync(join(ws, "03-共享资源", "参考图库"), { recursive: true });
writeFileSync(join(ws, "00-收件箱", "翡翠湾玄关参考.png"), PNG);
writeFileSync(join(ws, "00-收件箱", "翡翠湾户型图.dwg"), "DWG");
const wsCfgPath = join(dsRoot, "config", "workspace.json");
writeFileSync(wsCfgPath, JSON.stringify({
  root: ws, projectsDir: ".", projects: { [projA]: folderA },
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

/** 聊天暂存替身(同 intake.e2e):直调 ds_intake 核心,不烧 LLM。 */
function stageViaCore() {
  const py = `
import json, sys
sys.path.insert(0, ${JSON.stringify(join(ROOT, "bin"))})
import ds_intake
r = ds_intake.stage_intake(
    [{"name": "翡翠湾玄关参考.png", "project": None, "category": "参考图"},
     {"name": "翡翠湾户型图.dwg", "project": ${JSON.stringify(projA)}, "category": "CAD"}],
    allowed_roots=[${JSON.stringify(ws)}], ds_root=${JSON.stringify(dsRoot)})
print(json.dumps(r, ensure_ascii=False))
`;
  const out = execFileSync("python3", ["-c", py], { encoding: "utf-8" });
  return JSON.parse(out.trim().split("\n").pop());
}

let failures = 0;
let browser = null;
try {
  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(base, { waitUntil: "domcontentloaded" });

  // ① 变更正文就地编辑:hover 冒出「编辑」→ 改文本 → Enter → 重拉后新文本上屏,磁盘留痕
  await page.locator(`.proj-list .proj-row:has-text("${projA}")`).first().click();
  const row = page.locator('.change-row:has-text("玄关柜改高")');
  await row.waitFor({ timeout: 10000 });
  await row.hover();
  await row.locator(".edit-trigger").click();
  const editInput = page.locator(".change-scroll .edit-text");
  await editInput.waitFor({ timeout: 5000 });
  await editInput.fill("玄关柜改到 2.4 米,柜顶留检修口");
  await editInput.press("Enter");
  await page.locator('.change-row .txt:has-text("2.4 米")').waitFor({ timeout: 10000 });
  check(true, "就地编辑:新文本经整列重拉上屏");
  const mdA = readFileSync(join(dsRoot, "projects", `${projA}.md`), "utf-8");
  check(mdA.includes("玄关柜改到 2.4 米,柜顶留检修口"), "就地编辑:磁盘正文已更新");
  check(mdA.includes("原:玄关柜改高"), "就地编辑:变更历史段留痕(原文)");

  // ② 收件箱单条「跳过」:暂存2 → 跳过 png 行 → 剩 1 行 → 确认 → dwg 落位、png 还在箱
  const staged = stageViaCore();
  check(staged.ok === true, "核心 stage 成功(2 项)");
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.locator(`.proj-list .proj-row:has-text("${projA}")`).first().click();
  await page.locator(".inbox-card").waitFor({ timeout: 10000 });
  await expandInbox(page); // v4 起默认收成摘要行,两态兼容
  await page.locator(".inbox-plan").waitFor({ timeout: 10000 });
  check((await page.locator(".inbox-plan .plan-row").count()) === 2, "方案预览 2 行");
  await page.locator('.inbox-plan .plan-row:has-text("翡翠湾玄关参考.png") .skip-btn').click();
  // localEpoch bump → 重拉:旧案 superseded 被过滤,新案只剩 dwg 一行
  await page.locator('.inbox-plan:has-text("1 项")').waitFor({ timeout: 10000 });
  const planTxt = await page.locator(".inbox-plan").innerText();
  check(planTxt.includes("翡翠湾户型图.dwg"), "跳过后:剩余行=dwg");
  check(!planTxt.includes("翡翠湾玄关参考.png"), "跳过后:png 行已剔除");
  // 旧案磁盘留痕:superseded_at 已写、文件未删
  const plansDir = join(dsRoot, "organize", "plans");
  const oldPlan = JSON.parse(readFileSync(join(plansDir, `plan_${staged.plan_id}.json`), "utf-8"));
  check(!!oldPlan.superseded_at, "旧案标 superseded_at(审计留痕不删)");
  await page.locator('.inbox-plan button:has-text("确认执行")').click();
  await page.locator(".inbox-plan").waitFor({ state: "detached", timeout: 10000 });
  check(existsSync(join(ws, folderA, "03-CAD", "翡翠湾户型图.dwg")), "确认后:dwg 落项目 03-CAD");
  check(existsSync(join(ws, "00-收件箱", "翡翠湾玄关参考.png")), "被跳过的 png 仍在收件箱");

  // ③ 项目↔文件夹关联:未映射项目 → 下拉选文件夹 → 关联 → 映射写盘、表单消失
  await page.locator(`.proj-list .proj-row:has-text("${projB}")`).first().click();
  await page.locator(".bind-form").waitFor({ timeout: 10000 });
  await page.selectOption(".bind-select", folderB);
  await page.locator('.bind-form button:has-text("关联")').click();
  await page.locator(".bind-form").waitFor({ state: "detached", timeout: 10000 });
  const cfgAfter = JSON.parse(readFileSync(wsCfgPath, "utf-8"));
  check(cfgAfter.projects[projB] === folderB, "关联后:workspace.json 写入显式映射");
  check(cfgAfter.projects[projA] === folderA, "既有映射原样保留");
} catch (e) {
  failures++;
  console.error(String(e));
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}
console.log(failures === 0 ? "FRONTEND-P1 E2E: ALL PASS" : `FRONTEND-P1 E2E: ${failures} FAIL`);
process.exit(failures === 0 ? 0 : 1);
