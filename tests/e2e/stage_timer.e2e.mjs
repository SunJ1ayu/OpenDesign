// 阶段计时器 e2e(真 chromium + 真 ds_web)。主 agent 亲写,执行腿逐字节 off-limits。
//
// track opendesign-stage-timer。用户要解决的是「哪个项目卡住了」——
// 既有的「最近记录 N 天前」量的是档案最后更新日(记一条变更就清零),
// 量不到「这个项目在方案深化泡了三周」。
//
// 覆盖:
//   A 工作区 stage-chip 旁显示天数;**天数在 chip 外面**,chip 自己的文字仍
//     精确等于阶段名 —— 既有判据 stage_history.e2e.mjs:121 锁着这一条,
//     实现不许为了塞天数去改它。
//   B 没记录起始日的项目:天数元素**整个不渲染**(不出现占位数字、不出现「天」字)。
//   C 补录入口:下拉里设起始日 → **档案里真的写了**(不是只改了个 span)→
//     天数当场变 → **整页刷新后仍在**(防只做乐观更新、磁盘没落)。
//   D 待办页项目卡头出现天数(用户拍板「要吧」的那处);未记录的卡不出现天数。
//   E 两个天数不打架:同一张卡上「阶段天数」与「最近记录 N 天前」文案可区分。
//     —— design 里点名的"数字对、结果错"面:两个都是天数,用户分不清谁是谁。
//
// red-check(未实现前该红成什么样):
//   A/C/D 全红(没有 [data-ui=stage-days] 这个节点、下拉里没有设起始日的入口);
//   B 会**天然绿**(元素本来就不存在)—— 它是护栏不是判别式,见 B 段注释。
//
// 跑法:node tests/e2e/stage_timer.e2e.mjs(自起 ds_web 于 8814)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8814;
const TODAY = "2026-08-02";        // DS_TODAY 冻结后端"今天",判据不会跑到明年就红
const KEY = "翡翠湾-1801";          // 有阶段历史 → 该显示天数
const LEGACY = "云溪台-1203";       // 旧档案无该段 → 该"未记录"
const SINCE = "2026-07-20";        // → 到 TODAY 是 13 天
const DAYS = 13;
const BACKFILL = "2026-07-10";     // 补录用 → 23 天
const BACKFILL_DAYS = 23;

const tmp = mkdtempSync(join(tmpdir(), "stagetimer-e2e-"));
const dsRoot = join(tmp, "ds");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });

const withHist = `# ${KEY}

- 业主: [[王女士]]
- 阶段: 方案深化

## 阶段历史

- 2026-06-01 洽谈
- ${SINCE} 方案深化

## 变更记录

- [待确认] C1 2026-07-25 【主卧】灯位右移 30cm

## 沟通日志

---
最后更新: 2026-07-25
`;

// 旧档案:没有 `## 阶段历史` 段 —— 上线当天占绝大多数,B/D 段的主战场。
// ⚠️ 「最近记录」日期刻意取一个**不等于** SINCE 的值:两个日期若相等,
//    实现把"阶段天数"错算成"距最后更新"也会照绿(规划双出点名的骗过面)。
const legacyMd = `# ${LEGACY}

- 业主: [[李先生]]
- 阶段: 施工交底

## 变更记录

- [待确认] C1 2026-06-15 【客厅】插座位置确认

## 沟通日志

---
最后更新: 2026-06-15
`;

const projPath = join(dsRoot, "projects", `${KEY}.md`);
writeFileSync(projPath, withHist);
writeFileSync(join(dsRoot, "projects", `${LEGACY}.md`), legacyMd);
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

const readMd = () => readFileSync(projPath, "utf-8");

const browser = await launchBrowser();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
try {
  await page.goto(`${base}/`, { waitUntil: "domcontentloaded" });

  // ── A 工作区:天数在 chip 外面 ─────────────────────────────────────────
  await step("A 工作区 stage-chip 旁显示天数", async () => {
    await page.locator(`text=${KEY}`).first().click();
    const chip = page.locator('[data-ui="stage-chip"]').first();
    await chip.waitFor({ timeout: 10000 });

    expect((await chip.innerText()).trim() === "方案深化",
      "A1 chip 自己的文字仍**精确等于**阶段名(既有 stage_history.e2e.mjs:121 锁着)");

    const days = page.locator('[data-ui="stage-days"]').first();
    await days.waitFor({ timeout: 8000 });
    expect((await days.innerText()).includes(String(DAYS)),
      `A2 天数元素显示 ${DAYS}(${SINCE} → ${TODAY})`);

    // 锚:天数不是 chip 的后代 —— 否则 A1 迟早被"顺手合并"掉
    const nested = await page.evaluate(() => {
      const c = document.querySelector('[data-ui="stage-chip"]');
      return !!(c && c.querySelector('[data-ui="stage-days"]'));
    });
    expect(nested === false, "A3 天数必须是 chip 的**兄弟**,不许塞进 chip 里");
  });

  // ── B 未记录:整个元素不渲染 ──────────────────────────────────────────
  await step("B 旧档案不显示占位数字", async () => {
    // ⚠️ 本段红检阶段**天然绿**(元素本来就不存在)。它是护栏:防实现后
    //    给未记录的项目渲染出「0 天」或「未记录 天」。判别力在实现之后。
    await page.locator(`text=${LEGACY}`).first().click();
    const chip = page.locator('[data-ui="stage-chip"]').first();
    await chip.waitFor({ timeout: 10000 });
    expect((await chip.innerText()).trim() === "施工交底", "B1 chip 显示旧档案的阶段");
    expect(await page.locator('[data-ui="stage-days"]').count() === 0,
      "B2 没有起始日 ⇒ 天数元素整个不渲染(不许出现「0 天」这种假数字)");
  });

  // ── C 补录:写进档案 + 当场变 + 刷新仍在 ──────────────────────────────
  await step("C 下拉里补录起始日", async () => {
    await page.locator(`text=${KEY}`).first().click();
    await page.locator('[data-ui="stage-chip"]').first().click();
    const menu = page.locator('[data-ui="stage-menu"]');
    await menu.waitFor({ timeout: 5000 });

    const setter = menu.locator('[data-ui="stage-since-input"]');
    await setter.waitFor({ timeout: 5000 });
    await setter.fill(BACKFILL);
    await menu.locator('[data-ui="stage-since-save"]').click();

    await page.locator(`[data-ui="stage-days"]:has-text("${BACKFILL_DAYS}")`)
      .first().waitFor({ timeout: 8000 });
    expect(true, `C1 天数当场变成 ${BACKFILL_DAYS} 天`);

    expect(readMd().includes(`- ${BACKFILL} 方案深化`),
      "C2 **档案里真的改了**(不是只动了个 span)");
    expect(!readMd().includes(`- ${SINCE} 方案深化`),
      "C3 补录是**改末条**,不是追加第二条「方案深化」");

    await page.reload({ waitUntil: "domcontentloaded" });
    await page.locator(`text=${KEY}`).first().click();
    await page.locator(`[data-ui="stage-days"]:has-text("${BACKFILL_DAYS}")`)
      .first().waitFor({ timeout: 10000 });
    expect(true, "C4 整页刷新后仍在(防只做乐观更新、磁盘没落)");
  });

  // ── D 待办页项目卡头(用户 08-02 拍板「要吧」)──────────────────────────
  await step("D 待办页项目卡头显示天数", async () => {
    // 走路由,不去猜导航元素(照 todo_one_view.e2e.mjs 的 gotoTodo 先例)
    await page.goto(`${base}/#/todos`, { waitUntil: "domcontentloaded" });
    const card = page.locator(".todo-card").filter({ hasText: KEY }).first();
    await card.waitFor({ timeout: 15000 });

    const cardDays = card.locator('[data-ui="card-stage-days"]');
    await cardDays.waitFor({ timeout: 8000 });
    expect((await cardDays.innerText()).includes(String(BACKFILL_DAYS)),
      `D1 卡头显示 ${BACKFILL_DAYS} 天`);

    // 既有节点不许被动:one_view 的判据锁着它
    const stageTag = card.locator('[data-ui="card-stage"]');
    expect((await stageTag.innerText()).trim() === "方案深化",
      "D2 既有 card-stage 节点的文字不许被改(todo_one_view.e2e.mjs:199 锁着)");

    const legacyCard = page.locator(".todo-card").filter({ hasText: LEGACY }).first();
    if (await legacyCard.count()) {
      expect(await legacyCard.locator('[data-ui="card-stage-days"]').count() === 0,
        "D3 未记录的项目卡**不出现**天数(一屏几十张卡,占位就是噪音)");
    }
  });

  // ── E 两个天数不打架 ─────────────────────────────────────────────────
  await step("E 阶段天数与「最近记录 N 天前」可区分", async () => {
    // design 点名的"数字对、结果错":两个都是天数,断言各自对、用户仍分不清。
    // 判据能接住的只有"文案不同";真正接得住的是收货时的截图(G4)。
    await page.goto(`${base}/#/todos`, { waitUntil: "domcontentloaded" });
    const card = page.locator(".todo-card").filter({ hasText: KEY }).first();
    await card.waitFor({ timeout: 15000 });
    const stageDays = await card.locator('[data-ui="card-stage-days"]')
      .innerText({ timeout: 8000 });
    const recency = card.locator('[data-ui="card-recency"]');
    if (await recency.count()) {
      const rec = await recency.innerText();
      expect(stageDays.trim() !== rec.trim(),
        "E1 两处文案不许长得一模一样");
      expect(rec.includes("最近记录"),
        "E2 「最近记录 N 天前」保持原文案(它量的是另一个事实,不合并)");
    }
    expect(!stageDays.includes("最近记录"),
      "E3 阶段天数不许借用「最近记录」的文案");
  });
} finally {
  // ⚠️ 收尾必须**各自 try**:任何一步抛异常都会跳过 srv.kill(),留下的 ds_web
  // 会继承 stdout 管道 → 上层 `| tail` 永远等不到 EOF,表现成"判据卡死"。
  // (第一次跑就栽在这:finally 里一个 TypeError 让服务器成了孤儿。)
  try { await browser.close(); } catch { /* 已经死了就算了 */ }
  try { srv.kill(); } catch { /* 同上 */ }
  try { rmSync(tmp, { recursive: true, force: true }); } catch { /* 同上 */ }
}

console.log(failures === 0 ? "\nstage_timer e2e: ALL PASS" : `\nstage_timer e2e: ${failures} FAIL`);
process.exit(failures === 0 ? 0 : 1);
