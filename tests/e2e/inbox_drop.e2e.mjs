// 收件箱拖放落点 e2e(真 chromium + 真 ds_web)。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// 用户 2026-08-01 真机原话(M):「收件箱之前是有框的,我可以拖入文件的感觉,现在没有了,
// 变成只有打开按钮了……但是我在前端页面根本没法直接拖入文件,还得去电脑打开吗」。
//
// 主 agent 查实(写进判据免得重查):
//   ① 那个框是 0.56.0 `91d0aca` 按他自己的要求删的(「和左边图片对齐,底色和背景一样」)
//      —— **删掉的是装饰,顺手删掉的是 affordance**。
//   ② 收件箱卡**从来就不能拖放**:全 git 历史里 `InboxCard.tsx` 没出现过 onDrop。
//      原来那个框只是让人**以为**可以。
//   ③ 全应用能拖文件的只有图墙页和聊天输入卡,**落点都是收件箱** ——
//      东西叫收件箱、收件箱那块地方却不收东西,是真的反直觉。
// ⇒ 把收件箱卡本身做成落点,复用**已过审的写口** `uploadToInbox`(零新写口)。
//
// ⚠️ **写口只收图片**(`bin/ds_web.py::_safe_upload_name` → `ds_workspace.IMG_EXTS`:
//    png/jpg/jpeg/webp/gif,svg 明确排除)。放宽到 dwg/pdf = 动写口的安全面 = full lane
//    的另一单,本单不碰。所以拖非图片进来**必须当场说清楚**,不许静默失败 —— 见 D 段。
//
// 覆盖:
//   A 拖到收件箱卡上时,卡片**看得出来变了**(渲染值与静止态不同)= affordance。
//   B 松手 → 图片**真的落进磁盘上的 `00-收件箱`**(盘上验,不是看提示语)。
//   C 松手后高亮**退回静止态**(不许一直亮着)。
//   D 拖**非图片**进来 → 提示语必须同时说到「只收图片」和一条出路(打开文件夹/资源管理器),
//     且**不许有文件落盘**。静默无反应 = 不合格(本仓一贯:错误码不许裸怼给设计师)。
//   E 空箱那一态把入口**说出来**:那一行有「拖」字提示。两处代码,别只改一处。
//   F 【护栏】静止态**不许把 0.56 删掉的实框加回来**:收件箱卡在没拖东西时
//     无边框、不自带底色。用户 0.56 明确要求过"底色和背景一样"。
//   G 【护栏】「打开」按钮仍点得到(拖放层不许盖住它)。
//
// 跑法:node tests/e2e/inbox_drop.e2e.mjs(自起 ds_web 于 8828)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8828;
const PROJ = "翡翠湾-1801";
const FOLDER = "20260601 平湖 翡翠湾 3#1801";

const tmp = mkdtempSync(join(tmpdir(), "inboxdrop-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
mkdirSync(join(ws, FOLDER, "01-资料"), { recursive: true });
const INBOX = join(ws, "00-收件箱");
mkdirSync(INBOX, { recursive: true });

writeFileSync(join(dsRoot, "projects", `${PROJ}.md`), `# ${PROJ}

- 业主: [[李四]]
- 阶段: 施工跟进

## 变更记录

## 沟通日志

---
最后更新: 2026-08-01
`);
writeFileSync(
  join(dsRoot, "config", "workspace.json"),
  JSON.stringify({ root: ws, projectsDir: ".", projects: { [PROJ]: FOLDER } }),
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

const inboxFiles = () => readdirSync(INBOX).sort();

/** 轮询盘上文件,等写落地(UI→请求→落盘有毫秒级窗口)。 */
async function waitFor(fn, label, timeoutMs = 8000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    if (fn()) return true;
    await new Promise((r) => setTimeout(r, 120));
  }
  return false;
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

const CARD = ".inbox-card";
let browser = null;

try {
  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  const gotoWs = async () => {
    // 显式 reload:goto 到相同 URL 只做同文档 hash 跳转,收件箱数据会停在旧快照
    // (inbox_open_button.e2e.mjs 里栽过,红得不干净 = 等于没判)。
    await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.locator(CARD).waitFor({ timeout: 15000 });
  };

  /** 造一个带真文件的 DataTransfer(留在页面里,dragover/drop 复用同一个)。 */
  const makeDT = async (name, mime, bytes) => page.evaluateHandle(
    ({ name, mime, bytes }) => {
      const dt = new DataTransfer();
      dt.items.add(new File([new Uint8Array(bytes)], name, { type: mime }));
      return dt;
    },
    { name, mime, bytes },
  );

  // 1×1 PNG 的字节
  const PNG_BYTES = [...Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
    "base64")];

  /** 卡片的渲染指纹(A/C/F 三段都用它)。 */
  const cardLook = async () => page.evaluate((sel) => {
    const el = document.querySelector(sel);
    const s = getComputedStyle(el);
    return {
      border: `${s.borderTopWidth} ${s.borderTopStyle} ${s.borderTopColor}`,
      outline: s.outlineStyle === "none" ? "0" : `${s.outlineWidth} ${s.outlineStyle}`,
      bg: s.backgroundColor,
      cls: el.className,
      text: el.innerText,
    };
  }, CARD);

  // ── F 【护栏】静止态不许把实框加回来 ────────────────────────────────────
  // 先跑 F:它量的是"什么都没拖时"的样子,后面几段会把卡片搞脏。
  await step("F 【护栏】静止态无边框、不自带底色(0.56 用户要求过)", async () => {
    await gotoWs();
    const g = await cardLook();
    expect(/none/.test(g.border) || parseFloat(g.border) === 0,
      `静止态无边框(实测 ${g.border})`);
    expect(g.outline === "0", `静止态无外环(实测 ${g.outline})`);
    expect(g.bg === "rgba(0, 0, 0, 0)" || g.bg === "transparent",
      `静止态不自带底色,跟背景一样(实测 ${g.bg})`);
  });

  // ── A 拖上去看得出来 ────────────────────────────────────────────────────
  await step("A 拖文件到收件箱卡上,卡片看得出来变了(affordance)", async () => {
    await gotoWs();
    const idle = await cardLook();
    const dt = await makeDT("客厅效果图.png", "image/png", PNG_BYTES);
    await page.dispatchEvent(CARD, "dragenter", { dataTransfer: dt });
    await page.dispatchEvent(CARD, "dragover", { dataTransfer: dt });
    await page.waitForTimeout(150);
    const over = await cardLook();
    expect(over.border !== idle.border || over.outline !== idle.outline
           || over.bg !== idle.bg,
      `拖上去后渲染值确实变了(静止 ${idle.border} / ${idle.outline} / ${idle.bg}` +
      ` → 拖上去 ${over.border} / ${over.outline} / ${over.bg})`);
    // 光换个 class 不算 —— 上面比的就是渲染值。这里再要求"说人话"的提示出现。
    expect(/收件箱|松手|存进/.test(over.text.replace(idle.text, "")) || over.text !== idle.text,
      "拖上去时页面上多出了提示文字(不是只有颜色变化)");
    // C 段验它退得回去
    await page.dispatchEvent(CARD, "dragleave", { dataTransfer: dt });
    await page.waitForTimeout(150);
    const left = await cardLook();
    expect(left.border === idle.border && left.outline === idle.outline,
      `拖走后退回静止态(实测 ${left.border} / ${left.outline})`);
  });

  // ── B 松手真的落盘 ──────────────────────────────────────────────────────
  await step("B 松手 → 图片真的落进磁盘上的 00-收件箱", async () => {
    await gotoWs();
    check(inboxFiles().length === 0, `前提:收件箱是空的(实测 ${JSON.stringify(inboxFiles())})`);
    const dt = await makeDT("客厅效果图.png", "image/png", PNG_BYTES);
    await page.dispatchEvent(CARD, "dragenter", { dataTransfer: dt });
    await page.dispatchEvent(CARD, "dragover", { dataTransfer: dt });
    await page.dispatchEvent(CARD, "drop", { dataTransfer: dt });
    const landed = await waitFor(() => inboxFiles().includes("客厅效果图.png"),
      "图片落盘");
    expect(landed, `图片落进 00-收件箱(实测目录内容 ${JSON.stringify(inboxFiles())})`);
  });

  // ── C 松手后高亮退回去 ──────────────────────────────────────────────────
  await step("C 松手后高亮退回静止态(不许一直亮着)", async () => {
    await page.waitForTimeout(300);
    const after = await cardLook();
    expect(after.outline === "0",
      `drop 之后不再有拖拽外环(实测 ${after.outline})`);
    expect(/none/.test(after.border) || parseFloat(after.border) === 0,
      `drop 之后不再有拖拽边框(实测 ${after.border})`);
  });

  // ── D 非图片:说清楚,且不落盘 ──────────────────────────────────────────
  await step("D 拖非图片进来 → 说清「只收图片」+ 一条出路,且不落盘", async () => {
    await gotoWs();
    const before = inboxFiles();
    const dt = await makeDT("户型图.dwg", "application/octet-stream", [1, 2, 3]);
    await page.dispatchEvent(CARD, "dragenter", { dataTransfer: dt });
    await page.dispatchEvent(CARD, "dragover", { dataTransfer: dt });
    await page.dispatchEvent(CARD, "drop", { dataTransfer: dt });
    await page.waitForTimeout(800);
    const txt = (await cardLook()).text;
    expect(/图片/.test(txt), `提示语说到"只收图片"(实测卡片文案 ${JSON.stringify(txt)})`);
    // ⚠️ 别写成 /打开/ —— 静止文案里本来就有「打开」两字,那样这条**永远是绿的**
    //(红检当场抓到的假绿)。要的是"出路"这层新增信息,静止态没有的词才算数。
    expect(/文件夹|资源管理器/.test(txt),
      `提示语给了一条出路(自己打开文件夹放进去)(实测 ${JSON.stringify(txt)})`);
    expect(JSON.stringify(inboxFiles()) === JSON.stringify(before),
      `非图片没有落盘(实测 ${JSON.stringify(inboxFiles())})`);
  });

  // ── D2 提示条里的「知道了」不许被压成竖排 ────────────────────────────────
  // 🔴 **收货截图抓到的**,不是事前想到的:提示条是 `display:flex`,「知道了」没有
  // `flex: none`,在收件箱这条**窄列**里被压到比一个字还窄 ⇒ 「知/道/了」竖排三行。
  // 图墙那边有整页宽度,同一份 CSS 一直看不出来 —— **同一个组件换了个窄容器就现原形**,
  // 和 07-27「确认执行被挤成两行」是同一种病(button_roles F 段)。
  // ⇒ 观感类改动收尾必须截图,这条判据是把那次肉眼发现固化下来。
  await step("D2 提示里的「知道了」不被压成竖排(窄列里也装得下)", async () => {
    const g = await page.evaluate(() => {
      const b = [...document.querySelectorAll('.inbox-card .upload-note button')]
        .find((x) => x.innerText.trim() === "知道了");
      if (!b) return null;
      const cs = getComputedStyle(b);
      return {
        h: Math.round(b.getBoundingClientRect().height),
        lineH: parseFloat(cs.lineHeight) || 16,
        scrollW: b.scrollWidth, clientW: b.clientWidth,
      };
    });
    check(g !== null, "前提:「知道了」渲染出来了(D 段刚拖过一个非图片)");
    expect(g.scrollW <= g.clientW + 1,
      `文字没被横向裁掉(内容宽 ${g.scrollW} ≤ 可视宽 ${g.clientW})`);
    expect(g.h <= g.lineH * 1.9,
      `没被压成两行以上(按钮高 ${g.h} / 行高 ${g.lineH})`);
  });

  // ── E 空箱那一态也把入口说出来 ──────────────────────────────────────────
  await step("E 空箱态那一行有「拖」字提示(两处代码别只改一处)", async () => {
    for (const f of inboxFiles()) rmSync(join(INBOX, f), { force: true });
    const api = await (await fetch(`${base}/api/intake`)).json();
    check(api.entries.length === 0 && api.pending.length === 0,
      `前提:后端已是空箱(entries ${api.entries.length} / pending ${api.pending.length})`);
    await gotoWs();
    await page.locator(".inbox-quiet").waitFor({ timeout: 15000 });
    const txt = (await cardLook()).text;
    expect(/拖/.test(txt), `空箱那一行把入口说出来了(实测 ${JSON.stringify(txt)})`);
  });

  // ── G 【护栏】「打开」按钮没被拖放层盖住 ────────────────────────────────
  await step("G 【护栏】「打开」按钮仍点得到(拖放层不许盖住它)", async () => {
    await gotoWs();
    const btn = page.locator('[data-ui="inbox-open"]').first();
    await btn.waitFor({ timeout: 15000 });
    expect(await btn.isVisible(), "按钮可见");
    // trial:真做一次命中测试(有覆盖层挡着就会失败),但不真触发打开资源管理器
    await btn.click({ trial: true, timeout: 5000 });
    console.log("  ok - 按钮命中测试通过(没有覆盖层挡路)");
  });
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}

console.log(failures === 0 ? "\n全部通过" : `\n${failures} 条不通过`);
process.exit(failures === 0 ? 0 : 1);
