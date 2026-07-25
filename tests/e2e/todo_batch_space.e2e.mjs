// track opendesign-todo-batch-space e2e:三项前端改动的行为面契约
// (真 chromium + 真 ds_web,参照 frontend_p2_polish.e2e.mjs 的夹具/起服务写法)。
// 覆盖:
//   T3 待办页批量改状态——两视图(按时间/按项目)各选 2 条 → 浮栏 → 改状态 → 落盘 + reload 生效;
//   T4 单项目变更列「按空间」分组切换 → 出现空间分节;
//   T5 侧栏未建档项目无「建档/→」「未建档」文字,`.nm` 灰化(与已建档项目对比 computed color)。
//
// 跑法:node tests/e2e/todo_batch_space.e2e.mjs(自起 ds_web 于 8797)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8797;

// ── 夹具 ────────────────────────────────────────────────────────────────────
const tmp = mkdtempSync(join(tmpdir(), "tbs-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");
// projD:待办批量 + 分组切换主场景——2 个日期批次 × 2 个空间,状态均未办结(可批量改)
const projD = "海棠居-901";
const folderD = "20260610 海棠居 9#901";
// projE:第二个项目,给「按项目」视图凑第二张卡(与 projD 各自独立,批量应用互不影响)
const projE = "云璟湾-1502";
const folderE = "20260615 云璟湾 15#1502";
const folderB = "老宅翻新项目夹"; // 未建档行(token 不命中任何项目)
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
writeFileSync(join(dsRoot, "projects", `${projD}.md`), `# ${projD}

- 业主: [[张三]]
- 阶段: 施工跟进

## 变更记录
- [待确认] C1 2026-07-18 【玄关】玄关柜改高
- [待确认] C2 2026-07-18 【客厅】沙发靠墙摆
- [待确认] C3 2026-07-20 卫生间防水加一道
- [待确认] C4 2026-07-20 【卧室】飘窗台改石材

## 沟通日志

---
最后更新: 2026-07-20
`);
writeFileSync(join(dsRoot, "projects", `${projE}.md`), `# ${projE}

- 业主: [[李四]]
- 阶段: 方案深化

## 变更记录
- [待确认] C1 2026-07-19 【厨房】橱柜改地柜

## 沟通日志

---
最后更新: 2026-07-19
`);
mkdirSync(join(ws, folderD), { recursive: true });
mkdirSync(join(ws, folderE), { recursive: true });
mkdirSync(join(ws, folderB), { recursive: true });
writeFileSync(join(dsRoot, "config", "workspace.json"), JSON.stringify({
  root: ws, projectsDir: ".",
  projects: { [projD]: folderD, [projE]: folderE },
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

const projDMd = () => readFileSync(join(dsRoot, "projects", `${projD}.md`), "utf-8");

let failures = 0;
let browser = null;
try {
  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(base, { waitUntil: "domcontentloaded" });

  // ── T5:侧栏未建档行无「建档 →」/「未建档」文字,.nm 灰化(与已建档行对比) ──
  const unregRow = page.locator(`.proj-list .proj-row:has-text("${folderB}")`).first();
  await unregRow.waitFor({ timeout: 10000 });
  check(await unregRow.locator('[data-ui="side-reg-link"]').count() === 0,
    "侧栏未建档行:无「建档 →」链接");
  const unregTxt = await unregRow.innerText();
  check(!unregTxt.includes("建档 →") && !unregTxt.includes("未建档"),
    "侧栏未建档行:文案不含「建档 →」/「未建档」");
  check(await unregRow.evaluate((el) => el.classList.contains("unregistered")),
    "侧栏未建档行:保留 .unregistered class(title/onClick 不受影响)");
  const regRow = page.locator(`.proj-list .proj-row:has-text("${projD}")`).first();
  await regRow.waitFor({ timeout: 10000 });
  const [unregColor, regColor] = await Promise.all([
    unregRow.locator(".nm").evaluate((el) => getComputedStyle(el).color),
    regRow.locator(".nm").evaluate((el) => getComputedStyle(el).color),
  ]);
  check(unregColor !== regColor,
    `.nm 灰化 class 生效:未建档(${unregColor}) 与已建档(${regColor}) 颜色不同`);

  // ── T4:单项目变更列「按空间」分组切换 ──────────────────────────────────
  await regRow.click();
  await page.locator(".change-row").first().waitFor({ timeout: 10000 });
  check((await page.locator('[data-ui="change-group-toggle"] .opt.on').innerText()).includes("按时间"),
    "默认按时间分组");
  check((await page.locator(".change-group-head").count()) >= 1, "按时间:出现日期分节头");
  await page.locator('[data-ui="change-group-toggle"] .opt:has-text("按空间")').click();
  await page.waitForFunction(
    () => Array.from(document.querySelectorAll(".change-group-head .nm"))
      .some((el) => el.textContent?.includes("玄关")),
    { timeout: 5000 },
  );
  const spaceHeads = await page.locator(".change-group-head .nm").allInnerTexts();
  check(spaceHeads.includes("玄关") && spaceHeads.includes("客厅"), "按空间:玄关/客厅分节头出现");
  // 真机反馈 2026-07-24 #6:「没空间就不写」——分节仍在(条目要分开、全选本组要留),
  // 但**不再写「未分空间」四个字**。判据 = 页面上任何位置都不出现这四个字,
  // 且无名分节仍恒置末(次序语义没被顺手改掉)。
  check(!spaceHeads.includes("未分空间"), "按空间:不再出现「未分空间」字样");
  check((await page.locator("body").innerText()).includes("未分空间") === false,
    "整页无「未分空间」残留(含待办页/变更列两处同源文案)");
  check(spaceHeads[spaceHeads.length - 1].trim() === "",
    `按空间:无空间那节仍恒置末、只是没了名字(实测末节名「${spaceHeads[spaceHeads.length - 1]}」)`);

  // ── 变更筛选选中态语义色(真机反馈 2026-07-24 #5)────────────────────────
  // 单一状态的胶囊选中后用该状态的语义色(与行内 st-pill 同族);
  // 「未办结」「全部」不是单一状态 → 保持中性墨。
  // 判据取"两两不同 + 非单状态同色",不硬编码色值 —— 换主题不该假红。
  const pillBg = async (label) => {
    await page.locator(`.filter-pills .pill:has-text("${label}")`).first().click();
    await page.waitForTimeout(120); // 过渡动画
    return page.locator(`.filter-pills .pill.on:has-text("${label}")`).first()
      .evaluate((el) => getComputedStyle(el).backgroundColor);
  };
  const cPending = await pillBg("待确认");
  const cDoing = await pillBg("进行中");
  const cDone = await pillBg("已办结");
  const cOpen = await pillBg("未办结");
  const cAll = await pillBg("全部");
  check(new Set([cPending, cDoing, cDone]).size === 3,
    `三个单状态选中色互不相同(待确认 ${cPending} / 进行中 ${cDoing} / 已办结 ${cDone})`);
  check(cOpen === cAll, `「未办结」「全部」非单一状态 → 同中性色(${cOpen} / ${cAll})`);
  check(![cPending, cDoing, cDone].includes(cOpen),
    `中性色与三个语义色都不同(中性 ${cOpen})`);
  await page.locator('.filter-pills .pill:has-text("未办结")').first().click(); // 复位,免影响后续断言

  // ── T3:待办页批量改状态——按时间视图 ─────────────────────────────────
  // 日期批次默认只展开最新一批(gi===0);C3/C4(2026-07-20)是全场最新日期,
  // 免去先点开折叠头这步,选它俩。
  await page.locator('.side-row:has-text("待办事项")').first().click();
  await page.locator(".todo-card").first().waitFor({ timeout: 10000 });
  await page.locator('.todo-head .opt:has-text("按时间")').click();
  await page.locator(".batch-head").first().waitFor({ timeout: 5000 });
  const timeRow1 = page.locator('.todo-row:has-text("卫生间防水加一道")').first();
  const timeRow2 = page.locator('.todo-row:has-text("飘窗台改石材")').first();
  await timeRow1.locator('[data-ui="todo-select"]').check();
  await timeRow2.locator('[data-ui="todo-select"]').check();
  const bar = page.locator('[data-ui="todo-batch-bar"]');
  await bar.waitFor({ timeout: 5000 });
  check((await bar.innerText()).includes("已选 2 条"), "浮栏:已选 2 条");
  await bar.locator(".st-btn").click();
  await page.locator(".st-menu-item:has-text(\"进行中\")").click();
  await page.waitForFunction(
    () => !document.querySelector('[data-ui="todo-batch-bar"]'),
    { timeout: 10000 },
  );
  check(true, "应用后浮栏消失(选中集已清空)");
  const toast = page.locator(".todo-toast.batch");
  await toast.waitFor({ timeout: 5000 });
  check((await toast.innerText()).includes("已改 2 条"), "toast:已改 2 条");
  await page.waitForFunction(
    () => {
      const rows = Array.from(document.querySelectorAll(".todo-row"));
      const r1 = rows.find((r) => r.textContent?.includes("卫生间防水加一道"));
      return r1?.querySelector(".st-进行中") != null;
    },
    { timeout: 10000 },
  );
  check(true, "按时间视图批量应用后 UI 回显新状态");
  check(projDMd().includes("[进行中] C3"), "落盘:C3 已改为进行中");
  check(projDMd().includes("[进行中] C4"), "落盘:C4 已改为进行中");

  // ── T3:待办页批量改状态——按项目视图(空间小节)────────────────────────
  // 空间小节不折叠,任意条目直接可选;取 C1(玄关)/C2(客厅)两个不同小节各一条。
  await page.locator('.todo-head .opt:has-text("按项目")').click();
  await page.locator('[data-ui="todo-space-sect"]').first().waitFor({ timeout: 5000 });
  // #6:待办页同源文案也不写「未分空间」,但**分节与「全选本组」必须还在**
  // ——用户要的是"别写那四个字",不是"少一个按钮 / 条目混作一堆"。
  check((await page.locator('[data-ui="todo-space-sect"] .nm:has-text("未分空间")').count()) === 0,
    "待办页空间小节不再写「未分空间」");
  check((await page.locator('[data-ui="todo-space-sect"]').count()) >= 1,
    "空间小节本身仍在(分节没被顺手删掉)");
  check((await page.locator('[data-ui="todo-select-group"]').count()) >= 1,
    "「全选本组」仍在(去掉的是字,不是功能)");
  const projRow1 = page.locator('.todo-row:has-text("玄关柜改高")').first();
  const projRow2 = page.locator('.todo-row:has-text("沙发靠墙摆")').first();
  await projRow1.locator('[data-ui="todo-select"]').check();
  await projRow2.locator('[data-ui="todo-select"]').check();
  const bar2 = page.locator('[data-ui="todo-batch-bar"]');
  await bar2.waitFor({ timeout: 5000 });
  check((await bar2.innerText()).includes("已选 2 条"), "浮栏(按项目视图):已选 2 条");
  await bar2.locator(".st-btn").click();
  await page.locator(".st-menu-item:has-text(\"进行中\")").click();
  await page.waitForFunction(
    () => !document.querySelector('[data-ui="todo-batch-bar"]'),
    { timeout: 10000 },
  );
  const toast2 = page.locator(".todo-toast.batch");
  await toast2.waitFor({ timeout: 5000 });
  check((await toast2.innerText()).includes("已改 2 条"), "toast(按项目视图):已改 2 条");
  check(projDMd().includes("[进行中] C1"), "落盘:C1 已改为进行中");
  check(projDMd().includes("[进行中] C2"), "落盘:C2 已改为进行中");

  // ── T3:全选本组(冒烟)──────────────────────────────────────────────────
  await page.locator('.todo-head .opt:has-text("按时间")').click();
  await page.locator(".batch-head").first().waitFor({ timeout: 5000 });
  await page.locator('[data-ui="todo-select-group"]').first().click();
  await page.locator('[data-ui="todo-batch-bar"]').waitFor({ timeout: 5000 });
  check(true, "全选本组:浮栏出现");
  await page.locator(".todo-batch-bar .batch-cancel").click();
  await page.waitForFunction(
    () => !document.querySelector('[data-ui="todo-batch-bar"]'),
    { timeout: 5000 },
  );
  check(true, "取消:浮栏消失,选中集清空");
} catch (e) {
  failures++;
  console.error(String(e));
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}
console.log(failures === 0 ? "TODO-BATCH-SPACE E2E: ALL PASS" : `TODO-BATCH-SPACE E2E: ${failures} FAIL`);
process.exit(failures === 0 ? 0 : 1);
