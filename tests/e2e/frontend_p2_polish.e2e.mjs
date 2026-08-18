// track opendesign-frontend-p2-polish e2e:Claude Design v4 质感收口的**行为面**契约
// (真 chromium + 真 ds_web,**不需要 gateway**——未连接态本身就是被测对象:
//  未连接态由**拦 bootstrap 回 401** 造出来,见下方 page.route 那段的说明。
//  08-18 之前这里写的是「无 gateway」,那句话是错的 —— 它真正要的是
//  「有一个会拒绝口令的 gateway」,于是在没起 gateway 的机器上长期假红。)
// 覆盖修改单:B 快记单行输入卡(空间 chip popover/toast/顶部高亮/不猜空间)、
// C 连接卡两处(新对话页居中卡 + 工作区横幅→modal→esc)、发送按钮文字化、
// D 收件箱摘要行 + stage-chip 挪中央列 + 伴随列去业主、E 变更行 ✎/✓ 图标钮、
// F 空态可点动作、G 待办按项目=空间小节(无日期折叠)/按时间=日期折叠、
// H lightbox 方向键/esc + 侧栏未建档建档链接。纯样式项(颜色/圆角)不在此断言,
// 归 verify 亲读 diff。
//
// 跑法:node tests/e2e/frontend_p2_polish.e2e.mjs(自起 ds_web 于 8794)
import { spawn, execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, check } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8794;

// ── 夹具 ────────────────────────────────────────────────────────────────────
const tmp = mkdtempSync(join(tmpdir(), "fp2-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");
const projA = "翡翠湾-1801";                       // 主场景:快记/变更行/待办/图墙
const folderA = "20260601 平湖 翡翠湾 3#1801";
const projC = "空项目-701";                        // 空态场景:0 变更 + 空文件夹
const folderC = "20260701 平湖 空项目 7#701";
const folderB = "老宅翻新项目夹";                  // 未建档行(token 不命中任何项目)
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "refs"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
writeFileSync(join(dsRoot, "projects", `${projA}.md`), `# ${projA}

- 业主: [[李四]]
- 阶段: 施工跟进
- 当前状态: 等瓦工进场

## 变更记录
- [待确认] C1 2026-07-15 【玄关】玄关柜改高

## 沟通日志

---
最后更新: 2026-07-15
`);
writeFileSync(join(dsRoot, "projects", `${projC}.md`), `# ${projC}

- 业主: [[王五]]
- 阶段: 方案深化

## 变更记录

## 沟通日志

---
最后更新: 2026-07-14
`);
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64");
mkdirSync(join(ws, folderA, "06-效果图"), { recursive: true });
mkdirSync(join(ws, folderC, "01-资料"), { recursive: true });
mkdirSync(join(ws, folderB), { recursive: true });
mkdirSync(join(ws, "00-收件箱"), { recursive: true });
mkdirSync(join(ws, "03-共享资源", "参考图库"), { recursive: true });
writeFileSync(join(ws, folderA, "06-效果图", "终稿A.png"), PNG);
writeFileSync(join(ws, folderA, "06-效果图", "终稿B.png"), PNG);
writeFileSync(join(ws, "00-收件箱", "翡翠湾玄关参考.png"), PNG);
writeFileSync(join(ws, "00-收件箱", "翡翠湾户型图.dwg"), "DWG");
writeFileSync(join(dsRoot, "config", "workspace.json"), JSON.stringify({
  root: ws, projectsDir: ".",
  projects: { [projA]: folderA, [projC]: folderC },
}));

// ── 起 ds_web ───────────────────────────────────────────────────────────────
const srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
  env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT) },
  stdio: ["ignore", "inherit", "inherit"],
});
const base = `http://127.0.0.1:${PORT}`;
for (let i = 0; ; i++) {
  try { await fetch(`${base}/api/health`); break; }
  catch { if (i > 50) throw new Error("ds_web 起不来"); await new Promise((r) => setTimeout(r, 200)); }
}

/** 聊天暂存替身(同 intake.e2e):直调 ds_intake 核心,不烧 LLM。 */
function stageViaCore() {
  const py = `
import json, sys
sys.path.insert(0, ${JSON.stringify(join(ROOT, "bin"))})
import ds_intake
r = ds_intake.stage_intake(
    [{"name": "翡翠湾玄关参考.png", "project": None, "category": "参考图"},
     {"name": "翡翠湾户型图.dwg", "project": ${JSON.stringify(projA)}, "category": "CAD"}],
    allowed_roots=[${JSON.stringify(ws)}], ds_root=${JSON.stringify(dsRoot)})
print(json.dumps(r, ensure_ascii=False))
`;
  const out = execFileSync("python3", ["-c", py], { encoding: "utf-8" });
  return JSON.parse(out.trim().split("\n").pop());
}

const projMd = () => readFileSync(join(dsRoot, "projects", `${projA}.md`), "utf-8");

let failures = 0;
let browser = null;
try {
  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // ── 让页面进入「未连接」态:拦 bootstrap 回 401 ────────────────────────────
  // 连接卡只在 view.kind==="login" 时渲染(ChatPage.tsx:753)。
  // **本场景(全新加载)下**进入 login 的路径是:reduceReconnect 收到 PasswordRejected
  // (reconnect.ts:88)⇒ dispatchRc 落 setView login(ChatPage.tsx:224);
  // 而 PasswordRejected 唯一的来源是 /api/chat/bootstrap 回 401(connection.ts:93)。
  // **别把它读成"全局唯一路径"**(08-18 评审 subdeepseek 指出,核实成立):
  // 全仓还有两处能产生 login 视图 —— ChatPage.tsx:287(effect 起步时 mode 已是
  // "stopped",而 stopped 本身只在 PasswordRejected 之后才可达)与 :464(业主主动登出)。
  // 两处都到不了这条 e2e 的全新加载场景,但"唯一"这个词本身是错的。
  // 此前这一步是白拿的:开发机上常年有个真 gateway 在跑,它对没口令的请求正好回 401。
  // 于是这两条 e2e **悄悄依赖了机器上有没有起 gateway** —— 谁没起谁见两条假红,
  // 而红的原因("等 connect-card 超时")完全不指向真因。08-18 实测:
  // 无 gateway 时页面走的是重连路径(8s 后显示「连接不上,gateway 可能没在跑」),
  // 连接卡永不出现 —— 那是**正确的产品行为**,是判据问错了问题。
  // 尾部 `*`:playwright 的 glob 是**全串锚定**的,不带它的话将来谁给这个请求加个
  // query(`?x=1`)就会**静默**不再命中 ⇒ 这两条 e2e 悄悄退回"看机器上有没有 gateway",
  // 而症状和 08-18 修掉的那次一模一样。多一个字符,换掉一整类无声回归。
  await page.route("**/api/chat/bootstrap*", (route) =>
    route.fulfill({ status: 401, contentType: "application/json", body: "{}" }));
  await page.goto(base, { waitUntil: "domcontentloaded" });

  // ── C:新对话页(默认首页,未连接)= 居中连接卡,不是裸表单 ────────────
  const card = page.locator('.home-pane [data-ui="connect-card"]');
  await card.waitFor({ timeout: 10000 });
  const cardTxt = await card.innerText();
  check(cardTxt.includes("现在就能用"), "连接卡:说明含「现在就能用」(变更/图墙/文件不受影响)");
  check(cardTxt.includes("口令"), "连接卡:口令输入与获取提示在卡内");
  check(await card.locator('.chat-login input[type=password]').count() === 1,
    "连接卡:表单保留 .chat-login 契约(helpers.loginPane 兼容)");
  check(await card.locator('button:has-text("连接")').count() === 1, "连接卡:主按钮「连接」");

  // ── F:侧栏未连接 → 历史对话组整组隐藏 ──────────────────────────────────
  const sideTxt = await page.locator("nav.side").innerText();
  check(!sideTxt.includes("历史对话"), "侧栏:未连接不出「历史对话」组");
  check(!sideTxt.includes("连接聊天后显示"), "侧栏:旧占位提示已删");

  // ── H:侧栏未建档行(track opendesign-todo-batch-space T5 起改「建档 →」/「未建档」
  // 两处文字为纯 .unregistered class 灰化,不再有独立链接/小标 DOM)────
  const unregRow = page.locator(`.proj-list .proj-row:has-text("${folderB}")`).first();
  await unregRow.waitFor({ timeout: 10000 });
  check(await unregRow.locator('[data-ui="side-reg-link"]').count() === 0,
    "侧栏未建档行:不再渲染「建档 →」链接(T5 已删除)");

  // ── 进 projA 工作区 ────────────────────────────────────────────────────
  await page.locator(`.proj-list .proj-row:has-text("${projA}")`).first().click();
  await page.locator(".change-row").first().waitFor({ timeout: 10000 });

  // D:阶段 chip 挪中央列标题旁;伴随列不再展示业主,**当前状态 2026-07-28 也删了**
  //   (它没有写口,永远是模板默认值 —— 详见 cockpit.e2e.mjs ③ 与 CompanionColumn 注释)
  const headTxt = await page.locator(".center-head").innerText();
  check(headTxt.includes("施工跟进"), "中央列:标题旁 stage-chip");
  check(await page.locator('.center-head [data-ui="stage-chip"]').count() === 1,
    "中央列:stage-chip 落点契约");
  const asideTxt = await page.locator(".aside").innerText();
  check(!asideTxt.includes("李四"), "伴随列:速览行删掉(业主不再展示)");
  // 夹具档案里「当前状态: 等瓦工进场」那行是**留着**的 —— 有内容也不显示,才叫删干净。
  check(!asideTxt.includes("等瓦工进场"), "伴随列:当前状态那句话已删掉");

  // C:工作区聊天列 = 横幅,不放表单;点开 modal;esc 关
  const wsPane = page.locator(".ws-pane");
  check(await wsPane.locator(".chat-login input[type=password]:visible").count() === 0,
    "聊天列:未连接不放裸表单");
  const banner = wsPane.locator('[data-ui="connect-banner"]');
  await banner.waitFor({ timeout: 5000 });
  check((await banner.innerText()).includes("未连接聊天服务"), "聊天列:琥珀横幅文案");
  await banner.click();
  const modal = page.locator('[data-ui="connect-modal"]');
  await modal.waitFor({ timeout: 5000 });
  check(await modal.locator('[data-ui="connect-card"]').count() === 1, "横幅点开:同一张连接卡为 modal");
  await page.keyboard.press("Escape");
  await modal.waitFor({ state: "detached", timeout: 5000 });
  check(true, "esc 关掉连接 modal");

  // 发送按钮 = 文字「发送」(未连接置灰同形)
  const sendTxt = (await wsPane.locator(".send-btn").first().innerText()).trim();
  check(sendTxt === "发送", `发送按钮=文字「发送」(实际:${sendTxt})`);

  // ── B:快记单行输入卡 ──────────────────────────────────────────────────
  const qcard = page.locator('[data-ui="quicknote-card"]');
  await qcard.waitFor({ timeout: 5000 });
  const qinput = qcard.locator('[data-ui="quicknote-input"]');
  check(await qinput.count() === 1, "快记卡:单行输入契约");
  // 空间 chip → popover:已有空间建议 + 自由输入
  await qcard.locator('[data-ui="quicknote-space"]').click();
  const pop = page.locator('[data-ui="quicknote-space-pop"]');
  await pop.waitFor({ timeout: 5000 });
  check(await pop.locator(':text("玄关")').count() >= 1, "空间 popover:本项目已有空间「玄关」成建议");
  await pop.locator(':text("玄关")').first().click();
  check((await qcard.locator('[data-ui="quicknote-space"]').innerText()).includes("玄关"),
    "选中后 chip 显示空间名");
  // 回车提交 → toast「已记入 C2」 → 新行顶部高亮
  await qinput.fill("吊顶下调5公分");
  await qinput.press("Enter");
  const toast = page.locator('[data-ui="quicknote-toast"]');
  await toast.waitFor({ timeout: 10000 });
  check((await toast.innerText()).includes("已记入 C2"), "提交后轻提示「已记入 C2」");
  await page.locator('.change-row.hl-flash:has-text("吊顶下调5公分")')
    .waitFor({ timeout: 10000 });
  check(true, "新行插入列表并短暂高亮");
  check(projMd().includes("【玄关】吊顶下调5公分"), "磁盘:空间前缀落盘");
  // 不选空间 = 无前缀(拍板:砍 AI 猜)
  await qinput.fill("插座加高");
  await qinput.press("Enter");
  await page.locator('.change-row:has-text("插座加高")').waitFor({ timeout: 10000 });
  const line3 = projMd().split("\n").find((l) => l.includes("插座加高")) || "";
  check(line3.includes("C3") && !line3.includes("【"), "不选空间:C3 行无【】前缀(不猜不落未分类)");
  // popover 自由输入:自定义空间「客厅」
  await qcard.locator('[data-ui="quicknote-space"]').click();
  const spaceInput = pop.locator('[data-ui="quicknote-space-input"]');
  await spaceInput.waitFor({ timeout: 5000 });
  await spaceInput.fill("客厅");
  await spaceInput.press("Enter");
  check((await qcard.locator('[data-ui="quicknote-space"]').innerText()).includes("客厅"),
    "popover 自由输入自定义空间");
  await qinput.fill("沙发墙加木饰面");
  await qinput.press("Enter");
  await page.locator('.change-row:has-text("沙发墙加木饰面")').waitFor({ timeout: 10000 });
  check(projMd().includes("【客厅】沙发墙加木饰面"), "磁盘:自定义空间前缀落盘");

  // ── E:变更行图标按钮组 ✎ + ✓;✓ = 直接标记完成 ───────────────────────
  const rowC1 = page.locator('.change-row:has-text("玄关柜改高")');
  await rowC1.hover();
  check(await rowC1.locator('[data-ui="change-edit"].edit-trigger').count() === 1,
    "变更行:✎ 编辑图标钮(保留 .edit-trigger 契约)");
  check(await rowC1.locator('[data-ui="change-done"]').count() === 1, "变更行:✓ 标记完成图标钮");
  await rowC1.locator('[data-ui="change-done"]').click();
  await rowC1.waitFor({ state: "detached", timeout: 10000 }); // 默认「未办结」筛选下离场
  check(projMd().includes("[已完成] C1"), "✓ 点击:磁盘状态改已完成");

  // ── D:收件箱默认一行摘要,点开展开明细 ────────────────────────────────
  const staged = stageViaCore();
  check(staged.ok === true, "核心 stage 成功(2 项)");
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.locator(`.proj-list .proj-row:has-text("${projA}")`).first().click();
  const summary = page.locator('[data-ui="inbox-summary"]');
  await summary.waitFor({ timeout: 10000 });
  const sumTxt = await summary.innerText();
  check(sumTxt.includes("收件箱"), "收件箱摘要行:标题");
  check(sumTxt.includes("2"), "收件箱摘要行:计数");
  check(await summary.locator('button:has-text("扫描整理")').count() === 1,
    "收件箱摘要行:扫描整理次按钮在行内");
  check(!(await page.locator(".inbox-plan").isVisible().catch(() => false)),
    "收件箱默认收起:明细不可见");
  await summary.click();
  await page.locator('[data-ui="inbox-expanded"]').waitFor({ timeout: 5000 });
  await page.locator(".inbox-plan").waitFor({ timeout: 5000 });
  check((await page.locator(".inbox-plan .plan-row").count()) === 2, "点开:方案明细 2 行");

  // ── F:空态动作(projC:0 变更 + 空文件夹)────────────────────────────
  await page.locator(`.proj-list .proj-row:has-text("${projC}")`).first().click();
  const emptyBtn = page.locator('[data-ui="empty-add-first"]');
  await emptyBtn.waitFor({ timeout: 10000 });
  await emptyBtn.click();
  const focused = await page.evaluate(
    () => document.activeElement?.getAttribute("data-ui") ?? "");
  check(focused === "quicknote-input", "变更空态:「记第一条变更」→ 聚焦快记输入");
  check(await page.locator('.aside [data-ui="empty-reg-ref"]').count() === 1,
    "参考图空态:「登记参考图」可点");
  await page.locator('.seg .opt:has-text("项目图")').click();
  await page.locator('.aside [data-ui="empty-open-folder"]').waitFor({ timeout: 5000 });
  check(true, "项目图空态(已映射):「打开文件夹」次按钮");

  // ── G:【已删,2026-08-02】待办页的「按项目/按时间」看法断言 ─────────────
  //
  // **判据迁移账**(本项目规矩:改/删判据必须当场证明"不是放松",逐条指名)。
  // `549472d`(0.69.0,track opendesign-todo-one-view)把待办页收敛成**单一看法**:
  // 看法切换器整个移除,空间小节 `[data-ui="todo-space-sect"]` 随之删除
  // (空间改为行内标签),「全选本组」从小节头挪到项目卡头。那一单写了迁移账、
  // 也删了另外两份 e2e,但**漏了这一份的 G 段** —— 于是它从 08-02 起一直红着,
  // 直到 `tests/e2e/run-all.sh` 第一次把 30 个 e2e 全跑一遍才暴露。
  //
  //   G1 按项目:三个空间小节        → 功能移除(待办页不再有空间小节)。
  //   G2 小节按空间首现序(玄关→客厅) → 待办页移除;**同一事实在「变更列」仍存在**,
  //                                    由 todo_batch_space.e2e.mjs:121 钉住。
  //   G3 无空间那节恒置末且没名字     → **carry over**,todo_batch_space.e2e.mjs:133,
  //                                    且那边更强(:126 断整页无「未分空间」残留)。
  //   G4 按项目视图无日期折叠头        → 功能移除(看法切换器不存在了)。
  //   G5 按时间视图日期批次折叠保留    → 功能移除(同上)。
  //   附:「整组一次选中」这条 0.34.0 的能力没丢,挂到了卡头,
  //       由 todo_batch_space.e2e.mjs:185「全选本卡」钉住。
  //
  // ⇒ 五条里三条是功能被刻意移除,两条已在别处有更强的判据。**没有护栏净损失。**

  // ── H:图墙 lightbox 方向键切换 + esc 关 ───────────────────────────────
  // (G 段删掉后页面仍停在 F 段的项目页,下一行的 .proj-list 直接可用,无需先导航回去)
  await page.locator(`.proj-list .proj-row:has-text("${projA}")`).first().click();
  // 直接走路由进图墙:本段验的是 lightbox 方向键/esc,**不是**"怎么进来的"。
  // (2026-07-28「图墙 →」小字按用户要求删了;进图墙的入口本身另有判据
  //  inbox_pad_gallery.e2e.mjs 专门钉,这里不重复依赖某个具体控件。)
  await page.evaluate(() => { window.location.hash = "#/gallery"; });
  const album = page.locator(".g-cell:has(.g-badge)").first();
  await album.waitFor({ timeout: 10000 });
  await album.click();
  await page.locator(".g-cell").first().waitFor({ timeout: 5000 });
  await page.locator(".g-cell").first().click();
  const light = page.locator(".g-light");
  await light.waitFor({ timeout: 5000 });
  const src1 = await light.locator("img").getAttribute("src");
  await page.keyboard.press("ArrowRight");
  await page.waitForFunction(
    (s) => document.querySelector(".g-light img")?.getAttribute("src") !== s,
    src1, { timeout: 5000 });
  check(true, "lightbox:→ 键切到下一张");
  await page.keyboard.press("Escape");
  await light.waitFor({ state: "detached", timeout: 5000 });
  check(true, "lightbox:esc 关闭");
} catch (e) {
  failures++;
  console.error(String(e));
} finally {
  if (browser) await browser.close();
  srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}
console.log(failures === 0 ? "FRONTEND-P2-POLISH E2E: ALL PASS" : `FRONTEND-P2-POLISH E2E: ${failures} FAIL`);
process.exit(failures === 0 ? 0 : 1);
