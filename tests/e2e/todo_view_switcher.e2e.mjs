// 待办页看法切换器的位置契约 e2e(真 chromium + 真 ds_web)。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// 用户 07-31 真机原话:「待办事项列表,按项目/按时间/按阶段到了屏幕最右上角,
// 之前是在我们这个中间最大的工作区的,为什么移动位置了」。
//
// 根因(已查实,非设计选择):`4cc4308`(0.41.0)为修 07-24 第二轮反馈
// 「右栏日历顶边比左边首卡高 49px」,把题头 .todo-head 提到 .todo-page 顶部占满整宽,
// 于是挂在题头最右端(靠 `.grow` 撑开)的 .seg 被一路甩到**整个视口**的右上角 ——
// 那里是右栏 TodoRail 的正上方,离用户实际在看的卡片最远。修 A 碰坏 B。
//
// ⚠️ 本判据的要害是**两件事同时成立**:切换器回到主区,而 07-24 那个齐平修复
// **不许被我改回去**。所以 C/D 两段是护栏(写这份判据时本来就是绿的),
// A/B 才是新事实(写这份判据时全红)—— 只让 A/B 变绿而把 C/D 弄红 = 没修好,是换了个坑。
//
// 覆盖:
//   A 切换器整体落在**主区水平范围内**(seg 右缘不越过 .todo-main 右缘)——
//     即不再骑在右栏头上。这是与「屏幕最右上角」互斥的那条断言。
//   B 切换器**紧挨副标题**(与「N 条未办结 · M 个项目」的水平间隙 ≤ 40px),
//     不是被一个撑满的弹簧推开几百 px。
//   C 【护栏】右栏日历顶边仍与左边首张待办卡顶边齐平(07-24 第二轮的修复不许回归)。
//   D 【护栏】待办页仍撑满整宽 + 右栏仍留对称呼吸位(同上,4cc4308 的另两条)。
//   E 【护栏】三个看法的文案与顺序不变(按项目 / 按时间 / 按阶段)。
//   F 【护栏】三个看法都还切得动(挪位置不许把 onClick 挪丢)。
//
// 跑法:node tests/e2e/todo_view_switcher.e2e.mjs(自起 ds_web 于 8818)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8818;
const TODAY = "2026-07-30";

const tmp = mkdtempSync(join(tmpdir(), "todoswitch-e2e-"));
const dsRoot = join(tmp, "ds");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });

// 夹具只需"有卡可看、右栏有日历"即可 —— 本判据量的是题头几何,不是分组逻辑。
// 给一条带截止日的,保证右栏日历与「需要今天跟进」都有内容、不落空态。
const PROJECTS = [
  { key: "01张宅-1101", stage: "施工跟进", texts: ["吊顶改平顶", "衣柜加到顶"] },
  { key: "02李宅-0808", stage: "平面方案", texts: ["主卧门改推拉"] },
];
for (const p of PROJECTS) {
  const lines = p.texts.map(
    (t, i) => `- [待确认] C${i + 1} 2026-07-28 【主卧】${t}${i === 0 ? ` ⏳${TODAY}` : ""}`,
  );
  writeFileSync(join(dsRoot, "projects", `${p.key}.md`), `# ${p.key}

- 业主: [[某先生]]
- 阶段: ${p.stage}

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

  const gotoTodo = async () => {
    await page.goto(`${base}/#/todos`, { waitUntil: "domcontentloaded" });
    await page.locator(".todo-head .seg").waitFor({ timeout: 15000 });
    await page.locator(".todo-card").first().waitFor({ timeout: 15000 });
  };

  // 几何一次量全:.seg 是 `display:flex; flex:none`(缩到内容宽),量它本身是安全的
  // —— 不量任何块级盒子(几何断言量块级盒子的坑见记忆 opendesign-workspace-health:
  // 块级盒子撑满一整行,加个 padding 都能让断言假红/假绿)。
  const geo = async () => page.evaluate(() => {
    const box = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { left: Math.round(r.left), right: Math.round(r.right), top: Math.round(r.top) };
    };
    return {
      vw: window.innerWidth,
      seg: box(".todo-head .seg"),
      sub: box(".todo-head .sub"),
      main: box(".todo-main"),
      pane: box(".todos-pane"),
      rail: box(".todo-rail"),
      cal: box(".rail-cal"),
      card: box(".todo-card"),
    };
  });

  // ── A 切换器回到主区(与「屏幕最右上角」互斥)────────────────────────────
  await step("A 切换器落在主区水平范围内,不骑在右栏头上", async () => {
    await gotoTodo();
    const g = await geo();
    expect(g.seg !== null && g.main !== null, "题头切换器与主区都在(选择器没漂)");
    expect(g.seg.right <= g.main.right + 2,
      `切换器右缘不越过主区右缘(seg ${g.seg.right} / 主区 ${g.main.right})`);
    expect(g.seg.left < g.rail.left,
      `切换器整体在右栏左边(seg 左缘 ${g.seg.left} / 右栏左缘 ${g.rail.left})`);
  });

  // ── B 切换器紧挨副标题 ───────────────────────────────────────────────────
  await step("B 切换器紧挨副标题,不被弹簧推开", async () => {
    await gotoTodo();
    const g = await geo();
    const gap = g.seg.left - g.sub.right;
    expect(gap >= 0 && gap <= 40,
      `切换器与副标题的水平间隙 0~40px(实测 ${gap}px)`);
  });

  // ── C 【护栏】齐平不回归 ─────────────────────────────────────────────────
  await step("C 【护栏】右栏日历顶边仍与左首卡顶边齐平", async () => {
    await gotoTodo();
    const g = await geo();
    expect(Math.abs(g.cal.top - g.card.top) <= 3,
      `日历顶边 = 首卡顶边(日历 ${g.cal.top} / 首卡 ${g.card.top})`);
  });

  // ── D 【护栏】整宽 + 右栏呼吸位不回归 ────────────────────────────────────
  await step("D 【护栏】待办页仍撑满整宽,右栏仍留对称呼吸位", async () => {
    await gotoTodo();
    const g = await geo();
    expect(g.vw - g.pane.right <= 2,
      `待办页撑满整宽(pane 距右缘 ${g.vw - g.pane.right}px)`);
    const gutter = g.vw - g.rail.right;
    expect(gutter >= 10 && gutter <= 60,
      `右栏距屏幕右缘 10~60px(实测 ${gutter}px)`);
  });

  // ── E 【护栏】三个看法的文案与顺序不变 ───────────────────────────────────
  await step("E 【护栏】切换器仍是「按项目 / 按时间 / 按阶段」三个、顺序不变", async () => {
    await gotoTodo();
    const opts = (await page.locator(".todo-head .seg .opt").allInnerTexts())
      .map((t) => t.replace(/\s+/g, ""));
    expect(JSON.stringify(opts) === JSON.stringify(["按项目", "按时间", "按阶段"]),
      `三个看法文案与顺序不变(实测 ${JSON.stringify(opts)})`);
  });

  // ── F 【护栏】三个看法都还切得动 ─────────────────────────────────────────
  await step("F 【护栏】挪位置没把 onClick 挪丢", async () => {
    await gotoTodo();
    const click = async (label) =>
      page.locator(".todo-head .seg .opt", { hasText: label }).click();

    await click("按阶段");
    await page.locator(".todo-page .stage-sect").first().waitFor({ timeout: 15000 });
    expect(await page.locator(".todo-cards.by-stage").count() === 1, "点「按阶段」切到阶段堆");

    await click("按时间");
    await page.locator(".todo-cards.by-time").waitFor({ timeout: 15000 });
    expect(await page.locator(".todo-cards.by-time").count() === 1, "点「按时间」切到时间批次");

    await click("按项目");
    await page.locator(".todo-cards.by-project").waitFor({ timeout: 15000 });
    expect(await page.locator(".todo-cards.by-project").count() === 1, "点「按项目」切得回去");
  });
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}

console.log(failures === 0 ? "\n全部通过" : `\n${failures} 条不通过`);
process.exit(failures === 0 ? 0 : 1);
