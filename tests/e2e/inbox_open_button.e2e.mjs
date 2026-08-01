// 收件箱「打开」按钮的形制契约 e2e(真 chromium + 真 ds_web)。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// 用户 07-31 真机原话:「收件箱的打开按钮,也是打开→ 比较丑,有没有什么规范,正常的
// 软件工程他们是怎么做的呢,**这种按钮和发送给项目助手聊天的这种按钮应该要有区别吧**」
// 追加:「不需要箭头」。
//
// 主 agent 查实的病根(写进判据免得重查):**按位置命名而不是按角色命名。**
// 这个按钮用的 class 叫 `.gallery-link` —— 是从图墙「图墙 →」那条链接抄来的,
// 而那条链接用户 0.54.0 已经让我删了,class 却留下来长在了收件箱上。名字在撒谎。
// 全应用其实早就有三档角色 class(`.btn-primary` 主 / `.btn-secondary` 次 /
// `.link-act` 文字),CSS 里连用途注释都写了,只是没在用。
//
// 本单**只收编收件箱这一处**,不做全应用清点(那是 tasks.md 的 H,单独起 track)。
//
// 🔴 2026-08-01 改写 B/C(真机退回,K):**主 agent 认错,不是需求变更。**
// 用户 07-31 的原话是「都用一样的**白框然后里面字**」,是**具体形状指令**;我却按自己的
// 「层级论」把它做成了无框文字按钮(理由:同行的『扫描整理』才是主动作)。他 08-01 回:
// 「**我一直说的都是**收件箱的打开按钮,应该是一个白底的按钮,和左边项目文件夹的
// 打开文件夹一样的按钮!」
// ⇒ **抽象原则不许覆盖用户的具体形状指令。**
//
// **为什么改判据不是放松**(本仓规矩:改判据要当场证明比旧的严):
//   旧 B/C 钉的是**这一个按钮自己长什么样**(没边框 / 不填底 / 挂 .link-act)——
//   只约束一处,跨组件长不长得一样它管不着。
//   新 B/C 钉的是**跨组件外观全等**:「打开」与页面上**每一个**「打开文件夹」computed
//   逐字段相同,再加上同一行「扫描整理」与它等高。约束面从 1 处扩到 3 处,
//   而且"同一个动作只许有一种长相"这条恰恰是 0.66/0.67 两单立的规矩 —— 旧判据
//   与那条规矩是矛盾的,新判据把矛盾消掉。
//
// 覆盖:
//   A 「打开」上**没有箭头**,文字就是「打开」。箭头字符整类都挡(← → ↗ ⧉ …),
//     不是只挡当时那一个 —— 否则下次换个符号照样溜进来。
//   B 「打开」与页面上**每一个**「打开文件夹」**computed 外观逐字段全等**
//     (边框/圆角/底色/字色/字号/高度/内边距)。断言打在渲染值上,不是 class 名 ——
//     class 名相同也可能被别处规则覆盖成两个样(button_roles 那单的老教训)。
//   C 「打开」挂共享的 `.btn-secondary`,且不再挂 `.link-act` / `.gallery-link`。
//     ⚠️ 这条是**唯一一条按 class 名断言的**,因为"用不用共享角色 class"正是规范
//     落没落地的可验形式;A/B 才是观感。
//   C2 同一行的「扫描整理」与「打开」**等高**:两个白框按钮并排,一个 28px 一个 24px
//     (`.btn-secondary.sm`)会比统一前更难看。**这条是本次新增的约束**,不是原样保留。
//   D 空箱那一态(`state === "empty"`)的同一个按钮也改到了 —— 两处代码,别只改一处。
//   E 【护栏】按钮还在、可见、可点、带 title(0.52.0「常驻打开入口」的既有契约不许退化;
//     `chat_image.e2e.mjs` 也钉了这个 data-ui)。
//
// 跑法:node tests/e2e/inbox_open_button.e2e.mjs(自起 ds_web 于 8820)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8820;
const PROJ = "翡翠湾-1801";
const FOLDER = "20260601 平湖 翡翠湾 3#1801";

// 箭头**整类**,用码位区间写,免得靠肉眼比对字形:
//   2190–21FF 箭头 · 2794–27BF 装饰箭头 · 27F0–27FF 补充箭头A · 2900–297F 补充箭头B
//   2B00–2BFF 杂项符号与箭头 · FFE9–FFEC 全角箭头 · 29C9 外链方框(⧉)
const ARROWS = /[←-⇿➔-➿⟰-⟿⤀-⥿⬀-⯿￩-￬⧉]/u;

const tmp = mkdtempSync(join(tmpdir(), "inboxbtn-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
mkdirSync(join(ws, FOLDER, "01-资料"), { recursive: true });
mkdirSync(join(ws, "00-收件箱"), { recursive: true });

writeFileSync(join(dsRoot, "projects", `${PROJ}.md`), `# ${PROJ}

- 业主: [[李四]]
- 阶段: 施工跟进

## 变更记录

## 沟通日志

---
最后更新: 2026-07-31
`);
writeFileSync(
  join(dsRoot, "config", "workspace.json"),
  JSON.stringify({ root: ws, projectsDir: ".", projects: { [PROJ]: FOLDER } }),
);

// 收件箱里先放两个文件 ⇒ 卡片进「有待整理条目」那一态(A/B/C/E 验这一态);
// D 段再把文件删光、重进页面,验「空箱」那一态的同一个按钮。
const INBOX = join(ws, "00-收件箱");
writeFileSync(join(INBOX, "翡翠湾户型图.dwg"), "DWG");
writeFileSync(join(INBOX, "神秘文件.xyz"), "x");

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

let browser = null;
try {
  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // ⚠️ 必须显式 reload():`goto` 到**完全相同的 URL**(这里每次都是 `#/workspace`)
  // 只做同文档的 hash 跳转,**不重载文档** ⇒ React 不重挂、收件箱数据停在上一次的快照。
  // 写这份判据时在 D 段栽过:后端明明已空箱,卡片还显示「收件箱 2」,一度以为是产品
  // bug(「文件删了界面不更新」),实测是判据自己没重载。**红得不干净 = 等于没判。**
  const gotoWs = async () => {
    await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.locator('[data-ui="inbox-open"]').waitFor({ timeout: 15000 });
  };

  const look = async () => page.evaluate(() => {
    // 外观指纹:**只放"看得见的形状"字段**。渲染值相等才算"一样的按钮",
    // class 名相等不算(class 相同也可能被别处规则覆盖成两个样)。
    const shape = (el) => {
      const s = getComputedStyle(el);
      return {
        border: `${s.borderTopWidth} ${s.borderTopStyle} ${s.borderTopColor}`,
        radius: s.borderTopLeftRadius,
        bg: s.backgroundColor,
        color: s.color,
        fontSize: s.fontSize,
        height: s.height,
        padding: `${s.paddingTop} ${s.paddingRight} ${s.paddingBottom} ${s.paddingLeft}`,
      };
    };
    const one = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      return { text: el.innerText.trim(), cls: el.className, ...shape(el) };
    };
    // 页面上所有「打开文件夹」——按**文字**找,不按 class 找:判据不能预设它们挂什么
    // class(那正是被收编的东西)。CompanionColumn 里有两处(文件区题头 / 空图态)。
    const folders = [...document.querySelectorAll("button")]
      .filter((b) => b.innerText.trim() === "打开文件夹")
      .map((b) => ({ cls: b.className, ...shape(b) }));
    return {
      open: one('[data-ui="inbox-open"]'),
      // 同一行的另一个白框按钮:扫描整理。C2 要它与「打开」等高。
      scan: one(".inbox-summary .btn-secondary:not([data-ui='inbox-open'])"),
      folders,
    };
  });

  // ── A 没有箭头 ───────────────────────────────────────────────────────────
  await step("A 「打开」不带箭头,文字就是「打开」", async () => {
    await gotoWs();
    const g = await look();
    check(g.open !== null, "前提:收件箱「打开」按钮在场");
    expect(g.open.text === "打开", `按钮文字是「打开」(实测 ${JSON.stringify(g.open.text)})`);
    expect(!ARROWS.test(g.open.text),
      `按钮文字不含任何箭头字符(实测 ${JSON.stringify(g.open.text)})`);
  });

  // ── B 与「打开文件夹」外观全等 ───────────────────────────────────────────
  // 用户 08-01 原话:「应该是一个白底的按钮,**和左边项目文件夹的打开文件夹一样的按钮**」。
  // 「一样」= 渲染值逐字段相同,不是"也是个按钮"。
  const SHAPE_KEYS = ["border", "radius", "bg", "color", "fontSize", "height", "padding"];
  const fingerprint = (o) => JSON.stringify(Object.fromEntries(
    SHAPE_KEYS.map((k) => [k, o[k]])));

  await step("B 「打开」与页面上每一个「打开文件夹」外观全等", async () => {
    await gotoWs();
    const g = await look();
    check(g.folders.length >= 1, `前提:页面上有「打开文件夹」可比(实测 ${g.folders.length} 个)`);
    // 先确认「打开文件夹」自己是白框按钮 —— 否则"两边一样"可能是**一起错**
    // (两个都变成无框文字按钮也能让全等断言变绿)。这条是防"以错为准"的锚。
    const f0 = g.folders[0];
    expect(/solid/.test(f0.border) && parseFloat(f0.border) >= 1,
      `锚:「打开文件夹」本身是描边按钮(实测 border ${f0.border})`);
    expect(f0.bg === "rgb(255, 255, 255)",
      `锚:「打开文件夹」本身是白底(实测 ${f0.bg})`);
    // 再比全等
    for (const [i, f] of g.folders.entries()) {
      expect(fingerprint(g.open) === fingerprint(f),
        `与第 ${i + 1} 个「打开文件夹」外观全等\n      打开 = ${fingerprint(g.open)}\n      文件夹 = ${fingerprint(f)}`);
    }
  });

  // ── C 挂共享角色 class ───────────────────────────────────────────────────
  await step("C 「打开」挂共享的 .btn-secondary,不再挂 .link-act / .gallery-link", async () => {
    await gotoWs();
    const g = await look();
    expect(/\bbtn-secondary\b/.test(g.open.cls),
      `挂共享的 .btn-secondary(实测 class ${JSON.stringify(g.open.cls)})`);
    expect(!/\blink-act\b/.test(g.open.cls),
      `不再挂 .link-act(实测 class ${JSON.stringify(g.open.cls)})`);
    expect(!/\bgallery-link\b/.test(g.open.cls),
      `不再挂 .gallery-link(实测 class ${JSON.stringify(g.open.cls)})`);
  });

  // ── C2 同一行两个白框按钮等高 ────────────────────────────────────────────
  await step("C2 同一行的「扫描整理」与「打开」等高(不许一大一小)", async () => {
    await gotoWs();
    const g = await look();
    check(g.scan !== null, "前提:同一行的「扫描整理」在场");
    expect(g.scan.height === g.open.height,
      `两者等高(扫描整理 ${g.scan.height} / 打开 ${g.open.height})`);
    expect(g.scan.fontSize === g.open.fontSize,
      `两者字号相同(扫描整理 ${g.scan.fontSize} / 打开 ${g.open.fontSize})`);
  });

  // ── D 空箱那一态也改到了 ─────────────────────────────────────────────────
  await step("D 空箱那一态的同一个按钮也改到了(两处代码别只改一处)", async () => {
    rmSync(join(INBOX, "翡翠湾户型图.dwg"), { force: true });
    rmSync(join(INBOX, "神秘文件.xyz"), { force: true });
    // 先隔着 HTTP 确认后端真的进了空箱态 —— 否则这一段红了分不清是
    // 「按钮没改」还是「夹具没把箱子清空」(红得不干净就等于没判)。
    const api = await (await fetch(`${base}/api/intake`)).json();
    check(api.entries.length === 0 && api.pending.length === 0,
      `前提:后端已是空箱(entries ${api.entries.length} / pending ${api.pending.length})`);
    await gotoWs();
    await page.locator(".inbox-quiet").waitFor({ timeout: 15000 }); // 「空的」= 这一态的标志
    const g = await look();
    expect(g.open.text === "打开", `空箱态文字也是「打开」(实测 ${JSON.stringify(g.open.text)})`);
    expect(!ARROWS.test(g.open.text), "空箱态也不含箭头");
    expect(/\bbtn-secondary\b/.test(g.open.cls) && !/\blink-act\b/.test(g.open.cls)
           && !/\bgallery-link\b/.test(g.open.cls),
      `空箱态也用 .btn-secondary(实测 ${JSON.stringify(g.open.cls)})`);
    check(g.folders.length >= 1, "前提:空箱态页面上也有「打开文件夹」可比");
    expect(fingerprint(g.open) === fingerprint(g.folders[0]),
      `空箱态也与「打开文件夹」外观全等\n      打开 = ${fingerprint(g.open)}\n      文件夹 = ${fingerprint(g.folders[0])}`);
    // 复原,免得影响后面的段
    writeFileSync(join(INBOX, "翡翠湾户型图.dwg"), "DWG");
  });

  // ── E 【护栏】常驻打开入口不许退化 ───────────────────────────────────────
  await step("E 【护栏】按钮仍在、可见、可点、带 title", async () => {
    await gotoWs();
    const btn = page.locator('[data-ui="inbox-open"]').first();
    expect(await btn.isVisible(), "按钮可见");
    expect(await btn.isEnabled(), "按钮可点(没被 disabled)");
    const title = await btn.getAttribute("title");
    expect(title !== null, `按钮带 title(实测 ${JSON.stringify(title)})`);
  });
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}

console.log(failures === 0 ? "\n全部通过" : `\n${failures} 条不通过`);
process.exit(failures === 0 ? 0 : 1);
