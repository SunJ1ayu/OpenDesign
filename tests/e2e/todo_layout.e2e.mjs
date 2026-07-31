// track opendesign-todo-layout e2e:待办页布局 + 折叠一致性的行为面契约
// (真 chromium + 真 ds_web,DS_TODAY 冻结今天;参照 todo_batch_space.e2e.mjs 的夹具写法)。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// 覆盖:
//   I.7  「按项目」竖向单列(真机反馈 2026-07-24 从多列瀑布改回)+ 无 max-width 限宽/不居中 + 卡序 + 闲置项目占位卡;
//   I.8  「按时间」保持单列 + 去限宽;
//   #1/#2 折叠:两视图**同一个**控件(.grp-toggle[data-ui=group-toggle]),chev 字号与
//         cursor 一致;项目卡可整卡折叠;可点区域不吞掉「去项目 →」/「全选本组」;
//   回归  多列下 StatusPicker 菜单能开可见 + 批量勾选仍出浮栏。
//
// 跑法:node tests/e2e/todo_layout.e2e.mjs(自起 ds_web 于 8798)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8798;
const TODAY = "2026-07-20"; // DS_TODAY 冻结,超期天数才可断言

// ── 夹具 ────────────────────────────────────────────────────────────────────
// 卡序期望(orderProjectCards):超期(天数降序)在前 → 其余按未办结数降序
//   翡翠湾-1801   2 条  最后更新 07-01 → 超期 19 天  ①
//   云山名城-2302 3 条  最后更新 07-05 → 超期 15 天  ②
//   滨江一号-0905 4 条  最后更新 07-20 → 不超期      ③(条数最多)
//   万科城-1204   2 条  最后更新 07-19 → 不超期      ④
//   海棠居-0301   0 条  最后更新 07-18 → 不超期      → 闲置,进占位卡
//   松涛苑-0702   0 条  最后更新 06-01 → 超期 49 天  → 「⛑ 天没动静」独立行,**不**进占位卡
//   老宅翻新项目夹        工作区里未建档的文件夹      → **不**进占位卡(还不是项目)
const tmp = mkdtempSync(join(tmpdir(), "tlayout-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");
const P1 = "翡翠湾-1801";
const P2 = "云山名城-2302";
const P3 = "滨江一号-0905";
const P4 = "万科城-1204";
const P5 = "海棠居-0301";
const P6 = "松涛苑-0702";
const UNREG = "老宅翻新项目夹";
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });

const md = (name, changes, lastUpd) => `# ${name}

- 业主: [[张三]]
- 阶段: 施工跟进

## 变更记录
${changes}

## 沟通日志

---
最后更新: ${lastUpd}
`;
const open = (n, date, space, text) => `- [待确认] C${n} ${date} 【${space}】${text}`;

writeFileSync(join(dsRoot, "projects", `${P1}.md`), md(P1, [
  open(1, "2026-06-28", "玄关", "玄关柜改高"),
  open(2, "2026-07-01", "客厅", "沙发靠墙摆"),
].join("\n"), "2026-07-01"));

writeFileSync(join(dsRoot, "projects", `${P2}.md`), md(P2, [
  open(1, "2026-07-03", "书房", "整墙书柜改半墙"),
  open(2, "2026-07-04", "儿童房", "上下床换成榻榻米"),
  open(3, "2026-07-05", "餐厅", "餐边柜嵌入冰箱"),
].join("\n"), "2026-07-05"));

writeFileSync(join(dsRoot, "projects", `${P3}.md`), md(P3, [
  open(1, "2026-07-18", "全屋", "开关面板点位复核"),
  open(2, "2026-07-19", "主卫", "浴室柜面石材选样"),
  open(3, "2026-07-20", "客厅", "窗帘盒预留尺寸确认"),
  open(4, "2026-07-20", "厨房", "橱柜台面加挡水"),
].join("\n"), "2026-07-20"));

writeFileSync(join(dsRoot, "projects", `${P4}.md`), md(P4, [
  open(1, "2026-07-19", "卧室", "飘窗台改石材"),
  open(2, "2026-07-19", "阳台", "阳台柜加拖把池"),
].join("\n"), "2026-07-19"));

writeFileSync(join(dsRoot, "projects", `${P5}.md`), md(P5,
  "- [已完成] C1 2026-07-18 【客厅】电视墙尺寸重新放样", "2026-07-18"));

writeFileSync(join(dsRoot, "projects", `${P6}.md`), md(P6,
  "- [已关闭] C1 2026-05-30 【厨房】水槽换台下盆", "2026-06-01"));

mkdirSync(join(ws, UNREG), { recursive: true });
writeFileSync(join(dsRoot, "config", "workspace.json"),
  JSON.stringify({ root: ws, projectsDir: ".", projects: {} }));

// ── 起 ds_web ───────────────────────────────────────────────────────────────
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
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(base, { waitUntil: "domcontentloaded" });
  await page.locator('.side-row:has-text("待办事项")').first().click();
  await page.locator(".todo-card").first().waitFor({ timeout: 10000 });

  // ── I.7 竖向单列 + 去限宽(真机反馈 2026-07-24:多列瀑布看着乱,改回竖排)──────
  const cards = page.locator(".todo-cards");
  check(await cards.evaluate((el) => el.classList.contains("by-project")),
    "「按项目」容器带 .by-project 布局 class");
  // 单列不变量:所有顶层卡共享同一左边界 → 只有 1 个不同的 left = 单列。
  // (CSSOM 的 columnCount/flex 都不能可靠反映真实用量,收货踩过,一律量真实左边界。)
  const colCount = async () => cards.evaluate((el) =>
    new Set([...el.children].map((c) => Math.round(c.getBoundingClientRect().left))).size);
  const flex = await cards.evaluate((el) => {
    const cs = getComputedStyle(el);
    return { display: cs.display, dir: cs.flexDirection };
  });
  check(flex.display === "flex" && flex.dir === "column",
    `「按项目」竖向 flex 单列(实测 ${flex.display}/${flex.dir})`);
  check(await colCount() === 1, `「按项目」@1440 单列(实测 ${await colCount()} 列)`);
  // 无 max-width 上限 + 不居中(左右 margin 非 auto)+ 填满可用宽度。
  const projBox = await cards.evaluate((el) => {
    const cs = getComputedStyle(el);
    const parent = el.parentElement;
    return {
      maxWidth: cs.maxWidth, ml: cs.marginLeft, mr: cs.marginRight,
      w: el.clientWidth, parentW: parent ? parent.clientWidth : -1,
    };
  });
  check(projBox.maxWidth === "none", `「按项目」无 max-width 上限(实测 ${projBox.maxWidth})`);
  check(parseFloat(projBox.ml) === 0 && parseFloat(projBox.mr) === 0,
    `「按项目」不居中(margin ${projBox.ml}/${projBox.mr})`);
  check(projBox.w >= projBox.parentW - 1,
    `「按项目」填满可用宽度(${projBox.w}px / 容器 ${projBox.parentW}px)`);
  const gap = await cards.evaluate((el) =>
    parseFloat(getComputedStyle(el).rowGap) || parseFloat(getComputedStyle(el).gap) || 0);
  check(gap >= 12, `卡间距已设(gap=${gap}px)`);

  // 关键不变量:**任何视口下都保持单列**,不再随视口宽度铺成多列(防多列复辟的回归防线)。
  for (const vw of [1280, 1700, 2000, 2560]) {
    await page.setViewportSize({ width: vw, height: 900 });
    await page.waitForTimeout(150);
    check(await colCount() === 1, `@${vw} 仍单列(实测 ${await colCount()} 列)`);
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(150);

  // ── I.7 卡序:超期(天数降序)在前,其余未办结数降序 ────────────────────
  const order = await page.locator(".todo-card .card-head .nm").allInnerTexts();
  check(JSON.stringify(order) === JSON.stringify([P1, P2, P3, P4]),
    `卡序 = 超期19天 → 超期15天 → 4条 → 2条(实测 ${JSON.stringify(order)})`);
  const firstBadge = await page.locator(".todo-card").first().locator(".stale-badge").innerText();
  check(firstBadge.includes("19"), `首卡带 19 天超期标(实测「${firstBadge}」)`);

  // ── I.7 闲置项目占位卡 ──────────────────────────────────────────────────
  const idle = page.locator('[data-ui="todo-idle-card"]');
  check(await idle.count() === 1, "「按项目」有且只有一张闲置占位卡");
  const idleTxt = await idle.innerText();
  check(idleTxt.includes(P5) && idleTxt.includes("没有未办结事项"),
    `占位卡列出闲置项目(实测「${idleTxt}」)`);
  check(!idleTxt.includes(P6), "占位卡不含超期无卡项目(已由独立行报过,不重复说)");
  check(!idleTxt.includes(P1) && !idleTxt.includes(P3), "占位卡不含有卡项目");
  check(!idleTxt.includes(UNREG), "占位卡不含未建档文件夹(还不是项目)");
  check(await idle.evaluate((el) => el.closest(".todo-cards") !== null),
    "占位卡在单列容器内(参与竖排)");
  const lastCard = page.locator(".todo-cards > *").last();
  check(await lastCard.evaluate((el) => el.matches('[data-ui="todo-idle-card"]')),
    "占位卡排在列表末尾");
  const restTxt = (await page.locator(".todo-rest").allInnerTexts()).join(" | ");
  check(restTxt.includes(P6) && restTxt.includes("天没动静"),
    `超期无卡项目仍有「⛑ N 天没动静」独立行(实测「${restTxt}」)`);
  check(!restTxt.includes("其余"), "旧的「其余 N 个项目没有未办结事项」行已被占位卡取代");

  // ── 折叠:项目卡整卡折叠 ────────────────────────────────────────────────
  const card1 = page.locator(".todo-card").first();
  const toggle1 = card1.locator('[data-ui="group-toggle"]');
  check(await toggle1.count() === 1, "项目卡头有折叠控件");
  check(await card1.locator(".todo-row").count() === 2, "项目卡默认展开(首卡 2 行)");
  check(await toggle1.getAttribute("aria-expanded") === "true", "展开态 aria-expanded=true");
  await toggle1.click();
  await page.waitForFunction(
    () => document.querySelectorAll(".todo-card")[0].querySelectorAll(".todo-row").length === 0,
    { timeout: 5000 },
  );
  check(await card1.locator('[data-ui="todo-space-sect"]').count() === 0,
    "折叠后卡内空间小节也一并收起");
  check(await toggle1.getAttribute("aria-expanded") === "false", "收起态 aria-expanded=false");
  check(await card1.locator(".card-head .nm").innerText() === P1, "折叠后卡头仍在(只收正文)");
  await toggle1.click();
  await page.waitForFunction(
    () => document.querySelectorAll(".todo-card")[0].querySelectorAll(".todo-row").length === 2,
    { timeout: 5000 },
  );
  check(true, "再点一次恢复展开");

  // ── 折叠控件不吞掉同头部的其它按钮(嵌套 button 非法 + 语义) ───────────
  // 按文案选,不按 class 名(2026-08-01 `.go-link` 已并入共享 `.link-act`)。
  check(await card1.locator('.card-head button:has-text("去项目")').count() === 1,
        "卡头「去项目 →」仍在");
  check(await card1.locator('.card-head button:has-text("去项目")')
    .evaluate((el) => el.closest('[data-ui="group-toggle"]') === null),
    "「去项目 →」不在折叠控件内部(不被吞)");
  check(await card1.locator('[data-ui="group-toggle"] button').count() === 0,
    "折叠控件内部无嵌套 button");

  // ── 可见性(反馈 #1):可点区域横跨整行 + hover 底色 + cursor ────────────
  const headW = await card1.locator(".card-head").evaluate((el) => el.clientWidth);
  const togW = await toggle1.evaluate((el) => el.clientWidth);
  check(togW > headW * 0.5,
    `折叠可点区横跨大半行(触发区 ${togW}px / 行 ${headW}px)——不是只有 9px chev`);
  const cur = await toggle1.evaluate((el) => getComputedStyle(el).cursor);
  check(cur === "pointer", `折叠控件 cursor:pointer(实测 ${cur})`);
  // 主 agent 收货修正:原写法在两次 click 之后直接采样,鼠标还停在按钮上、且 transition
  // 在途(实测采到 alpha=0.97 的半程色),`bgHover !== bgBefore` 因此是**空断言**——它比的
  // 是"半程 vs 全程",没证明静止态与 hover 态不同。改成:先把鼠标挪走并等 transition 落定
  // 采静止态,再 hover 等落定采 hover 态,并直接钉住"静止=完全透明、hover=真上色"。
  const alphaOf = (c) => {
    const m = c.match(/rgba?\(([^)]+)\)/);
    const parts = m ? m[1].split(",").map((x) => parseFloat(x)) : [];
    return parts.length === 4 ? parts[3] : 1;
  };
  await page.mouse.move(5, 5);
  await page.waitForTimeout(400);
  const bgRest = await toggle1.evaluate((el) => getComputedStyle(el).backgroundColor);
  await toggle1.hover();
  await page.waitForTimeout(400);
  const bgHover = await toggle1.evaluate((el) => getComputedStyle(el).backgroundColor);
  check(alphaOf(bgRest) === 0, `静止态无底色(实测 ${bgRest})`);
  check(alphaOf(bgHover) > 0.9 && bgHover !== bgRest,
    `hover 态真上色(${bgRest} → ${bgHover})`);
  const chevSizeProj = await toggle1.locator(".chev")
    .evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
  check(chevSizeProj >= 11, `chev 已放大到 ≥11px(实测 ${chevSizeProj}px)`);

  // ── 回归:StatusPicker 菜单能开且可见 ───────────────────────────────────
  await card1.locator(".todo-row").first().locator(".st-btn").click();
  const menuItem = page.locator(".st-menu-item").first();
  await menuItem.waitFor({ state: "visible", timeout: 5000 });
  const box = await menuItem.boundingBox();
  check(box !== null && box.height > 0 && box.width > 0,
    "状态菜单可见");
  await page.keyboard.press("Escape"); // StatusPicker 自带 Escape 关闭(StatusPicker.tsx:29)
  await page.waitForFunction(
    () => document.querySelectorAll(".st-menu-item").length === 0, { timeout: 5000 },
  );

  // ── 回归:批量勾选仍出浮栏 ───────────────────────────────────────────────
  const rows = card1.locator(".todo-row");
  await rows.nth(0).locator('[data-ui="todo-select"]').check();
  await rows.nth(1).locator('[data-ui="todo-select"]').check();
  const bar = page.locator('[data-ui="todo-batch-bar"]');
  await bar.waitFor({ timeout: 5000 });
  check((await bar.innerText()).includes("已选 2 条"), "批量选择仍工作(已选 2 条)");
  await page.locator(".todo-batch-bar .batch-cancel").click();
  await page.waitForFunction(
    () => !document.querySelector('[data-ui="todo-batch-bar"]'), { timeout: 5000 },
  );

  // ── I.8「按时间」:单列 + 去限宽 + 无占位卡 ─────────────────────────────
  await page.locator('.todo-head .opt:has-text("按时间")').click();
  await page.locator(".batch-head").first().waitFor({ timeout: 5000 });
  const timeCards = page.locator(".todo-cards");
  check(await timeCards.evaluate((el) => el.classList.contains("by-time")),
    "「按时间」容器带 .by-time 布局 class");
  const ccTime = await timeCards.evaluate((el) => getComputedStyle(el).columnCount);
  check(ccTime === "auto" || ccTime === "1",
    `「按时间」保持单列(column-count=${ccTime})`);
  const boxTime = await timeCards.evaluate((el) => {
    const cs = getComputedStyle(el);
    return {
      maxWidth: cs.maxWidth, ml: cs.marginLeft, mr: cs.marginRight,
      w: el.clientWidth, parentW: el.parentElement ? el.parentElement.clientWidth : -1,
    };
  });
  check(boxTime.maxWidth === "none", `「按时间」无 max-width 上限(实测 ${boxTime.maxWidth})`);
  check(parseFloat(boxTime.ml) === 0 && parseFloat(boxTime.mr) === 0,
    `「按时间」不居中(margin ${boxTime.ml}/${boxTime.mr})`);
  check(boxTime.w >= boxTime.parentW - 1,
    `「按时间」填满可用宽度(${boxTime.w}px / 容器 ${boxTime.parentW}px)`);
  check(await page.locator('[data-ui="todo-idle-card"]').count() === 0,
    "「按时间」视图不出现闲置占位卡(项目维度摘要,时间轴里没位置)");

  // ── 一致性硬约束:两视图同一个折叠控件 ───────────────────────────────────
  const batchToggle = page.locator('.batch-head [data-ui="group-toggle"]').first();
  check(await batchToggle.count() === 1, "日期批次头用的是同一个折叠控件");
  check(await batchToggle.evaluate((el) => el.classList.contains("grp-toggle")),
    "日期批次折叠控件带 .grp-toggle");
  const chevSizeTime = await batchToggle.locator(".chev")
    .evaluate((el) => parseFloat(getComputedStyle(el).fontSize));
  check(chevSizeTime === chevSizeProj,
    `两视图 chev 字号一致(按项目 ${chevSizeProj}px / 按时间 ${chevSizeTime}px)`);
  const curTime = await batchToggle.evaluate((el) => getComputedStyle(el).cursor);
  check(curTime === cur, `两视图 cursor 一致(${cur} / ${curTime})`);
  const headWT = await page.locator(".batch-head").first().evaluate((el) => el.clientWidth);
  const togWT = await batchToggle.evaluate((el) => el.clientWidth);
  check(togWT > headWT * 0.5,
    `日期批次可点区同样横跨大半行(触发区 ${togWT}px / 行 ${headWT}px)`);
  check(await page.locator('.batch-head [data-ui="todo-select-group"]')
    .first().evaluate((el) => el.closest('[data-ui="group-toggle"]') === null),
    "「全选本组」不在折叠控件内部(不被吞)");

  // ── 折叠行为在「按时间」仍工作(最新一批默认展开 → 点掉) ────────────────
  const beforeRows = await page.locator(".batch-sect").first().locator(".todo-row").count();
  check(beforeRows > 0, "最新日期批次默认展开");
  await batchToggle.click();
  await page.waitForFunction(
    () => document.querySelector(".batch-sect").querySelectorAll(".todo-row").length === 0,
    { timeout: 5000 },
  );
  check(true, "日期批次折叠仍工作");
} catch (e) {
  failures++;
  console.error(String(e));
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}
console.log(failures === 0 ? "TODO-LAYOUT E2E: ALL PASS" : `TODO-LAYOUT E2E: ${failures} FAIL`);
process.exit(failures === 0 ? 0 : 1);
