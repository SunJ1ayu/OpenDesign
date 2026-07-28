// track opendesign-workspace-health 真机反馈 follow-ups(2026-07-27 夜口述)e2e:
// 真 chromium + 真 ds_web(不需要 gateway —— 两条都不走聊天链路)。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// 覆盖两条:
//   #2 收起「项目助手」后前端观感 —— 用户截图实证:`.chatcol.collapsed` 只有 36px,
//      而收件箱卡 / 体检卡仍按原尺寸渲染在里面,被压成**一字一行的竖排**并溢出到
//      视口右缘之外(截图最右侧被切掉的「收/件/箱」「工/作/区/文/件/夹」)。
//      ⚠️ 2026-07-28 体检卡按用户要求挪进了「设置」(判据见 settings_fvis.e2e.mjs),
//      所以本文件改用**收件箱卡**钉同一组不变量 —— 断言的对象换了,
//      **要守的性质一个没减**:竖条里的东西不许被压扁、不许越界、不许被卸载。
//      断言打在**几何**上(元素右边界 / 文档横向溢出),不断言"某个 class 在不在"——
//      史料(07-24)`columnCount==="3"` 数字全绿而正文被压成竖排,教训 = 断人眼看到的位置。
//   #3 图墙没有回到项目工作区的入口 —— 进得去出不来。注意与既有 `.g-back`(子相册
//      返回封面墙)是**两个不同层级**的返回,判据要能区分,不许一个顶替另一个。
//
// 跑法:node tests/e2e/ws_collapse_back.e2e.mjs(自起 ds_web 于 8803)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { deflateSync } from "node:zlib";
import { launchBrowser, check, expandInbox } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8803;
const KEY = "翡翠湾-1801";
const PROJ_REL = "20260701 王女士 翡翠湾 3#1801"; // 项目**摊在工作区根**:体检卡只在这种形态下适用

// 最小 PNG(stdlib zlib):图墙要有真图才有 .g-cell 可点。
function png(w, h) {
  const crcTable = [...Array(256)].map((_, n) => {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    return c >>> 0;
  });
  const crc = (buf) => {
    let c = 0xffffffff;
    for (const b of buf) c = crcTable[(c ^ b) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
  const chunk = (type, data) => {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length);
    const td = Buffer.concat([Buffer.from(type, "ascii"), data]);
    const cr = Buffer.alloc(4);
    cr.writeUInt32BE(crc(td));
    return Buffer.concat([len, td, cr]);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0);
  ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8;
  ihdr[9] = 2;
  const raw = Buffer.concat(
    [...Array(h)].map(() => Buffer.concat([Buffer.from([0]), Buffer.alloc(w * 3, 0x99)])),
  );
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

const tmp = mkdtempSync(join(tmpdir(), "wscb-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");
const projDir = join(ws, PROJ_REL);
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
// 收件箱(空箱也渲染一行常驻卡)+ 一个会被"猜"成结构目录的共享夹 → 体检卡有行可列。
// 两张卡都要在场:用户截图里溢出的正是这两张。
mkdirSync(join(ws, "00-收件箱"), { recursive: true });
// 收件箱里放一张真图:空箱只渲染一行摘要、没有可展开区,钉不住"收起只是隐藏、没卸载"
writeFileSync(join(ws, "00-收件箱", "业主发来的参考图.png"), png(400, 300));
mkdirSync(join(ws, "03-共享资源"), { recursive: true });
for (const n of [1, 2, 3]) {
  const p = join(projDir, "05-3DMAX", "客厅", `${KEY} 客厅 (${n}).png`);
  mkdirSync(dirname(p), { recursive: true });
  writeFileSync(p, png(400, 300));
}
writeFileSync(join(dsRoot, "projects", `${KEY}.md`), `# ${KEY}

- 业主: [[王女士]]
- 阶段: 施工跟进

## 变更记录

## 沟通日志

---
最后更新: 2026-07-28
`);
writeFileSync(
  join(dsRoot, "config", "workspace.json"),
  // projectsDir "." 是体检卡「适用」的前提(项目摊在工作区根 = 才有被误藏的风险);
  // 不写它 projects_root 找不到候选目录 → applicable=false → 整卡不渲染 = 这一段白测。
  JSON.stringify({ root: ws, projectsDir: ".", projects: { [KEY]: PROJ_REL } }),
);

const srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
  env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT) },
  stdio: ["ignore", "inherit", "inherit"],
});
const base = `http://127.0.0.1:${PORT}`;
for (let i = 0; ; i++) {
  try { await fetch(`${base}/api/health`); break; }
  catch { if (i > 50) throw new Error("ds_web 起不来"); await new Promise((r) => setTimeout(r, 200)); }
}

// 分段隔离(还既有工具债的一部分:全仓 e2e 共用的单 catch = 首个失败即跳过后面所有断言,
// 一次只看得见一个问题)。两层:
//   step()   —— 每段自己 catch,一段炸了不影响别段;
//   expect() —— **纯断言不抛**,记账后继续往下量,一轮把这一段所有坏掉的面报全。
//               继续下去会失去意义的**前提**仍用 check()(抛),别把两者混用。
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

/** 元素相对视口的右边界(不可见/不存在 → null)。 */
const rightEdge = (page, sel) =>
  page.evaluate((s) => {
    const el = document.querySelector(s);
    if (!el) return null;
    const b = el.getBoundingClientRect();
    return b.width === 0 && b.height === 0 ? null : Math.round(b.right);
  }, sel);

let browser = null;
try {
  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // ── #2 收起项目助手 ────────────────────────────────────────────────────────
  await step("#2 收起「项目助手」后不溢出、不留竖排残片", async () => {
    await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
    await page.locator(".chatcol").waitFor({ timeout: 15000 });
    // 卡片要真的在场,否则这一段测了个寂寞(假绿的经典形态)
    await page.locator(".inbox-card").waitFor({ timeout: 15000 });
    check(await page.locator(".inbox-card").isVisible(), "前提:展开态收件箱卡可见");
    // 体检卡已挪进设置,不该再出现在这一列(挪走要挪干净)
    expect(await page.locator('[data-ui="folder-visibility"]').count() === 0,
      "体检卡不在聊天列里(已挪进设置)");

    // 收件箱卡先展开:后面要验"收起整列只是藏起来、没把卡的状态毁掉"
    await expandInbox(page);
    await page.locator('[data-ui="inbox-expanded"]').waitFor({ timeout: 5000 });
    const expandedInnerH = await page.evaluate(() =>
      document.querySelector(".inbox-card").getBoundingClientRect().height);

    await page.locator('.chatcol-head .icon-btn[title="收起"]').click();
    await page.locator(".chatcol.collapsed").waitFor({ timeout: 5000 });

    const w = await page.evaluate(() =>
      Math.round(document.querySelector(".chatcol.collapsed").getBoundingClientRect().width));
    expect(w <= 40, `收起后聊天列收成竖条(实测 ${w}px)`);

    // ★ 本段红线一:整个文档不许出现横向溢出。
    //   坏实现下 36px 列里的卡片按 min-content 撑开、顶出视口右缘 —— 用户截图现场。
    const over = await page.evaluate(() => {
      const de = document.documentElement;
      return { scroll: de.scrollWidth, client: de.clientWidth };
    });
    expect(over.scroll <= over.client + 1,
      `收起后无横向溢出(scrollWidth ${over.scroll} ≤ clientWidth ${over.client})`);

    // ★ 红线二:竖条里**任何**可见后代都不许越过视口右缘。
    //   只查 scrollWidth 不够 —— 溢出被祖先裁掉时 scrollWidth 可以是干净的,
    //   而用户看到的仍是半截字(截图里那两片就是被视口切掉的)。
    const spill = await page.evaluate(() => {
      const vw = window.innerWidth;
      const out = [];
      for (const el of document.querySelectorAll(".chatcol.collapsed *")) {
        const b = el.getBoundingClientRect();
        if (b.width === 0 && b.height === 0) continue;
        if (b.right > vw + 1) out.push(`${el.className || el.tagName}@${Math.round(b.right)}`);
      }
      return out;
    });
    expect(spill.length === 0, `竖条内无越界元素(越界:${spill.join(", ") || "无"})`);

    // ★ 红线三:被压扁的卡片不许留在画面上。36px 宽里放不下一张卡,
    //   "还渲染着"和"看得过去"在这个宽度上不可兼得 —— 收起时它们必须让位。
    expect(!(await page.locator(".inbox-card").isVisible()),
      "收起态:收件箱卡不可见(不再被压成竖排)");

    // 展开回去:两张卡回来,且**体检卡仍是展开态** = 只是 CSS 隐藏、没有卸载重建
    // (keep-mounted 是全仓红线,卸载 = 用户刚点开的东西被吞掉)。
    await page.locator('.chat-rail .icon-btn').click();
    await page.locator(".chatcol:not(.collapsed)").waitFor({ timeout: 5000 });
    expect(await page.locator(".inbox-card").isVisible(), "展开回来:收件箱卡回到画面");
    expect(await page.locator('[data-ui="inbox-expanded"]').count() > 0,
      "展开回来:收件箱卡仍是展开态 = 只是 CSS 隐藏、没有卸载重建");
    const backInnerH = await page.evaluate(() =>
      document.querySelector(".inbox-card").getBoundingClientRect().height);
    expect(Math.abs(backInnerH - expandedInnerH) <= 2,
      `展开回来:收件箱卡高度分毫不差(期望 ≈${expandedInnerH}px,实测 ${backInnerH}px)`);
  });

  // ── #3 图墙回到项目工作区 ─────────────────────────────────────────────────
  await step("#3 图墙有回到项目工作区的入口", async () => {
    await page.goto(`${base}/#/gallery`, { waitUntil: "domcontentloaded" });
    await page.locator(".g-wall .g-cell").first().waitFor({ timeout: 15000 });

    const back = page.locator('[data-ui="gallery-back-ws"]');
    // 前提用 check(抛):按钮压根不存在时,后面的点击只会白等一个 30s 超时
    check(await back.count() > 0, "图墙上有返回工作区的按钮");
    expect(await back.first().isVisible(), "返回工作区按钮可见(不是藏在别的层里)");

    await back.first().click();
    await page.waitForFunction(() => location.hash === "#/workspace", { timeout: 5000 });
    expect(await page.locator(".ws-pane:not(.route-hidden)").isVisible(),
      "点了就回到项目工作区(ws-pane 现形)");
    expect(await page.locator(".chatcol").isVisible(), "回来的是完整工作区三列,不是空壳");
  });

  await step("#3b 子相册里两级返回不混淆", async () => {
    await page.goto(`${base}/#/gallery`, { waitUntil: "domcontentloaded" });
    await page.locator(".g-wall .g-cell").first().waitFor({ timeout: 15000 });
    await page.locator(".g-wall .g-cell").first().click();
    await page.locator(".g-back").waitFor({ timeout: 10000 });

    // 两个返回同时在场,且**不是同一个元素**:一个回封面墙,一个回工作区。
    const wsBack = page.locator('[data-ui="gallery-back-ws"]');
    check(await wsBack.count() > 0, "子相册里仍有返回工作区的按钮");
    const same = await page.evaluate(() => {
      const a = document.querySelector('[data-ui="gallery-back-ws"]');
      const b = document.querySelector(".g-back");
      return !!a && !!b && (a === b || a.contains(b) || b.contains(a));
    });
    expect(!same, "两级返回是两个独立控件(不是一个顶替另一个)");

    // 册内点返回工作区 = 直接回工作区,不是先退回封面墙(用户要的是出去,不是退一步)
    await wsBack.first().click();
    await page.waitForFunction(() => location.hash === "#/workspace", { timeout: 5000 });
    expect(await page.locator(".ws-pane:not(.route-hidden)").isVisible(),
      "子相册里点返回工作区 = 一步到位回工作区");

    // 而 .g-back 仍然只管相册层级:回图墙后进册、点 .g-back → 回封面墙,不离开图墙
    await page.goto(`${base}/#/gallery`, { waitUntil: "domcontentloaded" });
    await page.locator(".g-wall .g-cell").first().waitFor({ timeout: 15000 });
    await page.locator(".g-wall .g-cell").first().click();
    await page.locator(".g-back").click();
    await page.waitForFunction(() => !document.querySelector(".g-back"), { timeout: 10000 });
    expect(await page.evaluate(() => location.hash) === "#/gallery",
      ".g-back 只回封面墙,不把人踢出图墙");
  });

  const rightOfChat = await rightEdge(page, ".chatcol");
  if (rightOfChat !== null) console.log(`\n(参考:.chatcol 右边界 ${rightOfChat}px)`);
} catch (e) {
  failures++;
  console.error(String(e));
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}
console.log(failures === 0 ? "WS-COLLAPSE-BACK E2E: ALL PASS" : `WS-COLLAPSE-BACK E2E: ${failures} FAIL`);
process.exit(failures === 0 ? 0 : 1);
