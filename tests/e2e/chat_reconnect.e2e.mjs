// O2 判据:断线自愈的端到端(track opendesign-chat-reconnect,T6)。
// 真 chromium + 真 ds_web + **stub 掉 ws/bootstrap/thread**,做法沿用 chat_image.e2e.mjs
// 已验证的第三条路(页面里换掉 window.WebSocket / window.fetch)。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// 为什么必须有这一份(纯逻辑判据接不住的):
//   `reconnect.ts` 的退避序列可以字字正确,而 `ChatPage` 压根没调它 —— O1 照样全绿。
//   这里数的是**真的有第二个 WebSocket 被构造出来**,以及界面上到底发生了什么。
//   同型史料:07-24 `columnCount==="3"` 全绿,实际正文被压成竖排。
//
// 判据锁死的三条"假绿路线":
//   ① 整页 reload 也能让界面"恢复" ⇒ 断言断线前的气泡还在(reload 会清掉它)。
//   ② 补缺口断言被本地已有消息满足 ⇒ 缺口那条**只存在于 stub 的历史响应里**,
//      客户端从来没从 ws 收到过它。
//   ③ "重连成功"其实是新开了一个空会话 ⇒ 断言真的发出了 attach、且挂的是**原来那个**
//      chat_id(不是 ready 给的新 id)。
//
// 跑法:node tests/e2e/chat_reconnect.e2e.mjs(自起 ds_web 于 8813;不需要 nanobot)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, loginPane, sendMessage } from "./helpers.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8813;
const PW = "e2e-pw";

// 断线期间服务端多出来的那条 —— **客户端永远不会从 ws 收到它**,
// 只可能通过"重连后拉历史"看到。补缺口做没做,全看它出不出现。
const BEFORE_TEXT = "断线前说的话";
const PENDING_TEXT = "本地发出但服务端没记上的那句";
const GAP_TEXT = "断线期间助手记下的那条";

let failures = 0;
/** 等条件成真;超时不抛,统一由 check 报同一句话。 */
async function until(fn, timeoutMs = 15000, stepMs = 200) {
  const t0 = Date.now();
  for (;;) {
    try { if (await fn()) return true; } catch { /* 元素还没出现,等下一轮 */ }
    if (Date.now() - t0 > timeoutMs) return false;
    await new Promise((r) => setTimeout(r, stepMs));
  }
}
function check(ok, label) {
  if (ok) console.log(`  ok   - ${label}`);
  else { console.log(`  FAIL - ${label}`); failures += 1; }
}

// ── 页面注入:stub ws + bootstrap + thread ──────────────────────────────────
const STUB = () => {
  window.__sent = [];
  window.__wsCount = 0;
  window.__ws = null;
  window.__bootstrap401 = false;
  window.__threadStatus = 200;
  window.__threadFetches = [];
  window.__silent = false; // true = 发出去的消息服务端不回(模拟"没记上")
  window.__firstReadyId = null;   // 第一条连接拿到的 chat_id = "原来那个"
  window.__lastReadyId = null;
  window.__attachIds = [];
  window.__holdAttached = false;  // true = 收到 attach 不回 attached(验"没挂上不算连上")
  window.__pendingAttach = null;
  window.__threadReady = false;   // attached 之前历史里没有断线期间那条(快照更早)
  window.__threadUrls = [];
  window.__thread401 = false;
  window.__wsTimes = [];          // 每条连接构造时刻 ⇒ 退避间隔可断言
  window.__failConnect = false;   // true = 新连接一建就断(验退避真的在涨)
  window.__thread = { schemaVersion: 3, sessionKey: "websocket:chat-e2e", messages: [] };

  const json = (o, status = 200) =>
    Promise.resolve(new Response(JSON.stringify(o), {
      status, headers: { "Content-Type": "application/json" },
    }));

  const origFetch = window.fetch;
  window.fetch = (url, init) => {
    const u = String(url);
    if (u.includes("/api/chat/bootstrap")) {
      if (window.__bootstrap401) return Promise.resolve(new Response("", { status: 401 }));
      return json({ token: "stub-token", ws_path: "/ws", expires_in: 600, model_name: "stub-model" });
    }
    if (u.includes("/thread")) {
      window.__threadUrls.push(u);
      window.__threadFetches.push(u);
      // **精确匹配真实代理路径**:现状是 /api/chat/sessions/websocket:<id>/thread
      // (ChatPage.tsx:197)。原来这里用 includes("/thread") 模糊放行 ——
      // 那会让"照设计文字写成 /api/chat/thread/<id>"的实现在真环境 404、在考卷里全绿。
      const want = `/api/chat/sessions/websocket:${window.__firstReadyId}/thread`;
      if (!u.includes(want)) {
        return Promise.resolve(new Response("webui thread not found", { status: 404 }));
      }
      if (window.__thread401) return Promise.resolve(new Response("", { status: 401 }));
      if (window.__threadStatus !== 200) {
        // 实测过的真形状:新建的空会话上拉历史就是 404 + 这句话
        return Promise.resolve(new Response("webui thread not found",
          { status: window.__threadStatus }));
      }
      // attached 之前只有更早的快照(§4 没承诺 attached 时缺口一定已可见)
      const t = window.__thread;
      if (!window.__threadReady) {
        return json({ ...t, messages: t.messages.filter((m) => !m.__gap) });
      }
      return json(t);
    }
    return origFetch(url, init);
  };

  class StubWS {
    constructor(url) {
      this.url = url;
      this.readyState = 0;
      window.__wsCount += 1;
      window.__wsTimes.push(Date.now());
      window.__ws = this;
      setTimeout(() => {
        if (this.readyState === 3) return;
        if (window.__failConnect) {   // 一建就断:模拟 gateway 没起
          this.readyState = 3;
          this.onclose?.({ code: 1006, reason: "stub fail", wasClean: false });
          return;
        }
        this.readyState = 1;
        this.onopen?.({});
        // 协议:每条新连接都发新 chat_id,前端弃用它、再 attach 回旧的
        const id = `chat-new-${window.__wsCount}`;
        if (window.__firstReadyId === null) window.__firstReadyId = id;
        window.__lastReadyId = id;
        this.#emit({ event: "ready", chat_id: id });
      }, 10);
    }
    #emit(o) { this.onmessage?.({ data: JSON.stringify(o) }); }
    send(data) {
      window.__sent.push(data);
      let m = null;
      try { m = JSON.parse(data); } catch { return; }
      if (m.type === "attach") {
        window.__attachIds.push(m.chat_id);
        // 真 gateway 对非法 id 回 error(协议 §2),stub 不许照单全收 ——
        // 否则"随便 attach 个什么都算成功"的实现也能全绿
        setTimeout(() => {
          if (m.chat_id !== window.__firstReadyId) {
            this.#emit({ event: "error", detail: "invalid chat_id" });
            return;
          }
          if (window.__holdAttached) { window.__pendingAttach = m.chat_id; return; }
          // ⚠️ 顺序要紧:#emit 是同步的,客户端会在它里面同步发起拉历史 ——
          // 先 emit 再置位,拉历史那一刻读到的还是 false(夹具自己的时序 bug,
          // 08-04 第一次跑实现时被 ⑦ 抓出来)。
          window.__threadReady = true; // attached 之后历史里才有断线期间那条
          this.#emit({ event: "attached", chat_id: m.chat_id });
        }, 10);
        return;
      }
      if (m.type !== "message" || window.__silent) return;
      setTimeout(() => {
        const sid = `stub-stream-${window.__sent.length}`;
        this.#emit({ event: "delta", text: "收到", stream_id: sid,
                     turn_id: m.turn_id, turn_phase: "answer", turn_seq: 1 });
        this.#emit({ event: "stream_end", stream_id: sid, turn_seq: 2 });
        this.#emit({ event: "turn_end", turn_phase: "complete", turn_seq: 3,
                     goal_state: { active: false } });
      }, 10);
    }
    close() { this.readyState = 3; }
  }
  window.WebSocket = StubWS;

  // 判据用的遥控器:放行被扣住的 attached
  window.__releaseAttach = () => {
    window.__holdAttached = false;
    const id = window.__pendingAttach;
    if (!id || !window.__ws) return false;
    window.__pendingAttach = null;
    window.__threadReady = true;
    window.__ws.onmessage?.({ data: JSON.stringify({ event: "attached", chat_id: id }) });
    return true;
  };

  // 判据用的遥控器:掐断当前连接
  window.__killWS = (code = 1006) => {
    const ws = window.__ws;
    if (!ws) return false;
    ws.readyState = 3;
    ws.onclose?.({ code, reason: "e2e kill", wasClean: false });
    return true;
  };
};

// ── 夹具 ────────────────────────────────────────────────────────────────────
const tmp = mkdtempSync(join(tmpdir(), "reconnect-e2e-"));
const dsRoot = join(tmp, "ds");
const wsdir = join(tmp, "ws");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
mkdirSync(wsdir, { recursive: true });
writeFileSync(join(dsRoot, "config", "workspace.json"),
  JSON.stringify({ root: wsdir, projects: {} }));

const pane = ".home-pane"; // 聊天在首页伴随列(chat_image.e2e.mjs 同款作用域)
let browser = null;
let srv = null;
try {
  srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
    env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT) },
    stdio: ["ignore", "inherit", "inherit"],
  });
  const base = `http://127.0.0.1:${PORT}`;
  for (let i = 0; ; i++) {
    try { await fetch(`${base}/api/health`); break; }
    catch {
      if (i > 50) throw new Error("ds_web 起不来");
      await new Promise((r) => setTimeout(r, 200));
    }
  }

  browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  const errs = [];
  page.on("pageerror", (e) => errs.push(String(e)));
  await page.addInitScript(STUB);
  await page.goto(`${base}/#/`, { waitUntil: "domcontentloaded" });
  await page.locator(pane).waitFor({ state: "visible", timeout: 10000 });
  await loginPane(page, pane, PW);

  const wsCount = () => page.evaluate(() => window.__wsCount);
  const sent = () => page.evaluate(() =>
    window.__sent.map((s) => { try { return JSON.parse(s); } catch { return null; } })
      .filter(Boolean));

  // ── 铺场景:先正常聊一句,留下"断线前"的痕迹 ─────────────────────────────
  await sendMessage(page, pane, BEFORE_TEXT);
  await page.locator(`${pane} .msg-user:has-text("${BEFORE_TEXT}")`).waitFor({ timeout: 15000 });
  check(await wsCount() === 1, "前置:一条连接,断线前的消息已上屏");

  // 服务端这一侧:历史里有前面那轮 + 一条**客户端没收到过**的缺口消息;
  // 之后再发的消息服务端"没记上"(__silent)
  await page.evaluate(({ before, gap }) => {
    window.__thread = { schemaVersion: 3, sessionKey: "websocket:chat-e2e", messages: [
      { id: "u-1", role: "user", content: before },
      { id: "a-1", role: "assistant", content: "收到" },
      { id: "a-2", role: "assistant", content: gap, __gap: true },
    ] };
    window.__silent = true;
  }, { before: BEFORE_TEXT, gap: GAP_TEXT });

  await sendMessage(page, pane, PENDING_TEXT);
  await page.locator(`${pane} .msg-user:has-text("${PENDING_TEXT}")`).waitFor({ timeout: 15000 });

  // ── 掐断 ────────────────────────────────────────────────────────────────
  await page.evaluate(() => window.__killWS(1006));

  check(await until(() => page.locator('[data-ui="chat-reconnecting"]').isVisible(), 5000),
    "① 掐断后出现「正在重连」提示");
  check(await until(async () =>
    !(await page.locator(pane).innerText()).includes("连接已断开"), 3000),
    "② 不再是「连接已断开」那个死胡同");
  check(await page.locator(`${pane} .msg-user:has-text("${BEFORE_TEXT}")`).isVisible(),
    "③ 重连期间断线前的气泡还在(锁死「其实是整页 reload」)");

  // ── 自己回来 ────────────────────────────────────────────────────────────
  check(await until(async () => (await wsCount()) >= 2, 20000),
    "④ 到点自己建了第二条连接(纯逻辑层真的被接上了)");
  check(await until(() => page.locator(`${pane} .chat-meta`).isVisible(), 20000),
    "⑤ 回到已连接态");
  // ⚠️ 这条原来写反了(2026-08-04 攻题抓到,是**判据的 bug 不是实现的**):
  // 原断言要求 attach 的 id "不以 chat-new- 开头",而**第一条连接拿到的正是
  // chat-new-1** —— 正确实现反而会红,硬编码一个假 id 的错实现反而绿。
  // 改成对着 stub 记下的首个 ready id 精确比。
  const ids = await page.evaluate(() =>
    ({ first: window.__firstReadyId, last: window.__lastReadyId,
       attaches: window.__attachIds }));
  check(await until(async () => {
    const a = await page.evaluate(() => window.__attachIds);
    return a.length >= 1 && a.every((x) => x === ids.first);
  }, 10000), "⑥ 重连后 attach 回**第一条连接那个** chat_id(逐字符比,不是形状比)");
  check(ids.first !== ids.last,
    "⑥b 前置:新连接确实拿到了不同的 chat_id(否则上一条等于没判)");

  // ── 补缺口 ──────────────────────────────────────────────────────────────
  check(await until(() => page.locator(`${pane}`).innerText()
    .then((t) => t.includes(GAP_TEXT)), 20000),
    "⑦ 断线期间那条(只存在于服务端历史里)重连后出现在屏幕上");
  check(await page.locator(`${pane} .msg-user:has-text("${PENDING_TEXT}")`).isVisible(),
    "⑧ 本地发出、服务端没记上的那句没有被对账吃掉");
  check(await page.locator(`${pane} .msg-user:has-text("${BEFORE_TEXT}")`).count() === 1,
    "⑨ 对账不许把消息弄重(每条只出现一次)");

  // ── 攻题补强 1:历史请求打的是**真实那条代理路径**,且发生在 attach 之后 ──────
  //   (原来 stub 用 includes("/thread") 模糊放行 ⇒ 照设计文字写错地址也能全绿)
  check(await until(async () => {
    const urls = await page.evaluate(() => window.__threadUrls);
    const first = await page.evaluate(() => window.__firstReadyId);
    return urls.some((u) => u.includes(`/api/chat/sessions/websocket:${first}/thread`));
  }, 10000), "⑬ 补历史打的是真实代理路径 /api/chat/sessions/websocket:<id>/thread");

  // ── 攻题补强 2:没收到 attached 之前**不算连上** ─────────────────────────────
  //   在 ready 就宣告成功 ⇒ 输入框已可用,消息发往还没挂好的会话
  await page.evaluate(() => { window.__holdAttached = true; window.__killWS(1006); });
  check(await until(async () => (await page.evaluate(() => window.__attachIds.length)) >= 2, 20000),
    "⑭ 前置:重连后又发了一次 attach");
  check(!(await page.locator(`${pane} .chat-meta`).isVisible()),
    "⑮ attach 还没回 attached ⇒ **不算连上**(不许在 ready 就宣告成功)");
  await page.evaluate(() => window.__releaseAttach());
  check(await until(() => page.locator(`${pane} .chat-meta`).isVisible(), 15000),
    "⑯ 收到 attached 之后才回到已连接态");

  // ── 攻题补强 3:退避真的在涨(接线层不许每轮都从 500ms 重来)─────────────────
  await page.evaluate(() => {
    window.__failConnect = true; window.__wsTimes = []; window.__killWS(1006);
  });
  check(await until(async () => (await page.evaluate(() => window.__wsTimes.length)) >= 4, 30000),
    "⑰ 前置:连续失败下攒到 4 次重连尝试");
  const gaps = await page.evaluate(() => {
    const t = window.__wsTimes;
    return t.slice(1).map((x, i) => x - t[i]);
  });
  check(gaps.length >= 3 && gaps[1] > gaps[0] * 1.3 && gaps[2] > gaps[1] * 1.3,
    `⑱ 间隔逐次变长(退避没被每轮重置):${JSON.stringify(gaps)}`);
  await page.evaluate(() => { window.__failConnect = false; });
  check(await until(() => page.locator(`${pane} .chat-meta`).isVisible(), 25000),
    "⑲ gateway 回来后自己接上");

  // ── 攻题补强 4:拉历史 401 **不是**口令失效,不许踹回登录框 ───────────────────
  //   connection.ts:116 在"重签后仍 401"时也抛 PasswordRejected —— 来源被抹掉了
  await page.evaluate(() => { window.__thread401 = true; window.__killWS(1006); });
  check(await until(() => page.locator(`${pane} .chat-meta`).isVisible(), 25000),
    "⑳ 历史接口 401 ⇒ 照常连上");
  check(!(await page.locator(`${pane} .chat-login input[type=password]`).isVisible()),
    "㉑ 历史接口 401 **不许**清口令、不许弹登录框(只有 bootstrap 自己 401 才算)");
  await page.evaluate(() => { window.__thread401 = false; });

  // ── 空会话拉历史 = 404,当"没历史"处理,不弹错 ───────────────────────────
  await page.evaluate(() => { window.__threadStatus = 404; window.__killWS(1006); });
  check(await until(async () => {
    if (!(await page.locator(`${pane} .chat-meta`).isVisible())) return false;
    const t = await page.locator(pane).innerText();
    return !t.includes("连接已断开") && !t.includes("404");
  }, 25000), "⑩ 拉历史 404(空会话的真实形状)⇒ 照常连上,不把 404 弹给用户");

  // ── 口令真失效 ⇒ 回登录框(本单最容易做反的地方)─────────────────────────
  await page.evaluate(() => { window.__bootstrap401 = true; window.__killWS(1006); });
  check(await until(() =>
    page.locator(`${pane} .chat-login input[type=password]`).isVisible(), 25000),
    "⑪ bootstrap 401(口令真失效)⇒ 回登录框,不是无声转圈");

  check(errs.length === 0, `⑫ 全程没有页面级 JS 报错${errs.length ? ":" + errs[0] : ""}`);
} catch (e) {
  console.error("FAIL(异常):", e);
  failures += 1;
} finally {
  if (browser) await browser.close();
  if (srv) srv.kill();
}

console.log(failures === 0 ? "\nALL PASS" : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
