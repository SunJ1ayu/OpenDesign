// 真机反馈(2026-07-28 下午,用户截图 + 口述)两条 e2e。真 chromium + 真 ds_web。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// 覆盖:
//   A 收件箱卡「还没有收件箱文件夹」那一态:**小字和按钮都不许贴在卡片边线上**。
//     用户原话「收件箱里面的小字跟左右太贴了,都快喘不过气了」——截图实证:
//     `.inbox-hint` 左右 padding 是 0、`.plan-acts` 的样式只写在 `.inbox-plan` 底下
//     (这一态的按钮行**不在** .inbox-plan 里 → 一条样式都没吃到)→ 双双顶到边框。
//     **断言打在几何上**(元素边界与卡片边界的间距),不断言"某条 padding 写了没"——
//     写了 padding 也可能被别的规则盖掉,量像素才是用户眼睛看到的东西。
//     并且钉住「和卡片自己的标题同一条左边界」= 用户问的"款式规范跟其它的一致吗"的可验形式。
//   A' 按钮**靠右**(用户拍板:「帮我建收件箱这个按钮我感觉在右边合适一点」)。
//     钉法 = 右边距在 8~16px 之间 **且左边距明显大于右边距** —— 只钉右边距的话,
//     一个撑满整行的按钮也能过(两边都贴着,右边距同样是 12),那不是"靠右"。
//   B 伴随列「图片」标题旁不再有「图墙 →」小字(用户:点图片就进去了,这条多余)。
//     ⚠️ 这条**推翻了 cockpit.e2e.mjs 里原先的产品要求**「图墙常驻入口(<4 张图也可达)」。
//     所以本文件必须把"入口还在不在"接过来钉住:**缩略图仍然点得进图墙**,
//     「+N 图墙 →」那块溢出砖也仍在 —— 删的是重复的那一个,不是把路堵死。
//     已知代价(用户已知情):一张图都没有时进不去图墙 —— 那时图墙本来也是空的。
//
// 跑法:node tests/e2e/inbox_pad_gallery.e2e.mjs(自起 ds_web 于 8805)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { deflateSync } from "node:zlib";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8805;
const KEY = "翡翠湾-1801";
const PROJ_REL = "20260701 王女士 翡翠湾 3#1801";

function png(w, h) {
  const t = [...Array(256)].map((_, n) => {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    return c >>> 0;
  });
  const crc = (b) => {
    let c = 0xffffffff;
    for (const x of b) c = t[(c ^ x) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
  const ch = (ty, d) => {
    const l = Buffer.alloc(4); l.writeUInt32BE(d.length);
    const td = Buffer.concat([Buffer.from(ty, "ascii"), d]);
    const c = Buffer.alloc(4); c.writeUInt32BE(crc(td));
    return Buffer.concat([l, td, c]);
  };
  const ih = Buffer.alloc(13);
  ih.writeUInt32BE(w, 0); ih.writeUInt32BE(h, 4); ih[8] = 8; ih[9] = 2;
  const raw = Buffer.concat(
    [...Array(h)].map(() => Buffer.concat([Buffer.from([0]), Buffer.alloc(w * 3, 0x99)])));
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    ch("IHDR", ih), ch("IDAT", deflateSync(raw)), ch("IEND", Buffer.alloc(0)),
  ]);
}

const tmp = mkdtempSync(join(tmpdir(), "ipg-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
// **故意不建 00-收件箱**:A 段要的正是「还没有收件箱文件夹」那一态(截图里的那张卡)。
// 7 张项目图:>5 才有「+N 图墙 →」溢出砖,B 段要钉它还在。
for (let n = 1; n <= 7; n++) {
  const p = join(ws, PROJ_REL, "05-3DMAX", "客厅", `客厅 (${n}).png`);
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

// 分段隔离 + 纯断言不抛(照 ws_collapse_back 的两层写法:一轮把坏掉的面报全)
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

/** 元素相对视口的 box(不存在/零尺寸 → null)。 */
const box = (page, sel) =>
  page.evaluate((s) => {
    const el = document.querySelector(s);
    if (!el) return null;
    const b = el.getBoundingClientRect();
    if (b.width === 0 && b.height === 0) return null;
    return { left: b.left, right: b.right, top: b.top, bottom: b.bottom };
  }, sel);

let browser = null;
try {
  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // ── A 收件箱卡:字和按钮都不许贴边,按钮靠右 ───────────────────────────────
  await step("A 收件箱卡「还没有收件箱」态:不贴边 + 按钮靠右", async () => {
    await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
    await page.locator('[data-ui="inbox-missing"]').waitFor({ timeout: 15000 });
    check(await page.locator('[data-ui="inbox-create"]').isVisible(),
      "前提:「帮我建收件箱」那一态在场(夹具没建收件箱夹)");

    const card = await box(page, ".inbox-card");
    const title = await box(page, ".inbox-card .inbox-summary .t");
    const hint = await box(page, '[data-ui="inbox-missing"]');
    const btn = await box(page, '[data-ui="inbox-create"]');
    check(card && title && hint && btn, "前提:卡片/标题/小字/按钮四个盒子都量得到");

    const padL = Math.round(hint.left - card.left);
    const padR = Math.round(card.right - hint.right);
    expect(padL >= 10, `小字左边不贴卡片边线(实测 ${padL}px,期望 ≥10)`);
    expect(padR >= 10, `小字右边不贴卡片边线(实测 ${padR}px,期望 ≥10)`);
    // 「跟我们其它的一致」的可验形式:和这张卡自己的标题同一条左边界。
    expect(Math.abs(hint.left - title.left) <= 1,
      `小字与标题「收件箱」同一条左边界(标题 ${Math.round(title.left)} / 小字 ${Math.round(hint.left)})`);

    const btnR = Math.round(card.right - btn.right);
    const btnL = Math.round(btn.left - card.left);
    expect(btn.right <= card.right, `按钮不越出卡片右缘(按钮 ${Math.round(btn.right)} / 卡片 ${Math.round(card.right)})`);
    expect(btnR >= 8 && btnR <= 16, `按钮右边留出边距(实测 ${btnR}px,期望 8~16)`);
    // 只钉右边距的话,撑满整行的按钮也能过 —— 必须钉"左边空得比右边多"才叫靠右。
    expect(btnL > btnR, `按钮真的靠右(左空 ${btnL}px > 右空 ${btnR}px)`);
  });

  // ── B 伴随列不再有「图墙 →」小字,但进图墙的路没堵死 ───────────────────────
  await step("B「图片」标题旁不再有「图墙 →」,缩略图仍是入口", async () => {
    await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
    await page.locator(".aside .aside-head").first().waitFor({ timeout: 15000 });
    await page.locator(`.proj-list .proj-row:has-text("${KEY}")`).first().click();
    await page.locator('.seg .opt:has-text("项目图")').click();
    await page.locator(".aside .thumb-grid .thumb").first().waitFor({ timeout: 15000 });

    expect(await page.locator(".aside .aside-head .gallery-link").count() === 0,
      "「图片」标题旁没有「图墙 →」链接了");
    const headTexts = (await page.locator(".aside .aside-head").allInnerTexts()).join(" ");
    expect(!headTexts.includes("图墙"),
      `伴随列标题行里不再出现「图墙」字样(实测 ${JSON.stringify(headTexts)})`);

    // 入口没堵死:缩略图点得进图墙(cockpit 那条「图少也能进」的要求换了载体接着钉)
    await page.locator(".aside .thumb-grid .thumb:not(.more)").first().click();
    await page.locator(".gallery-page").waitFor({ timeout: 10000 });
    expect(page.url().includes("#/gallery"), "点缩略图进得了图墙");

    // 「+N 图墙 →」溢出砖:用户没要求删它,别顺手删过头
    await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
    await page.locator(`.proj-list .proj-row:has-text("${KEY}")`).first().click();
    await page.locator('.seg .opt:has-text("项目图")').click();
    const more = page.locator(".aside .thumb-grid .thumb.more");
    await more.waitFor({ timeout: 15000 });
    expect(await more.count() === 1, "「+N 图墙 →」溢出砖仍在(7 张图 > 5)");
    await more.click();
    await page.locator(".gallery-page").waitFor({ timeout: 10000 });
    expect(page.url().includes("#/gallery"), "点溢出砖也进得了图墙");
  });

  console.log(failures === 0 ? "\nINBOX-PAD-GALLERY E2E: ALL PASS"
                             : `\nINBOX-PAD-GALLERY E2E: ${failures} FAIL`);
} catch (e) {
  failures++;
  console.error(String(e));
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}
process.exit(failures === 0 ? 0 : 1);
