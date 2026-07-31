// track opendesign-button-roles e2e(行为 + 观感):真 chromium + 真 ds_web。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// 用户 07-31 原话:「有没有什么规范,正常的软件工程他们是怎么做的呢,这种按钮和发送给
// 项目助手聊天的这种按钮应该要有区别吧」+「打开文件夹也统一一下,都用一样的白框然后里面字」。
//
// 规范早就有(`.btn-primary` 主 / `.btn-secondary` 次 / `.link-act` 文字),只是没在用。
// 本单把剩下 3 个**按位置命名**的一次性 class 收编掉。范围与不做什么见 proposal.md。
//
// 覆盖:
//   A 走过的每条路由上,三个一次性 class 渲染出的元素数 = 0。
//   B **同一角色 class 的按钮,computed 外观必须完全一致** —— 这是"规范落地"唯一可验的形式。
//     ⚠️ 比渲染值,不比 class 名:class 名相同也可能被别处规则覆盖成两个样。
//   C 逐点钉死目标角色(不只钉"组内一致"):
//     「去项目」= link-act、「展开对话」= link-act、「帮我建收件箱」= btn-primary。
//     **只钉组内一致会被"角色分错但一致"骗过** —— 把主动作降成文字链接,组内照样全绿。
//   D 【陷阱】「去项目」**不许被压缩**:它长在项目卡头的 flex 行里,原 class 带 `flex: none`。
//   E 【陷阱】「展开对话」**不许被拉伸**,且**仍贴着标题行右端**:原 class 带
//     `align-self: flex-start`,另有上下文规则 `.rail-ask-head ... { margin-left: auto }`。
//   F 【护栏】任何按钮的文字不许被裁掉(scrollWidth ≤ clientWidth),页面不许横向溢出。
//
// ⚠️ 本判据接不住的:**"全都一致了,但整体更难看"**。一致性断言对此永远是绿的
//    ⇒ 收货必须截图,且要截到聊天区与整理方案两处(见 verify 的已知缺口)。
//
// 跑法:node tests/e2e/button_roles.e2e.mjs(自起 ds_web 于 8824)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8824;
const TODAY = "2026-08-01";
const PROJ = "翡翠湾-1801";
const FOLDER = "20260601 平湖 翡翠湾 3#1801";

const BANNED = ["chat-btn", "go-link", "rail-expand-link"];
const ROUTES = ["#/workspace", "#/todos", "#/gallery", "#/"];

const tmp = mkdtempSync(join(tmpdir(), "btnroles-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
mkdirSync(join(ws, FOLDER, "01-资料"), { recursive: true });
// **刻意不建 `00-收件箱`**:收件箱卡因此进「还没有收件箱文件夹」那一态,
// 「帮我建收件箱」(chat-btn primary)才渲染得出来 —— C 段要逐点钉它。
writeFileSync(join(dsRoot, "projects", `${PROJ}.md`), `# ${PROJ}

- 业主: [[李四]]
- 阶段: 施工跟进

## 变更记录
- [待确认] C1 2026-07-28 【主卧】床头背景墙改木饰面 ⏳${TODAY}
- [待确认] C2 2026-07-28 【客厅】窗帘盒预留尺寸

## 沟通日志

---
最后更新: ${TODAY}
`);
writeFileSync(
  join(dsRoot, "config", "workspace.json"),
  JSON.stringify({ root: ws, projectsDir: ".", projects: { [PROJ]: FOLDER } }),
);

const srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
  env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT), DS_TODAY: TODAY },
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

  // goto 到只差 hash 的同一 URL 不会重载文档(踩过) ⇒ 每次显式 reload。
  const go = async (hash) => {
    await page.goto(`${base}/${hash}`, { waitUntil: "domcontentloaded" });
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1800);
  };

  // 一次采全:每个可见按钮的角色、文案、几何、computed 外观。
  const scan = async () => page.evaluate((roles) => {
    const look = (b) => {
      const s = getComputedStyle(b);
      const r = b.getBoundingClientRect();
      return {
        text: b.innerText.trim(),
        cls: b.className,
        role: roles.find((x) => new RegExp(`(?:^|\\s)${x}(?:\\s|$)`).test(b.className)) ?? null,
        look: [s.height, s.borderTopWidth, s.borderTopStyle, s.borderTopColor, s.borderRadius,
               s.backgroundColor, s.fontSize, s.fontWeight, s.color].join(" | "),
        w: Math.round(r.width), left: Math.round(r.left), right: Math.round(r.right),
        clipped: b.scrollWidth > b.clientWidth + 1,
      };
    };
    const de = document.documentElement;
    return {
      buttons: [...document.querySelectorAll("button")]
        .filter((b) => b.getBoundingClientRect().height > 0)
        .map(look),
      overflow: de.scrollWidth > de.clientWidth + 1,
    };
  }, ["btn-primary", "btn-secondary", "link-act"]);

  const all = [];

  // ── A 一次性 class 在每条路由上都不再渲染 ────────────────────────────────
  await step("A 三个一次性 class 在所有路由上都不再出现", async () => {
    for (const hash of ROUTES) {
      await go(hash);
      for (const cls of BANNED) {
        const n = await page.locator(`.${cls}`).count();
        expect(n === 0, `${hash}:.${cls} 已不存在(实测 ${n} 个)`);
      }
      const s = await scan();
      all.push(...s.buttons);
      expect(!s.overflow, `${hash}:页面没有横向溢出`);
    }
    check(all.length > 0, "前提:确实采到了按钮");
  });

  // ── B 同角色的按钮,渲染出来必须完全一致 ─────────────────────────────────
  await step("B 同一角色 class 的按钮 computed 外观完全一致", async () => {
    // ⚠️ 只比**光戴角色 class、没有其它修饰符**的按钮。
    // 红检时抓到:`.btn-primary` 现在就有两种高度(28 / 30),因为 `.quicknote-card .qn-submit`
    // 合法地把它压到 28px —— 那是本单之前就存在的、**刻意的上下文微调**。
    // 一刀切"同角色必须一模一样"会把它判红,执行腿只能去删一条与本单无关的规则
    // ⇒ **我的规格错会变成它的返工**。带修饰符的按钮是有意的变体,不在本单射程内。
    // 漏网风险(靠 A/C 段与静态判据兜住):加个修饰符就能躲开这条比对。
    // 每个角色至少要采到 MIN 个,否则"只有一种长相"是**空真** —— 跳过的判据等于没判
    // (0.64/0.65 连漏两轮的根因就是一段被 skip 掉)。改完之后这三档在本轮路由上必有:
    //   link-act ≥2(「去项目」「展开对话」,外加收件箱「打开」)· btn-primary ≥1(「帮我建收件箱」)
    //   · btn-secondary ≥1(图墙/伴随列的「打开文件夹」)
    const MIN = { "btn-primary": 1, "btn-secondary": 1, "link-act": 2 };
    const bare = (b, role) => b.cls.trim().split(/\s+/).filter(Boolean).join(" ") === role;
    for (const role of ["btn-primary", "btn-secondary", "link-act"]) {
      const group = all.filter((b) => bare(b, role));
      expect(group.length >= MIN[role],
        `.${role} 在本轮路由上至少采到 ${MIN[role]} 个(实测 ${group.length} 个,少于此则下一条是空真)`);
      const looks = [...new Set(group.map((b) => b.look))];
      expect(looks.length === 1,
        `.${role}(不带修饰符的)只有一种长相(实测 ${looks.length} 种:${JSON.stringify(looks)})`);
    }
    // 每个按钮的文字都不许被裁
    const clipped = all.filter((b) => b.clipped).map((b) => `${b.text}(${b.cls})`);
    expect(clipped.length === 0, `没有按钮的文字被裁掉(被裁:${clipped.join("、") || "无"})`);
  });

  // ── C 逐点钉死目标角色 ───────────────────────────────────────────────────
  await step("C 三个可达点的角色都换对了(不只是组内一致)", async () => {
    await go("#/todos");
    const goLink = page.locator('.todo-card button:has-text("去项目")').first();
    check(await goLink.count() === 1, "前提:「去项目」在场");
    expect(/\blink-act\b/.test((await goLink.getAttribute("class")) ?? ""),
      `「去项目」= link-act(实测 ${JSON.stringify(await goLink.getAttribute("class"))})`);

    const expand = page.locator('[data-ui="rail-expand"]');
    check(await expand.count() === 1, "前提:「展开对话」在场");
    expect(/\blink-act\b/.test((await expand.getAttribute("class")) ?? ""),
      `「展开对话」= link-act(实测 ${JSON.stringify(await expand.getAttribute("class"))})`);

    await go("#/workspace");
    const create = page.locator('[data-ui="inbox-create"]');
    check(await create.count() === 1, "前提:「帮我建收件箱」在场(夹具刻意没建收件箱夹)");
    expect(/\bbtn-primary\b/.test((await create.getAttribute("class")) ?? ""),
      `「帮我建收件箱」= btn-primary,没被降级成文字链接(实测 ${
        JSON.stringify(await create.getAttribute("class"))})`);
  });

  // ── D 【陷阱】「去项目」不许被压缩 ───────────────────────────────────────
  await step("D 「去项目」在卡头 flex 行里不许被压缩", async () => {
    await go("#/todos");
    const g = await page.evaluate(() => {
      const b = [...document.querySelectorAll(".todo-card button")]
        .find((x) => x.innerText.trim().startsWith("去项目"));
      if (!b) return null;
      const r = b.getBoundingClientRect();
      const cs = getComputedStyle(b);
      return { w: Math.round(r.width), scrollW: b.scrollWidth,
               lines: Math.round(r.height / parseFloat(cs.lineHeight || "16")) };
    });
    check(g !== null, "前提:量得到「去项目」");
    expect(g.w >= g.scrollW - 1,
      `没被压缩(渲染宽 ${g.w} ≥ 内容宽 ${g.scrollW})`);
    expect(g.lines <= 1, `没有换成两行(实测约 ${g.lines} 行)`);
  });

  // ── E 【陷阱】「展开对话」不许被拉伸,且仍贴标题行右端 ───────────────────
  await step("E 「展开对话」不许被拉伸,且仍贴在标题行右端", async () => {
    await go("#/todos");
    const g = await page.evaluate(() => {
      const b = document.querySelector('[data-ui="rail-expand"]');
      const head = document.querySelector(".rail-ask-head");
      if (!b || !head) return null;
      const rb = b.getBoundingClientRect(), rh = head.getBoundingClientRect();
      return { bw: Math.round(rb.width), hw: Math.round(rh.width),
               gapRight: Math.round(rh.right - rb.right) };
    });
    check(g !== null, "前提:量得到「展开对话」与它所在的标题行");
    expect(g.bw < g.hw * 0.8,
      `没被拉伸成整行(按钮 ${g.bw}px / 标题行 ${g.hw}px)`);
    expect(g.gapRight <= 2,
      `仍贴着标题行右端(距右端 ${g.gapRight}px —— 上下文规则 margin-left:auto 不许丢)`);
  });
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}

console.log(failures === 0 ? "\n全部通过" : `\n${failures} 条不通过`);
process.exit(failures === 0 ? 0 : 1);
