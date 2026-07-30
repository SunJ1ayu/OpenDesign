// 工作区变更列:备注可写可改 e2e(真 chromium + 真 ds_web)。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// 用户 07-30 真机原话:「项目工作区的待办里的备注无法修改,没有用户自己写入的通道」。
// 诊断(tasks.md A):**不是字段没人写,是一个写口两个读侧只接了一个** ——
// 后端 `note` 早在 /api/changes/edit 白名单里(ds_web.py `_EDIT_ALLOWED_KEYS`),
// 待办页有输入框(TodoPage 的 .edit-note),但 ChangesColumn 的行内编辑器只有
// new_text,备注那行是纯只读 <span class="note-tag">。而用户天天待的是工作区。
// ⇒ 本单纯前端,后端一字不动。
//
// 覆盖:
//   A 工作区行内编辑器里**有备注输入框**,且复用待办页同一套 `.edit-note`
//     (不另起第二套编辑语言 —— 与 GroupToggle/boolPrefs 同一条纪律)。
//   B 写备注 → 保存 → 行上出现「备注:…」**且磁盘 `## 变更历史` 段真落了**
//     (真写口,不是乐观 tag;TodoPage 那份是会话级 noted 映射,这里不许照抄)。
//   C 再点编辑 → 备注框**预填**既有备注(在原文上改,不是重打;待办页同口径)。
//   D **只改备注、不动正文** → 正文不变,且**不产生「改过」历史留痕**
//     (别把没改的 new_text 变成一条假留痕)。
//   E 备注 + 正文一起改 → 两者都落盘,正文那条留痕照常。
//   F 取消 → 一个字都不写。
//
// 跑法:node tests/e2e/ws_change_note.e2e.mjs(自起 ds_web 于 8816)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8816;
const TODAY = "2026-07-30";
const PROJ = "张宅-1101";

const tmp = mkdtempSync(join(tmpdir(), "wsnote-e2e-"));
const dsRoot = join(tmp, "ds");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });

// C1 = 已有备注(验预填);C2/C3 = 无备注(验新写入)。
// 备注行格式与写侧同处定义:`## 变更历史` 段内 `- C{n} 备注:{内容}`(ds_tools._HISTORY_NOTE_RE)。
writeFileSync(join(dsRoot, "projects", `${PROJ}.md`), `# ${PROJ}

- 业主: [[王女士]]
- 阶段: 施工跟进

## 变更记录
- [待确认] C1 2026-07-28 【客厅】吊顶改平顶
- [待确认] C2 2026-07-28 【主卧】衣柜加到顶
- [待确认] C3 2026-07-28 【厨房】加净水器点位

## 变更历史
- C1 备注:业主口头确认

## 沟通日志

---
最后更新: ${TODAY}
`);
writeFileSync(join(dsRoot, "config", "workspace.json"), JSON.stringify({ projects: {} }));

const srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
  env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT), DS_TODAY: TODAY },
  stdio: ["ignore", "inherit", "inherit"],
});
const base = `http://127.0.0.1:${PORT}`;
for (let i = 0; ; i++) {
  try { await fetch(`${base}/api/health`); break; }
  catch { if (i > 50) throw new Error("ds_web 起不来"); await new Promise((r) => setTimeout(r, 200)); }
}

let failures = 0;
async function step(name, fn) {
  console.log(`\n== ${name}`);
  try { await fn(); } catch (e) { failures++; console.error(String(e)); }
}
function expect(cond, label) {
  if (cond) { console.log(`  ok - ${label}`); return; }
  failures++;
  console.error(`  FAIL: ${label}`);
}
const md = () => readFileSync(join(dsRoot, "projects", `${PROJ}.md`), "utf-8");

let browser = null;
try {
  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  const row = (t) => page.locator(`.change-row:has-text("${t}")`);
  const noteBox = () => page.locator(".change-scroll .edit-fields .edit-note");
  const textBox = () => page.locator(".change-scroll .edit-fields .edit-text");

  // 左栏 T3 之后按阶段分堆:施工跟进不在默认收起的「已交付」堆里,直接点得到。
  const openProject = async () => {
    await page.goto(base, { waitUntil: "domcontentloaded" });
    await page.locator(`.proj-list .proj-row:has-text("${PROJ}")`).first().click();
    await row("吊顶改平顶").waitFor({ timeout: 15000 });
  };
  // hover 才冒出图标按钮组;.edit-trigger 是编辑那颗(data-ui="change-edit")。
  const startEdit = async (t) => {
    const r = row(t);
    await r.hover();
    await r.locator(".edit-trigger").click();
    await textBox().waitFor({ timeout: 5000 });
  };

  // ── A 编辑器里有备注框 ───────────────────────────────────────────────────
  await step("A 工作区行内编辑器有备注输入框(复用待办页 .edit-note)", async () => {
    await openProject();
    await startEdit("衣柜加到顶");
    expect(await noteBox().count() === 1, "编辑态里有且只有一个 .edit-note 输入框");
    expect(await noteBox().isVisible(), "备注框可见");
  });

  // ── B 写入 → 上屏 + 落盘 ─────────────────────────────────────────────────
  await step("B 写备注保存:行上出现「备注:…」,且磁盘变更历史段真落了", async () => {
    await openProject();
    await startEdit("衣柜加到顶");
    await noteBox().fill("业主要求柜门做长虹玻璃");
    await page.locator(".change-scroll .edit-fields .btn-save").click();
    await page.locator('.change-row:has-text("衣柜加到顶") .note-tag')
      .waitFor({ timeout: 10000 });
    const tag = await row("衣柜加到顶").locator(".note-tag").innerText();
    expect(tag.includes("业主要求柜门做长虹玻璃"), `行上备注已上屏(实测「${tag}」)`);
    expect(md().includes("- C2 备注:业主要求柜门做长虹玻璃"),
      "磁盘 `## 变更历史` 段已落 C2 备注(真写口,不是乐观 tag)");
  });

  // ── C 预填 ───────────────────────────────────────────────────────────────
  await step("C 再点编辑:备注框预填既有备注(在原文上改,不是重打)", async () => {
    await openProject();
    await startEdit("吊顶改平顶");
    expect(await noteBox().inputValue() === "业主口头确认",
      `C1 备注框预填了既有备注(实测「${await noteBox().inputValue()}」)`);
    expect(await textBox().inputValue() === "吊顶改平顶",
      "正文框同样预填(既有行为不许退化)");
  });

  // ── D 只改备注不动正文 ───────────────────────────────────────────────────
  await step("D 只改备注:正文原样,且不产生假的「改过」留痕", async () => {
    await openProject();
    await startEdit("吊顶改平顶");
    await noteBox().fill("业主书面确认");
    await page.locator(".change-scroll .edit-fields .btn-save").click();
    await page.locator('.change-row:has-text("吊顶改平顶") .note-tag:has-text("书面")')
      .waitFor({ timeout: 10000 });
    const m = md();
    expect(m.includes("- C1 备注:业主书面确认"), "C1 备注已改写(upsert,不是追加第二行)");
    expect(!m.includes("- C1 备注:业主口头确认"), "旧备注已被替换掉");
    expect(m.includes("【客厅】吊顶改平顶"), "正文一字未动");
    expect(!/- C1 改于/.test(m), "没有假的「C1 改于 …｜原:…」留痕(正文没改就别留痕)");
  });

  // ── E 备注 + 正文一起改 ──────────────────────────────────────────────────
  await step("E 备注与正文同改:两者都落盘,正文留痕照常", async () => {
    await openProject();
    await startEdit("加净水器点位");
    await textBox().fill("加净水器和前置过滤点位");
    await noteBox().fill("水电交底前定");
    await page.locator(".change-scroll .edit-fields .btn-save").click();
    await page.locator('.change-row:has-text("前置过滤")').waitFor({ timeout: 10000 });
    const m = md();
    expect(m.includes("加净水器和前置过滤点位"), "新正文已落盘");
    expect(m.includes("- C3 备注:水电交底前定"), "新备注已落盘");
    expect(/- C3 改于 .*原:加净水器点位/.test(m), "正文那条留痕照常写");
  });

  // ── F 取消不写入 ─────────────────────────────────────────────────────────
  await step("F 取消:一个字都不写", async () => {
    await openProject();
    const before = md();
    await startEdit("衣柜加到顶");
    await noteBox().fill("这条不该被保存");
    await page.locator(".change-scroll .edit-fields .btn-cancel").click();
    await page.waitForTimeout(500);
    expect(md() === before, "取消后档案逐字节不变");
    expect(!md().includes("这条不该被保存"), "草稿没有泄漏到磁盘");
  });
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}

console.log(failures === 0 ? "\n全部通过" : `\n${failures} 条不通过`);
process.exit(failures === 0 ? 0 : 1);
