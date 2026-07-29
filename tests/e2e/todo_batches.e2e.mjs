// 待办「按时间」批次:人话标题 + 折叠规则 e2e(真 chromium + 真 ds_web)。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// 用户拍板(tasks.md T4):批次头现在是「7月28日 · 3条」,要换成一句人话;
// 「1~2 条不折;≥3 条默认折起;有过了截止日的自动展开」;折叠状态持久化(同 T3)。
// 本单 T4a 只做**兜底标题**(第一条内容 等 N 条)—— 助手起名是 T4b。
// 纯逻辑那半由 tests/test_todo_batches.mjs 钉;这里钉用户看得见的那半。
//
// 覆盖:
//   A 批次头是**人话**:含首条内容,不再是光秃秃的「N 条」;日期仍在(找得回时间)。
//   B 默认态:2 条的批次展开、3 条的批次收起。
//   C 含**过期**条目的批次即使 4 条也默认展开(急压过整洁)。
//   D 点批次头收得起也放得回来。
//   E **刷新后折叠状态还在** —— ⚠️ 本单重点:现有 toggled 是 useState、刷新即忘,
//     tasks.md 明写"别重蹈覆辙"(T3 已在左栏还过一次债,这里是待办页那笔)。
//   F **用户点收了就得收着,过期不许把它顶开** —— 折叠键不许变死键(T3 教训)。
//   G 一条都不丢:全部展开后待办行数 == 条目总数。
//
// 跑法:node tests/e2e/todo_batches.e2e.mjs(自起 ds_web 于 8814)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8814;
const TODAY = "2026-07-29";

const tmp = mkdtempSync(join(tmpdir(), "todobatch-e2e-"));
const dsRoot = join(tmp, "ds");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });

// 三个日期批次(按时间视图按日期分批):
//   07-28:3 条,无过期 → 默认收起(≥3)
//   07-27:2 条,无过期 → 默认展开(≤2)
//   07-26:4 条,其中 1 条过了截止日 → 默认展开(急压过整洁)
const BATCHES = [
  { date: "2026-07-28", texts: ["效果图改浅色", "餐桌换圆桌", "主卧加衣柜"], due: {} },
  { date: "2026-07-27", texts: ["阳台封窗", "厨房加插座"], due: {} },
  { date: "2026-07-26", texts: ["客厅吊顶改平顶", "电视墙留白", "地板换木色", "玄关做柜"],
    due: { 0: "2026-07-01" } }, // 第 1 条过期
];
const TOTAL = BATCHES.reduce((n, b) => n + b.texts.length, 0) + 6; // +6 = 李宅四条命名 + 两条 07-26 命名

const lines = [];
let cn = 0;
for (const b of BATCHES) {
  b.texts.forEach((t, i) => {
    cn++;
    // 截止日格式 = 正文尾部 ⏳YYYY-MM-DD(ds_common.split_due 切;别自造第二种写法)
    const due = b.due[i] ? ` ⏳${b.due[i]}` : "";
    lines.push(`- [待确认] C${cn} ${b.date} 【主卧】${t}${due}`);
  });
}
writeFileSync(join(dsRoot, "projects", "张宅-1101.md"), `# 张宅-1101

- 业主: [[王女士]]
- 阶段: 施工跟进

## 变更记录
${lines.join("\n")}

## 沟通日志

---
最后更新: ${TODAY}
`);
// T4b 夹具:第二个项目带 `## 批次` 段(助手起的名)。**故意用新日期 07-25**,
// 不打扰上面 A–G 三批的默认态断言。同一天里两个命名批次,验"各自成组、各自折叠"。
writeFileSync(join(dsRoot, "projects", "李宅-0808.md"), `# 李宅-0808

- 业主: [[李先生]]
- 阶段: 效果图

## 变更记录
- [待确认] C1 2026-07-25 【客厅】沙发背景墙改护墙板
- [待确认] C2 2026-07-25 【客厅】灯带改暗藏
- [待确认] C3 2026-07-25 【厨房】加净水器点位
- [待确认] C4 2026-07-25 【阳台】洗衣机位留水口

- [待确认] C5 2026-07-26 【主卧】床头灯改壁灯
- [待确认] C6 2026-07-26 【主卧】插座下移

## 批次
- C1-C2 2026-07-25 效果图修改
- C3-C4 2026-07-25 水电改动
- C5-C6 2026-07-26 主卧微调

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

let browser = null;
try {
  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  const sects = () => page.locator('.todo-page .batch-sect');
  // A–G 量的是**没有名字的那个日期组**;07-26 现在同一天还有李宅的命名批次
  // (I 段要用),所以这里必须 :not([data-batch]) 精确到无名组,否则数到两组的行。
  const sect = (date) =>
    page.locator(`.todo-page .batch-sect[data-date="${date}"]:not([data-batch])`);
  const bsect = (id) => page.locator(`.todo-page .batch-sect[data-batch="${id}"]`);
  const bhead = (id) => bsect(id).locator('[data-ui="group-toggle"]');
  const brows = (id) => bsect(id).locator(".todo-row");
  const head = (date) => sect(date).locator('[data-ui="group-toggle"]');
  const rowsIn = (date) => sect(date).locator(".todo-row");
  const allRows = () => page.locator(".todo-page .todo-row");

  // hash 路由是 `#/todos`(App.tsx fromHash 只认 workspace|todos|skills|gallery,
  // 写错会静默退回首页 —— 别改成 #/todo)。
  // 待办页默认「按项目」视图,批次只在「按时间」下存在:每次进页面都要切一下。
  // (视图选择本身不落盘,与本单要验的批次折叠持久化是两回事,别混。)
  const gotoTodo = async () => {
    await page.goto(`${base}/#/todos`, { waitUntil: "domcontentloaded" });
    await page.locator(".todo-head .seg .opt", { hasText: "按时间" }).click();
    await sects().first().waitFor({ timeout: 15000 });
  };

  // ── A 批次头是人话 ───────────────────────────────────────────────────────
  await step("A 批次头写的是人话(首条内容 等 N 条),不是光秃秃的「N 条」", async () => {
    await gotoTodo();
    for (const b of BATCHES) {
      const txt = (await head(b.date).innerText()).replace(/\s+/g, "");
      expect(txt.includes(b.texts[0].slice(0, 6)),
        `「${b.date}」批次头含首条内容「${b.texts[0]}」(实测「${txt}」)`);
      expect(txt.includes(String(b.texts.length)),
        `「${b.date}」批次头仍带条数 ${b.texts.length}`);
    }
    // 日期不能丢:人话标题替掉的是"只有日期",不是把时间线抹了
    const first = (await head("2026-07-28").innerText()).replace(/\s+/g, "");
    expect(/7月28日|07-28|7\/28/.test(first), `批次头仍找得回日期(实测「${first}」)`);
  });

  // ── B 默认态:条数规则 ───────────────────────────────────────────────────
  await step("B 默认:2 条的批次展开,3 条的批次收起", async () => {
    await gotoTodo();
    expect(await rowsIn("2026-07-27").count() === 2, "07-27(2 条)默认展开着");
    expect(await head("2026-07-27").getAttribute("aria-expanded") === "true",
      "07-27 批次头 aria-expanded=true");
    expect(await rowsIn("2026-07-28").count() === 0, "07-28(3 条)默认收着");
    expect(await head("2026-07-28").getAttribute("aria-expanded") === "false",
      "07-28 批次头 aria-expanded=false");
  });

  // ── C 过期压过条数 ───────────────────────────────────────────────────────
  await step("C 含过期条目的批次(4 条)默认展开 —— 急压过整洁", async () => {
    await gotoTodo();
    expect(await rowsIn("2026-07-26").count() === 4,
      "07-26 有一条过了截止日,4 条也默认全展开");
  });

  // ── D 点得动 ─────────────────────────────────────────────────────────────
  await step("D 点批次头收得起、也放得回来", async () => {
    await gotoTodo();
    await head("2026-07-27").click();
    await page.waitForTimeout(150);
    expect(await rowsIn("2026-07-27").count() === 0, "点一下:收起来了");
    await head("2026-07-27").click();
    await page.waitForTimeout(150);
    expect(await rowsIn("2026-07-27").count() === 2, "再点一下:又回来了");
  });

  // ── E 刷新后还在(本单重点)─────────────────────────────────────────────
  await step("E 刷新后折叠状态还在(useState 实现在这里必红)", async () => {
    await gotoTodo();
    await head("2026-07-28").click(); // 默认收着 → 点开
    await page.waitForTimeout(150);
    check(await rowsIn("2026-07-28").count() === 3, "前提:07-28 已被点开");
    await gotoTodo(); // 刷新
    expect(await rowsIn("2026-07-28").count() === 3,
      "刷新后 07-28 仍是展开的 —— 折叠状态落了盘");

    await head("2026-07-27").click(); // 默认展开 → 点收
    await page.waitForTimeout(150);
    await gotoTodo();
    expect(await rowsIn("2026-07-27").count() === 0,
      "刷新后 07-27 仍是收着的 —— 两个方向都记住");
  });

  // ── F 用户显式收起压过「过期自动展开」──────────────────────────────────
  await step("F 用户点收了含过期条目的批次 → 刷新后仍收着(折叠键不许变死键)", async () => {
    await gotoTodo();
    check(await rowsIn("2026-07-26").count() === 4, "前提:07-26 因过期默认展开");
    await head("2026-07-26").click();
    await page.waitForTimeout(150);
    expect(await rowsIn("2026-07-26").count() === 0, "点一下收得起来(过期不许顶住)");
    await gotoTodo();
    expect(await rowsIn("2026-07-26").count() === 0,
      "刷新后仍收着 —— 显式偏好压过过期规则");
  });

  // ── G 一条都不丢 ─────────────────────────────────────────────────────────
  await step("G 全部展开后一条都不丢", async () => {
    // 清掉本轮攒下的偏好,回默认态再逐个展开
    await page.goto(`${base}/#/todos`, { waitUntil: "domcontentloaded" });
    await page.evaluate(() => localStorage.removeItem("ds.todo.batchOpen"));
    await gotoTodo();
    for (const b of BATCHES) {
      if (await rowsIn(b.date).count() === 0) {
        await head(b.date).click();
        await page.waitForTimeout(120);
      }
    }
    expect(await allRows().count() === TOTAL,
      `全展开后待办行数 = ${TOTAL}(实测 ${await allRows().count()})`);
    // 求和要遍历**页面上所有分组**(含李宅那两个命名批次),不能只数 BATCHES 那三个日期
    // —— 否则"总数"与"分组之和"量的根本不是同一批东西。
    const perGroup = await sects().evaluateAll(
      (els) => els.map((e) => e.querySelectorAll(".todo-row").length));
    const sum = perGroup.reduce((a, b) => a + b, 0);
    expect(sum === TOTAL, `各分组行数之和 = ${TOTAL}(实测 ${sum})`);
  });

  // ── H 助手起的名(T4b)─────────────────────────────────────────────────────
  await step("H 档案里有 ## 批次 → 批次头显示助手起的名,同日两批各自成组各自折叠", async () => {
    await gotoTodo();
    expect(await bsect("C1-C2").count() === 1, "命名批次 C1-C2 自成一组");
    expect(await bsect("C3-C4").count() === 1, "命名批次 C3-C4 自成一组");

    const t1 = (await bhead("C1-C2").innerText()).replace(/\s+/g, "");
    expect(t1.includes("效果图修改"), `头上是助手起的名(实测「${t1}」)`);
    expect(!t1.includes("沙发背景墙"), "有名字就不该再退回首条内容兜底");
    const t2 = (await bhead("C3-C4").innerText()).replace(/\s+/g, "");
    expect(t2.includes("水电改动"), `第二批用自己的名字(实测「${t2}」)`);

    // 两批各 2 条 → 都默认展开;收其中一个不许带走另一个(折叠键必须分开)
    expect(await brows("C1-C2").count() === 2, "C1-C2 默认展开,2 条都在");
    expect(await brows("C3-C4").count() === 2, "C3-C4 默认展开,2 条都在");
    await bhead("C1-C2").click();
    await page.waitForTimeout(150);
    expect(await brows("C1-C2").count() === 0, "收起第一批");
    expect(await brows("C3-C4").count() === 2, "第二批不受影响(折叠键分开了)");
    await gotoTodo();
    expect(await brows("C1-C2").count() === 0, "刷新后第一批仍收着");
  });


  // ── I 跨项目(四审 subkimi 孤腿 BLOCK)──────────────────────────────────────
  await step("I 同一天里两个项目各有批次 → 各自成组,不许张冠李戴", async () => {
    await gotoTodo();
    // 07-26:张宅有 4 条无名条目(含过期),李宅有命名批次「主卧微调」
    const li = page.locator('.todo-page .batch-sect[data-date="2026-07-26"]',
      { hasText: "主卧微调" });
    expect(await li.count() === 1, "李宅的命名批次在 07-26 自成一组");
    const liRows = li.locator(".todo-row");
    expect(await liRows.count() === 2, "组里只有李宅那 2 条");
    const projs = await liRows.locator(".proj-tag, .proj").allInnerTexts()
      .catch(() => []);
    if (projs.length) {
      expect(new Set(projs.map((t) => t.trim())).size === 1,
        `一组里不许混两个项目(实测 ${JSON.stringify(projs)})`);
    }
    // 张宅那 4 条仍在它们自己的无名组里
    const zhang = page.locator('.todo-page .batch-sect[data-date="2026-07-26"]')
      .filter({ hasNot: page.locator("text=主卧微调") });
    expect(await zhang.locator(".todo-row").count() === 4,
      "张宅 07-26 的 4 条不受影响");
  });

} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}

console.log(failures === 0 ? "\n全部通过" : `\n${failures} 条失败`);
process.exit(failures === 0 ? 0 : 1);
