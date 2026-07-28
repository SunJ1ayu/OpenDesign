// 截止日「就地弹出日历」e2e(真 chromium + 真 ds_web)。主 agent 亲写,执行腿逐字节 off-limits。
//
// 用户 2026-07-28 提的:「现在我没法手动设置待办事项的截止日期……我觉得截止日还是
// 出现一个日历比较好,这样可以随便点就行了,就是出现的位置你可能得考虑一下」。
// 查下来:写口 set_due_date 早就有,UI 入口**只在工作区变更栏**、还是个原生
// <input type=date>;**待办页只读**(TodoPage 里那句注释写死了"设置入口留在工作区")。
// 而待办页恰恰是他"准备开工时看"的地方。
//
// 覆盖:
//   A 待办页能设,而且是**真的写进档案**(刷新后还在)—— 这条现在必红:待办页无入口。
//   B 弹层**完全在视口内**(顶/底/左/右四边都不越界),对**第一条和最后一条**各验一次。
//     ⚠️ 翻不翻转是实现细节,由纯逻辑 oracle(tests/test_due_picker.mjs)钉;
//        这里钉的是用户看得见的那条:**不管点哪一条,日历都得整个看得见**。
//   C 正在设的那条高亮、别的条目压暗 —— 用户拍板"一眼看清在给谁设"。
//   D 「清除」拿得掉(设错了能退回没有截止日)。
//   E Esc 关掉且**不写入**(半路反悔不该留下痕迹)。
//   F 日历上标出**同项目其它条目**的截止日 —— 用户要的"免得把三件活约到同一天"。
//   G 工作区变更栏换成同一个日历:原生 `input[type=date]` 不复存在。
//     "同一个东西一个交互"是用户的要求,不是我加的仪式 —— 所以钉住旧的那个真没了。
//
// 跑法:node tests/e2e/duedate_picker.e2e.mjs(自起 ds_web 于 8812)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8812;
const KEY = "翡翠湾-1801";
// 判据里出现的日期全部相对这一天算,免得跑到明年就红(DS_TODAY 冻结后端"今天")
const TODAY = "2026-07-28";
const OTHER_DUE = "2026-07-31"; // C3 已有的截止日 → F 段要它在日历上有点

const tmp = mkdtempSync(join(tmpdir(), "duepick-e2e-"));
const dsRoot = join(tmp, "ds");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });

// 12 条未办结:够把列表铺过一屏,B 段才有"最后一条贴着底边"可验。
const changes = [];
for (let n = 1; n <= 12; n++) {
  const due = n === 3 ? ` ⏳${OTHER_DUE}` : "";
  changes.push(`- [${n % 2 ? "待确认" : "进行中"}] C${n} ${TODAY} 【主卧】第 ${n} 条待办${due}`);
}
const projPath = join(dsRoot, "projects", `${KEY}.md`);
writeFileSync(projPath, `# ${KEY}

- 业主: [[王女士]]
- 阶段: 施工跟进

## 变更记录
${changes.join("\n")}

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

const fileHas = (s) => readFileSync(projPath, "utf-8").includes(s);

/** 弹层四边是否都在视口内(用户看得见的那条)。 */
const popInViewport = (page) =>
  page.evaluate(() => {
    const el = document.querySelector('[data-ui="due-pop"]');
    if (!el) return null;
    const b = el.getBoundingClientRect();
    return {
      ok: b.top >= 0 && b.left >= 0 &&
          b.bottom <= window.innerHeight && b.right <= window.innerWidth,
      box: { top: Math.round(b.top), left: Math.round(b.left),
             bottom: Math.round(b.bottom), right: Math.round(b.right) },
      vp: { w: window.innerWidth, h: window.innerHeight },
    };
  });

let browser = null;
try {
  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const rows = () => page.locator('.todo-page .todo-row');
  const trigger = (i) => rows().nth(i).locator('[data-ui="due-trigger"]');
  const pop = page.locator('[data-ui="due-pop"]');

  // ── A 待办页能设,而且真写进了档案 ──────────────────────────────────────────
  await step("A 待办页上设得了截止日,且刷新后还在", async () => {
    await page.goto(`${base}/#/todos`, { waitUntil: "domcontentloaded" });
    await rows().first().waitFor({ timeout: 15000 });
    check(await rows().count() >= 12, `前提:12 条未办结都在(实测 ${await rows().count()})`);

    await trigger(0).click();
    await pop.waitFor({ timeout: 8000 });
    // 点"今天"这一格 —— 日期是算出来的,不写死,换年换月不会红
    await page.locator(`[data-ui="due-cell"][data-date="${TODAY}"]`).click();
    await pop.waitFor({ state: "detached", timeout: 8000 });

    expect(fileHas(`⏳${TODAY}`), "档案里真的写上了截止日(不是只改了界面)");
    await page.reload({ waitUntil: "domcontentloaded" });
    await rows().first().waitFor({ timeout: 15000 });
    const txt = await rows().first().innerText();
    expect(txt.includes("截止"), `刷新后那一行还带着截止日(实测 ${JSON.stringify(txt)})`);
  });

  // ── B 不管点哪一条,日历都整个看得见 ───────────────────────────────────────
  await step("B 弹层完全在视口内(第一条 + 最后一条各验一次)", async () => {
    await page.goto(`${base}/#/todos`, { waitUntil: "domcontentloaded" });
    await rows().first().waitFor({ timeout: 15000 });

    await trigger(0).click();
    await pop.waitFor({ timeout: 8000 });
    const top = await popInViewport(page);
    check(top, "前提:第一条的弹层量得到");
    expect(top.ok, `第一条:弹层四边都在视口内(${JSON.stringify(top.box)} / 视口 ${JSON.stringify(top.vp)})`);
    await page.keyboard.press("Escape");
    await pop.waitFor({ state: "detached", timeout: 8000 });

    const last = (await rows().count()) - 1;
    await rows().nth(last).scrollIntoViewIfNeeded();
    await trigger(last).click();
    await pop.waitFor({ timeout: 8000 });
    const bot = await popInViewport(page);
    check(bot, "前提:最后一条的弹层量得到");
    expect(bot.ok, `最后一条:弹层四边都在视口内(${JSON.stringify(bot.box)} / 视口 ${JSON.stringify(bot.vp)})`);
    await page.keyboard.press("Escape");
  });

  // ── C 正在设的那条高亮,别的压暗 ───────────────────────────────────────────
  await step("C 正在设的那条高亮、其余压暗", async () => {
    await page.goto(`${base}/#/todos`, { waitUntil: "domcontentloaded" });
    await rows().first().waitFor({ timeout: 15000 });
    await trigger(1).click();
    await pop.waitFor({ timeout: 8000 });

    expect(await rows().nth(1).evaluate((el) => el.classList.contains("due-editing")),
      "被设的那一条挂上了 due-editing");
    const dim = await rows().nth(4).evaluate((el) => parseFloat(getComputedStyle(el).opacity));
    expect(dim < 1, `别的条目压暗了(实测 opacity=${dim})`);
    await page.keyboard.press("Escape");
    const back = await rows().nth(4).evaluate((el) => parseFloat(getComputedStyle(el).opacity));
    expect(back === 1, `关掉后压暗要撤销(实测 opacity=${back})`);
  });

  // ── D 清除 ────────────────────────────────────────────────────────────────
  await step("D「清除」拿得掉已设的截止日", async () => {
    await page.goto(`${base}/#/todos`, { waitUntil: "domcontentloaded" });
    await rows().first().waitFor({ timeout: 15000 });
    check(fileHas(`⏳${OTHER_DUE}`), "前提:C3 本来带着截止日");

    const c3 = page.locator('.todo-page .todo-row', { hasText: "第 3 条待办" }).first();
    await c3.locator('[data-ui="due-trigger"]').click();
    await pop.waitFor({ timeout: 8000 });
    await page.locator('[data-ui="due-clear"]').click();
    await pop.waitFor({ state: "detached", timeout: 8000 });
    expect(!fileHas(`⏳${OTHER_DUE}`), "档案里那条截止日没了");
  });

  // ── E Esc 半路反悔:不写入 ────────────────────────────────────────────────
  await step("E Esc 关掉不写入", async () => {
    await page.goto(`${base}/#/todos`, { waitUntil: "domcontentloaded" });
    await rows().first().waitFor({ timeout: 15000 });
    const before = readFileSync(projPath, "utf-8");
    const c5 = page.locator('.todo-page .todo-row', { hasText: "第 5 条待办" }).first();
    await c5.locator('[data-ui="due-trigger"]').click();
    await pop.waitFor({ timeout: 8000 });
    await page.keyboard.press("Escape");
    await pop.waitFor({ state: "detached", timeout: 8000 });
    expect(readFileSync(projPath, "utf-8") === before, "档案逐字节没动");
  });

  // ── F 日历上标出同项目其它条目的截止日 ────────────────────────────────────
  await step("F 日历标出同项目其它条目的截止日", async () => {
    // A 段给 C1 设了 TODAY;现在打开 C7 的日历,TODAY 那格该有点(那是"别人"的)
    check(fileHas(`⏳${TODAY}`), "前提:C1 带着 TODAY 这个截止日");
    await page.goto(`${base}/#/todos`, { waitUntil: "domcontentloaded" });
    await rows().first().waitFor({ timeout: 15000 });
    const c7 = page.locator('.todo-page .todo-row', { hasText: "第 7 条待办" }).first();
    await c7.locator('[data-ui="due-trigger"]').click();
    await pop.waitFor({ timeout: 8000 });
    const dots = await page.locator(`[data-ui="due-cell"][data-date="${TODAY}"] .due-dot`).count();
    expect(dots === 1, `${TODAY} 那格有"这天已经有事"的点(实测 ${dots} 个)`);
    await page.keyboard.press("Escape");
  });

  // ── G 工作区变更栏换成同一个日历 ──────────────────────────────────────────
  await step("G 工作区变更栏用同一个日历,原生 date 输入框没了", async () => {
    await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
    await page.locator(`.proj-list .proj-row:has-text("${KEY}")`).first().click();
    const chRow = page.locator('.change-row').first();
    await chRow.waitFor({ timeout: 15000 });
    await chRow.hover();
    await chRow.locator('[data-ui="change-due"]').click();
    await pop.waitFor({ timeout: 8000 });
    expect(await page.locator('.due-input[type="date"]').count() === 0,
      "原生 <input type=date> 已经不复存在(两处用的是同一个日历)");
    const inVp = await popInViewport(page);
    expect(inVp && inVp.ok, `工作区里弹层也不越界(${JSON.stringify(inVp && inVp.box)})`);
    await page.keyboard.press("Escape");
  });

  console.log(failures === 0 ? "\nDUEDATE-PICKER E2E: ALL PASS"
                             : `\nDUEDATE-PICKER E2E: ${failures} FAIL`);
} catch (e) {
  failures++;
  console.error(String(e));
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}
process.exit(failures === 0 ? 0 : 1);
