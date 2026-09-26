// 业主同意卡:点完之后结果要送回**提卡的那个聊天** —— track opendesign-consent-dock。
// 真 chromium + 真 ds_web;聊天网关用页内 WebSocket 替身(底座见 _ws-stub.mjs)。
//
// 由来(PR #2 两轮本地审查,都是实机复现、都是"结果被吞掉、对话卡死"):
//   R1 助手等确认时点「停止」,再点「同意」:工具还在等(nanobot 不把取消传给 MCP 进程),
//      后端仍报 waiter=true,前端只看 waiter ⇒ 不通知助手。
//   R2 修成"waiter 且任意聊天在跑"之后:首页停止 → 项目助手跑另一条 → 回首页点同意,
//      "项目助手在跑"被当成"这张卡有人接" ⇒ 又吞掉。
//
// 替身怎么模拟"工具停在卡上等":聊天发出一句 ⇒ 替身回 running、**不收尾**(这一轮一直在跑),
// 同时由本脚本经**核心函数**排一条真的待确认、并打上"有工具在等"的标记(ds_consent.mark_waiter,
// 截止时刻在未来)—— 这正是 await_owner 等待期间、以及点了停止之后那次孤儿调用留下的状态。
// 收到 `/stop` ⇒ 替身回 goal_status:idle(网关真实行为),这一轮结束。
//
// 覆盖:
//   C0 对照:提卡的聊天还在跑 ⇒ 点同意后**不许**补话(结果已作为工具返回值送到)。
//   C1 R2 原样:首页停止 → 项目助手在跑另一条 → 回首页点同意 ⇒ 首页那条连接收到"同意"那句话。
//   C2 在**别的聊天**里点首页提的卡 ⇒ 话仍送回首页(是首页的助手在等)。
//   C3 三审原样:首页提 A → 停止 → 首页又提 B → 点 A 的旧卡 ⇒ 仍要告诉首页(在跑的是 B 那一轮):
//      B 在跑时排队、不塞输入框,B 一结束自动发;补话带上落盘结果(认出几个项目夹、已生效),
//      助手不用再拿同样参数申请一遍。
//
// 跑法:node tests/e2e/consent_dock_two_chats.e2e.mjs(自起 ds_web 于 8860)
import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, waitSendable, check } from "./helpers.mjs";
import { WS_STUB_BASE } from "./_ws-stub.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8860;
const HOME = ".home-pane";
const COL = ".chatcol";

const STUB = () => {
  window.__sent = [];            // [{ slot, content }]
  const json = (obj) => Promise.resolve(new Response(JSON.stringify(obj),
    { status: 200, headers: { "Content-Type": "application/json" } }));
  const origFetch = window.fetch;
  window.fetch = (url, init) => {
    const u = String(url);
    if (u.includes("/api/chat/bootstrap")) {
      return json({ token: "stub-token", ws_path: "/ws", expires_in: 600, model_name: "stub-model" });
    }
    if (u.includes("/api/chat/sessions")) return json({ sessions: [] });
    return origFetch(url, init);
  };
  let n = 0;
  class StubWS extends window.__BaseStubWS {
    constructor(url) {
      super(url);
      this.chatId = `chat-${++n}`;
      setTimeout(() => {
        this.readyState = StubWS.OPEN;
        this.onopen?.({});
        this._emit({ event: "ready", chat_id: this.chatId });
      }, 10);
    }
    send(data) {
      let m = null;
      try { m = JSON.parse(data); } catch { return; }
      if (m.type === "attach") {            // 项目助手挂回它那条项目对话
        this.chatId = m.chat_id;
        setTimeout(() => this._emit({ event: "attached", chat_id: m.chat_id }), 10);
        return;
      }
      if (m.type !== "message") return;
      window.__sent.push({ slot: this.__dsSlot || "?", content: m.content });
      if (m.content === "/stop") {
        setTimeout(() => this._emit({ event: "goal_status", chat_id: this.chatId, status: "idle" }), 20);
        return;
      }
      // 这一轮开始跑、不收尾 —— 等价于助手的工具正停在确认卡上等
      setTimeout(() => this._emit({ event: "goal_status", chat_id: this.chatId,
                                    status: "running", started_at: 1 }), 10);
    }
  }
  window.WebSocket = StubWS;
};

const tmp = mkdtempSync(join(tmpdir(), "consent2-e2e-"));
const dsRoot = join(tmp, "ds");
const oldRoot = join(tmp, "old");
const newRoot = join(tmp, "new");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
mkdirSync(join(oldRoot, "01-项目", "翡翠湾-1801"), { recursive: true });
mkdirSync(join(newRoot, "01-项目", "机密别墅"), { recursive: true });
const cfgPath = join(dsRoot, "config", "workspace.json");
writeFileSync(cfgPath, JSON.stringify({ root: oldRoot, projects: {}, projectsDir: "01-项目" }, null, 2));
// 已配 key 的机器(否则 App 一打开就跳去模型设置页,见 chat_model_error.e2e.mjs 同款夹具)
const home = join(tmp, "home");
const nbCfg = join(home, ".nanobot", "config.json");
mkdirSync(join(home, ".openDesign"), { recursive: true });
writeFileSync(join(home, ".openDesign", "key.txt"), "sk-e2e-consent-two-chats\n");
mkdirSync(join(home, ".nanobot"), { recursive: true });
const template = readFileSync(join(ROOT, "config", "nanobot.config.windows.jsonc"), "utf8")
  .split("\n").filter((ln) => !/^\s*\/\//.test(ln)).join("\n");
writeFileSync(nbCfg, JSON.stringify(JSON.parse(template), null, 2));

/** 经**核心函数**排一条真的待确认,并标上"有工具在等"(截止时刻在未来)。 */
function stageWaitingCard(root) {
  const r = spawnSync("python3", ["-c", `
import sys; sys.path.insert(0, ${JSON.stringify(join(ROOT, "bin"))})
import ds_tools, ds_consent
r = ds_tools.set_workspace(${JSON.stringify(root)}, ds_root=${JSON.stringify(dsRoot)})
assert r.get("pending"), r
ds_consent.mark_waiter(${JSON.stringify(dsRoot)}, r["pending_id"], "2099-01-01T00:00:00")
print(r["pending_id"])
`], { encoding: "utf-8" });
  const pid = (r.stdout || "").trim();
  if (!/^\d{8}-\d{6}-[0-9a-f]{6}$/.test(pid)) throw new Error(`夹具没排上待确认:${r.stdout}${r.stderr}`);
  return pid;
}

let failures = 0;
let browser = null;
let srv = null;
const step = async (label, fn) => {
  console.log(`\n== ${label}`);
  try { await fn(); } catch (e) { failures += 1; console.log(`  not ok - ${label}: ${e.message}`); }
};
const sentBy = (page, slot) =>
  page.evaluate((s) => window.__sent.filter((x) => x.slot === s).map((x) => x.content), slot);

async function send(page, scope, text) {
  await page.locator(`${scope} textarea`).fill(text);
  await waitSendable(page, scope);
  await page.locator(`${scope} .send-btn`).click();
  await page.locator(`${scope} .stop-btn`).waitFor({ timeout: 8000 });   // 这一轮真的在跑了
}

try {
  srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
    env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT), DS_NANOBOT_CONFIG: nbCfg,
           HOME: home, USERPROFILE: home },
    stdio: ["ignore", "inherit", "inherit"],
  });
  const base = `http://127.0.0.1:${PORT}`;
  for (let i = 0; ; i++) {
    try { await fetch(`${base}/api/health`); break; }
    catch { if (i > 50) throw new Error("ds_web 起不来"); await new Promise((r) => setTimeout(r, 200)); }
  }
  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.route("**/api/update/**", (r) => r.fulfill({ status: 200, body: "{}" }));
  await page.addInitScript(() => localStorage.setItem("ds-chat-password", "stub"));
  await page.addInitScript(WS_STUB_BASE);
  await page.addInitScript(STUB);
  const resolves = [];
  page.on("response", async (r) => {
    if (r.url().includes("/api/consent/resolve")) resolves.push(await r.json().catch(() => null));
  });
  const homeCard = page.locator(`${HOME} [data-ui="consent-card"]`);
  const colCard = page.locator(`${COL} [data-ui="consent-card"]`);

  await step("C0 对照:提卡的聊天还在跑 ⇒ 点同意后不补话(结果已由工具送到)", async () => {
    await page.goto(`${base}/#/`, { waitUntil: "domcontentloaded" });
    await send(page, HOME, "把工作区接到新文件夹");
    stageWaitingCard(newRoot);
    await homeCard.waitFor({ timeout: 10000 });
    const before = (await sentBy(page, "home")).length;
    await homeCard.locator('[data-ui="consent-item"] button').nth(1).click();   // 同意
    await homeCard.waitFor({ state: "detached", timeout: 8000 });
    await page.waitForTimeout(800);
    check(resolves.at(-1)?.waiter === true, `后端回 waiter=true(${JSON.stringify(resolves.at(-1))})`);
    check((await sentBy(page, "home")).length === before, "首页那一轮还在跑 ⇒ 没有多发一句");
    // 收尾:停掉这一轮,回到干净状态
    await page.locator(`${HOME} .stop-btn`).click();
    await page.locator(`${HOME} .stop-btn`).waitFor({ state: "detached", timeout: 8000 });
  });

  await step("C1 R2 原样:首页停止 → 项目助手跑另一条 → 回首页点同意 ⇒ 告诉首页", async () => {
    writeFileSync(cfgPath, JSON.stringify({ root: oldRoot, projects: {}, projectsDir: "01-项目" }, null, 2));
    await send(page, HOME, "再把工作区接一次");
    stageWaitingCard(newRoot);
    await homeCard.waitFor({ timeout: 10000 });                 // 卡在首页跑着时冒出来 ⇒ 归首页
    await page.locator(`${HOME} .stop-btn`).click();            // ① 首页 ■ 停止
    await page.locator(`${HOME} .stop-btn`).waitFor({ state: "detached", timeout: 8000 });
    await page.goto(`${base}/#/workspace`);                     // ② 项目助手跑另一条请求
    await send(page, COL, "汇总还没确认的");
    await page.goto(`${base}/#/`);                              // ③ 回首页点原卡的「同意」
    await homeCard.waitFor({ timeout: 10000 });
    const before = (await sentBy(page, "home")).length;
    await homeCard.locator('[data-ui="consent-item"] button').nth(1).click();
    await homeCard.waitFor({ state: "detached", timeout: 8000 });
    check(resolves.at(-1)?.waiter === true, "复现条件成立:后端仍报 waiter=true(孤儿工具还在等)");
    check(JSON.parse(readFileSync(cfgPath, "utf-8")).root.endsWith("new"), "配置已改");
    await page.waitForFunction((n) => window.__sent.filter((x) => x.slot === "home").length > n,
      before, { timeout: 5000 }).catch(() => {});
    const homeMsgs = (await sentBy(page, "home")).slice(before);
    check(homeMsgs.some((c) => c.includes("同意") && c.includes(newRoot)),
      `首页那条连接收到了结果:${JSON.stringify(homeMsgs)}`);
    check(homeMsgs.some((c) => /认出 \d+ 个项目夹/.test(c) && c.includes("已经生效")),
      "补话带上了落盘结果并明说已生效");
    check(!(await sentBy(page, "workspace")).some((c) => c.includes("确认卡")),
      "没有错发给正在跑别的事的项目助手");
  });

  await step("C2 在项目助手里点首页提的卡 ⇒ 话仍送回首页", async () => {
    // 项目助手那一轮先停掉,好让卡在首页跑着时冒出来、归属唯一
    await page.goto(`${base}/#/workspace`);
    await page.locator(`${COL} .stop-btn`).click();
    await page.locator(`${COL} .stop-btn`).waitFor({ state: "detached", timeout: 8000 });
    writeFileSync(cfgPath, JSON.stringify({ root: oldRoot, projects: {}, projectsDir: "01-项目" }, null, 2));
    await page.goto(`${base}/#/`);
    // C1 替业主说的那句话本身开了新的一轮(替身不收尾),先停掉
    if (await page.locator(`${HOME} .stop-btn`).count()) {
      await page.locator(`${HOME} .stop-btn`).click();
      await page.locator(`${HOME} .stop-btn`).waitFor({ state: "detached", timeout: 8000 });
    }
    await send(page, HOME, "第三次接工作区");
    stageWaitingCard(newRoot);
    await homeCard.waitFor({ timeout: 10000 });
    await page.locator(`${HOME} .stop-btn`).click();
    await page.locator(`${HOME} .stop-btn`).waitFor({ state: "detached", timeout: 8000 });
    await page.goto(`${base}/#/workspace`);
    await colCard.waitFor({ timeout: 10000 });
    const before = (await sentBy(page, "home")).length;
    await colCard.locator('[data-ui="consent-item"] button').nth(1).click();
    await colCard.waitFor({ state: "detached", timeout: 8000 });
    await page.waitForFunction((n) => window.__sent.filter((x) => x.slot === "home").length > n,
      before, { timeout: 5000 }).catch(() => {});
    const homeMsgs = (await sentBy(page, "home")).slice(before);
    check(homeMsgs.some((c) => c.includes("同意")), `送回了首页:${JSON.stringify(homeMsgs)}`);
    check(!(await sentBy(page, "workspace")).some((c) => c.includes("确认卡")), "没有发给点卡的项目助手");
  });
  await step("C3 三审原样:首页提 A → 停止 → 首页又提 B → 点 A 的旧卡 ⇒ 仍告诉首页", async () => {
    await page.goto(`${base}/#/`);
    if (await page.locator(`${HOME} .stop-btn`).count()) {       // C2 的补话开了新一轮,先停掉
      await page.locator(`${HOME} .stop-btn`).click();
      await page.locator(`${HOME} .stop-btn`).waitFor({ state: "detached", timeout: 8000 });
    }
    writeFileSync(cfgPath, JSON.stringify({ root: oldRoot, projects: {}, projectsDir: "01-项目" }, null, 2));
    await send(page, HOME, "请求 A:接工作区");
    stageWaitingCard(newRoot);
    await homeCard.waitFor({ timeout: 10000 });                  // A 的卡归「首页这一轮」
    await page.locator(`${HOME} .stop-btn`).click();             // ■ 停止
    await page.locator(`${HOME} .stop-btn`).waitFor({ state: "detached", timeout: 8000 });
    await send(page, HOME, "请求 B:汇总一下");                   // 同一个聊天开了新一轮
    const before = (await sentBy(page, "home")).length;
    await homeCard.locator('[data-ui="consent-item"] button').nth(1).click();   // 点 A 的旧卡
    await homeCard.waitFor({ state: "detached", timeout: 8000 });
    check(resolves.at(-1)?.waiter === true, "复现条件成立:后端仍报 waiter=true");
    // 首页正在跑 B ⇒ 这时发不出去:排队,不许塞进输入框让业主自己按发送
    await page.waitForTimeout(800);
    check(!(await page.locator(`${HOME} textarea`).inputValue()).includes("同意"), "没有把话塞进输入框");
    check((await sentBy(page, "home")).length === before, "B 还在跑时没有插话");
    await page.locator(`${HOME} .stop-btn`).click();             // B 这一轮结束(这里用停止模拟)
    await page.waitForFunction((n) => window.__sent.filter((x) => x.slot === "home" && x.content.includes("同意")).length > 0
      && window.__sent.filter((x) => x.slot === "home").length > n, before + 1, { timeout: 8000 }).catch(() => {});
    const landed = (await sentBy(page, "home")).slice(before).find((c) => c.includes("同意")) || "";
    check(!!landed, `B 一结束,首页自动把 A 的结果发给了助手:${JSON.stringify((await sentBy(page, "home")).slice(before))}`);
    check(/认出 \d+ 个项目夹/.test(landed) && landed.includes("不用再调用工具"),
      `带上了落盘结果、明说别再申请:${JSON.stringify(landed)}`);
  });
} catch (e) {
  failures += 1;
  console.log(`  not ok - 场景中断: ${e.message}`);
} finally {
  if (browser) await browser.close();
  if (srv) srv.kill();
  rmSync(tmp, { recursive: true, force: true });
}

console.log(failures === 0 ? "\nALL PASS" : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
