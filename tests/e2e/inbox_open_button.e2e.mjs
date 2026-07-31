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
// 覆盖:
//   A 「打开」上**没有箭头**,文字就是「打开」。箭头字符整类都挡(← → ↗ ⧉ …),
//     不是只挡当时那一个 —— 否则下次换个符号照样溜进来。
//   B 「打开」与同一行的「扫描整理」**层级看得出差别**:扫描整理是这张卡的主动作
//     (描边 + 白底的次按钮),打开是辅助动作(文字按钮,无边框、不填底)。
//     断言打在 computed 上 —— 用户说的"有区别"是**看得出来的区别**,不是 class 名不同。
//   C 「打开」不再挂 `.gallery-link`(名字撒谎的那个),改用共享的文字按钮角色 class。
//     ⚠️ 这条是**唯一一条按 class 名断言的** —— 因为用户问的就是"有没有规范",
//     而"用不用共享角色 class"正是规范落没落地的可验形式。A/B 才是观感。
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
    const one = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const s = getComputedStyle(el);
      return {
        text: el.innerText.trim(),
        cls: el.className,
        borderW: s.borderTopWidth,
        borderStyle: s.borderTopStyle,
        bg: s.backgroundColor,
        color: s.color,
      };
    };
    return {
      open: one('[data-ui="inbox-open"]'),
      // 同一行的主动作:扫描整理。它才是这张卡的次按钮档,打开必须比它低一档。
      scan: one(".inbox-summary .btn-secondary"),
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

  // ── B 与「扫描整理」层级看得出差别 ───────────────────────────────────────
  await step("B 「打开」比同行的「扫描整理」低一档(看得出来的差别)", async () => {
    await gotoWs();
    const g = await look();
    check(g.scan !== null, "前提:同一行的「扫描整理」次按钮在场");
    expect(g.scan.borderStyle === "solid" && parseFloat(g.scan.borderW) >= 1,
      `扫描整理是描边按钮(border ${g.scan?.borderW} ${g.scan?.borderStyle})`);
    const openNoBorder =
      g.open.borderStyle === "none" || parseFloat(g.open.borderW) === 0;
    expect(openNoBorder,
      `打开没有边框(border ${g.open.borderW} ${g.open.borderStyle})`);
    expect(g.open.bg === "rgba(0, 0, 0, 0)" || g.open.bg === "transparent",
      `打开不填底色(实测 ${g.open.bg})`);
    expect(g.open.bg !== g.scan.bg || openNoBorder,
      "两者外观确有差别,不是同一种按钮");
  });

  // ── C 不再挂名字撒谎的 .gallery-link ─────────────────────────────────────
  await step("C 「打开」改用共享的文字按钮角色 class,不再挂 .gallery-link", async () => {
    await gotoWs();
    const g = await look();
    expect(!/\bgallery-link\b/.test(g.open.cls),
      `不再挂 .gallery-link(实测 class ${JSON.stringify(g.open.cls)})`);
    expect(/\blink-act\b/.test(g.open.cls),
      `改用共享的 .link-act(实测 class ${JSON.stringify(g.open.cls)})`);
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
    expect(/\blink-act\b/.test(g.open.cls) && !/\bgallery-link\b/.test(g.open.cls),
      `空箱态也用 .link-act(实测 ${JSON.stringify(g.open.cls)})`);
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
