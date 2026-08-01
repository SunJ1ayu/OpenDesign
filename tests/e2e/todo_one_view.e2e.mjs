// 待办页收敛成**单一看法**后的契约 e2e(真 chromium + 真 ds_web)。
// track opendesign-todo-one-view。主 agent 亲写,执行腿逐字节 off-limits。
//
// 用户 08-01 原话:「待办事项的三个分类 按项目 按时间 按阶段 还是挺乱的,比如按时间之后
// 各个项目其实都是乱的 直接穿插在一起了……按阶段现在的每个阶段标题不太明显,根本第一眼
// 看不出来是什么阶段,反而旁边的十几天没动静更明显一些」。
// panel-explore 四腿全票主张砍掉切换器;方案见 tracks/opendesign-todo-one-view/design.md。
//
// ════════════════════════════════════════════════════════════════════════════
// **判据迁移账**(本项目规矩:改/删判据必须当场证明"不是放松",逐条指名)。
// 本单删掉了两份 e2e,它们判的功能是**被刻意移除的**,但其中的**护栏一条不许丢**:
//
//   tests/e2e/todo_view_switcher.e2e.mjs(已删)
//     A 切换器落在主区内            → 功能移除(切换器不存在了)。**替代**=本文件 A 段
//                                     反向断言"切换器确实不存在",比原来更强:
//                                     原断言只管它在哪,新断言管它在不在。
//     B 切换器紧挨副标题            → 同上,随切换器移除。
//     C 右栏日历顶边与首卡齐平      → **逐字carry over 到本文件 G 段**(07-24 修复护栏)
//     D 整宽 + 右栏对称呼吸位        → **逐字carry over 到本文件 H 段**(同上)
//     E 三个看法文案与顺序          → 功能移除。
//     F 三个看法都切得动            → 功能移除。
//
//   tests/e2e/todo_stage_view.e2e.mjs(已删)
//     A 有第三个看法「按阶段」      → 功能移除。
//     B 阶段堆里长项目卡            → 功能移除(阶段改为卡头标签,本文件 D 段判新形态)
//     C 堆序=后端词表序、未建档垫底 → **该逻辑(groupProjectsByStage)仍在左栏用着,
//                                     且 tests/e2e/side_stage_groups.e2e.mjs 覆盖同一条**
//                                     ⇒ 不是丢了,是本来就有第二个判据在盯。
//     D 堆头折叠状态刷新后还在      → 功能移除(没有堆头了)。折叠"不许是 useState/死键"
//                                     这条纪律仍由 side_stage_groups + todo_batches 覆盖。
//     E 一条都不丢                  → **carry over 到本文件 F 段**(改成单一看法下的同义断言)
//     F 「去项目」点得到            → **carry over 到本文件 I 段**
//
// 净变化:删掉的全部是"被移除功能"的断言;**每一条护栏都指名接住了**。
// 新增的是旧结构表达不出来的:两轨排序在真 DOM 里的顺序、阶段标签的字号层级、
// 徽标去底色+改文案。
// ════════════════════════════════════════════════════════════════════════════
//
// 覆盖:
//   A 看法切换器**不存在**(`.todo-head .seg` 一个都没有)。
//   B 硬轨在前:有截止日的条目整体排在无截止日的之前,且过期的最靠前。
//   C 软轨"最久在前":无截止日的条目按记录日期升序(**不是倒序**)。
//   D 阶段是卡头上的标签,且**字号不小于项目名**(修反层级)。
//   E 徽标改成「最近记录 N 天前」且**没有底色**(不再是全页最抢眼的东西)。
//   F 一条都不丢:页面上的待办行数 == 夹具条目总数。
//   G 【护栏】右栏日历顶边仍与左首卡顶边齐平(07-24 修复不许回归)。
//   H 【护栏】待办页仍撑满整宽 + 右栏仍留对称呼吸位(同上)。
//   I 【护栏】「去项目」仍点得到(既有能力不许退化)。
//
// 跑法:node tests/e2e/todo_one_view.e2e.mjs(自起 ds_web 于 8819)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8819;
const TODAY = "2026-07-30";

const tmp = mkdtempSync(join(tmpdir(), "todooneview-e2e-"));
const dsRoot = join(tmp, "ds");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });

// 夹具刻意造出两轨都非空的形态(真实档案目前硬轨恒空,那个形态由纯函数判据的
// 「真实形态」一组覆盖;这里要能量到两轨的相对位置,所以必须有 due)。
// 张宅:一条过期 + 一条未来 + 两条无 due(记录日期一新一老)
// 李宅:全部无 due —— 用来判"无 due 的卡整体排在有 due 的卡之后"
const FIXTURE = [
  {
    key: "01张宅-1101", stage: "施工跟进",
    // ⚠️ 行序是**故意排成"目标顺序的反面"**的:红检时发现原来的写法里
    // 「老意见」本来就在「新意见」前面(档案里 C1 在 C2 前),于是 C 段
    // **不排序也会绿** = 假绿。现在档案序 = 新→老、无 due→有 due,
    // 期望序 = 过期→未来→老→新,两者在每一维上都相反,不排序必红。
    rows: [
      "- [待确认] C1 2026-07-28 【客厅】新意见没截止日",       // 软轨,新
      "- [待确认] C2 2026-07-10 【主卧】老意见没截止日",       // 软轨,老
      "- [待确认] C3 2026-07-20 【厨房】未来到期 ⏳2026-08-20", // 硬轨,未来
      "- [待确认] C4 2026-07-22 【阳台】已经过期 ⏳2026-07-25", // 硬轨,过期
      "- [待确认] C5 2026-07-10 【书房】效果图整体调浅一档",   // 软轨,与 C2 同日=同一批
    ],
    // 助手起过名的批次(格式与 ds_common.BATCH_LINE_RE 同源):C2 与 C5 同属这一批
    batch: "- C2-C5 2026-07-10 效果图这轮改浅色",
  },
  {
    key: "02李宅-0808", stage: "平面方案",
    rows: [
      "- [待确认] C1 2026-07-15 【主卧】李宅没有任何截止日",
    ],
  },
];
for (const p of FIXTURE) {
  writeFileSync(join(dsRoot, "projects", `${p.key}.md`), `# ${p.key}

- 业主: [[某先生]]
- 阶段: ${p.stage}

${p.batch ? `## 批次\n${p.batch}\n` : ""}
## 变更记录
${p.rows.join("\n")}

## 沟通日志

---
最后更新: ${TODAY}
`);
}
writeFileSync(join(dsRoot, "config", "workspace.json"), JSON.stringify({ projects: {} }));
const TOTAL_ITEMS = FIXTURE.reduce((n, p) => n + p.rows.length, 0);

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
    await page.locator(".todo-card").first().waitFor({ timeout: 15000 });
  };

  // 张宅那张卡里,按渲染顺序取出每行的正文关键词
  const rowTexts = async (cardIdx = 0) => page.evaluate((i) => {
    const card = document.querySelectorAll(".todo-card")[i];
    if (!card) return [];
    return [...card.querySelectorAll(".todo-row")].map((r) => (r.textContent || "").replace(/\s+/g, ""));
  }, cardIdx);

  // ── A 切换器不存在 ───────────────────────────────────────────────────────
  await step("A 看法切换器已撤掉", async () => {
    await gotoTodo();
    expect(await page.locator(".todo-head .seg").count() === 0,
      "题头里没有 .seg 切换器");
    for (const label of ["按项目", "按时间", "按阶段"]) {
      expect(await page.locator(".todo-head", { hasText: label }).count() === 0,
        `题头里没有「${label}」这个按钮`);
    }
    // ⚠️ 这里原本还有一条「.by-time / .by-stage 容器不再渲染」——**红检时它是绿的**,
    // 因为默认看法本来就是 by-project,那两个容器**任何时候都只在切过去时才渲染**。
    // 它绿的原因与"分支删没删"无关 ⇒ 假绿,已删。
    // "死分支有没有真删掉"是**源码层**性质,DOM 判不了;由主 agent 闸③亲读 diff 负责。
  });

  // ── B 硬轨在前,过期最靠前 ───────────────────────────────────────────────
  await step("B 有截止日的整体在前,过期的最靠前", async () => {
    await gotoTodo();
    const rows = await rowTexts(0);
    expect(rows.length === 5, `张宅卡里 5 行(实测 ${rows.length})`);
    const idx = (kw) => rows.findIndex((t) => t.includes(kw));
    const iOverdue = idx("已经过期"), iFuture = idx("未来到期");
    const iOld = idx("老意见"), iNew = idx("新意见");
    expect(iOverdue === 0, `过期那条排第 1(实测第 ${iOverdue + 1})`);
    expect(iFuture === 1, `未来到期那条排第 2(实测第 ${iFuture + 1})`);
    expect(iOverdue < iOld && iFuture < iOld && iFuture < iNew,
      "两条有截止日的都排在无截止日的前面");
  });

  // ── C 软轨最久在前(不是倒序)─────────────────────────────────────────────
  await step("C 无截止日的按记录日期升序 —— 最久没动静的在前", async () => {
    await gotoTodo();
    const rows = await rowTexts(0);
    const iOld = rows.findIndex((t) => t.includes("老意见"));
    const iNew = rows.findIndex((t) => t.includes("新意见"));
    expect(iOld < iNew,
      `07-10 那条排在 07-28 那条前面(实测 老=${iOld} 新=${iNew});` +
      "软轨回答的是「什么被忘了」,不是「最近发生了什么」");
  });

  // ── D 阶段是卡头标签,且字号不小于项目名 ─────────────────────────────────
  await step("D 阶段降为卡头标签,层级不再是反的", async () => {
    await gotoTodo();
    const m = await page.evaluate(() => {
      const head = document.querySelector(".todo-card .card-head");
      if (!head) return null;
      const nm = head.querySelector(".nm");
      const stage = head.querySelector("[data-ui=card-stage]");
      const px = (el) => (el ? parseFloat(getComputedStyle(el).fontSize) : null);
      return {
        stageText: stage ? (stage.textContent || "").trim() : null,
        stageInHead: !!stage,
        nmPx: px(nm), stagePx: px(stage),
      };
    });
    expect(m && m.stageInHead, "阶段标签就在项目卡头里");
    expect(m && m.stageText === "施工跟进", `标签文案是阶段名(实测 ${m && m.stageText})`);
    // ⚠️ 锚:下面两条是数值比较,**元素不存在时 stagePx 是 null**,而 `null <= 14`
    // 在 JS 里为 true ⇒ 红检时那条是绿的 = 假绿。先要求它真的是个数,再比。
    const hasPx = !!m && typeof m.stagePx === "number" && Number.isFinite(m.stagePx);
    expect(hasPx, `阶段标签量得到字号(实测 ${m && m.stagePx})`);
    // 反层级的修复:原来阶段标题 13px 比它管着的项目名 14px 还小。现在阶段是子级,
    // 不要求它更大,但**不许比项目名大**(它是标签不是标题),同时不许小到看不见。
    expect(hasPx && m.stagePx <= m.nmPx,
      `阶段标签不比项目名大(阶段 ${m && m.stagePx}px / 项目名 ${m && m.nmPx}px)`);
    expect(hasPx && m.stagePx >= 11,
      `阶段标签字号 ≥11px,不许小到看不清(实测 ${m && m.stagePx}px)`);
  });

  // ── E 徽标改文案 + 去底色 ────────────────────────────────────────────────
  await step("E 「最近记录 N 天前」小字,没有底色", async () => {
    await gotoTodo();
    // ⚠️ 必须**限定到张宅那张卡**:卡序按紧急度排,张宅(有过期条目)排第一但没有徽标,
    // 裸 document.querySelector 会抓到李宅那个 15 天的徽标 —— 断言查的对象就不是它
    // 声称的对象了(收货时实测踩到,是我这条断言写错,不是实现错)。
    const b = await page.evaluate(() => {
      const cards = [...document.querySelectorAll(".todo-card")];
      const card = cards.find((c) => (c.textContent || "").includes("张宅"));
      const el = card && card.querySelector("[data-ui=card-recency]");
      if (!el) return { exists: false };
      const cs = getComputedStyle(el);
      return {
        exists: true,
        text: (el.textContent || "").replace(/\s+/g, ""),
        bg: cs.backgroundColor,
        px: parseFloat(cs.fontSize),
      };
    });
    // 李宅最新记录 07-15 ⇒ 15 天 ≥ 7 ⇒ 该出现,且必须是新文案、无底色
    const li = await page.evaluate(() => {
      const cards = [...document.querySelectorAll(".todo-card")];
      const card = cards.find((c) => (c.textContent || "").includes("李宅"));
      const el = card && card.querySelector("[data-ui=card-recency]");
      if (!el) return { exists: false };
      const cs = getComputedStyle(el);
      return { exists: true, text: (el.textContent || "").replace(/\s+/g, ""), bg: cs.backgroundColor };
    });
    expect(li.exists, "李宅(15 天没记录)有徽标");
    expect(li.exists && li.text.includes("最近记录"),
      `文案是「最近记录 N 天前」(实测 ${li.text})`);
    expect(li.exists && !li.text.includes("没动静"),
      "不再说「没动静」—— 那个词对应的是被证伪的档案 mtime 指标");
    expect(li.exists && /^(transparent|rgba\(0, 0, 0, 0\))$/.test(li.bg),
      `徽标没有底色(实测 ${li.bg})—— 它不该是全页最抢眼的东西`);
    // ⚠️ 阈值那条必须**锚在"机制已存在"之后**:红检时它单独跑是绿的,
    // 因为徽标压根还没做出来(不存在 = 也"没出现")= 假绿。
    // 现在先证明李宅那张确实长出了徽标,再断言张宅(2 天 < 阈值 7)那张没有。
    expect(li.exists && b.exists === false,
      `张宅最近记录才 2 天(< 阈值 ${7} 天),徽标不该出现` +
      `(实测 ${b.exists ? b.text : "不存在"});此断言以李宅徽标存在为前提`);
  });

  // ── J 批次小标题真的渲染出来 ─────────────────────────────────────────────
  // ⚠️ 这段是**收尾截图时补的**:原来批次小标题只有纯函数判据(batchCaption),
  // 渲染这一层没有任何断言盯着 —— 纯函数全绿而页面上一个字都不出现是完全可能的。
  // 本项目第 N 次同一教训:数字对、页面错。
  await step("J 助手起名的批次,在该批第一条上方显示一行小标题", async () => {
    await gotoTodo();
    const caps = await page.locator("[data-ui=batch-cap]").allInnerTexts();
    expect(caps.length === 1, `整页恰好一行批次小标题(实测 ${caps.length} 行)`);
    expect(caps[0] && caps[0].includes("效果图这轮改浅色"),
      `小标题文案是助手起的名(实测 ${JSON.stringify(caps[0])})`);
    // 位置:必须紧贴在**该批在渲染顺序里的第一条**之前,不是飘在卡顶或卡尾。
    // ⚠️ 这一批是 C2-C5,里面 C4 是过期条目 ⇒ 它在硬轨最前 ⇒ 小标题落在 C4 上方,
    // 不是档案里编号最小的 C2。(第一版断言按"编号最小"写,实测红 —— 我算错了,
    // 不是实现错;顺手把这条推理写进注释,免得日后又按直觉改回去。)
    const okPos = await page.evaluate(() => {
      const cap = document.querySelector("[data-ui=batch-cap]");
      const next = cap && cap.nextElementSibling;
      return !!next && next.classList.contains("todo-row")
        && (next.textContent || "").includes("已经过期");
    });
    expect(okPos, "小标题紧跟着的就是该批在渲染顺序里的第一条");
  });

  // ── F 一条都不丢 ─────────────────────────────────────────────────────────
  await step("F 一条待办都不丢", async () => {
    await gotoTodo();
    const n = await page.locator(".todo-row").count();
    expect(n === TOTAL_ITEMS, `页面上 ${TOTAL_ITEMS} 行待办(实测 ${n})`);
  });

  // ── G/H 护栏:07-24 那两条几何修复不许因本单回归 ──────────────────────────
  const geo = async () => page.evaluate(() => {
    const box = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { left: Math.round(r.left), right: Math.round(r.right), top: Math.round(r.top) };
    };
    return {
      vw: window.innerWidth,
      main: box(".todo-main"), pane: box(".todos-pane"),
      rail: box(".todo-rail"), cal: box(".rail-cal"), card: box(".todo-card"),
    };
  });

  await step("G 【护栏】右栏日历顶边仍与左首卡顶边齐平", async () => {
    await gotoTodo();
    const g = await geo();
    expect(Math.abs(g.cal.top - g.card.top) <= 3,
      `日历顶边 = 首卡顶边(日历 ${g.cal.top} / 首卡 ${g.card.top})`);
  });

  await step("H 【护栏】待办页仍撑满整宽,右栏仍留对称呼吸位", async () => {
    await gotoTodo();
    const g = await geo();
    expect(g.vw - g.pane.right <= 2,
      `待办页撑满整宽(pane 距右缘 ${g.vw - g.pane.right}px)`);
    const gutter = g.vw - g.rail.right;
    expect(gutter >= 10 && gutter <= 60, `右栏距屏幕右缘 10~60px(实测 ${gutter}px)`);
  });

  await step("I 【护栏】「去项目」仍点得到", async () => {
    await gotoTodo();
    const btn = page.locator(".todo-card .card-head", { hasText: "张宅" })
      .locator("button", { hasText: "去项目" }).first();
    expect(await btn.count() > 0, "卡头有「去项目」按钮");
    await btn.click();
    await page.locator(".ws-pane").first().waitFor({ timeout: 15000 });
    expect(await page.locator(".ws-pane").count() > 0, "点了真的进到项目工作区");
  });
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}

console.log(failures === 0 ? "\n全部通过" : `\n${failures} 条不通过`);
process.exit(failures === 0 ? 0 : 1);
