// track opendesign-intake e2e:收件箱卡片全链(真 chromium + 真 ds_web,无需 gateway
// ——GET 数据面 + 针孔④ POST,聊天暂存这步用核心直调替身)。夹具自建临时 DS_ROOT +
// 工作区(收件箱 3 文件:图/dwg/未知扩展);跑完自清理。
//
// 跑法:node tests/e2e/intake.e2e.mjs(自起 ds_web 于空闲端口)
import { spawn, execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync, existsSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8792;

// ── 夹具 ────────────────────────────────────────────────────────────────────
const tmp = mkdtempSync(join(tmpdir(), "intake-e2e-"));
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

## 变更记录

## 沟通日志

---
最后更新: 2026-07-15
`);
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64");
mkdirSync(join(ws, folder, "01-资料"), { recursive: true });
mkdirSync(join(ws, "00-收件箱"), { recursive: true });
mkdirSync(join(ws, "03-共享资源", "参考图库"), { recursive: true });
writeFileSync(join(ws, "00-收件箱", "翡翠湾玄关参考.png"), PNG);
writeFileSync(join(ws, "00-收件箱", "翡翠湾户型图.dwg"), "DWG");
writeFileSync(join(ws, "00-收件箱", "神秘文件.xyz"), "x");
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

/** 聊天暂存的替身:e2e 不烧 LLM,直调 ds_intake 核心(与 MCP 工具同一函数)。 */
function stageViaCore() {
  const py = `
import json, sys
sys.path.insert(0, ${JSON.stringify(join(ROOT, "bin"))})
import ds_intake
r = ds_intake.stage_intake(
    [{"name": "翡翠湾玄关参考.png", "project": None, "category": "参考图"},
     {"name": "翡翠湾户型图.dwg", "project": ${JSON.stringify(proj)}, "category": "CAD"}],
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

  // ① 进工作区路由 → 收件箱卡片:3 条目 + 确定性建议
  await page.locator(`.proj-list .proj-row:has-text("${proj}")`).first().click();
  await page.locator(".inbox-card").waitFor({ timeout: 10000 });
  const card = await page.locator(".inbox-card").innerText();
  check(card.includes("翡翠湾玄关参考.png"), "收件箱:图片条目上屏");
  check(card.includes("→ 参考图"), "收件箱:图片建议=参考图(入口约定)");
  check(card.includes("翡翠湾 3#1801 · CAD"), "收件箱:dwg 项目 token 唯一命中+CAD");
  check(card.includes("待认领"), "收件箱:未知扩展=待认领,不猜");

  // ② 聊天暂存(核心直调替身)→ 刷新 → 待确认方案预览可见
  const staged = stageViaCore();
  check(staged.ok === true, "核心 stage 成功(零改动)");
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.locator(`.proj-list .proj-row:has-text("${proj}")`).first().click();
  await page.locator(".inbox-plan").waitFor({ timeout: 10000 });
  const plan = await page.locator(".inbox-plan").innerText();
  check(plan.includes("参考图库"), "预览:参考图 → 共享参考图库");
  check(plan.includes("03-CAD"), "预览:dwg → 项目 03-CAD");
  // stage 零改动:文件还在收件箱
  check(existsSync(join(ws, "00-收件箱", "翡翠湾户型图.dwg")), "stage 后文件未动");

  // ③ 点「确认执行」→ 文件真归位 + 卡片清掉待确认 + audit 落盘
  await page.locator('.inbox-plan button:has-text("确认执行")').click();
  await page.locator(".inbox-plan").waitFor({ state: "detached", timeout: 10000 });
  check(existsSync(join(ws, "03-共享资源", "参考图库", "翡翠湾玄关参考.png")),
    "确认后:参考图落共享参考图库");
  check(existsSync(join(ws, folder, "03-CAD", "翡翠湾户型图.dwg")),
    "确认后:dwg 落项目 03-CAD(目录自动建)");
  check(!existsSync(join(ws, "00-收件箱", "翡翠湾户型图.dwg")), "确认后:收件箱已清");
  const audit = readFileSync(join(dsRoot, "organize", "audit.log"), "utf-8");
  check(audit.includes(staged.plan_id), "audit.log 记录了本次执行");
  // 未认领的神秘文件还在箱里,卡片仍显示
  const after = await page.locator(".inbox-card").innerText();
  check(after.includes("神秘文件.xyz"), "未认领文件仍在卡片");
} catch (e) {
  failures++;
  console.error(String(e));
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}
console.log(failures === 0 ? "INTAKE E2E: ALL PASS" : `INTAKE E2E: ${failures} FAIL`);
process.exit(failures === 0 ? 0 : 1);
