// track opendesign-feedback-0724-ui e2e:图墙三条真机反馈的行为面契约
// (真 chromium + 真 ds_web;不需要 gateway —— 图墙不走聊天链路)。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// 覆盖(对应 2026-07-24 反馈 #2 / #10a / #10b):
//   #2  封面墙四列排列整齐 —— 断言**几何**(同行 top 相等 + 第 5 格换行 + 各格等高),
//       不断言 CSS 属性字符串。史料:07-24 `columnCount==="3"` 全绿而正文被压成竖排,
//       教训 = 断言人眼看到的位置,不是声明值。
//   #10a 子相册内图序 = 文件名自然升序(资源管理器口径),不是 mtime 降序。
//   #10b 从子相册返回封面墙,滚动位置回到点进去之前,而不是弹回顶端。
//
// 跑法:node tests/e2e/gallery_order.e2e.mjs(自起 ds_web 于 8801)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { deflateSync } from "node:zlib";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8801;
const KEY = "翡翠湾-1801";
const PROJ_REL = "01-项目/20260701 王女士 翡翠湾 3#1801";

// ── 最小 PNG 编码器(stdlib zlib):造**不同宽高比**的真图片。
// 为什么不用 1x1 占位:#2 的病根就是"图高不一 → 多列流越积越偏",
// 全用同尺寸假图会让坏实现也显得整齐 = 假绿。
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
  ihdr[8] = 8; // bit depth
  ihdr[9] = 2; // truecolor
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

const tmp = mkdtempSync(join(tmpdir(), "gorder-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");
const projDir = join(ws, ...PROJ_REL.split("/"));
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });

writeFileSync(join(dsRoot, "projects", `${KEY}.md`), `# ${KEY}

- 业主: [[王女士]]
- 阶段: 施工跟进

## 变更记录

## 沟通日志

---
最后更新: 2026-07-25
`);
writeFileSync(
  join(dsRoot, "config", "workspace.json"),
  JSON.stringify({ root: ws, projects: { [KEY]: PROJ_REL } }),
);

// 8 个相册 × 各 3 张 = 封面墙 8 格(足够验四列换行);高度刻意参差。
// mtime **与文件名同序**(真实情形:按顺序拷进文件夹)→ mtime 降序恰好是文件名倒序,
// 与正确答案相反,夹具因此能区分两种实现。
const ALBUMS = ["主卧", "客厅", "餐厅", "书房", "厨房", "卫生间", "阳台", "玄关"];
const SHAPES = [[400, 300], [400, 640], [400, 260], [400, 520]];
let stamp = 1_700_000_000;
for (const [ai, album] of ALBUMS.entries()) {
  for (const n of [1, 2, 10]) {
    // 括号 + 空格 + 多位数字的**真实中文文件名**:纯字典序会把 (10) 排到 (2) 前,
    // 只有 numeric 自然序才对 —— 造 a/b/c 式假名字证明不了用户机器上也对。
    const name = `${KEY} ${album} (${n}).png`;
    const [w, h] = SHAPES[(ai + n) % SHAPES.length];
    const p = join(projDir, "05-3DMAX", album, name);
    mkdirSync(dirname(p), { recursive: true });
    writeFileSync(p, png(w, h));
    stamp += 100;
  }
}

const srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
  env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT) },
  stdio: ["ignore", "inherit", "inherit"],
});
const base = `http://127.0.0.1:${PORT}`;
for (let i = 0; ; i++) {
  try { await fetch(`${base}/api/health`); break; }
  catch { if (i > 50) throw new Error("ds_web 起不来"); await new Promise((r) => setTimeout(r, 200)); }
}

const boxes = (page) =>
  page.$$eval(".g-wall .g-cell", (els) =>
    els.map((e) => {
      const b = e.getBoundingClientRect();
      return { top: Math.round(b.top), left: Math.round(b.left), h: Math.round(b.height) };
    }));

let failures = 0;
let browser = null;
try {
  browser = await launchBrowser();
  // 窄一点的视口保证封面墙一定要滚动(#10b 需要可滚动的容器)
  const page = await browser.newPage({ viewport: { width: 1280, height: 700 } });
  await page.goto(`${base}/#/gallery`, { waitUntil: "domcontentloaded" });
  await page.locator(".g-wall .g-cell").first().waitFor({ timeout: 15000 });
  // 懒加载图片不参与布局会让"整齐"变得没有意义 —— 先把图都加载出来再量
  await page.waitForFunction(
    () => [...document.querySelectorAll(".g-wall .g-cell img")].every((i) => i.complete),
    { timeout: 15000 },
  );

  // ── #2 封面墙排列整齐 ───────────────────────────────────────────────────
  const wall = await boxes(page);
  check(wall.length === ALBUMS.length, `封面墙 ${ALBUMS.length} 格(实测 ${wall.length})`);
  const cols = new Set(wall.map((b) => b.left)).size;
  check(cols === 4, `封面墙四列(实测 ${cols} 列)`);
  const row1 = wall.slice(0, 4);
  const row1Tops = new Set(row1.map((b) => b.top));
  check(row1Tops.size === 1, `第一行 4 格顶边齐平(实测 ${[...row1Tops].join("/")})`);
  check(wall[4].top > wall[0].top,
    `第 5 格换到第二行(row-major 阅读序;实测 top ${wall[4].top} vs ${wall[0].top})`);
  check(wall[4].left === wall[0].left,
    `第 5 格回到第一列(实测 left ${wall[4].left} vs ${wall[0].left})`);
  const hs = new Set(wall.map((b) => b.h));
  check(hs.size === 1, `所有封面等高 = 不会越翻越歪(实测高度种类 ${hs.size}:${[...hs].join("/")})`);
  // 「整齐」还可以整齐得没法看:格子不能被压扁成一条
  check(wall[0].h >= 120, `封面格子高度可用(实测 ${wall[0].h}px)`);

  // ── #10b 记录滚动位置 ───────────────────────────────────────────────────
  const scroller = ".page.gallery-page";
  const scrolled = await page.evaluate((sel) => {
    const el = document.querySelector(sel);
    el.scrollTop = 240;
    return el.scrollTop;
  }, scroller);
  check(scrolled > 0, `封面墙可滚动并已滚到 ${scrolled}(否则 #10b 无从谈起)`);

  // ── #10a 点进子相册:图序 = 文件名自然升序 ────────────────────────────────
  await page.locator(".g-wall .g-cell").first().click();
  await page.locator(".g-back").waitFor({ timeout: 10000 });
  const labels = await page.$$eval(".g-wall .g-cell .g-cap .l", (els) =>
    els.map((e) => e.textContent.trim()));
  const album0 = ALBUMS[0];
  check(
    JSON.stringify(labels) ===
      JSON.stringify([1, 2, 10].map((n) => `${KEY} ${album0} (${n}).png`)),
    `子相册按文件名自然序:(1)(2)(10) —— 实测 ${JSON.stringify(labels)}`,
  );

  // ── #10b 返回封面墙:滚动位置恢复 ─────────────────────────────────────────
  await page.locator(".g-back").click();
  await page.waitForFunction(() => !document.querySelector(".g-back"), { timeout: 10000 });
  const back = await page.evaluate((sel) => document.querySelector(sel).scrollTop, scroller);
  check(Math.abs(back - scrolled) <= 2,
    `返回后回到原滚动位置(期望 ≈${scrolled},实测 ${back})`);
} catch (e) {
  failures++;
  console.error(String(e));
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}
console.log(failures === 0 ? "GALLERY-ORDER E2E: ALL PASS" : `GALLERY-ORDER E2E: ${failures} FAIL`);
process.exit(failures === 0 ? 0 : 1);
