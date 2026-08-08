// 待办「删除」e2e(真 chromium + 真 ds_web)。主 agent 亲写,执行腿逐字节 off-limits。
// track opendesign-owner-review-0808。
//
// 08-08 业主验收对话原话:「他建错之后我跟他说建错了……我这个只是实验的话所以我删掉这个
// 待办 但是发现没有手动的删除按钮」+「删按钮我觉得还是需要有的,但是删除前会弹一个确定和
// 取消 防止误触就好了吧」——两句话就是本文件的全部覆盖范围。
//
// 覆盖:
//   A 待办行上有删除按钮。
//   B 点删除 → 出确认/取消弹窗;**点取消不发请求、条目还在**(专防"忘了接取消分支,
//     点哪个都在删"这种低级 bug——纯前端断言不够,这里连磁盘一起验)。
//   C 点确定 → 真的写进档案(状态位变已删除,回收站式,不是物理删行)+ 条目从列表消失,
//     邻项不受影响。
//   D 刷新页面后条目仍不见(真持久化,不是只改了界面上的乐观状态)。
//
// 跑法:node tests/e2e/todo_delete.e2e.mjs(自起 ds_web 于 8829)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8829;
const KEY = "翡翠湾-1801";
const TODAY = "2026-07-22";

const tmp = mkdtempSync(join(tmpdir(), "tododelete-e2e-"));
const dsRoot = join(tmp, "ds");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });

const projPath = join(dsRoot, "projects", `${KEY}.md`);
writeFileSync(projPath, `# ${KEY}

- 业主: [[王女士]]
- 阶段: 施工跟进

## 变更记录
- [待确认] C1 ${TODAY} 【主卧】误建的一条,这是实验数据
- [进行中] C2 ${TODAY} 【客厅】真正要跟进的一条

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

const fileText = () => readFileSync(projPath, "utf-8");
const rowOf = (page, text) => page.locator(".todo-page .todo-row", { hasText: text }).first();
const deleteBtnOf = (page, text) => rowOf(page, text).locator('[data-ui="delete-btn"]');

let browser = null;
try {
  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // ── A 待办行上有删除按钮 ─────────────────────────────────────────────────
  await step("A 待办行渲染出删除按钮", async () => {
    await page.goto(`${base}/#/todos`, { waitUntil: "domcontentloaded" });
    await page.locator(".todo-page .todo-row").first().waitFor({ timeout: 15000 });
    await expect(await deleteBtnOf(page, "误建的一条").count() === 1,
      "「误建的一条」这一行有一个删除按钮");
  });

  // ── B 点取消:不发请求、条目还在 ──────────────────────────────────────────
  await step("B 点删除后选取消 → 条目还在,磁盘不动", async () => {
    const before = fileText();
    page.once("dialog", (d) => d.dismiss());
    await deleteBtnOf(page, "误建的一条").click();
    await page.waitForTimeout(500); // 给"万一真发了请求"留出网络往返时间
    expect(await rowOf(page, "误建的一条").count() === 1, "取消后那一行还在页面上");
    expect(fileText() === before, "取消后档案文件逐字节不变(没有偷偷发请求)");
    expect(!fileText().includes("已删除"), "档案里没有出现「已删除」字样");
  });

  // ── C 点确定:真的写进档案 + 从列表消失 + 邻项不受影响 ────────────────────
  await step("C 点删除后选确定 → 写进档案(软删除)+ 从列表消失", async () => {
    page.once("dialog", (d) => d.accept());
    await deleteBtnOf(page, "误建的一条").click();
    await rowOf(page, "误建的一条").waitFor({ state: "detached", timeout: 8000 });
    expect(fileText().includes("- [已删除] C1 " + TODAY), "档案里 C1 状态变成了已删除");
    expect(!fileText().includes("- [待确认] C1"), "C1 不再是待确认状态(行没被物理删除,是状态位变了)");
    expect(await rowOf(page, "真正要跟进的一条").count() === 1, "没被删的 C2 还在页面上");
    expect(fileText().includes("- [进行中] C2 " + TODAY + " 【客厅】真正要跟进的一条"),
      "C2 那一行字节不受影响");
  });

  // ── D 刷新后仍不见:真持久化,不是只改了界面 ────────────────────────────────
  await step("D 刷新页面后,已删除的条目仍不出现", async () => {
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.locator(".todo-page .todo-row").first().waitFor({ timeout: 15000 });
    expect(await rowOf(page, "误建的一条").count() === 0, "刷新后「误建的一条」仍不在列表里");
    expect(await rowOf(page, "真正要跟进的一条").count() === 1, "刷新后 C2 仍在列表里");
  });

  console.log(failures === 0 ? "\nTODO-DELETE E2E: ALL PASS"
                             : `\nTODO-DELETE E2E: ${failures} FAIL`);
} catch (e) {
  failures++;
  console.error(String(e));
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}
process.exit(failures === 0 ? 0 : 1);
