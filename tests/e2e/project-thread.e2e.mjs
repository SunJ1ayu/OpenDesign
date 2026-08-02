// e2e:项目级对话(track opendesign-project-thread)。
// 断言:①项目会话首条消息带【当前项目:X】前缀 ②切项目=全新转录(上下文隔离)
// ③切回=attach 回放(消息还在,chat_id 不变) ④映射进 localStorage
// ⑤切到只连过没聊过的项目不卡死(attach 虚会话失败走自愈,仍能连上)。
// 前置:gateway(8765)+ds_web 在跑,见 tests/e2e/README.md。
import {
  launchBrowser,
  loginPane,
  sendMessage,
  waitAssistantDone,
  check,
} from "./helpers.mjs";

const BASE = process.env.E2E_BASE || "http://127.0.0.1:8768";
const PASSWORD = process.env.E2E_PASSWORD || "e2etest";
const PROJ_A = "翡翠湾-1801";
const PROJ_B = "星河名邸-2302";
const COL = ".chatcol"; // 工作区聊天列

const projRow = (page, name) =>
  page.locator(".proj-row", { hasText: name }).first();
const threadMap = (page) =>
  page.evaluate(() => JSON.parse(localStorage.getItem("odw.projectThreads") || "{}"));
/** 等某项目的映射落盘再读。
 *  记账是异步的:chat_id 从网关回来 → setState → effect 写 localStorage,
 *  比「已连接」文案晚一两帧(实测 2-4ms)。原来在 .chat-meta 出现后立刻读这个
 *  瞬间值,margin 薄到前端任何渲染改动都能把它翻红(2026-07-24 前端批实锤:
 *  同一份代码基线读到、新构建晚 4ms 读不到)。断言强度不变——仍要求映射存在
 *  且与 A 不同,只是允许它在几秒内到达。 */
const waitThread = async (page, project, timeout = 10000) => {
  await page.waitForFunction(
    (p) => !!JSON.parse(localStorage.getItem("odw.projectThreads") || "{}")[p],
    project,
    { timeout },
  );
  return threadMap(page);
};

const browser = await launchBrowser();
let failed = 0;
try {
  const page = await browser.newPage();
  await page.goto(BASE, { waitUntil: "domcontentloaded" });

  // ① 首页登录(home 实例;口令进 localStorage,后续列实例共享凭据)
  await loginPane(page, ".home-pane", PASSWORD);
  console.log("step1 home 登录已连接");

  // ② 进项目 A:登录后选项目 → colResume nonce 变 → 列实例自动连上(不用二次登录)
  await projRow(page, PROJ_A).click();
  await page.locator(`${COL} .chat-meta`).waitFor({ timeout: 20000 });
  console.log("step2 项目 A 聊天列已连接");

  // ③ 发消息:首条带【当前项目】前缀,上屏可见
  await sendMessage(page, COL, "这是A项目的e2e测试消息,请不要调用任何工具,直接回复「收到」两个字");
  const userMsg = page.locator(`${COL} .msg-user`).first();
  await userMsg.waitFor({ timeout: 5000 });
  const sent = (await userMsg.textContent()) || "";
  check(sent.startsWith(`【当前项目:${PROJ_A}】`), "首条消息带项目前缀");
  // AI 回复=可选断言:本 track 测的是会话隔离/前缀/回放/映射(协议层事实);
  // MiMo 上游抖动时(stream stall)turn 以错误回复收尾,后续断言照走。
  try {
    await waitAssistantDone(page, COL, 90000);
    console.log("step3 A 项目一轮对话完成(含 AI 回复)");
  } catch {
    console.log("step3 ⚠️ AI 回复未等到(上游 LLM 抖动)——协议层断言继续");
  }

  // ④ 映射已记账
  let map = await waitThread(page, PROJ_A);
  check(typeof map[PROJ_A] === "string" && map[PROJ_A].length > 0, "A 项目映射进 localStorage");
  const chatIdA = map[PROJ_A];

  // ⑤ 切项目 B:全新上下文(转录清空,回到空态文案)
  await projRow(page, PROJ_B).click();
  await page.locator(`${COL} .chat-meta`).waitFor({ timeout: 20000 });
  check((await page.locator(`${COL} .msg-user`).count()) === 0, "B 项目转录为空(上下文隔离)");
  map = await waitThread(page, PROJ_B);
  check(map[PROJ_B] && map[PROJ_B] !== chatIdA, "B 项目映射独立于 A");
  console.log("step5 B 项目全新上下文");

  // ⑥ 切回 A:attach + thread 回放,消息还在,chat_id 不变
  await projRow(page, PROJ_A).click();
  await page.locator(`${COL} .chat-meta`).waitFor({ timeout: 20000 });
  await page
    .locator(`${COL} .msg-user`, { hasText: "这是A项目的e2e测试消息" })
    .first()
    .waitFor({ timeout: 30000 });
  map = await threadMap(page);
  check(map[PROJ_A] === chatIdA, "切回 A:chat_id 稳定不变");
  console.log("step6 A 项目续聊回放命中");

  // ⑦ 再切 B(此前只连过没聊过):attach 虚会话即便失败也要自愈连上,不卡死,
  //   且映射保持可用(原 id 挂住或自愈换新 id,总之 B 名下有值)
  await projRow(page, PROJ_B).click();
  await page.locator(`${COL} .chat-meta`).waitFor({ timeout: 25000 });
  map = await waitThread(page, PROJ_B);
  check(typeof map[PROJ_B] === "string" && map[PROJ_B].length > 0, "B 再入后映射仍可用(挂住或自愈换新)");
  check(map[PROJ_A] === chatIdA, "B 的自愈不误伤 A 的映射");
  console.log("step7 虚会话再入韧性通过");

  console.log("ALL PASS (7 steps)");
} catch (e) {
  failed = 1;
  console.error(String(e));
} finally {
  await browser.close();
}
process.exit(failed);
