// 待办页第三个看法「按阶段」e2e(真 chromium + 真 ds_web)。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// 用户 07-30 真机原话:「待办事项可以区分一下进度,比如平面图阶段的、效果图阶段的、
// 施工图阶段的……这样不只是待办清单,也相当于是一眼能知道项目在哪个阶段」。
// tasks.md C 的结论:**零新字段** —— 用项目已有的阶段字段分堆即可。
//
// ⚠️ 与 D(十系统覆盖表)是两个轴,别在这里混:阶段答「在哪个阶段」,
// 十系统答「差什么东西」,后者要单独起 track。
//
// 覆盖:
//   A 看法切换器有第三个「按阶段」(原来只有 按项目/按时间)。
//   B 切过去:每个阶段一个堆,项目卡照旧长在堆里(不另起第二种卡片语言)。
//   C **堆序 = 后端阶段词表序**(洽谈…售后),不是遇见序/字典序;
//     **没阶段的项目归「未建档」且垫底**(一个项目都不丢)。
//   D 堆头收得起也放得回来,且**刷新后还在**(与 T3 左栏、T4a 批次同一条纪律:
//     折叠状态不许是 useState、不许变死键)。
//   E 一条都不丢:全部展开后待办行数 == 条目总数。
//   F 「去项目 →」在这个看法里照样点得到(既有能力不许退化)。
//
// 跑法:node tests/e2e/todo_stage_view.e2e.mjs(自起 ds_web 于 8817)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8817;
const TODAY = "2026-07-30";

const tmp = mkdtempSync(join(tmpdir(), "todostage-e2e-"));
const dsRoot = join(tmp, "ds");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });

// 夹具**故意把词表序打乱着写**(文件名序 = 遇见序 = 施工跟进 → 平面方案 → 效果图),
// 这样 C 段才证明得了"堆序取的是后端词表序、不是遇见序"。
// 「无阶段」那个档案头**不写 `- 阶段:` 行** → 应归「未建档」并垫底。
const PROJECTS = [
  { key: "01张宅-1101", stage: "施工跟进", texts: ["吊顶改平顶", "衣柜加到顶"] },
  { key: "02李宅-0808", stage: "平面方案", texts: ["主卧门改推拉"] },
  { key: "03王宅-2202", stage: "效果图", texts: ["客厅改浅色", "餐边柜加高", "阳台封窗"] },
  { key: "04无阶段-9999", stage: null, texts: ["水电点位待定"] },
];
const TOTAL = PROJECTS.reduce((n, p) => n + p.texts.length, 0);
// 词表序(ds_tools.PROJECT_STAGES)里 平面方案 < 效果图 < 施工跟进;未建档恒垫底。
const EXPECTED_ORDER = ["平面方案", "效果图", "施工跟进", "未建档"];

for (const p of PROJECTS) {
  const stageLine = p.stage ? `- 阶段: ${p.stage}\n` : "";
  const lines = p.texts.map((t, i) => `- [待确认] C${i + 1} 2026-07-28 【主卧】${t}`);
  writeFileSync(join(dsRoot, "projects", `${p.key}.md`), `# ${p.key}

- 业主: [[某先生]]
${stageLine}
## 变更记录
${lines.join("\n")}

## 沟通日志

---
最后更新: ${TODAY}
`);
}
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

  const sects = () => page.locator(".todo-page .stage-sect");
  const sect = (stage) => page.locator(`.todo-page .stage-sect[data-stage="${stage}"]`);
  const head = (stage) => sect(stage).locator('[data-ui="group-toggle"]').first();
  const cardsIn = (stage) => sect(stage).locator(".todo-card");
  const allRows = () => page.locator(".todo-page .todo-row");

  // hash 路由是 `#/todos`(App.tsx fromHash 只认 workspace|todos|skills|gallery)。
  const gotoTodo = async (switchView = true) => {
    await page.goto(`${base}/#/todos`, { waitUntil: "domcontentloaded" });
    await page.locator(".todo-head .seg").waitFor({ timeout: 15000 });
    if (switchView) {
      await page.locator(".todo-head .seg .opt", { hasText: "按阶段" }).click();
      await sects().first().waitFor({ timeout: 15000 });
    }
  };

  // ── A 有第三个看法 ───────────────────────────────────────────────────────
  await step("A 看法切换器有「按阶段」", async () => {
    await gotoTodo(false);
    const opts = await page.locator(".todo-head .seg .opt").allInnerTexts();
    expect(opts.some((t) => t.replace(/\s+/g, "") === "按阶段"),
      `切换器含「按阶段」(实测 ${JSON.stringify(opts)})`);
    expect(opts.length === 3, `切换器共 3 个看法(实测 ${opts.length})`);
  });

  // ── B 分堆,卡片长在堆里 ─────────────────────────────────────────────────
  await step("B 每个阶段一个堆,项目卡照旧长在堆里", async () => {
    await gotoTodo();
    expect(await sects().count() === EXPECTED_ORDER.length,
      `共 ${EXPECTED_ORDER.length} 个阶段堆(实测 ${await sects().count()})`);
    expect(await cardsIn("效果图").count() === 1, "效果图堆里 1 张项目卡");
    const t = await sect("效果图").innerText();
    expect(t.includes("王宅-2202"), "效果图堆里是王宅(卡片没换成第二种语言)");
  });

  // ── C 堆序 = 词表序,未建档垫底 ───────────────────────────────────────────
  await step("C 堆序取后端阶段词表序,未建档垫底", async () => {
    await gotoTodo();
    const order = await sects().evaluateAll((els) =>
      els.map((e) => e.getAttribute("data-stage")));
    expect(JSON.stringify(order) === JSON.stringify(EXPECTED_ORDER),
      `堆序 = ${JSON.stringify(EXPECTED_ORDER)}(实测 ${JSON.stringify(order)})`);
    expect(await cardsIn("未建档").count() === 1,
      "没写阶段的项目归「未建档」堆(一个项目都不丢)");
  });

  // ── D 收放 + 持久化 ──────────────────────────────────────────────────────
  await step("D 堆头收得起放得回,刷新后还在", async () => {
    await gotoTodo();
    expect(await cardsIn("效果图").count() === 1, "初始:效果图堆展开着");
    await head("效果图").click();
    expect(await cardsIn("效果图").count() === 0, "点一下:收起来了");
    await gotoTodo();
    expect(await cardsIn("效果图").count() === 0, "刷新后:仍然收着(不是 useState)");
    await head("效果图").click();
    expect(await cardsIn("效果图").count() === 1, "再点一下:放得回来(折叠键不是死键)");
    await gotoTodo();
    expect(await cardsIn("效果图").count() === 1, "刷新后:仍然开着");
  });

  // ── E 一条都不丢 ─────────────────────────────────────────────────────────
  await step("E 全部展开后待办行数 == 条目总数", async () => {
    await gotoTodo();
    for (const s of EXPECTED_ORDER) {
      if ((await cardsIn(s).count()) === 0) await head(s).click();
    }
    expect(await allRows().count() === TOTAL,
      `待办行数 ${TOTAL}(实测 ${await allRows().count()})`);
  });

  // ── F 「去项目 →」没退化 ─────────────────────────────────────────────────
  await step("F 「去项目 →」在按阶段看法里照样点得到", async () => {
    await gotoTodo();
    const go = sect("效果图").locator(".go-link");
    expect(await go.count() === 1, "效果图堆里的卡片有「去项目 →」");
    await go.click();
    await page.locator(".change-scroll").waitFor({ timeout: 15000 });
    expect(page.url().includes("#/workspace") || !page.url().includes("#/todos"),
      "点了确实跳到项目工作区");
  });
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}

console.log(failures === 0 ? "\n全部通过" : `\n${failures} 条不通过`);
process.exit(failures === 0 ? 0 : 1);
