// track opendesign-image-upload e2e(真 chromium + 真 ds_web,不需要 gateway)。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// **这条走完整条链才叫"上传能用"**:真拖拽 → 提示回显落盘名 → 收件箱卡片里看得见
// → 点「扫描整理」→ 出方案 → 点「确认执行」→ 文件真的进了项目类目。
// 只断"接口 200"是假绿:前端没接上、或文件落盘但整理链路看不见(名字过不了
// 单段闸),接口照样 200。
//
// 跑法:node tests/e2e/image_upload.e2e.mjs(自起 ds_web 于 8808)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, readdirSync, existsSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { deflateSync } from "node:zlib";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8808;
const KEY = "翡翠湾-1801";
const PROJ_REL = "01-项目/20260701 王女士 翡翠湾 3#1801";
const INBOX = "00-收件箱";

// ── 真 PNG(最小编码器,与 gallery_order 同款)──────────────────────────────
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
    [...Array(h)].map(() => Buffer.concat([Buffer.from([0]), Buffer.alloc(w * 3, 0x77)])));
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr), chunk("IDAT", deflateSync(raw)), chunk("IEND", Buffer.alloc(0)),
  ]);
}

const tmp = mkdtempSync(join(tmpdir(), "upload-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
mkdirSync(join(ws, INBOX), { recursive: true });
mkdirSync(join(ws, ...PROJ_REL.split("/"), "02-参考图"), { recursive: true });
writeFileSync(join(dsRoot, "projects", `${KEY}.md`), `# ${KEY}

- 业主: [[王女士]]
- 阶段: 施工跟进

## 变更记录

## 沟通日志

---
最后更新: 2026-07-26
`);
writeFileSync(join(dsRoot, "config", "workspace.json"),
  JSON.stringify({ root: ws, projects: { [KEY]: PROJ_REL } }));

const srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
  env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT) },
  stdio: ["ignore", "inherit", "inherit"],
});
const base = `http://127.0.0.1:${PORT}`;
for (let i = 0; ; i++) {
  try { await fetch(`${base}/api/health`); break; }
  catch { if (i > 50) throw new Error("ds_web 起不来"); await new Promise((r) => setTimeout(r, 200)); }
}

/** 在页面里真造一个 File 并 drop 到目标元素(playwright 没有原生拖文件 API)。 */
async function dropFile(page, selector, name, b64) {
  await page.evaluate(async ({ selector, name, b64 }) => {
    const bin = atob(b64);
    const arr = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    const file = new File([arr], name, { type: "image/png" });
    const dt = new DataTransfer();
    dt.items.add(file);
    const el = document.querySelector(selector);
    el.dispatchEvent(new DragEvent("dragover", { dataTransfer: dt, bubbles: true, cancelable: true }));
    el.dispatchEvent(new DragEvent("drop", { dataTransfer: dt, bubbles: true, cancelable: true }));
  }, { selector, name, b64 });
}

const inboxFiles = () => readdirSync(join(ws, INBOX)).filter((f) => !f.startsWith("."));
/** 落点**从方案里读**,不写死:归到哪个类目是 taxonomy 规则说了算(实测这张图去的是
 *  `03-共享资源/参考图库`,不是我一开始猜的项目内 `02-参考图`)。断言要跟着方案走,
 *  否则测的是我的猜测而不是系统的承诺。 */
const fileAt = (dstRel, name) =>
  existsSync(join(ws, ...dstRel.split("/"), name));

let failures = 0;
let browser = null;
try {
  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  await page.goto(`${base}/#/gallery`, { waitUntil: "domcontentloaded" });
  await page.locator('[data-ui="gallery-drop"]').waitFor({ timeout: 15000 });

  // ── ① 真拖一张图进图墙 → 提示回显**落盘名** ───────────────────────────────
  const fileName = `${KEY} 客厅现场.png`;
  await dropFile(page, '[data-ui="gallery-drop"]', fileName, png(60, 40).toString("base64"));
  const note = page.locator('[data-ui="upload-note"]');
  await note.waitFor({ timeout: 15000 });
  await page.waitForFunction(
    () => (document.querySelector('[data-ui="upload-note"]')?.textContent || "").includes("已存进收件箱"),
    { timeout: 20000 });
  const noteTxt = (await note.innerText()).trim();
  check(noteTxt.includes(fileName), `提示里回显真实落盘名(实测「${noteTxt}」)`);

  // ── ② 真的落进收件箱,且没有临时文件残留 ──────────────────────────────────
  check(inboxFiles().includes(fileName), `文件真的进了收件箱(实测 ${JSON.stringify(inboxFiles())})`);
  check(readdirSync(join(ws, INBOX)).every((f) => !f.startsWith(".upload-")),
    "没有 .upload-*.tmp 残留");

  // ── ③ 收件箱卡片里看得见(= 整理链路认得它,不只是落盘)──────────────────
  await page.goto(`${base}/#/`, { waitUntil: "domcontentloaded" });
  await page.locator(`.proj-list .proj-row:has-text("${KEY}")`).first().click();
  const summary = page.locator('[data-ui="inbox-summary"]');
  await summary.waitFor({ timeout: 15000 });
  check((await summary.innerText()).includes("收件箱 1"),
    `收件箱卡片计数 = 1(实测「${(await summary.innerText()).trim()}」)`);

  // ── ④ 扫描整理 → 出方案 ───────────────────────────────────────────────────
  await summary.locator("button", { hasText: "扫描整理" }).click();
  await page.locator(".inbox-plan").first().waitFor({ timeout: 20000 });
  const planTxt = (await page.locator(".inbox-plan").first().innerText()).trim();
  check(planTxt.includes(fileName), `方案里是这张图(实测「${planTxt.slice(0, 60)}…」)`);
  // 目的地 = 方案行里 `→` 之后那一段(前端 planPreview 的 dst)
  const dstRel = (await page.locator(".inbox-plan .plan-row .dst").first().innerText()).trim();
  check(!!dstRel, `方案给出了目的地(实测「${dstRel}」)`);

  // ── ⑤ 确认执行 → 文件真的进了项目类目 ────────────────────────────────────
  await page.locator(".inbox-plan button", { hasText: "确认执行" }).first().click();
  await page.waitForFunction(
    () => !document.querySelector(".inbox-plan"), { timeout: 25000 });
  check(!inboxFiles().includes(fileName), "确认执行后,文件已离开收件箱");
  check(fileAt(dstRel, fileName),
    `文件真的落到方案说的那个位置(${dstRel}/${fileName})`);

  // ── ⑥ 非图片被拒(前端就拦住,不打服务端)────────────────────────────────
  await page.goto(`${base}/#/gallery`, { waitUntil: "domcontentloaded" });
  await page.locator('[data-ui="gallery-drop"]').waitFor({ timeout: 15000 });
  await page.evaluate(() => {
    const dt = new DataTransfer();
    dt.items.add(new File([new Uint8Array([1, 2, 3])], "图纸.dwg", { type: "application/acad" }));
    const el = document.querySelector('[data-ui="gallery-drop"]');
    el.dispatchEvent(new DragEvent("drop", { dataTransfer: dt, bubbles: true, cancelable: true }));
  });
  await page.waitForFunction(
    () => (document.querySelector('[data-ui="upload-note"]')?.textContent || "").includes("只收图片"),
    { timeout: 10000 });
  check(true, "非图片:提示「只收图片」且零上传");
  check(!inboxFiles().includes("图纸.dwg"), "非图片没有落盘");

  console.log(failures ? `IMAGE-UPLOAD E2E: ${failures} FAIL` : "IMAGE-UPLOAD E2E: ALL PASS");
} catch (e) {
  failures++;
  console.error(String(e));
} finally {
  if (browser) await browser.close();
  srv.kill("SIGTERM");
  rmSync(tmp, { recursive: true, force: true });
}
process.exit(failures ? 1 : 0);
