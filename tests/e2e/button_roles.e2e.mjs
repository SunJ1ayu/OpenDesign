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
//   F 【护栏】任何按钮的**内容装得下它自己**:横向不许被裁(scrollWidth ≤ clientWidth),
//     纵向不许溢出(scrollHeight ≤ clientHeight)。**后者是补上来的**:收货截图抓到
//     「确认执行」被挤成两行、撑破 `.btn-primary` 的固定 30px 高 —— 而"换行"不是"被裁",
//     原来那条 scrollWidth 断言对它永远是绿的。
//   G 【补覆盖】**整理方案那一处**(收件箱待确认方案里的「确认执行」)也得体。
//     design 里我自己写明过这条路由行为判据够不着、只能靠截图 —— 结果就漏在这儿。
//     现在另起一个**带收件箱的 ds_web**(PORT+1)把它逼出来判。
//
// ⚠️ 本判据接不住的:**"全都一致了,但整体更难看"**。一致性断言对此永远是绿的
//    ⇒ 收货必须截图,且要截到聊天区与整理方案两处(见 verify 的已知缺口)。
//
// 跑法:node tests/e2e/button_roles.e2e.mjs(自起 ds_web 于 8824)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from "node:fs";
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

// G 段专用的第二套档案库:**有收件箱、且里面放着能被自动认领的文件**
// ⇒ 点「扫描整理」后会出现「待确认的整理方案」,那一处的「确认执行」才渲染得出来。
// 主夹具刻意没有收件箱(为了逼出「帮我建收件箱」),两者互斥,只能各起一个。
const planRoot = join(tmp, "plan-ds");
const planWs = join(tmp, "plan-ws");
mkdirSync(join(planRoot, "projects"), { recursive: true });
mkdirSync(join(planRoot, "config"), { recursive: true });
mkdirSync(join(planWs, FOLDER, "01-资料"), { recursive: true });
mkdirSync(join(planWs, "00-收件箱"), { recursive: true });
// 文件名照 tests/e2e/intake.e2e.mjs 里验证过的形状(能被自动认领)
writeFileSync(join(planWs, "00-收件箱", "翡翠湾户型图.dwg"), "DWG");
writeFileSync(join(planWs, "00-收件箱", "翡翠湾玄关参考.png"), "P");
writeFileSync(join(planRoot, "projects", `${PROJ}.md`),
  readFileSync(join(dsRoot, "projects", `${PROJ}.md`), "utf8"));
writeFileSync(join(planRoot, "config", "workspace.json"),
  JSON.stringify({ root: planWs, projectsDir: ".", projects: { [PROJ]: FOLDER } }));

const spawnWeb = (root, port) => spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
  env: { ...process.env, DS_ROOT: root, DS_WEB_PORT: String(port), DS_TODAY: TODAY },
  stdio: ["ignore", "inherit", "inherit"],
});
const srv = spawnWeb(dsRoot, PORT);
const planSrv = spawnWeb(planRoot, PORT + 1);
const base = `http://127.0.0.1:${PORT}`;
const planBase = `http://127.0.0.1:${PORT + 1}`;
for (const b of [base, planBase]) {
  for (let i = 0; ; i++) {
    try { await fetch(`${b}/api/health`); break; }
    catch { if (i > 50) throw new Error(`ds_web 起不来:${b}`); await new Promise((r) => setTimeout(r, 200)); }
  }
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
        // 纵向装不下 = 文字换行撑破了固定高度(截图抓到过,scrollWidth 那条接不住)
        overflowY: b.scrollHeight > b.clientHeight + 1,
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
    const burst = all.filter((b) => b.overflowY).map((b) => `${b.text}(${b.cls})`);
    expect(burst.length === 0, `没有按钮被文字撑破(撑破:${burst.join("、") || "无"})`);
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
  // ── G 【补覆盖】整理方案那一处的「确认执行」也得体 ────────────────────────
  await step("G 待确认整理方案里的「确认执行」不被挤变形", async () => {
    await page.goto(`${planBase}/#/workspace`, { waitUntil: "domcontentloaded" });
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.locator('[data-ui="inbox-summary"]').waitFor({ timeout: 15000 });
    await page.locator('[data-ui="inbox-summary"]').click();
    await page.locator('button:has-text("扫描整理")').first().click();
    await page.locator(".inbox-plan").waitFor({ timeout: 20000 });

    const g = await page.evaluate(() => {
      const b = [...document.querySelectorAll(".inbox-plan .plan-acts button")]
        .find((x) => x.innerText.trim().startsWith("确认执行"));
      if (!b) return null;
      const s = getComputedStyle(b);
      return { cls: b.className, h: Math.round(b.getBoundingClientRect().height),
               scrollH: b.scrollHeight, clientH: b.clientHeight,
               scrollW: b.scrollWidth, clientW: b.clientWidth,
               lineH: parseFloat(s.lineHeight) || 16 };
    });
    check(g !== null, "前提:「确认执行」渲染出来了(夹具真造出了待确认方案)");
    expect(/\bbtn-primary\b/.test(g.cls),
      `「确认执行」= btn-primary(实测 ${JSON.stringify(g.cls)})`);
    expect(g.scrollH <= g.clientH + 1,
      `文字没把按钮撑破(内容高 ${g.scrollH} ≤ 可视高 ${g.clientH})`);
    expect(g.scrollW <= g.clientW + 1,
      `文字没被横向裁掉(内容宽 ${g.scrollW} ≤ 可视宽 ${g.clientW})`);
    expect(g.h <= g.lineH * 1.9,
      `没换成两行(按钮高 ${g.h} / 行高 ${g.lineH})`);

    // 评审(submimo,MEDIUM)质疑执行腿自己加的 `.inbox-plan .plan-hint{min-width:0}`:
    // 说它"允许收缩,与修病初衷相反",失败路径是"提示文字被压成每行几个字的竖排"。
    // **主 agent 裁决:驳回该推理**——对一段**文字**来说,允许收缩→换行正是要的;
    // 07-27 那次的病是**卡片**被塞进 36px 竖条,不是同一件事。按钮已有 flex:none,
    // 不会被它挤到。**但不空口驳回:在真实列宽下量一次,证明提示文字没退化。**
    const hint = await page.evaluate(() => {
      const h = document.querySelector(".inbox-plan .plan-hint");
      if (!h) return null;
      const r = h.getBoundingClientRect();
      const lh = parseFloat(getComputedStyle(h).lineHeight) || 15;
      return { w: Math.round(r.width), lines: Math.round(r.height / lh) };
    });
    check(hint !== null, "前提:量得到方案区的提示文字");
    expect(hint.w >= 80, `提示文字没被压成窄条(实测宽 ${hint.w}px)`);
    expect(hint.lines <= 3, `提示文字没被压成竖排(实测约 ${hint.lines} 行)`);
  });

  // ── H 【2026-08-01 新增】按钮文字里整类不许有箭头 ────────────────────────
  // 用户 07-31 定死过:「不需要箭头」,而且是**整类**不要(我当时想按通行做法改成 `↗`
  // 表示"跳出应用",被他否掉)。0.65 只去掉了他当场点到的两个,**剩下两个还留着**:
  // 「展开对话 →」「去项目 →」—— 这正是 K 那条的教训(只改他点到的那一处,
  // 下次他再指另一处)。这里改成**扫过所有路由上的所有按钮**,一次收干净。
  //
  // ⚠️ **只扫按钮文字**:`源 → 目的` 那种表示流向的箭头(整理方案行、技能卡的
  // 「口头 → 变更记录」)是**在说事**不是在装饰按钮,不在此列,别顺手删掉。
  await step("H 所有路由上的按钮文字都不含箭头字符", async () => {
    const ARROWS = /[←-⇿➔-➿⟰-⟿⤀-⥿⬀-⯿￩-￬⧉]/u;
    check(all.length > 0, "前提:A 段已采到全部路由的按钮");
    const bad = all.filter((b) => ARROWS.test(b.text)).map((b) => b.text);
    expect(bad.length === 0,
      `没有按钮带箭头(实测带箭头的:${JSON.stringify([...new Set(bad)])})`);
  });
} finally {
  if (browser) await browser.close();
  srv.kill();
  planSrv.kill();
  rmSync(tmp, { recursive: true, force: true });
}

console.log(failures === 0 ? "\n全部通过" : `\n${failures} 条不通过`);
process.exit(failures === 0 ? 0 : 1);
