// track opendesign-feedback-0724-ui e2e:「新对话」必须给出一张白纸(真机反馈 2026-07-24 #9)
// 前置:gateway(8765)+ ds_web 在跑,见 tests/e2e/README.md。主 agent 亲写,执行腿逐字节 off-limits。
//
// 病根(已定位):App.tsx `newChat` 只写 setResumeTarget(null);人**已经在新对话里**时
// prev 本就是 null → React setState(null→null) bail-out → ChatPage 的连接 effect
// (依赖 resume?.nonce ?? 0)不重跑 → keep-mounted 的首页聊天原封不动。
// 于是"点了没反应",用户永远拿不到干净的新对话。
//
// 判据刻意绑**侧栏那个按钮**([data-ui="side-new-chat"]):项目列的「+ 新对话」本来就
// 没坏(它早就是 nonce 递增),拿它来测会绿得毫无意义 —— design.md 记的假绿之一。
// 不等 AI 回复:发出去的瞬间本地就先落一条 .msg-user(appendLocalUser),
// 这已经足够证明"转录非空 → 点新对话 → 转录空",还免掉模型不确定性与 key 依赖。
import { launchBrowser, loginPane, sendMessage, check } from "./helpers.mjs";

const BASE = process.env.E2E_BASE || "http://127.0.0.1:8768";
const PASSWORD = process.env.E2E_PASSWORD || "e2etest";
const HOME = ".home-pane";

const userMsgs = (page) => page.locator(`${HOME} .msg-user`).count();

const browser = await launchBrowser();
let failed = 0;
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.on("dialog", (d) => d.accept()); // 删除历史对话的 confirm
  await page.goto(BASE, { waitUntil: "domcontentloaded" });
  await loginPane(page, HOME, PASSWORD);

  const newChatBtn = page.locator('[data-ui="side-new-chat"]');
  check((await newChatBtn.count()) === 1, "侧栏「新对话」按钮可精确定位");

  // ── ① 主场景:聊过 → 点新对话 → 白纸 ─────────────────────────────────────
  await sendMessage(page, HOME, "第一条:测试新对话是否清空");
  await page.locator(`${HOME} .msg-user`).first().waitFor({ timeout: 20000 });
  check((await userMsgs(page)) === 1, "发出后首页转录有 1 条用户消息");

  await newChatBtn.click();
  await page.waitForFunction(
    (sel) => document.querySelectorAll(`${sel} .msg-user`).length === 0,
    HOME,
    { timeout: 20000 },
  );
  check((await userMsgs(page)) === 0, "点「新对话」后转录清空 = 拿到干净的新对话");

  // ── ② 连点两次:第二次同样要给白纸(bail-out 的正身)────────────────────
  // 此刻 resumeTarget 已经是"新对话"态;旧实现在这里 setState(null→null) 什么都不做。
  await sendMessage(page, HOME, "第二条:再聊一句");
  await page.waitForFunction(
    (sel) => document.querySelectorAll(`${sel} .msg-user`).length === 1,
    HOME,
    { timeout: 20000 },
  );
  await newChatBtn.click();
  await page.waitForFunction(
    (sel) => document.querySelectorAll(`${sel} .msg-user`).length === 0,
    HOME,
    { timeout: 20000 },
  );
  check((await userMsgs(page)) === 0, "已在新对话里再点「新对话」:仍然清空(不 bail-out)");

  // ── ③ 切页再回来:keep-mounted 不该把旧对话带回来 ────────────────────────
  await sendMessage(page, HOME, "第三条:切页测试");
  await page.waitForFunction(
    (sel) => document.querySelectorAll(`${sel} .msg-user`).length === 1,
    HOME,
    { timeout: 20000 },
  );
  await page.locator('.side-row:has-text("待办事项")').first().click();
  await page.locator(".todo-page").waitFor({ timeout: 10000 });
  await newChatBtn.click();
  await page.waitForFunction(
    (sel) => document.querySelectorAll(`${sel} .msg-user`).length === 0,
    HOME,
    { timeout: 20000 },
  );
  check((await userMsgs(page)) === 0, "从别的页点「新对话」回首页:也是白纸");

  // ── ④ 旧对话没丢:仍能在历史里点回去(清空 ≠ 删除)────────────────────────
  await page.waitForFunction(
    () => document.querySelectorAll(".session-row").length > 0,
    { timeout: 20000 },
  );
  const sessions = await page.locator(".session-row").count();
  check(sessions > 0, `旧对话进了历史列表(${sessions} 条)= 清空不是丢失`);
} catch (e) {
  failed++;
  console.error(String(e));
} finally {
  await browser.close();
}
console.log(failed === 0 ? "NEW-CHAT E2E: ALL PASS" : `NEW-CHAT E2E: ${failed} FAIL`);
process.exit(failed === 0 ? 0 : 1);
