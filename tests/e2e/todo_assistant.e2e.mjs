// track opendesign-todo-assistant e2e:待办页 keep-mounted 改造 + 右栏项目助手。
// 真 chromium + 真 ds_web,**无 gateway**(真正的发送链路交装机验收)。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// 覆盖:
//   A keep-mounted 四性质:离开后 DOM 仍在 / UI 态保留 / 回来会重新取数(磁盘改动可见)
//     / 隐藏期间不取数
//   B 右栏项目助手:收起态(说明+输入+发送)、ChatPage 常驻但隐藏、展开让位、收起不丢 DOM
//   C 不吞字:未连接时提交 → 展开露出连接卡,且刚打的字仍在右栏输入框里
//
// 跑法:node tests/e2e/todo_assistant.e2e.mjs(自起 ds_web 于 8806)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8806;
// ⚠️ DS_TODAY 只冻结服务端的今天;前端全程用服务端下发的 data.today,零 new Date()。
const TODAY = "2026-07-22";

const tmp = mkdtempSync(join(tmpdir(), "tasst-e2e-"));
const dsRoot = join(tmp, "ds");
const P1 = "翡翠湾-1801";
mkdirSync(join(dsRoot, "projects"), { recursive: true });
const mdPath = join(dsRoot, "projects", `${P1}.md`);
writeFileSync(mdPath, `# ${P1}

- 业主: [[张三]]
- 阶段: 施工跟进

## 变更记录
- [待确认] C6 2026-07-10 【主卧】床头背景墙改木饰面 ⏳2026-07-15
- [待确认] C7 2026-07-11 【玄关】玄关柜加感应灯带 ⏳2026-07-22
- [进行中] C8 2026-07-12 【客厅】电视墙尺寸重新放样

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

let failures = 0;
let browser = null;
try {
  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } });

  // /api/todos 请求计数(性质④用)。注意:不能断言"没进过待办页时为 0"——
  // api.ts:101 侧栏未办结角标也拉这个口,App 挂载即拉,那样写会因合法原因红。
  let todosHits = 0;
  page.on("request", (r) => {
    if (new URL(r.url()).pathname === "/api/todos") todosHits++;
  });

  await page.goto(base, { waitUntil: "domcontentloaded" });
  await page.locator('.side-row:has-text("技能")').first().waitFor({ timeout: 10000 });
  await page.waitForTimeout(600);

  // ── A① 没进过待办页时,待办页不该已经渲染出来 ──────────────────────────
  check(await page.locator(".todo-page .todo-card").count() === 0,
    "未进入待办页时:页面内容未渲染");

  // ── A④ 停在别的页面,计数不涨 ────────────────────────────────────────
  await page.locator('.side-row:has-text("技能")').first().click();
  await page.waitForTimeout(700);
  const hitsIdle = todosHits;
  await page.waitForTimeout(700);
  check(todosHits === hitsIdle, `停在技能页时 /api/todos 不再增长(维持 ${hitsIdle} 次)`);

  // ── 进入待办页:必取数 ────────────────────────────────────────────────
  await page.locator('.side-row:has-text("待办事项")').first().click();
  await page.locator(".todo-card").first().waitFor({ timeout: 10000 });
  check(todosHits > hitsIdle, `进入待办页触发取数(${hitsIdle} → ${todosHits})`);
  check(await page.locator(".todo-row").count() === 3, "初始 3 条未办结");

  // ── 制造可观察的 UI 态:日期过滤 + 折叠首卡 ────────────────────────────
  await page.locator('[data-ui="cal-cell"][data-date="2026-07-15"]').click();
  await page.waitForFunction(
    () => document.querySelectorAll(".todo-cards .todo-row").length === 1, { timeout: 5000 });
  check(await page.locator('[data-ui="todo-date-filter"]').count() === 1, "日期过滤已生效");

  // ── A① 离开后 DOM 仍在(keep-mounted 的机械证据)────────────────────────
  await page.locator('.side-row:has-text("技能")').first().click();
  await page.waitForTimeout(500);
  check(await page.locator(".todo-page").count() === 1,
    "离开待办页后 .todo-page 仍在 DOM(未被卸载)");
  check(await page.locator(".todo-page").evaluate((el) => el.closest(".route-hidden") !== null),
    "且被 .route-hidden 祖先隐藏(与 home-pane/ws-pane 同款)");
  check(!(await page.locator(".todo-page").isVisible()), "视觉上不可见");
  const hitsHidden = todosHits;
  await page.waitForTimeout(700);
  check(todosHits === hitsHidden, "隐藏期间不取数");

  // ── 磁盘上加一条变更(证明回来时是真重拉,不是拿旧数据)──────────────────
  writeFileSync(mdPath, readFileSync(mdPath, "utf-8").replace(
    "## 沟通日志",
    "- [待确认] C9 2026-07-21 【厨房】橱柜台面加挡水\n\n## 沟通日志",
  ));

  // ── A② UI 态保留 + A③ 数据重拉 ───────────────────────────────────────
  await page.locator('.side-row:has-text("待办事项")').first().click();
  await page.locator(".todo-page").first().waitFor({ state: "visible", timeout: 5000 });
  check(await page.locator('[data-ui="todo-date-filter"]').count() === 1,
    "切回后日期过滤仍在(UI 态保留 = 确实没被卸载重建)");
  check(await page.locator('[data-ui="cal-cell"][data-date="2026-07-15"]')
    .evaluate((el) => el.classList.contains("sel")), "切回后日历选中态仍在");
  check(todosHits > hitsHidden, `切回待办页重新取数(${hitsHidden} → ${todosHits})`);
  await page.locator('[data-ui="todo-date-filter"] button').first().click();
  await page.waitForFunction(
    () => document.querySelectorAll(".todo-cards .todo-row").length === 4, { timeout: 5000 });
  check((await page.locator(".todo-cards").innerText()).includes("橱柜台面加挡水"),
    "磁盘上新增的变更切回后可见(数据确实是新拉的,不是旧快照)");

  // ── B 右栏项目助手 ───────────────────────────────────────────────────
  const asst = page.locator('[data-ui="rail-assistant"]');
  await asst.waitFor({ timeout: 5000 });
  const ask = page.locator('[data-ui="rail-ask"]');
  check(await ask.count() === 1, "收起态有输入框");
  check(await page.locator('[data-ui="rail-send"]').count() === 1, "收起态有「发送」按钮");
  check((await asst.innerText()).includes("项目"),
    "有一句能力说明(提示带项目名——「记一下」的归属靠它)");
  const chat = page.locator('[data-ui="rail-chat"]');
  check(await chat.count() === 1, "ChatPage 常驻挂载(收起态也在 DOM 里)");
  check(!(await chat.isVisible()), "收起态下聊天区不可见");
  check(await page.locator('[data-ui="cal-month"]').isVisible(), "收起态月历可见");

  await page.locator('[data-ui="rail-expand"]').click();
  await page.waitForFunction(
    () => document.querySelector('[data-ui="rail-chat"]')?.checkVisibility?.() === true,
    { timeout: 5000 });
  check(!(await page.locator('[data-ui="cal-month"]').isVisible()),
    "展开后月历让位(对话流占满右栏)");
  check(await page.locator('[data-ui="cal-cell"]').count() === 42,
    "让位是 CSS 隐藏,月历 DOM 未卸载(切回不用重建)");

  await page.locator('[data-ui="rail-collapse"]').click();
  await page.waitForFunction(
    () => document.querySelector('[data-ui="cal-month"]')?.checkVisibility?.() === true,
    { timeout: 5000 });
  check(await chat.count() === 1, "收起后聊天节点仍在 DOM(收起≠丢对话)");

  // ── C 不吞字:未连接时提交 ────────────────────────────────────────────
  const TEXT = "C7 业主上次怎么说的";
  await ask.fill(TEXT);
  await page.locator('[data-ui="rail-send"]').click();
  // 主 agent 修正①:选择器必须限定在右栏内。App 里 home-pane 常驻着另一个 login 态
  // ChatPage,它的 connect-card 在 DOM 里更靠前且恒隐藏,裸 `.first()` 会永远锁死在
  // 那一张上超时(实测 2 张卡:home 的隐藏、rail 的可见)。仓里 frontend_p2_polish.e2e.mjs:113
  // 早已立下 `.home-pane [data-ui="connect-card"]` 的限定先例,是我没跟。
  await page.locator('[data-ui="rail-chat"] [data-ui="connect-card"]')
    .waitFor({ state: "visible", timeout: 5000 });
  check(true, "未连接时提交:展开并露出**右栏自己的**连接卡");
  // 主 agent 修正②:原断言只验 inputValue() ——它读隐藏元素照样返回值,
  // 于是"字留在 DOM 里但用户看不见"也能过。而"看不见"正是这条要防的体验。
  // 收紧为:输入框必须**可见**且带着原文。
  check(await ask.isVisible(), "未连接时输入框仍可见(字得让人看得见,不能只留在 DOM 里)");
  check(await ask.inputValue() === TEXT,
    `未连接时**不清空**输入框(实测「${await ask.inputValue()}」)`);
} catch (e) {
  failures++;
  console.error(String(e));
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}
console.log(failures === 0 ? "TODO-ASSISTANT E2E: ALL PASS" : `TODO-ASSISTANT E2E: ${failures} FAIL`);
process.exit(failures === 0 ? 0 : 1);
