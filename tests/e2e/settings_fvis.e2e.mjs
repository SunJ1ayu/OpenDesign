// 真机反馈 #1(用户 2026-07-28 拍板「体检卡挪进设置」)+ 顺出的两条既有问题 e2e。
// 真 chromium + 真 ds_web(不走聊天链路)。主 agent 亲写,执行腿逐字节 off-limits。
//
// 覆盖:
//   A 体检卡**不再**出现在工作区那一列 —— 挪走要挪干净,不能两处都有;
//     侧栏那句指路文案必须同步改口(它现在写着"到右边卡片里改",挪完就是错的指路)。
//   B 设置弹层里有入口、点开**默认就是展开可用**的(设置里再要求点一次展开是多余的一层),
//     且**写路径仍然通**:勾选→保存→左侧项目列表真的变了。
//     ⚠️ 这一条是本次改动唯一有风险的地方:卡片换了容器,active/dataEpoch 的取数门
//     和 onSaved 的回调链最容易在搬家时断掉,而断了以后卡片长得**一模一样**。
//   C 图墙默认回到一行 4 个(0.51.0 缩放那一单把默认顺手改成了最密的 7),
//     且**用户存过的偏好仍然优先**——默认值改动不许把"记住选择"一起改掉。
//
// 跑法:node tests/e2e/settings_fvis.e2e.mjs(自起 ds_web 于 8804)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { deflateSync } from "node:zlib";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8804;
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

const tmp = mkdtempSync(join(tmpdir(), "sfvis-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
// 两个会被"猜"成结构目录的文件夹:体检卡要有行可列,保存后它们该出现在项目列表里
mkdirSync(join(ws, "00-收件箱"), { recursive: true });
mkdirSync(join(ws, "03-共享资源"), { recursive: true });
// 8 个相册:够验"一行 4 个"要换行(4 个的话一行就排完了,列数断言会退化成"最多 4 列")
const ALBUMS = ["主卧", "客厅", "餐厅", "书房", "厨房", "卫生间", "阳台", "玄关"];
for (const a of ALBUMS) {
  for (const n of [1, 2]) {
    const p = join(ws, PROJ_REL, "05-3DMAX", a, `${a} (${n}).png`);
    mkdirSync(dirname(p), { recursive: true });
    writeFileSync(p, png(400, 300));
  }
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

/** 侧栏项目行名字(未建档的工作区文件夹也在这条列表里)。 */
const projRows = (page) =>
  page.$$eval(".proj-list .proj-row .nm", (els) => els.map((e) => e.textContent.trim()));

let browser = null;
try {
  browser = await launchBrowser();

  await step("A 体检卡挪走要挪干净(工作区列里不再有,指路文案改口)", async () => {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
    await page.locator(".chatcol").waitFor({ timeout: 15000 });
    // 等侧栏那条"没列进项目列表"的提示出来 = 后端数据已到、体检面确实适用,
    // 这时候再断言"卡片不在"才有意义(否则可能只是还没渲染出来 = 假绿)
    await page.locator('[data-ui="excluded-structural"]').waitFor({ timeout: 15000 });

    expect(await page.locator('[data-ui="folder-visibility"]').count() === 0,
      "工作区那一列里不再有体检卡");

    const hint = await page.locator('[data-ui="excluded-structural"]').innerText();
    expect(hint.includes("设置"), `指路文案改指设置(实测「${hint.replace(/\s+/g, " ")}」)`);
    expect(!hint.includes("右边"), "指路文案不再说「到右边卡片里改」(挪走后那是错的指路)");
    await page.close();
  });

  await step("B 设置里打开体检卡:默认展开、能改、保存真的生效", async () => {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
    await page.locator('[data-ui="excluded-structural"]').waitFor({ timeout: 15000 });

    const before = await projRows(page);
    check(before.length === 1, `前提:一开始项目列表只有 1 个项目(实测 ${before.length}:${before})`);

    await page.locator('.side-footer .side-row').click();       // 打开设置弹层
    await page.locator(".settings-pop").waitFor({ timeout: 5000 });
    const entry = page.locator('[data-ui="settings-folder-visibility"]');
    check(await entry.count() > 0, "设置弹层里有「工作区文件夹」入口");
    await entry.click();

    const card = page.locator('[data-ui="folder-visibility"]');
    await card.waitFor({ timeout: 10000 });
    expect(await card.isVisible(), "点开后体检卡可见");
    // 设置里是"专门来改这个"的场景,不该再要求点一次展开
    const boxes = card.locator('input[type=checkbox]');
    expect(await boxes.count() >= 3,
      `默认就是展开可用的(实测 ${await boxes.count()} 个勾选框,期望 ≥3)`);
    const names = await card.locator(".fvis-name").allInnerTexts();
    expect(names.includes("00-收件箱") && names.includes("03-共享资源"),
      `列出了工作区根下的文件夹(实测 ${JSON.stringify(names)})`);

    // 什么都不动直接保存 = 撤销所有猜测、全部显示(A6 的不对称取舍,原样保留)
    await card.locator(".fvis-actions .primary").click();
    await page.locator(".fvis-ok").waitFor({ timeout: 10000 });

    // ★ 写路径真的通:左侧项目列表当场多出那两个被猜掉的文件夹。
    //   断在**用户看得见的结果**上,不是"请求发出去了"。
    await page.waitForFunction(
      () => document.querySelectorAll(".proj-list .proj-row").length >= 3, { timeout: 10000 });
    const after = await projRows(page);
    expect(after.includes("00-收件箱") && after.includes("03-共享资源"),
      `保存后被猜掉的文件夹回到项目列表(实测 ${JSON.stringify(after)})`);
    await page.close();
  });

  await step("C 图墙默认一行 4 个,但存过的偏好仍然优先", async () => {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    await page.goto(`${base}/#/gallery`, { waitUntil: "domcontentloaded" });
    await page.locator(".g-wall .g-cell").first().waitFor({ timeout: 15000 });
    await page.waitForFunction(
      () => [...document.querySelectorAll(".g-wall .g-cell img")].every((i) => i.complete),
      { timeout: 15000 });

    // 量**真实左边界**数列数,不读 CSS 声明值(07-24 史料:columnCount 数字对、结果错)
    const colsOf = () =>
      page.$$eval(".g-wall .g-cell", (els) =>
        new Set(els.map((e) => Math.round(e.getBoundingClientRect().left))).size);
    expect(await colsOf() === 4, `没存过偏好时默认一行 4 个(实测 ${await colsOf()} 列)`);
    const label = await page.locator('[data-ui="gallery-zoom"] .g-zoom-n').innerText();
    expect(label.trim() === "一行 4", `缩放读数与实际一致(实测「${label.trim()}」)`);

    // 存过偏好的照旧听用户的 —— 改默认值不许把"记住选择"一起改掉
    await page.evaluate(() => localStorage.setItem("ds.gallery.cols", "6"));
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.locator(".g-wall .g-cell").first().waitFor({ timeout: 15000 });
    await page.waitForFunction(
      () => [...document.querySelectorAll(".g-wall .g-cell img")].every((i) => i.complete),
      { timeout: 15000 });
    expect(await colsOf() === 6, `存过的偏好优先于默认值(实测 ${await colsOf()} 列,期望 6)`);
    await page.close();
  });
} catch (e) {
  failures++;
  console.error(String(e));
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}
console.log(failures === 0 ? "SETTINGS-FVIS E2E: ALL PASS" : `SETTINGS-FVIS E2E: ${failures} FAIL`);
process.exit(failures === 0 ? 0 : 1);
