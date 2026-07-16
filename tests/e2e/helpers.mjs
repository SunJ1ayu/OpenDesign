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

/** 简易断言:失败即抛,场景层统一 try/catch 计数。 */
export function check(cond, label) {
  if (!cond) throw new Error(`FAIL: ${label}`);
  console.log(`  ok - ${label}`);
}
