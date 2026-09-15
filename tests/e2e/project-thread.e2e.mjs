// e2e:项目级对话(track opendesign-project-thread)。
// 断言:①项目会话首条消息带【当前项目:X】前缀 ②切项目=全新转录(上下文隔离)
// ③切回=attach 回放(消息还在,chat_id 不变) ④映射进 localStorage
// ⑤切到只连过没聊过的项目不卡死(attach 虚会话失败走自愈,仍能连上)。
// 前置:gateway(8765)+ds_web 在跑,见 tests/e2e/README.md。
import {
  launchBrowser,
  waitConnected,
  sendMessage,
  waitAssistantDone,
  check,
} from "./helpers.mjs";

const BASE = process.env.E2E_BASE || "http://127.0.0.1:8768";
// 口令常量已删(2026-08-16):T2 起 ds-web 替前端代签,这两条**不再手输口令**。
// 留个死变量在这儿会让人以为还要设 E2E_PASSWORD —— 见 helpers.waitConnected。
const PROJ_A = "翡翠湾-1801";
const PROJ_B = "星河名邸-2302";
const COL = ".chatcol"; // 工作区聊天列

const projRow = (page, name) =>
  page.locator(".proj-row", { hasText: name }).first();
const threadMap = (page) =>
  page.evaluate(() => JSON.parse(localStorage.getItem("odw.projectThreads") || "{}"));
/** 等某项目的映射落盘再读。
 *  记账是异步的:chat_id 从网关回来 → setState → effect 写 localStorage,
 *  比「已连接」文案晚一两帧(实测 2-4ms)。原来在 模型按钮 [data-ui="chat-model"] 出现后立刻读这个
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

/** 夹具:**这条 e2e 自己造它要用的两个项目**(继承的账 B)。
 *
 * 🔴 为什么非做不可:这条场景和别的 e2e 不一样 —— 别的自己起 ds_web、自己造夹具;
 * 它连的是**外面已经起好的那一个**,只知道 HTTP 地址、够不着人家的 DS_ROOT。
 * 于是夹具长年靠"这台机器上碰巧有 `projects/翡翠湾-1801.md` 和 `星河名邸-2302.md`",
 * 而 git 里 `projects/` 只提交了 `.gitkeep`(`.gitignore:23` 排掉整个目录)
 * ⇒ **换一台机器新克隆必红**,而且报错里一个字都不提夹具 ——
 * 表现只是在 `.proj-row` 上干等 30 秒然后 TimeoutError。
 * 它长年因为"要活 gateway"而 SKIP,这个洞从来没露过头,
 * 2026-09-08 收第一刀时才真撞上(ds_web 起在一个空的 DS_ROOT 上)。
 *
 * 够得着的只有 HTTP,那就用 HTTP:`/api/projects/create`。
 */
async function ensureFixtures() {
  const list = async () => {
    const r = await fetch(`${BASE}/api/projects`);
    if (!r.ok) {
      throw new Error(`夹具:列项目失败 HTTP ${r.status} —— ds_web 起在 ${BASE} 了吗?`);
    }
    return new Set(((await r.json()).projects || []).map((p) => p.key));
  };
  const have = await list();
  for (const name of [PROJ_A, PROJ_B]) {
    if (have.has(name)) continue;
    const r = await fetch(`${BASE}/api/projects/create`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project: name }),
    });
    if (!r.ok) throw new Error(`夹具:建不出项目「${name}」(HTTP ${r.status})`);
  }
  // 🔴 建完**再问一次列表**。不许拿"POST 回了 200"当"它真在列表里" ——
  // 本项目为这条栽过(「接线测试证明不了接上了」):写门和读门的名字校验口径
  // 曾经不一致,建得出来却 GET 恒 404。这一步问的是读门。
  const after = await list();
  const missing = [PROJ_A, PROJ_B].filter((n) => !after.has(n));
  if (missing.length) {
    throw new Error(`夹具:建完了,但 /api/projects 里仍然没有:${missing.join("、")}`);
  }
}

await ensureFixtures();

const browser = await launchBrowser();
let failed = 0;
try {
  const page = await browser.newPage();
  await page.goto(BASE, { waitUntil: "domcontentloaded" });

  // ① 首页登录(home 实例;口令进 localStorage,后续列实例共享凭据)
  await waitConnected(page, ".home-pane");
  console.log("step1 home 登录已连接");

  // ② 进项目 A:登录后选项目 → colResume nonce 变 → 列实例自动连上(不用二次登录)
  await projRow(page, PROJ_A).click();
  await page.locator(`${COL} [data-ui="chat-model"]`).waitFor({ timeout: 20000 });
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
  await page.locator(`${COL} [data-ui="chat-model"]`).waitFor({ timeout: 20000 });
  check((await page.locator(`${COL} .msg-user`).count()) === 0, "B 项目转录为空(上下文隔离)");
  map = await waitThread(page, PROJ_B);
  check(map[PROJ_B] && map[PROJ_B] !== chatIdA, "B 项目映射独立于 A");
  console.log("step5 B 项目全新上下文");

  // ⑥ 切回 A:attach + thread 回放,消息还在,chat_id 不变
  await projRow(page, PROJ_A).click();
  await page.locator(`${COL} [data-ui="chat-model"]`).waitFor({ timeout: 20000 });
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
  await page.locator(`${COL} [data-ui="chat-model"]`).waitFor({ timeout: 25000 });
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
