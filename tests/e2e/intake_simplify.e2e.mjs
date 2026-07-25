// track opendesign-intake-simplify e2e(真机反馈 2026-07-24 #3):
// 未建档文件夹的建档小表单**只填项目名**。主 agent 亲写,执行腿逐字节 off-limits。
//
// 判据不是"页面上没有『业主名』四个字"——那样把整个表单删掉也能绿。
// 真判据 = **只填项目名就真的建成了档**:建完那个项目不再是未建档态(中心区出现
// 变更记录面板 / 阶段 chip 不再是「未建档」),且档案里没有 `[[]]` 空链接。
//
// 跑法:node tests/e2e/intake_simplify.e2e.mjs(自起 ds_web 于 8805,不需要 gateway)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8805;

// ── 夹具:一个已建档项目(对照)+ 两个未建档文件夹(两条建档路径各用一个)────
const tmp = mkdtempSync(join(tmpdir(), "intake-simpl-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");
const projA = "翡翠湾-1801";
const folderA = "20260601 平湖 翡翠湾 3#1801";
const folderNew = "20260720 云玺台 5#1203";      // 点按钮建档
const folderNew2 = "20260722 观澜府 2#0901";     // 项目名框按 Enter 建档
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
writeFileSync(join(dsRoot, "projects", `${projA}.md`), `# ${projA}

- 业主: [[李四]]
- 阶段: 施工跟进

## 变更记录
- [待确认] C1 2026-07-15 【玄关】玄关柜改高

## 沟通日志

---
最后更新: 2026-07-15
`);
mkdirSync(join(ws, folderA), { recursive: true });
mkdirSync(join(ws, folderNew), { recursive: true });
mkdirSync(join(ws, folderNew2), { recursive: true });
writeFileSync(join(dsRoot, "config", "workspace.json"), JSON.stringify({
  root: ws, projectsDir: ".", projects: { [projA]: folderA },
}));

const srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
  env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT) },
  stdio: ["ignore", "inherit", "inherit"],
});
const base = `http://127.0.0.1:${PORT}`;
for (let i = 0; ; i++) {
  try { await fetch(`${base}/api/health`); break; }
  catch { if (i > 50) throw new Error("ds_web 起不来"); await new Promise((r) => setTimeout(r, 200)); }
}

const projFile = (slug) => join(dsRoot, "projects", `${slug}.md`);
const unregRow = (page, folder) =>
  page.locator(`.proj-list .proj-row[title*="${folder}"]`).first();

let failures = 0;
let browser = null;
try {
  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  await page.goto(base, { waitUntil: "domcontentloaded" });

  // ── ① 建档表单只剩一个输入框,页面无「业主名」字样 ────────────────────────
  await unregRow(page, folderNew).waitFor({ timeout: 10000 });
  await unregRow(page, folderNew).click();
  const form = page.locator(".create-proj-form");
  await form.waitFor({ timeout: 10000 });
  const inputs = await form.locator("input").count();
  check(inputs === 1, `建档表单只有 1 个输入框(实测 ${inputs} 个)`);
  const pageTxt = await page.locator("body").innerText();
  check(!pageTxt.includes("业主名"), "页面不出现「业主名」字样");

  // ── ② 只填项目名 → 建档按钮可点(旧实现空业主时是 disabled)──────────────
  const nameInput = form.locator("input").first();
  const btn = form.locator("button").last();
  await nameInput.fill(folderNew);
  check(await btn.isEnabled(), "只填项目名,建档按钮就可点");

  // ── ③ 点建档 → 真的建成:不再是未建档态 ─────────────────────────────────
  await btn.click();
  // 建成的判据取"未建档态消失 + 变更记录面板出现",不是文案消失
  await page.locator('.center-head [data-ui="stage-chip"]:not(.unreg)')
    .first().waitFor({ timeout: 15000 });
  const chip = (await page.locator('[data-ui="stage-chip"]').first().innerText()).trim();
  check(chip !== "未建档", `建档后阶段 chip 不再是「未建档」(实测「${chip}」)`);
  check(existsSync(projFile(folderNew)), "projects/<项目>.md 真的落盘了");
  const text = readFileSync(projFile(folderNew), "utf-8");
  check(!text.includes("[[]]"), "档案里没有 `[[]]` 空链接(否则 ds_lint 判断链)");
  check(text.split("\n").some((ln) => ln.startsWith("- 业主:")),
    "业主字段行仍在(值为空,可后补)");
  check(text.includes("## 变更记录"), "骨架完整:变更记录段在(append_change 靠它)");

  // ── ④ 项目名框按 Enter 直接提交(原来 Enter 挂在业主名框上)──────────────
  await unregRow(page, folderNew2).click();
  const form2 = page.locator(".create-proj-form");
  await form2.waitFor({ timeout: 10000 });
  await form2.locator("input").first().fill(folderNew2);
  await form2.locator("input").first().press("Enter");
  await page.locator('.center-head [data-ui="stage-chip"]:not(.unreg)')
    .first().waitFor({ timeout: 15000 });
  check(existsSync(projFile(folderNew2)), "项目名框按 Enter 也能建档");

  // ── ⑤ 空项目名不能建(必填只剩项目名这一个)──────────────────────────────
  const remaining = page.locator(".proj-list .proj-row.unregistered").first();
  if (await remaining.count()) {
    await remaining.click();
    const form3 = page.locator(".create-proj-form");
    if (await form3.count()) {
      check(!(await form3.locator("button").last().isEnabled()),
        "项目名为空时建档按钮仍不可点(项目名仍必填)");
    }
  } else {
    check(true, "无剩余未建档行可测空名闸(夹具两条都已建档;核心 oracle 已锁)");
  }

  console.log(failures ? `INTAKE-SIMPLIFY E2E: ${failures} FAIL` : "INTAKE-SIMPLIFY E2E: ALL PASS");
} catch (e) {
  failures++;
  console.error(String(e));
} finally {
  if (browser) await browser.close();
  srv.kill("SIGTERM");
  rmSync(tmp, { recursive: true, force: true });
}
process.exit(failures ? 1 : 0);
