// e2e 公共件(O1 工具债沉淀):chromium 定位 / 登录 / 常用等待。
// 场景文件 import 这里,别再手搓 driver。
import { createRequire } from "node:module";
import { readdirSync, existsSync } from "node:fs";
import os from "node:os";
import path from "node:path";

const DEFAULT_PW_MODULES = "/root/.npm/_npx/e41f203b7505f1fb/node_modules";

/** 从 npx 缓存(或 E2E_PW_MODULES)拿 playwright-core。 */
export function loadPlaywright() {
  const base = process.env.E2E_PW_MODULES || DEFAULT_PW_MODULES;
  const req = createRequire(path.join(base, "/"));
  return req("playwright-core");
}

/** 找 ms-playwright 缓存里最新的 chromium 可执行。 */
export function chromiumPath() {
  const root = path.join(os.homedir(), ".cache", "ms-playwright");
  const dirs = readdirSync(root)
    .filter((d) => /^chromium-\d+$/.test(d))
    .sort((a, b) => Number(b.split("-")[1]) - Number(a.split("-")[1]));
  for (const d of dirs) {
    for (const sub of ["chrome-linux64", "chrome-linux"]) {
      const p = path.join(root, d, sub, "chrome");
      if (existsSync(p)) return p;
    }
  }
  throw new Error(`ms-playwright 缓存里没有 chromium:${root}`);
}

export async function launchBrowser() {
  const pw = loadPlaywright();
  return pw.chromium.launch({ headless: true, executablePath: chromiumPath() });
}

/** 在 scope(容器选择器)内完成口令登录并等到已连接(.chat-meta 出现)。 */
export async function loginPane(page, scope, password, timeout = 20000) {
  const input = page.locator(`${scope} .chat-login input[type=password]`);
  await input.waitFor({ timeout });
  await input.fill(password);
  await page.locator(`${scope} .chat-login button[type=submit]`).click();
  await page.locator(`${scope} .chat-meta`).waitFor({ timeout });
}

/** 等到已连接(.chat-meta 出现)—— **全程不手输口令**。
 *
 * track opendesign-key-onboarding(2026-08-16):T2 起 ds-web 用后端口令替前端签
 * (`_gateway_password()`),业主不该被要求记一个我们自己生成的口令。
 * 于是 `loginPane` 那条路在**有代签的环境里根本走不到** —— 登录框压根不出现。
 *
 * 🔴 断言方向是这一条的全部价值:不是「没有登录框就跳过」,而是
 *    **连上了 + 登录框一次都没露面**。写成「有登录框就填、没有就算了」的话,
 *    代签哪天坏掉,判据照样绿 —— 而那正是这条主路从 T2.5 到今天
 *    **没有任何一条自动判据走通过**的原因(tasks.md T5 记的第三条)。
 *
 * 🔴 两种病必须分得开:连不上时,「回落到要口令」和「压根没连上」是不同的病,
 *    报同一句话会让我从头查错方向(08-14 那一夜的代价就在这儿)。
 *
 * 口令兜底路径仍然活着、仍然被测 —— 那是 `loginPane` 的活儿(自起 ds_web 的场景
 * 拿不到代签口令,登录框照常出现)。两条路各有各的判据,别合并。
 */
export async function waitConnected(page, scope, timeout = 20000) {
  try {
    await page.locator(`${scope} .chat-meta`).waitFor({ timeout });
  } catch (e) {
    const login = await page.locator(`${scope} .chat-login`).count();
    throw new Error(login > 0
      ? `代签主路没走通:界面回落到「请业主手输口令」了(T2 起前端不该再持有口令)`
      : `没连上,而且登录框也没出现 —— 是另一种病(后端没起来?):${e.message}`);
  }
  const login = await page.locator(`${scope} .chat-login`).count();
  if (login !== 0) throw new Error("已连接了但登录框还在,状态自相矛盾");
}

/** 等到**真的能发消息**(view 已是 connected)。
 *
 * 🔴 为什么不并进 waitConnected:`.chat-meta` 出现 **不等于** 连上了 —— ChatPage 让
 *    reconnecting 与 connected **走同一条渲染路径**(断线前的对话必须留在眼前,
 *    见 ChatPage 875 行那段注释),重连中它照样在。要发消息的场景光等它会撞上
 *    disabled 的输入框,报「element is not enabled」,而那句报错完全不指向真因。
 * 🔴 但也**不能无条件加进 waitConnected**:2026-08-16 我这么干过一次,当场把原本
 *    绿的 chat_image 打红 —— 它是 stub 场景、压根不发消息,connected 对它是**过强**
 *    的要求。**误报和假绿一样坏**,而且更贵:它指着一份好判据让我去改。
 * ⇒ 谁要发消息谁自己加这一句。发送键的 disabled 在 ChatPage 里写死
 *   `disabled={view.kind !== "connected"}`,是 connected 唯一可观察的代理。
 */
export async function waitSendable(page, scope, timeout = 20000) {
  await page.locator(`${scope} .send-btn:not([disabled])`).waitFor({ timeout });
}

/** 在 scope 内发一条消息(textarea + 发送键)。 */
export async function sendMessage(page, scope, text) {
  await page.locator(`${scope} textarea`).fill(text);
  await page.locator(`${scope} .send-btn`).click();
}

/** 等 scope 内出现一条完成态的 AI 回复(流式结束;不断言内容)。 */
export async function waitAssistantDone(page, scope, timeout = 180000) {
  await page
    .locator(`${scope} .msg-ai:not(.streaming):not(.thinking)`)
    .first()
    .waitFor({ timeout });
}

/** 收件箱两态兼容(v4 质感收口起默认收成一行摘要):有摘要行且未展开 → 点开;
 * 旧版(无摘要行)no-op。展开态以 [data-ui="inbox-expanded"] 标记为准。 */
export async function expandInbox(page) {
  const sum = page.locator('[data-ui="inbox-summary"]');
  if ((await sum.count()) > 0 &&
      (await page.locator('[data-ui="inbox-expanded"]').count()) === 0) {
    await sum.first().click();
  }
}

/** 简易断言:失败即抛,场景层统一 try/catch 计数。 */
export function check(cond, label) {
  if (!cond) throw new Error(`FAIL: ${label}`);
  console.log(`  ok - ${label}`);
}
