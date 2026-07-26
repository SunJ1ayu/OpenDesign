// track opendesign-chat-image e2e(真 chromium + 真 ds_web + **stub 掉 ws/bootstrap**)。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// 本单要断的是"**浏览器真的按协议把 media 装进信封发出去了**"。三种做法里选第三种:
//   ① 真 gateway:烧 token、答案不确定,而且**看不见信封** —— 断不了 media 形状。
//   ② 自建假 gateway 占 8765:浏览器侧 ws 端口写死 8765(connection.ts:61),
//      开发机上常年有真 gateway 在跑 → 端口冲突,还得让人先停服务。**已试,弃**。
//   ③ 页面里 stub `window.WebSocket` + `/api/chat/bootstrap`:直接截住 `ws.send()`
//      的原始字符串,信封逐字段可断;登录流不再依赖真 gateway 的口令。
// 代价必须写明:③ 只证明"我按我抄的协议发了",**不证明 nanobot 会收下**。
// 那一条由 verify.md 的手工冒烟兜(对真 gateway 发 1 张小图,看 mimo 描述得出)。
// 除 ws/bootstrap 外一律真货:ds_web 真进程、上传真落盘、收件箱真建目录。
//
// 走的是完整一条链:
//   工作区**没有**收件箱 → 卡片给「帮我建收件箱」(点前就写清建在哪)→ 点 → 真建出来
//   → 聊天框粘贴 + `+` 选文件两个入口各进一张图 → svg 被拦 → 撤掉一张
//   → 发送 → 断信封里 media 形状/张数 → 缩略图清空
//   → 气泡「存进收件箱」→ 文件真落盘 + 提示回显**绝对路径**
//
// 跑法:node tests/e2e/chat_image.e2e.mjs(自起 ds_web 于 8810;不需要 nanobot)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, readdirSync, existsSync, rmSync }
  from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { deflateSync } from "node:zlib";
import { launchBrowser, loginPane, expandInbox, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8810;
const PASSWORD = "e2etest";
const HOME = ".home-pane";
const INBOX = "00-收件箱";

// ── 真 PNG(与 image_upload/gallery_order 同款最小编码器)────────────────────
function png(w, h, byte = 0x77) {
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
    [...Array(h)].map(() => Buffer.concat([Buffer.from([0]), Buffer.alloc(w * 3, byte)])));
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr), chunk("IDAT", deflateSync(raw)), chunk("IEND", Buffer.alloc(0)),
  ]);
}

// ── 页面注入:stub ws + bootstrap,把 send() 的原始字符串攒进 window.__sent ──
const STUB = () => {
  window.__sent = [];
  const origFetch = window.fetch;
  window.fetch = (url, init) => {
    if (String(url).includes("/api/chat/bootstrap")) {
      return Promise.resolve(new Response(JSON.stringify({
        token: "stub-token", ws_path: "/ws", expires_in: 600, model_name: "stub-model",
      }), { status: 200, headers: { "Content-Type": "application/json" } }));
    }
    return origFetch(url, init);
  };
  class StubWS {
    constructor(url) {
      this.url = url;
      this.readyState = 0;
      setTimeout(() => {
        this.readyState = 1;
        this.onopen?.({});
        this.#emit({ event: "ready", chat_id: "chat-e2e" });
      }, 10);
    }
    #emit(o) { this.onmessage?.({ data: JSON.stringify(o) }); }
    send(data) {
      window.__sent.push(data);
      let m = null;
      try { m = JSON.parse(data); } catch { /* 非 JSON:忽略 */ }
      if (m?.type !== "message") return;
      setTimeout(() => {
        const sid = "stub-stream";
        this.#emit({ event: "delta", text: "收到", stream_id: sid,
                     turn_id: m.turn_id, turn_phase: "answer", turn_seq: 1 });
        this.#emit({ event: "stream_end", stream_id: sid, turn_seq: 2 });
        this.#emit({ event: "turn_end", turn_phase: "complete", turn_seq: 3,
                     goal_state: { active: false } });
      }, 10);
    }
    close() { this.readyState = 3; }
  }
  window.WebSocket = StubWS;
};

// ── 夹具:DS_ROOT + 工作区(**故意不建收件箱**)─────────────────────────────
const tmp = mkdtempSync(join(tmpdir(), "chatimg-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
mkdirSync(ws, { recursive: true });
writeFileSync(join(dsRoot, "config", "workspace.json"),
  JSON.stringify({ root: ws, projects: {} }));

const inboxFiles = () =>
  existsSync(join(ws, INBOX))
    ? readdirSync(join(ws, INBOX)).filter((f) => !f.startsWith("."))
    : [];

/** 页面里造 File 并触发 paste(ClipboardEvent + DataTransfer)。 */
async function pasteFile(page, selector, name, b64, mime = "image/png") {
  await page.evaluate(({ selector, name, b64, mime }) => {
    const bin = atob(b64);
    const arr = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    const dt = new DataTransfer();
    dt.items.add(new File([arr], name, { type: mime }));
    const el = document.querySelector(selector);
    el.focus();
    el.dispatchEvent(new ClipboardEvent("paste", {
      clipboardData: dt, bubbles: true, cancelable: true,
    }));
  }, { selector, name, b64, mime });
}

const sentMessages = (page) => page.evaluate(() =>
  window.__sent.map((s) => { try { return JSON.parse(s); } catch { return null; } })
    .filter((m) => m && m.type === "message"));

let failures = 0;
let browser = null;
let srv = null;
try {
  srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
    env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT) },
    stdio: ["ignore", "inherit", "inherit"],
  });
  const base = `http://127.0.0.1:${PORT}`;
  for (let i = 0; ; i++) {
    try { await fetch(`${base}/api/health`); break; }
    catch {
      if (i > 50) throw new Error("ds_web 起不来");
      await new Promise((r) => setTimeout(r, 200));
    }
  }

  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  const errs = [];
  page.on("pageerror", (e) => errs.push(String(e)));
  await page.addInitScript(STUB);
  // 收件箱卡片在**工作区路由**的伴随列(App.tsx:443 `active={route==="workspace"}`),
  // 不在新对话首页 —— 起初把 ① 写在 `/` 上是我搞错了路由(红检时才发现)。
  await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });

  // ── ① 没有收件箱 → 卡片给出路,且**点之前**就告诉你会建在哪 ────────────────
  const createBtn = page.locator('[data-ui="inbox-create"]');
  await createBtn.waitFor({ timeout: 15000 });
  const hint = await page.locator('[data-ui="inbox-missing"]').textContent();
  check(hint.includes(join(ws, INBOX)),
    `点之前就写清会建在哪(绝对路径):${JSON.stringify(hint)}`);
  check(!existsSync(join(ws, INBOX)), "点之前收件箱确实不存在");

  await createBtn.click();
  await page.waitForFunction(
    () => document.querySelector('[data-ui="inbox-create"]') === null,
    null, { timeout: 15000 });
  check(existsSync(join(ws, INBOX)), "点「帮我建收件箱」后目录真的建出来了");
  check(readdirSync(ws).length === 1, "只建了这一个,没顺手造别的目录");
  // 建完不能只是"卡片消失"(空箱=隐身),要留一句带路径的确认 —— 点一下东西没了,
  // 对一个不是程序员的人读起来像"坏了"(四审 subkimi)。
  const createdNote = await page.locator('[data-ui="inbox-created"]').textContent();
  check(createdNote.includes(join(ws, INBOX)),
    `建完要确认且带路径:${JSON.stringify(createdNote)}`);

  // ── ② 聊天:两个入口各进一张图 → 缩略图 → svg 被拦 → 撤掉一张 ─────────────
  await page.evaluate(() => { window.location.hash = "#/"; });
  await page.locator(HOME).waitFor({ state: "visible", timeout: 10000 });
  await loginPane(page, HOME, PASSWORD);
  const thumbs = page.locator(`${HOME} [data-ui="chat-thumb"]`);

  await pasteFile(page, `${HOME} textarea`, "客厅现场.png", png(40, 30).toString("base64"));
  await thumbs.first().waitFor({ timeout: 10000 });
  check((await thumbs.count()) === 1, "粘贴一张 → 缩略图 1 个");

  await page.locator(`${HOME} [data-ui="chat-attach-input"]`)
    .setInputFiles({ name: "主卧.jpg", mimeType: "image/jpeg", buffer: png(30, 20, 0x22) });
  await page.waitForFunction(
    (sel) => document.querySelectorAll(`${sel} [data-ui="chat-thumb"]`).length === 2,
    HOME, { timeout: 10000 });
  check(true, "`+` 按钮选文件 → 缩略图 2 个(两个入口都通)");

  // svg 必须被前端拦住(协议显式排除;放过去 = 整条消息静默不发布)
  await pasteFile(page, `${HOME} textarea`, "图标.svg",
    Buffer.from("<svg xmlns='http://www.w3.org/2000/svg'/>").toString("base64"),
    "image/svg+xml");
  await page.waitForTimeout(400);
  check((await thumbs.count()) === 2, "svg 被前端拦住,没进缩略图");
  const note = await page.locator(`${HOME} [data-ui="chat-media-note"]`).textContent();
  check(/[一-龥]/.test(note) && !/^[a-z_]+$/.test(note.trim()),
    `被拒要给人话而不是错误码:${JSON.stringify(note)}`);

  await page.locator(`${HOME} [data-ui="chat-thumb-remove"]`).first().click();
  await page.waitForFunction(
    (sel) => document.querySelectorAll(`${sel} [data-ui="chat-thumb"]`).length === 1,
    HOME, { timeout: 10000 });
  check(true, "缩略图可单张撤掉");

  // ── ③ 发送 → 信封里真的带 media(形状照协议)──────────────────────────────
  await page.evaluate(() => { window.__sent.length = 0; });
  await page.locator(`${HOME} textarea`).fill("这个客厅怎么改?");
  await page.locator(`${HOME} .send-btn`).click();
  await page.waitForFunction(
    () => window.__sent.some((s) => s.includes('"type":"message"')),
    null, { timeout: 15000 });
  const [sent] = await sentMessages(page);
  check(!!sent, "ws 上发出了 message 信封");
  check(sent.content.includes("这个客厅怎么改?"), "文字照旧带上");
  check(Array.isArray(sent.media) && sent.media.length === 1,
    `media 是数组且只有留下的那 1 张:got ${JSON.stringify(sent.media?.length)}`);
  check(typeof sent.media[0].data_url === "string"
    && /^data:image\/(png|jpeg);base64,/.test(sent.media[0].data_url),
    "data URL 形状照协议(data:<mime>;base64,…)");
  check(typeof sent.media[0].name === "string" && sent.media[0].name.length > 0,
    "带上文件名(模型/历史回放要用)");
  check(sent.webui === true && typeof sent.turn_id === "string",
    "一等路径字段没被 media 挤掉(webui:true + turn_id)");

  // 发完缩略图要清空 —— 否则下一条会把同一张图再发一遍
  await page.waitForFunction(
    (sel) => document.querySelectorAll(`${sel} [data-ui="chat-thumb"]`).length === 0,
    HOME, { timeout: 10000 });
  check(true, "发送后缩略图清空(不会重复发)");

  // ── ④ 气泡「存进收件箱」→ 真落盘 + 提示回显绝对路径 ──────────────────────
  check(inboxFiles().length === 0, "存之前收件箱是空的");
  const saveBtn = page.locator(`${HOME} [data-ui="save-to-inbox"]`).first();
  await saveBtn.waitFor({ timeout: 10000 });
  await saveBtn.click();
  await page.waitForFunction(() => {
    const el = document.querySelector('[data-ui="save-to-inbox-note"]');
    return el && /已存/.test(el.textContent || "");
  }, null, { timeout: 15000 });
  const saveNote = await page.locator('[data-ui="save-to-inbox-note"]').textContent();
  const landed = inboxFiles();
  check(landed.length === 1, `图真的落进收件箱:${JSON.stringify(landed)}`);
  check(saveNote.includes(join(ws, INBOX)),
    `提示要回显**绝对路径**(用户问过"收件箱在我电脑哪个文件夹"):${JSON.stringify(saveNote)}`);
  check(saveNote.includes(landed[0]), "提示里的名字 = 真实落盘名");

  // ── ⑤ 收件箱卡片要显示它在硬盘哪儿(回工作区路由)────────────────────────
  await page.evaluate(() => { window.location.hash = "#/workspace"; });
  await page.locator('[data-ui="inbox-summary"]').waitFor({ timeout: 15000 });

  // -p2:收件箱**在右列(项目助手上面)**,不在中间那列;且常驻「打开」入口
  check(await page.locator('.chatcol [data-ui="inbox-summary"]').count() === 1,
    "收件箱在右列(项目助手上面)");
  check(await page.locator('.aside [data-ui="inbox-summary"]').count() === 0,
    "中间伴随列里不再有收件箱(那列 = 纯这个项目的东西)");
  check(await page.locator('[data-ui="inbox-open"]').count() >= 1, "常驻「打开」入口在");
  // 收起项目助手(»)→ 收件箱那一行**仍在**(它不属于聊天)
  await page.locator('.chatcol-head button[title="收起"]').click();
  await page.waitForFunction(
    () => document.querySelector(".chatcol.collapsed") !== null, null, { timeout: 5000 });
  check(await page.locator('.chatcol [data-ui="inbox-summary"]').count() === 1,
    "收起项目助手后,收件箱仍在");
  await page.locator('.chat-rail button').click();   // 展开回来,后续断言照旧
  await page.waitForFunction(
    () => document.querySelector(".chatcol.collapsed") === null, null, { timeout: 5000 });
  await expandInbox(page);   // 卡片默认收成一行摘要(v4 质感收口),路径在折叠区里
  const whereEl = page.locator('[data-ui="inbox-where"]');
  await whereEl.waitFor({ timeout: 15000 });
  const where = await whereEl.textContent();
  check(where.includes(join(ws, INBOX)), `收件箱卡片显示绝对路径:${JSON.stringify(where)}`);

  check(errs.length === 0, `全程无 JS 报错:${errs.join(" | ")}`);
} catch (e) {
  failures++;
  console.error(`FAIL: ${e.message}`);
} finally {
  if (browser) await browser.close();
  if (srv) srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}
console.log(failures === 0
  ? "\nchat_image e2e: ALL PASS"
  : `\nchat_image e2e: ${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
