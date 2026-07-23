// track opendesign-todo-rail e2e:待办页右栏(日程月历 + 需要今天跟进)的行为面契约
// (真 chromium + 真 ds_web,DS_TODAY 冻结今天)。主 agent 亲写,执行腿逐字节 off-limits。
//
// 覆盖:
//   右栏骨架(320px 固定,主区多列仍在)
//   日程月历:月份头 + 今天高亮 + 有到期的日期带圆点 + 圆点按 dueStatus 着色(复用既有分类)
//             + 月份前后翻 + 点日期过滤主列表 + 再点取消
//   需要今天跟进:只列 超期 + 今天到期、越久越前、超期天数/今天到期文案
//   反应性:把这些条目批量改成已完成 → 圆点消失 + 跟进区落到空态文案
//
// 跑法:node tests/e2e/todo_rail.e2e.mjs(自起 ds_web 于 8800)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8800;
const TODAY = "2026-07-22"; // 与设计稿 screenshots/12 同一天

const tmp = mkdtempSync(join(tmpdir(), "trail-e2e-"));
const dsRoot = join(tmp, "ds");
const P1 = "翡翠湾-1801";
const P2 = "云山名城-2302";
mkdirSync(join(dsRoot, "projects"), { recursive: true });

// 到期分布(相对 DS_TODAY=2026-07-22):
//   07-15 超期 7 天(C6) · 07-17 超期 5 天(C7) · 07-22 今天到期(C4)
//   07-23 未来(C8) · 08-05 下月(C5) · 无 due(C9)
writeFileSync(join(dsRoot, "projects", `${P1}.md`), `# ${P1}

- 业主: [[张三]]
- 阶段: 施工跟进

## 变更记录
- [待确认] C6 2026-07-10 【主卧】床头背景墙改木饰面 ⏳2026-07-15
- [待确认] C7 2026-07-11 【主卧】等业主定颜色 ⏳2026-07-17
- [待确认] C8 2026-07-12 【客厅】窗帘盒预留尺寸 ⏳2026-07-23

## 沟通日志

---
最后更新: 2026-07-22
`);

writeFileSync(join(dsRoot, "projects", `${P2}.md`), `# ${P2}

- 业主: [[李四]]
- 阶段: 方案深化

## 变更记录
- [待确认] C4 2026-07-13 【书房】整墙书柜改半墙加卡座 ⏳2026-07-22
- [待确认] C5 2026-07-14 【餐厅】餐边柜嵌入冰箱 ⏳2026-08-05
- [待确认] C9 2026-07-15 【厨房】橱柜台面加挡水

## 沟通日志

---
最后更新: 2026-07-22
`);

const srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
  env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT), DS_TODAY: TODAY },
  stdio: ["ignore", "inherit", "inherit"],
});
const base = `http://127.0.0.1:${PORT}`;
for (let i = 0; ; i++) {
  try { await fetch(`${base}/api/health`); break; }
  catch { if (i > 50) throw new Error("ds_web 起不来"); await new Promise((r) => setTimeout(r, 200)); }
}

// 某日格的定位:data-date 精确寻址,避免"数字 15"撞到邻月的 15
const cell = (page, iso) => page.locator(`[data-ui="cal-cell"][data-date="${iso}"]`);

let failures = 0;
let browser = null;
try {
  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.on("dialog", (d) => d.accept()); // 终态批量的 confirm
  await page.goto(base, { waitUntil: "domcontentloaded" });
  await page.locator('.side-row:has-text("待办事项")').first().click();
  await page.locator(".todo-card").first().waitFor({ timeout: 10000 });

  // ── 右栏骨架 ────────────────────────────────────────────────────────────
  const rail = page.locator('[data-ui="todo-rail"]');
  await rail.waitFor({ timeout: 5000 });
  const railW = await rail.evaluate((el) => el.clientWidth);
  check(railW >= 300 && railW <= 340, `右栏约 320px(实测 ${railW}px)`);
  // 真实列数只能量子元素左边界:CSS 用 column-width 驱动时,getComputedStyle 的
  // columnCount 返回的是声明上限而非实际用量(收货时踩到过)。
  const mainCols = await page.locator(".todo-cards").evaluate((el) =>
    new Set([...el.children].map((c) => Math.round(c.getBoundingClientRect().left))).size);
  check(mainCols >= 2, `右栏落地后主区仍多列(实测 ${mainCols} 列)`);

  // ── 日程月历 ────────────────────────────────────────────────────────────
  const monthLabel = page.locator('[data-ui="cal-month"]');
  check((await monthLabel.innerText()).includes("2026") && (await monthLabel.innerText()).includes("7"),
    `月份头显示当月(实测「${await monthLabel.innerText()}」)`);
  check(await page.locator('[data-ui="cal-cell"]').count() === 42, "月历恒 42 格");
  check(await cell(page, TODAY).evaluate((el) => el.classList.contains("today")),
    "今天(07-22)高亮");

  for (const [iso, cls, why] of [
    ["2026-07-15", "dot-overdue", "超期日红陶点"],
    ["2026-07-17", "dot-overdue", "超期日红陶点"],
    ["2026-07-22", "dot-today", "今天到期点"],
    ["2026-07-23", "dot-upcoming", "未来到期琥珀点"],
  ]) {
    const dot = cell(page, iso).locator(".cal-dot");
    check(await dot.count() === 1, `${iso} 有到期圆点(${why})`);
    check(await dot.evaluate((el, c) => el.classList.contains(c), cls),
      `${iso} 圆点着色 = ${cls}`);
  }
  check(await cell(page, "2026-07-16").locator(".cal-dot").count() === 0,
    "07-16 无到期事项 → 无圆点");
  // 圆点纯粹跟数据走:7 月网格尾部补的 08-05 是**看得见的真日期**,在它上面藏掉圆点
  // 等于对用户撒谎(还要多写按月特判)。邻月补格照样带点。
  check(await cell(page, "2026-08-05").count() === 1, "7 月网格尾部含补格 08-05");
  check(await cell(page, "2026-08-05").locator(".cal-dot").count() === 1,
    "邻月补格上的到期日照样带点(圆点跟数据走,不按月特判)");
  check(await cell(page, "2026-08-05").evaluate((el) => !el.classList.contains("in-month")),
    "但 08-05 仍标记为非本月(视觉淡化)");

  // ── 月份前后翻 ──────────────────────────────────────────────────────────
  check(await cell(page, "2026-08-20").count() === 0, "翻页前:8/20 不在 7 月网格内");
  await page.locator('[data-ui="cal-next"]').click();
  await page.waitForFunction(
    () => document.querySelector('[data-ui="cal-month"]')?.textContent?.includes("8"),
    { timeout: 5000 },
  );
  check(await cell(page, "2026-08-20").count() === 1, "翻到 8 月:8/20 出现(确实换了网格)");
  check(await cell(page, "2026-08-05").locator(".cal-dot").count() === 1,
    "8 月视图里 08-05 的到期点仍在");
  check(await cell(page, "2026-08-05").locator(".cal-dot")
    .evaluate((el) => el.classList.contains("dot-upcoming")), "08-05 为未来到期");
  await page.locator('[data-ui="cal-prev"]').click();
  await page.waitForFunction(
    () => document.querySelector('[data-ui="cal-month"]')?.textContent?.includes("7"),
    { timeout: 5000 },
  );
  check(true, "翻回 7 月");

  // ── 点日期过滤主列表 / 再点取消 ──────────────────────────────────────────
  const mainRows = () => page.locator(".todo-cards .todo-row");
  const before = await mainRows().count();
  check(before === 6, `未过滤时主列表 6 条(实测 ${before})`);
  await cell(page, "2026-07-17").click();
  await page.waitForFunction(
    () => document.querySelectorAll(".todo-cards .todo-row").length === 1,
    { timeout: 5000 },
  );
  check((await mainRows().first().innerText()).includes("等业主定颜色"),
    "按 07-17 过滤:只剩该日到期的那条");
  check(await cell(page, "2026-07-17").evaluate((el) => el.classList.contains("sel")),
    "被选日期有选中态");
  const banner = page.locator('[data-ui="todo-date-filter"]');
  check(await banner.count() === 1, "出现日期过滤条(否则列表凭空变短会让人困惑)");
  await cell(page, "2026-07-17").click();
  await page.waitForFunction(
    () => document.querySelectorAll(".todo-cards .todo-row").length === 6,
    { timeout: 5000 },
  );
  check(await banner.count() === 0, "再点同一日期:过滤取消,过滤条消失");

  // ── 需要今天跟进 ────────────────────────────────────────────────────────
  const follow = page.locator('[data-ui="follow-card"]');
  check(await follow.count() === 3, `跟进区 3 条(2 超期 + 1 今天到期,实测 ${await follow.count()})`);
  const followTexts = await follow.allInnerTexts();
  check(followTexts[0].includes("床头背景墙") && followTexts[0].includes("超期 7 天"),
    `最久超期(7 天)排最前(实测「${followTexts[0].replace(/\n/g, " ")}」)`);
  check(followTexts[1].includes("等业主定颜色") && followTexts[1].includes("超期 5 天"),
    "次久超期(5 天)排第二");
  check(followTexts[2].includes("整墙书柜") && followTexts[2].includes("今天到期"),
    "今天到期垫后且文案为「今天到期」");
  check(followTexts.every((t) => !t.includes("窗帘盒") && !t.includes("餐边柜") && !t.includes("橱柜台面")),
    "未来到期 / 无到期日的条目不进跟进区");
  check(followTexts[0].includes(P1) && followTexts[2].includes(P2),
    "跟进卡带项目名(跨项目视图)");
  check(await page.locator('[data-ui="follow-empty"]').count() === 0, "有事项时不显示空态");

  // ── 反应性:把这三条改成已完成 → 圆点消失 + 跟进区落空态 ──────────────────
  for (const t of ["床头背景墙", "等业主定颜色", "整墙书柜"]) {
    await page.locator(`.todo-cards .todo-row:has-text("${t}")`).first()
      .locator('[data-ui="todo-select"]').check();
  }
  const bar = page.locator('[data-ui="todo-batch-bar"]');
  await bar.waitFor({ timeout: 5000 });
  await bar.locator(".st-btn").click();
  await page.locator('.st-menu-item:has-text("已完成")').click();
  await page.locator('[data-ui="follow-empty"]').waitFor({ timeout: 15000 });
  check((await page.locator('[data-ui="follow-empty"]').innerText()).includes("今天没有到期事项"),
    "全部办结后跟进区显示空态文案");
  check(await cell(page, "2026-07-15").locator(".cal-dot").count() === 0,
    "办结后 07-15 的圆点消失(月历跟着数据走,不是静态装饰)");
  check(await cell(page, "2026-07-23").locator(".cal-dot").count() === 1,
    "未办结的未来到期点仍在(没有误杀)");
} catch (e) {
  failures++;
  console.error(String(e));
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}
console.log(failures === 0 ? "TODO-RAIL E2E: ALL PASS" : `TODO-RAIL E2E: ${failures} FAIL`);
process.exit(failures === 0 ? 0 : 1);
