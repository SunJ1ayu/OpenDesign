// 输入框选中态(focus ring)的一致性 e2e(真 chromium + 真 ds_web)。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// 用户 2026-08-01 真机原话(L):「待办事项的项目助手选中后的外框红色描边粗细和别的窗口
// 不一样,别的窗口会细一点,比如项目工作区的项目助手」。
//
// 主 agent 查实的病根(写进判据免得重查):全局兜底
//   `button:focus-visible, …, input:focus-visible { outline: 2px solid var(--terra) }`
// 是给键盘可达性兜底的。**已经自己表达了选中态的输入框**(靠 1px 边框变色)必须显式
// `outline: none` 把兜底关掉,否则 2px 外环 + 1px 边框叠在一起 = 用户看到的"粗"。
// 全仓 8 个文本输入框里,**只有两个漏关**:
//   `.rail-ask-input`(待办页右栏项目助手,用户点到的那个)
//   `.ref-edit-note`(图墙 lightbox 里的参考图备注框)—— **第三处,他还没看见**。
// K 那条的教训就是"只改他点到的那一处,下次他再指另一处",所以两处一起判。
//
// 覆盖:
//   A 【基准·改动前应为绿】项目工作区快记卡输入框:选中后**不吃 2px 外环**,
//     且选中态**看得出来**(自己或最近的带边框祖先边框变色)。
//     这一段先绿证明"判据量得准" —— B/C 红才是"功能不存在",不是量法不对。
//   B 待办页右栏「项目助手」输入框:同 A 的两条。
//   C 图墙 lightbox 里的参考图「备注」框:同 A 的两条。
//   D **三处的选中环粗细完全相同** —— 用户说的是"粗细不一样",一致性才是主张本身。
//   E 【护栏】**全局 `:focus-visible` 兜底不许被删**:按钮键盘聚焦后仍有 ≥2px 外环。
//     不设这条,执行腿把全局那几行删掉能让 A–D 全绿,代价是键盘用户全应用失去焦点提示。
//
// 跑法:node tests/e2e/focus_ring.e2e.mjs(自起 ds_web 于 8826)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8826;
const PROJ = "翡翠湾-1801";
const FOLDER = "20260601 平湖 翡翠湾 3#1801";

const tmp = mkdtempSync(join(tmpdir(), "focusring-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
mkdirSync(join(dsRoot, "refs", "奶油风", "客厅"), { recursive: true });
mkdirSync(join(ws, FOLDER, "06-效果图"), { recursive: true });
mkdirSync(join(ws, "00-收件箱"), { recursive: true });

writeFileSync(join(dsRoot, "projects", `${PROJ}.md`), `# ${PROJ}

- 业主: [[李四]]
- 阶段: 方案深化

## 变更记录
- [待确认] C1 2026-07-15 【主卧】灯位右移 30cm
- [进行中] C2 2026-07-16 玄关柜改高

## 沟通日志

---
最后更新: 2026-08-01
`);

const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64");
writeFileSync(join(dsRoot, "refs", "奶油风", "客厅", "a.jpg"), PNG);
writeFileSync(join(dsRoot, "refs-index.md"), `# 参考图索引

- [r1] 奶油风|客厅 | 来源:小红书 | 文件:refs/奶油风/客厅/a.jpg | 用于:${PROJ} | 备注:弧形吊顶

---
最后更新: 2026-08-01
`);
writeFileSync(join(dsRoot, "refs-vocab.md"), `# 风格词表

## 风格
- 奶油风
- 侘寂风
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
const rings = {};

try {
  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  /** 量一个输入框的选中态。
   *  - `outline`:外环用值。`outline-style: none` 时用值就是 0,两种写法都认。
   *  - `edge`:**自己或最近的带边框祖先**的 border-top-color。三处输入框结构不同
   *    (有的边框在自己身上,有的在外层卡片上),所以不能写死量哪一层 ——
   *    要量的是"用户看到那一圈线"的颜色,不是某个选择器写没写。 */
  const measure = async (sel) => page.evaluate((s) => {
    const el = document.querySelector(s);
    if (!el) return null;
    const edgeOf = (node) => {
      for (let n = node, i = 0; n && i < 4; n = n.parentElement, i++) {
        const cs = getComputedStyle(n);
        if (parseFloat(cs.borderTopWidth) > 0) {
          return { color: cs.borderTopColor, width: cs.borderTopWidth };
        }
      }
      return { color: "", width: "" };
    };
    const cs = getComputedStyle(el);
    return {
      outline: cs.outlineStyle === "none" ? 0 : parseFloat(cs.outlineWidth) || 0,
      edge: edgeOf(el),
    };
  }, sel);

  /** 点进去(真实用户动作 —— 程序化 focus 与 `:focus-visible` 的匹配规则不同,
   *  用点击才量得到用户真正看到的那一环)。 */
  const focusAndMeasure = async (sel, label) => {
    const before = await measure(sel);
    check(before !== null, `前提:${label} 在场`);
    await page.locator(sel).click();
    await page.waitForTimeout(120);           // 让 transition 走完
    const after = await measure(sel);
    return { before, after };
  };

  const assertRing = async (sel, label, key) => {
    const { before, after } = await focusAndMeasure(sel, label);
    expect(after.outline === 0,
      `${label} 选中后不吃全局 2px 外环(实测 ${after.outline}px)`);
    expect(after.edge.color !== before.edge.color,
      `${label} 选中态仍看得出来:边框颜色变了(${before.edge.color} → ${after.edge.color})`);
    // 记下"用户看到的那一圈线有多粗",D 段比一致性:外环 + 边框
    rings[key] = `${after.outline}px + ${after.edge.width}`;
  };

  // ── A 基准(改动前应为绿)────────────────────────────────────────────────
  await step("A 【基准】项目工作区快记卡输入框:细边框、无 2px 外环", async () => {
    await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.locator('[data-ui="quicknote-input"]').waitFor({ timeout: 15000 });
    await assertRing('[data-ui="quicknote-input"]', "快记卡输入框", "quicknote");
  });

  // ── B 用户点到的那一处 ──────────────────────────────────────────────────
  await step("B 待办页右栏「项目助手」输入框", async () => {
    await page.goto(`${base}/#/todos`, { waitUntil: "domcontentloaded" });
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.locator('[data-ui="rail-ask"]').waitFor({ timeout: 15000 });
    await assertRing('[data-ui="rail-ask"]', "待办页项目助手输入框", "railAsk");
  });

  // ── C 第三处(他还没看见的那个)──────────────────────────────────────────
  await step("C 图墙 lightbox 里的参考图「备注」框", async () => {
    await page.goto(`${base}/#/gallery`, { waitUntil: "domcontentloaded" });
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.locator(".gallery-page").waitFor({ timeout: 15000 });
    await page.locator('.gallery-page .g-cell:has(.g-cap .g:text-is("参考"))')
      .first().click();
    await page.locator('[data-ui="ref-note-input"]').waitFor({ timeout: 10000 });
    await assertRing('[data-ui="ref-note-input"]', "参考图备注框", "refNote");
  });

  // ── D 三处粗细完全相同 ──────────────────────────────────────────────────
  await step("D 三处的选中环粗细完全相同(用户说的就是「粗细不一样」)", async () => {
    const got = JSON.stringify(rings);
    const vals = Object.values(rings);
    check(vals.length === 3, `前提:三处都量到了(实测 ${got})`);
    expect(vals[0] === vals[1] && vals[1] === vals[2], `三处一致(实测 ${got})`);
  });

  // ── E 【护栏】全局键盘焦点环不许被删 ─────────────────────────────────────
  await step("E 【护栏】按钮的全局 :focus-visible 外环仍在(≥2px)", async () => {
    await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
    await page.reload({ waitUntil: "domcontentloaded" });
    const btn = page.locator('[data-ui="inbox-open"]').first();
    await btn.waitFor({ timeout: 15000 });
    // 键盘聚焦:按钮只有在键盘路径上才匹配 :focus-visible(鼠标点不算)
    await page.evaluate(() => {
      document.querySelector('[data-ui="inbox-open"]').focus();
    });
    await page.keyboard.press("Tab");
    await page.keyboard.press("Shift+Tab");
    await page.waitForTimeout(120);
    const w = await page.evaluate(() => {
      const el = document.querySelector('[data-ui="inbox-open"]');
      const cs = getComputedStyle(el);
      return cs.outlineStyle === "none" ? 0 : parseFloat(cs.outlineWidth) || 0;
    });
    expect(w >= 2,
      `按钮键盘聚焦仍有 ≥2px 外环(实测 ${w}px)—— 全局兜底不许为了修 L 而删掉`);
  });
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}

console.log(failures === 0 ? "\n全部通过" : `\n${failures} 条不通过`);
process.exit(failures === 0 ? 0 : 1);
