// e2e 公共件(O1 工具债沉淀):chromium 定位 / 登录 / 常用等待。
// 场景文件 import 这里,别再手搓 driver。
//
// 🔴 **本文件导入即生效**:顶部有无出口守卫,会把导入它的 e2e 进程搬进独立网络命名空间。
//    所以 tests/test_e2e_harness_guard.mjs 绝不能导入它(那样就问不出前提了)。
import { createRequire } from "node:module";
import { readdirSync, existsSync, mkdtempSync, rmSync, appendFileSync, readlinkSync } from "node:fs";
import { spawnSync } from "node:child_process";
import os from "node:os";
import path from "node:path";

// ── 无出口守卫(track opendesign-e2e-no-egress-browser-tmp,2026-09-16)────────────
//
// 不变量只有一句:**跑判据的进程不许有外网出口。**
// 由来:默认 e2e 起的真 ds_web 一打开页面就调 `/api/update/check`,**真去问 GitHub** ——
// 38 条里只有 update_notice 用 page.route 拦了。代价是判据替业主花掉他的免登录额度
// (09-15 发 0.98.5 时产品查更新被 403 挡住,疑似就是被它用光;归因没钉死,但代码路径是确定的),
// 而且判据结果从此看外网脸色。aiwork 08-10 为同一件事立过机械不变量(kimi 额度被判据烧光),
// 这边一直没有。做法照搬 aiwork `tests/_no_egress.py` / `_no-egress.sh`。
//
// ⚠️ **强度声明**:这道闸挡的是手滑,不是蓄意。豁免按脚本名,改个名就能绕过;root 一行
//    `nsenter` 也能出去。它保证的是"没人不小心留下一个外呼口",不是安全边界。
//
// 守在**每个 e2e 进程自己身上**,不守在 run-all.sh 入口:手跑单条 e2e 是日常,
// 只包总跑入口等于守错门(本机"守卫守错门"已经栽过三次)。

/** 要连主命名空间里活网关与 8768 的两条 —— **豁免名单的唯一一份**。
 *  run-all.sh 的 NEEDS_GATEWAY 由判据 ne5 钉成与它逐项相同(名单散成两份迟早只更新一处)。 */
export const NEEDS_LIVE_GATEWAY = ["new_chat.e2e.mjs", "project-thread.e2e.mjs"];

const NO_EGRESS_REFUSED = 78;
const NO_EGRESS_TRIED = "DS_E2E_NOEGRESS_TRIED";

function noEgressRefuse(why) {
  process.stderr.write(`🔴 无出口守卫:${why}\n`);
  process.stderr.write("   e2e 判据进程必须没有外网出口(不许在跑判据时把业主的额度花出去)。\n");
  process.stderr.write("   来源:tests/e2e/helpers.mjs,track opendesign-e2e-no-egress-browser-tmp。\n");
  process.exit(NO_EGRESS_REFUSED);
}

/** 已经在独立网络命名空间里?——**看内核,不看环境变量**(环境变量是零成本后门)。 */
function noEgressIsolated() {
  try {
    return readlinkSync("/proc/self/ns/net") !== readlinkSync("/proc/1/ns/net");
  } catch {
    return false;
  }
}

function noEgressOpen() {
  return spawnSync("bash", ["-c", "exec 3<>/dev/tcp/1.1.1.1/443"],
    { timeout: 3000, stdio: "ignore" }).status === 0;
}

function enforceNoEgress() {
  const script = process.argv[1] ? path.basename(process.argv[1]) : "";
  if (NEEDS_LIVE_GATEWAY.includes(script)) return;   // 明示豁免:它们要的就是活网关

  if (!noEgressIsolated()) {
    // 自举标记只用来打断死循环,**不是身份牌**:预设它不能让人蒙混过关(ne6)。
    if (process.env[NO_EGRESS_TRIED]) {
      noEgressRefuse("已经自举过一次,却仍然不在独立的网络命名空间里(unshare 没生效?)");
    }
    // 先探再 re-exec:直接换掉本进程的话,unshare 失败连一句解释都留不下。
    let probe;
    try {
      probe = spawnSync("unshare", ["-n", "--", "true"], { stdio: "ignore" });
    } catch {
      noEgressRefuse("找不到 unshare,做不到网络隔离 ⇒ 拒跑");
    }
    if (!probe || probe.error || probe.status !== 0) {
      noEgressRefuse("unshare -n 用不了(没权限?内核不支持?)⇒ 拒跑");
    }
    // 用 spawnSync 而不是 exec:node 没有 execve。父进程原样透传子进程的退出码/信号。
    const child = spawnSync("unshare",
      ["-n", "--", "bash", "-c", 'ip link set lo up 2>/dev/null || true; exec "$0" "$@"',
       process.execPath, ...process.execArgv, ...process.argv.slice(1)],
      { stdio: "inherit", env: { ...process.env, [NO_EGRESS_TRIED]: "1" } });
    if (child.error) noEgressRefuse(`起不来隔离子进程:${child.error.message}`);
    if (child.signal) process.exit(128 + (os.constants.signals[child.signal] || 0));
    process.exit(child.status ?? 1);
  }

  // 隔离成功就摘掉标记:留着会被子进程继承,子进程若回到主命名空间会被误判成"自举失败"。
  delete process.env[NO_EGRESS_TRIED];

  // **进来了还要实测一次**:闸没生效却以为生效,比没有闸更糟。
  if (noEgressOpen()) {
    noEgressRefuse("已经进了命名空间,却**仍然连得出去** ⇒ 拒跑(别把没生效的闸当生效)");
  }
}

enforceNoEgress();

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
  // 浏览器的临时目录**归测试自己所有**:给 Chromium 一个我们建的 TMPDIR,进程退出时收掉。
  // 由来:浏览器没走正常关闭(开着就退出 / 被硬杀)每次都在 TMPDIR 留一个
  // `org.chromium.Chromium.XXXXXX`,与泄漏闸偶发红"剩 1 个空前缀目录"同形。
  const dir = mkdtempSync(path.join(os.tmpdir(), "ds-e2e-browser-"));
  let browser;
  try {
    browser = await pw.chromium.launch({
      headless: true,
      executablePath: chromiumPath(),
      env: { ...process.env, TMPDIR: dir, TMP: dir, TEMP: dir },
    });
  } catch (err) {
    rmSync(dir, { recursive: true, force: true });   // 起不来也不留壳
    throw err;
  }
  // 🔴 监听在 launch **之后**注册 ⇒ 排在 Playwright 自己的退出清理(杀浏览器)之后。
  // 🔴 收掉之前必须**点名**:悄悄收掉等于把泄漏闸的信号吞了,下次再发生就没人知道是谁干的。
  process.on("exit", () => {
    let left = [];
    try { left = readdirSync(dir); } catch { /* 已经没了 */ }
    if (left.length) {
      const who = process.argv[1] ? path.basename(process.argv[1]) : "(未知脚本)";
      const what = `浏览器没走正常关闭,留下 ${left.join(" ")}(已收掉)`;
      process.stderr.write(`⚠️ ${what} —— ${who}\n`);
      if (process.env.E2E_BROWSER_NOTES) {
        try { appendFileSync(process.env.E2E_BROWSER_NOTES, `${who}: ${what}\n`); } catch { /* 记不下也别把测试带崩 */ }
      }
    }
    try { rmSync(dir, { recursive: true, force: true }); } catch { /* 尽力 */ }
  });
  return browser;
}

/** 在 scope(容器选择器)内完成口令登录并等到已连接(模型按钮 [data-ui="chat-model"] 出现)。 */
export async function loginPane(page, scope, password, timeout = 20000) {
  const input = page.locator(`${scope} .chat-login input[type=password]`);
  await input.waitFor({ timeout });
  await input.fill(password);
  await page.locator(`${scope} .chat-login button[type=submit]`).click();
  await page.locator(`${scope} [data-ui="chat-model"]`).waitFor({ timeout });
}

/** 等到已连接(模型按钮 [data-ui="chat-model"] 出现)—— **全程不手输口令**。
 *
 * ⚠️ 2026-09-15 换过标记(track opendesign-composer-model-picker):原来认的是聊天头部 `.chat-meta`
 *    (左上角「已连接 · 模型名」)。业主验收时拍板**删掉那一行**、把模型挪进输入框右下角
 *    ⇒ "连上了"的可观察代理换成那颗按钮。语义不变:它和旧头部一样**只在真连上时渲染**,
 *    重连中不出现(chat_reconnect 的 ⑬/㉝ 那几条照问)。这不是放宽:删头部是业主的决定,不是考卷的。
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
    await page.locator(`${scope} [data-ui="chat-model"]`).waitFor({ timeout });
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
 * 🔴 为什么不并进 waitConnected:模型按钮 `[data-ui="chat-model"]` 只在 `view.kind === "connected"`
 *    时渲染(重连中**不在**,model_picker.e2e ⑭ 与红检 c1 钉着),可"连上了"仍**不等于**
 *    "发得出去":发送键在 `view.kind !== "connected" || transcript.busy || 草稿为空` 时灰着,
 *    上一轮还没答完时它照样灰着。要发消息的场景光等按钮会撞上 disabled,
 *    报「element is not enabled」,而那句报错完全不指向真因。
 *    (09-15 之前这里写的是「重连中它照样在」—— 那是旧 `.chat-meta` 时代就已不成立的理由,
 *     换标记时被机械照抄;评审 DeepSeek 指出、我核 ChatPage 属实。)
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
