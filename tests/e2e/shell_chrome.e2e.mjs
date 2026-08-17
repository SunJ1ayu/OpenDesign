// 无边框窗口的窗口栏**到底会不会被画出来**(真 chromium + 真 ds_web)。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// 业主 2026-08-17 装完 0.90.0 的原话:
//   「1、这个页面为什么我拖不动 现在是固定住了吗 2、右上角还是没有缩小放大和退出」
//
// 0.89.0 把系统标题栏拿掉了(`frameless=True`),三个按钮 + 顶部 30px 拖动带 +
// 八个边角把手改由前端自己画。业主机器上**这三样一样都没出现** —— `WindowChrome`
// 在"我不在外壳里"这个判断下 `return null`,一次性全撤。
//
// 病根:那个判断原来问的是 `window.pywebview.api` 在不在,而 pywebview 5.4 的
// Windows 后端在 `on_navigation_completed` 之后才注入(edgechromium.py:314)——
// **页面脚本早跑完了**,所以那一问永远答 false。改成外壳在地址里报身份(`?shell=1`),
// 第一帧就在。
//
// 🔴 这份 e2e 存在的理由不是"多一层保险",是**这一层原来在 Linux 上一条判据都没有**:
//    现存 12 条判据问的全是名字对不对、层号对不对、把手贴不贴边 —— 没有一条问过
//    "这条栏会不会被画出来"。那件事被推给了真机清单,而那趟业主一直没走,
//    于是 0.89/0.90 两版带着同一个病发出去。地址标记没有 pywebview 依赖 ⇒
//    真 chromium 能直接考,从此每次 e2e 总跑都在问。
//
// 覆盖:
//   A 【病本身·修复前必红】`/?shell=1`:三个按钮**可见**、拖动带在场、
//     八个把手都在、body 让出 30px。
//   B 【浏览器】`/`:三个按钮一个都不许在(那边没有窗口可关,画出来就是死按钮),
//     且 body 不许白让 30px。
//   C 【命中测试】把 x8 的"层号结构"断言换成真浏览器里的行为:关闭按钮中心点下去
//     必须是关闭按钮(不是把手、不是栏);顶边 2px 是把手;顶边 15px 是拖动带。
//   D 【别盖住拖动带】界面往下让 30px 之后,页面上真正的元素不许伸进 0~30px 那条 ——
//     否则业主看着有栏、按下去在点别的东西(这正是"拖不动"的另一种长相)。
//
// 跑法:node tests/e2e/shell_chrome.e2e.mjs(自起 ds_web 于 8840)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8840;
const PROJ = "翡翠湾-1801";
const FOLDER = "20260601 平湖 翡翠湾 3#1801";
const BAR_H = 30;                     // app.css 的 .win-bar 高度 / body padding-top

const tmp = mkdtempSync(join(tmpdir(), "shellchrome-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
mkdirSync(join(ws, FOLDER, "06-效果图"), { recursive: true });
mkdirSync(join(ws, "00-收件箱"), { recursive: true });

writeFileSync(join(dsRoot, "projects", `${PROJ}.md`), `# ${PROJ}

- 业主: [[李四]]
- 阶段: 方案深化

## 变更记录
- [待确认] C1 2026-07-15 【主卧】灯位右移 30cm

## 沟通日志

---
最后更新: 2026-08-17
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

const BTNS = [
  ['[data-ui="window-min"]', "最小化"],
  ['[data-ui="window-max"]', "最大化"],
  ['[data-ui="window-close"]', "关闭"],
];

let browser = null;
try {
  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1280, height: 860 } });

  /** 打开工作区页面并等前端真的挂上来。
   *
   *  🔴 等的元素不许是 `.ws-pane, .home-pane` 那种裸选择器 + `.first()` ——
   *  两个 pane 都常驻挂载、靠 `.route-hidden` 藏,`.first()` 恒中那个**隐藏的**
   *  home-pane,于是 20 秒后超时红在"页面没起来"上(和本单要查的病长得一样)。
   *  同族的坑 07-24 记过一次(frontend_p1 的 connect-card)。等侧栏:它一直可见。 */
  const open = async (query) => {
    await page.goto(`${base}/${query}#/workspace`, { waitUntil: "domcontentloaded" });
    await page.reload({ waitUntil: "domcontentloaded" });   // hash 路由:reload 才认
    await page.locator("nav.side").waitFor({ state: "visible", timeout: 20000 });
    await page.locator(".ws-pane:not(.route-hidden)").waitFor({ timeout: 20000 });
  };
  const bodyPad = () => page.evaluate(
    () => parseFloat(getComputedStyle(document.body).paddingTop) || 0);
  /** 屏幕坐标上那一点,鼠标真正会点到谁(把"层号"换成"命中")。 */
  const hitAt = (x, y) => page.evaluate(([px, py]) => {
    const el = document.elementFromPoint(px, py);
    if (!el) return null;
    return { cls: el.className || "", ui: el.getAttribute("data-ui") || "",
             tag: el.tagName.toLowerCase(),
             // 按钮里是 <svg>/<path>,命中的是子节点 —— 往上找带 data-ui 的祖先
             ownerUi: el.closest("[data-ui]")?.getAttribute("data-ui") || "" };
  }, [x, y]);

  // ── A 病本身 ────────────────────────────────────────────────────────────
  await step("A 外壳里(地址带标记):三个按钮 + 拖动带 + 八个把手都在", async () => {
    await open("?shell=1");
    for (const [sel, what] of BTNS) {
      const loc = page.locator(sel);
      expect(await loc.count() === 1, `${what}按钮在场`);
      expect(await loc.isVisible().catch(() => false), `${what}按钮看得见`);
    }
    expect(await page.locator('[data-ui="window-bar"]').count() === 1,
      "顶部拖动带在场(系统标题栏已经没有了,这是唯一能拖的地方)");
    const grips = await page.locator(".win-grip").count();
    expect(grips === 8, `八个边角把手都在(实测 ${grips} 个)`);
    const pad = await bodyPad();
    expect(pad === BAR_H, `界面往下让出 ${BAR_H}px(实测 ${pad}px)`);
  });

  // ── C 命中测试(同一次开页,接着 A 量)─────────────────────────────────
  await step("C 命中测试:按钮/把手/拖动带各自点得到", async () => {
    // 短超时:窗口栏不在场时这一段要立刻红,别让它在默认 30 秒里干等
    const box = await page.locator('[data-ui="window-close"]')
      .boundingBox({ timeout: 5000 }).catch(() => null);
    check(box !== null, "前提:量到了关闭按钮的位置");
    const cx = box.x + box.width / 2, cy = box.y + box.height / 2;
    const onClose = await hitAt(cx, cy);
    expect(onClose?.ownerUi === "window-close",
      `关闭按钮中心点下去就是关闭按钮(实测命中 ${JSON.stringify(onClose)})`);
    // 上沿也要是它:把手曾经压掉按钮顶部 5px(x8 那条老病的行为面)
    const onCloseTop = await hitAt(cx, box.y + 2);
    expect(onCloseTop?.ownerUi === "window-close",
      `关闭按钮上沿 2px 仍是关闭按钮,不是"改窗口大小"(实测 ${JSON.stringify(onCloseTop)})`);

    const midX = 1280 / 2;
    const onGrip = await hitAt(midX, 2);
    expect(String(onGrip?.cls || "").includes("win-grip-top"),
      `顶边 2px 是"改大小"的把手(实测 ${JSON.stringify(onGrip)})`);
    const onBar = await hitAt(midX, 15);
    expect(String(onBar?.ui || "") === "window-bar",
      `顶栏 15px 处是拖动带,没被别的东西盖着(实测 ${JSON.stringify(onBar)})`);
  });

  // ── D 界面里的东西不许被压在拖动带底下 ──────────────────────────────────
  await step("D 没有界面元素躲在拖动带底下(压住 = 看得见但点不着)", async () => {
    // 拖动带是 z-index 200,压过一切 ⇒ 谁的可点区落在那 30px 里就**点不着**。
    // 0.89 的设计注释里写的就是这件事(所以选了 body padding 而不是绝对定位盖上去)——
    // 但那时没有任何判据问过它。这里问的是行为:有没有真元素躲在带子底下。
    // **整屏容器/遮罩不算**(它们本来就铺满全屏,不是"被挤到上面去的内容");
    // 它们的子元素照样逐个查,所以躲在里面的东西藏不住。
    const intruders = await page.evaluate((h) => {
      const bad = [];
      const vh = window.innerHeight, vw = window.innerWidth;
      for (const el of document.querySelectorAll("body *")) {
        if (el.closest(".win-bar, .win-btns, .win-grip")) continue;
        const r = el.getBoundingClientRect();
        if (r.width < 4 || r.height < 4) continue;           // 装饰性细线/空节点
        if (r.height >= vh - 1 && r.width >= vw - 1) continue; // 整屏容器/遮罩
        const cs = getComputedStyle(el);
        if (cs.visibility === "hidden" || cs.display === "none") continue;
        if (parseFloat(cs.opacity) === 0) continue;
        if (r.top < h - 1 && r.bottom > 1) {
          bad.push(`${el.tagName.toLowerCase()}.${String(el.className).slice(0, 40)}`
                   + ` top=${Math.round(r.top)}`);
        }
      }
      return bad.slice(0, 8);
    }, BAR_H);
    expect(intruders.length === 0,
      `没有界面元素被压在拖动带底下(实测:${JSON.stringify(intruders)})`);
  });

  // ── B 浏览器里一个按钮都不许出现 ────────────────────────────────────────
  await step("B 普通浏览器(地址没标记):一个窗口按钮都没有", async () => {
    await open("");
    for (const [sel, what] of BTNS) {
      expect(await page.locator(sel).count() === 0,
        `${what}按钮不在(浏览器里没有窗口可关,画出来就是死按钮)`);
    }
    expect(await page.locator('[data-ui="window-bar"]').count() === 0, "拖动带也不在");
    expect(await page.locator(".win-grip").count() === 0, "把手也不在");
    const pad = await bodyPad();
    expect(pad === 0, `body 不许白让出那 30px(实测 ${pad}px)`);
  });
} finally {
  if (browser) await browser.close();
  srv.kill("SIGTERM");
  rmSync(tmp, { recursive: true, force: true });
}

console.log(failures === 0
  ? "\n✅ shell_chrome e2e 全绿"
  : `\n❌ shell_chrome e2e 有 ${failures} 条失败`);
process.exit(failures === 0 ? 0 : 1);
