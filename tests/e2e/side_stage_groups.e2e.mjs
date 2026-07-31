// 左栏项目按**阶段**分堆折叠 e2e(真 chromium + 真 ds_web)。主 agent 亲写,执行腿逐字节 off-limits。
//
// 用户 07-28 拍板:左栏项目列表按**阶段**分堆折叠(不是"只折已交付",也不是按硬盘文件夹)。
// 纯逻辑那半由 tests/test_project_groups.mjs 钉;这里钉用户看得见的那半。
//
// 覆盖:
//   A 分堆出现:堆头按**词表顺序**排,未建档垫底;每堆带条数。
//   B 默认态:已交付的堆(竣工验收/售后)默认收起,其余默认展开 —— 分堆就是为了它们别占地方。
//   C 点堆头收得起也放得回来。
//   D **刷新后折叠状态还在** —— ⚠️ 这条是本单的重点:待办页的 toggled 是 useState、
//     刷新即忘,tasks.md 明写"别重蹈覆辙"。useState 实现在这条必红。
//   E 从**别处**选中一个收着的堆里的项目(待办页「去项目 →」)→ 那堆自己展开、
//     人看得见自己在哪;**且堆头不能变成死键**(还能再点回收起)。
//     渲染期强制展开的实现会在"再点一下"这一步红。
//   F **一个项目都不丢**:全部展开后侧栏项目行数 == 项目总数;堆头计数之和也等于它。
//
// 跑法:node tests/e2e/side_stage_groups.e2e.mjs(自起 ds_web 于 8813)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8813;
const TODAY = "2026-07-29";

const tmp = mkdtempSync(join(tmpdir(), "sidestage-e2e-"));
const dsRoot = join(tmp, "ds");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });

// 六个项目铺满五个堆:效果图1 / 施工跟进2 / 竣工验收1 / 售后1 / 未建档1。
// 「未建档」这堆用的是**头部没有「- 阶段:」行**的档案 —— 与工作区自动发现的
// 未建档文件夹(stage="")同一条前端路径,免得 e2e 还得摆一套工作区根目录。
const PROJ = [
  { key: "云山名城-2302", stage: "施工跟进", open: 1 },
  { key: "翡翠湾-1801", stage: "施工跟进", open: 2 },
  { key: "江畔花园-0705", stage: "效果图", open: 1 },
  { key: "松涛苑-0101", stage: "竣工验收", open: 1 }, // 已交付但仍有未办结 → E 段从待办页进得来
  { key: "旧宅-0202", stage: "售后", open: 0 },
  { key: "待建档-0303", stage: null, open: 0 },
];
const DELIVERED = ["松涛苑-0101", "旧宅-0202"];
// 词表顺序:效果图(5) < 施工跟进(8) < 竣工验收(10) < 售后(11);未建档恒垫底
const WANT_ORDER = ["效果图", "施工跟进", "竣工验收", "售后", "未建档"];
const WANT_COUNT = { 效果图: 1, 施工跟进: 2, 竣工验收: 1, 售后: 1, 未建档: 1 };

for (const p of PROJ) {
  const changes = [];
  for (let n = 1; n <= p.open; n++) {
    changes.push(`- [待确认] C${n} ${TODAY} 【主卧】${p.key} 第 ${n} 条待办`);
  }
  writeFileSync(join(dsRoot, "projects", `${p.key}.md`), `# ${p.key}

- 业主: [[王女士]]
${p.stage ? `- 阶段: ${p.stage}\n` : ""}
## 变更记录
${changes.join("\n")}

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

  const groups = () => page.locator('.proj-list [data-ui="stage-group"]');
  const group = (stage) => page.locator(`.proj-list [data-ui="stage-group"][data-stage="${stage}"]`);
  const head = (stage) => group(stage).locator('[data-ui="group-toggle"]');
  const rowsIn = (stage) => group(stage).locator(".proj-row");
  const row = (key) => page.locator(`.proj-list .proj-row`, { hasText: key });
  const stageOrder = () =>
    groups().evaluateAll((els) => els.map((e) => e.getAttribute("data-stage")));

  const gotoWorkspace = async () => {
    await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
    await groups().first().waitFor({ timeout: 15000 });
  };

  // ── A 分堆出现,顺序按词表 ────────────────────────────────────────────────
  await step("A 项目按阶段分堆,堆头按词表顺序排、未建档垫底、各带条数", async () => {
    await gotoWorkspace();
    check(await page.locator(".side-sect.projects .sect-count").innerText() === String(PROJ.length),
      `前提:侧栏「项目」总数 = ${PROJ.length}`);

    expect(JSON.stringify(await stageOrder()) === JSON.stringify(WANT_ORDER),
      `堆头顺序 = ${WANT_ORDER.join(" / ")}(实测 ${(await stageOrder()).join(" / ")})`);

    for (const [stage, n] of Object.entries(WANT_COUNT)) {
      const txt = (await head(stage).innerText()).replace(/\s+/g, "");
      expect(txt.includes(stage) && txt.includes(String(n)),
        `堆头「${stage}」写着它有 ${n} 个项目(实测「${txt}」)`);
    }
  });

  // ── B 默认态 ─────────────────────────────────────────────────────────────
  await step("B 已交付的堆默认收起,其余默认展开", async () => {
    await gotoWorkspace();
    for (const stage of ["竣工验收", "售后"]) {
      expect(await rowsIn(stage).count() === 0, `「${stage}」默认收着(不占地方)`);
      expect(await head(stage).getAttribute("aria-expanded") === "false",
        `「${stage}」堆头 aria-expanded=false`);
    }
    for (const stage of ["效果图", "施工跟进", "未建档"]) {
      expect(await rowsIn(stage).count() === WANT_COUNT[stage],
        `「${stage}」默认展开着,${WANT_COUNT[stage]} 行都在`);
    }
    for (const key of DELIVERED) {
      expect(await row(key).count() === 0, `已交付的「${key}」这行默认不出现`);
    }
  });

  // ── C 收得起放得回 ────────────────────────────────────────────────────────
  await step("C 点堆头收得起,再点放得回来", async () => {
    await gotoWorkspace();
    await head("施工跟进").click();
    expect(await rowsIn("施工跟进").count() === 0, "点一下「施工跟进」→ 它的 2 行收起来了");
    expect(await row("翡翠湾-1801").count() === 0, "翡翠湾-1801 跟着收进去了");
    await head("施工跟进").click();
    expect(await rowsIn("施工跟进").count() === 2, "再点一下 → 2 行回来了");
  });

  // ── D 折叠状态落盘 ────────────────────────────────────────────────────────
  await step("D 刷新后折叠状态还在(⚠️ useState 实现必红)", async () => {
    await gotoWorkspace();
    await head("施工跟进").click();                        // 收起一个默认开的
    await head("售后").click();                            // 展开一个默认关的
    expect(await rowsIn("施工跟进").count() === 0, "刷新前:施工跟进已收起");
    expect(await rowsIn("售后").count() === 1, "刷新前:售后已展开");

    await gotoWorkspace();                                 // 整页重载
    expect(await rowsIn("施工跟进").count() === 0, "刷新后:施工跟进**仍然**收着");
    expect(await rowsIn("售后").count() === 1, "刷新后:售后**仍然**开着");
    expect(await row("旧宅-0202").count() === 1, "刷新后:售后堆里那个项目还看得见");

    const prefs = await page.evaluate(() => localStorage.getItem("ds.side.stageOpen"));
    expect(prefs !== null && JSON.parse(prefs)["施工跟进"] === false
                         && JSON.parse(prefs)["售后"] === true,
      `折叠状态确实落在 localStorage 的 ds.side.stageOpen 里(实测 ${prefs})`);
  });

  // ── E 从别处选中 → 那堆自己展开,且堆头不是死键 ───────────────────────────
  await step("E 待办页「去项目 →」进到收着的堆里的项目 → 那堆自己展开,堆头仍可再收", async () => {
    await gotoWorkspace();
    expect(await rowsIn("竣工验收").count() === 0, "前提:竣工验收默认收着");

    await page.goto(`${base}/#/todos`, { waitUntil: "domcontentloaded" });
    await page.locator(".todo-page .opt", { hasText: "按项目" }).click();
    const card = page.locator(".todo-card", { hasText: "松涛苑-0101" }).first();
    await card.waitFor({ timeout: 15000 });
    // 按**用户看得见的文案**选,不按 class 名(2026-08-01 按钮角色收编:`.go-link`
    // 并入共享的 `.link-act`,原来钉在 class 名上的选择器全断了)。文案选择器对
    // 下一次改 class 免疫,而这一段本来要验的就是"这个入口点得到",不是它叫什么。
    await card.locator('button:has-text("去项目")').click();

    await groups().first().waitFor({ timeout: 15000 });
    expect(await row("松涛苑-0101").count() === 1,
      "进来了就看得见自己在哪:竣工验收这堆自己展开了");
    expect(await head("竣工验收").getAttribute("aria-expanded") === "true",
      "堆头也如实显示成展开态");

    await head("竣工验收").click();
    expect(await rowsIn("竣工验收").count() === 0,
      "堆头没变成死键:选中着也照样收得起(渲染期强制展开的实现在这里红)");
  });

  // ── F 一个项目都不丢 ──────────────────────────────────────────────────────
  await step("F 全部展开后一个项目都不丢", async () => {
    await page.evaluate(() => localStorage.removeItem("ds.side.stageOpen"));
    await gotoWorkspace();
    for (const stage of WANT_ORDER) {
      if (await head(stage).getAttribute("aria-expanded") === "false") await head(stage).click();
    }
    const total = await page.locator(".proj-list .proj-row").count();
    expect(total === PROJ.length, `侧栏项目行 = ${PROJ.length}(实测 ${total})`);

    let sum = 0;
    for (const stage of WANT_ORDER) sum += await rowsIn(stage).count();
    expect(sum === PROJ.length, `各堆行数之和 = ${PROJ.length}(实测 ${sum})`);
    for (const p of PROJ) {
      expect(await row(p.key).count() === 1, `「${p.key}」在且只在一个堆里`);
    }
  });

  console.log(failures === 0 ? "\nSIDE-STAGE-GROUPS E2E: ALL PASS"
                             : `\nSIDE-STAGE-GROUPS E2E: ${failures} FAIL`);
} catch (e) {
  failures++;
  console.error(String(e));
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}
process.exit(failures === 0 ? 0 : 1);
