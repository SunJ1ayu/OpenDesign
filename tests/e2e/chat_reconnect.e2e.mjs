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
import { WS_STUB_BASE } from "./_ws-stub.mjs";

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
  window.__sendThrows = false;    // true = ws.send() 抛(socket 已死,界面还没反应过来)
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

  // readyState 常量由底座从**真** WebSocket 派生(见 _ws-stub.mjs 文件头:
  // 这两份替身各手抄过一遍,08-05 同一处漏了两遍、隔 39 分钟修了两次)。
  // 这里只写本场景的行为。
  class StubWS extends window.__BaseStubWS {
    constructor(url) {
      super(url);
      window.__wsCount += 1;
      window.__wsTimes.push(Date.now());
      window.__ws = this;
      setTimeout(() => {
        if (this.readyState === StubWS.CLOSED) return;
        if (window.__failConnect) {   // 一建就断:模拟 gateway 没起
          this.readyState = StubWS.CLOSED;
          this.onclose?.({ code: 1006, reason: "stub fail", wasClean: false });
          return;
        }
        this.readyState = StubWS.OPEN;
        this.onopen?.({});
        // 协议:每条新连接都发新 chat_id,前端弃用它、再 attach 回旧的
        const id = `chat-new-${window.__wsCount}`;
        if (window.__firstReadyId === null) window.__firstReadyId = id;
        window.__lastReadyId = id;
        this._emit({ event: "ready", chat_id: id });
      }, 10);
    }
    send(data) {
      // track opendesign-turn-id:模拟"socket 已经死了但界面还没反应过来" ——
      // 真浏览器在 CLOSING/CLOSED 上 send() 会抛 InvalidStateError。
      // 抛之前**不记进 __sent**:没发出去就是没发出去。
      //
      // ⚠️ **只让"发消息"这一种 send 抛**(判据本身的坑,08-05 实测):
      // 一视同仁地抛会把重连时的 `attach` 也弄挂 ⇒ 界面永远回不到已连接态,
      // 于是这一幕变成"输入框是灰的",判的不再是"发送失败怎么表现"。
      // 那次表现为**同一份代码一次红一次绿**(取决于这期间有没有正好在重连)——
      // 判据自己制造的抖动,比它要抓的 bug 还难查。
      if (window.__sendThrows) {
        let kind = null;
        try { kind = JSON.parse(data).type; } catch { /* 非 JSON 当普通发送 */ }
        if (kind !== "attach") {
          throw new DOMException("stub: socket is already in CLOSING or CLOSED state",
                                 "InvalidStateError");
        }
      }
      window.__sent.push(data);
      let m = null;
      try { m = JSON.parse(data); } catch { return; }
      if (m.type === "attach") {
        window.__attachIds.push(m.chat_id);
        // 真 gateway 对非法 id 回 error(协议 §2),stub 不许照单全收 ——
        // 否则"随便 attach 个什么都算成功"的实现也能全绿
        setTimeout(() => {
          if (m.chat_id !== window.__firstReadyId) {
            this._emit({ event: "error", detail: "invalid chat_id" });
            return;
          }
          if (window.__holdAttached) { window.__pendingAttach = m.chat_id; return; }
          // ⚠️ 顺序要紧:_emit 是同步的,客户端会在它里面同步发起拉历史 ——
          // 先 emit 再置位,拉历史那一刻读到的还是 false(夹具自己的时序 bug,
          // 08-04 第一次跑实现时被 ⑦ 抓出来)。
          window.__threadReady = true; // attached 之后历史里才有断线期间那条
          this._emit({ event: "attached", chat_id: m.chat_id });
        }, 10);
        return;
      }
      if (m.type !== "message" || window.__silent) return;
      setTimeout(() => {
        const sid = `stub-stream-${window.__sent.length}`;
        this._emit({ event: "delta", text: "收到", stream_id: sid,
                     turn_id: m.turn_id, turn_phase: "answer", turn_seq: 1 });
        this._emit({ event: "stream_end", stream_id: sid, turn_seq: 2 });
        this._emit({ event: "turn_end", turn_phase: "complete", turn_seq: 3,
                     goal_state: { active: false } });
      }, 10);
    }
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
  await page.addInitScript(WS_STUB_BASE);   // 先装底座(常量从真 WebSocket 派生)
  await page.addInitScript(STUB);
  await page.goto(`${base}/#/`, { waitUntil: "domcontentloaded" });
  await page.locator(pane).waitFor({ state: "visible", timeout: 10000 });
  await loginPane(page, pane, PW);

  const wsCount = () => page.evaluate(() => window.__wsCount);
  const sent = () => page.evaluate(() =>
    window.__sent.map((s) => { try { return JSON.parse(s); } catch { return null; } })
      .filter(Boolean));

  /** 从 stub 记下的**真信封**里取某句话的 turn_id(不是我们自己编一个)。 */
  const sentTurnId = (text) => page.evaluate((t) => {
    for (const raw of window.__sent) {
      try {
        const m = JSON.parse(raw);
        if (m.type === "message" && String(m.content).includes(t)) return m.turn_id;
      } catch { /* 非 JSON 跳过 */ }
    }
    return null;
  }, text);

  // ── 铺场景:先正常聊一句,留下"断线前"的痕迹 ─────────────────────────────
  await sendMessage(page, pane, BEFORE_TEXT);
  await page.locator(`${pane} .msg-user:has-text("${BEFORE_TEXT}")`).waitFor({ timeout: 15000 });
  check(await wsCount() === 1, "前置:一条连接,断线前的消息已上屏");

  // 服务端这一侧:历史里有前面那轮 + 一条**客户端没收到过**的缺口消息;
  // 之后再发的消息服务端"没记上"(__silent)
  // 服务端历史:user 行带**真实 turn_id**(实测 gateway 每条 user 行都写,7/7)。
  // 凭空造一条"没有 turnId 的服务端行"等于在问现实里不存在的题;
  // "两边都没有 turnId 时按文本去重"那条老行为由单测 ⑤b 咬住。
  const beforeTurnId0 = await sentTurnId(BEFORE_TEXT);
  check(typeof beforeTurnId0 === "string" && beforeTurnId0.length > 0,
    "前置:断线前那条的出站信封里有 turn_id");
  await page.evaluate(({ before, beforeId, gap }) => {
    window.__thread = { schemaVersion: 3, sessionKey: "websocket:chat-e2e", messages: [
      { id: "u-1", role: "user", content: before, turnId: beforeId, turnPhase: "user" },
      { id: "a-1", role: "assistant", content: "收到" },
      { id: "a-2", role: "assistant", content: gap, __gap: true },
    ] };
    window.__silent = true;
  }, { before: BEFORE_TEXT, beforeId: beforeTurnId0, gap: GAP_TEXT });

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

  // ── 四审补强 P1(DeepSeek 孤发现):重连之后**还能不能再发一条消息** ──────────
  //   这是本单的主场景,而原来 23 条判据从头到尾没有在重连后再发过消息 ——
  //   于是整轮判据都跑在"聊天已死锁"的状态上还全绿。**判据的绿只覆盖它问过的事。**
  await page.evaluate(() => { window.__silent = false; });
  const AFTER_TEXT = "重连之后再说一句";
  await page.locator(`${pane} textarea`).fill(AFTER_TEXT);
  // **先查状态再点**:P1 的症状就是发送键永久 disabled,直接点会抛超时把整轮判据
  // 打断(第一次红检就是这样),那样报出来的是"异常"不是"哪条断言错了"。
  check(await until(async () =>
    !(await page.locator(`${pane} .send-btn`).isDisabled()), 8000),
    "㉒ 重连之后发送键是可用的(不是能打字发不出去)");
  if (!(await page.locator(`${pane} .send-btn`).isDisabled())) {
    await page.locator(`${pane} .send-btn`).click();
    check(await until(() =>
      page.locator(`${pane} .msg-user:has-text("${AFTER_TEXT}")`).isVisible(), 10000),
      "㉓ 而且这条真的发出去并上屏了");
  } else {
    check(false, "㉓ 而且这条真的发出去并上屏了(发送键锁着,没得发)");
  }

  // ── track opendesign-turn-id ㉔:同一句话说两遍,断线后两条都得还在 ──────────
  //   旧实现在这里必红:对账靠 `role\0content` 猜身份 ⇒ 第二遍被当成第一遍吃掉,
  //   用户打过的字凭空消失。真身份 = 出站信封里的 turn_id(gateway 会原样写回历史,
  //   08-05 探针实抓)。夹具**从 window.__sent 里取真信封的 turn_id** 塞进 stub 历史,
  //   所以"本地 turnId 和信封 turn_id 是两个不同 uuid"的假实现也会被照出来。
  const DUP_TEXT = "同一句话说两遍";
  await sendMessage(page, pane, DUP_TEXT);
  await page.locator(`${pane} .msg-user:has-text("${DUP_TEXT}")`).first()
    .waitFor({ timeout: 15000 });
  const dupTurnId = await sentTurnId(DUP_TEXT);
  const beforeTurnId = await sentTurnId(BEFORE_TEXT);
  check(typeof dupTurnId === "string" && dupTurnId.length > 0,
    "㉔a 前置:出站信封里确实带了 turn_id(协议 §2 一等路径)");

  // 服务端这一侧:记上了第一遍(带真 turn_id),**没记上**第二遍。
  // 老消息那行也按真机的样子带上它自己的 turn_id —— 实测 gateway 每条 user 行都有
  // (抽样 7 个会话,带 7 / 不带 0)。夹具里凭空造一条"没有 turnId 的服务端行"
  // 等于在问一道现实里不存在的题,08-05 四审后改掉。
  // MARK2 = **只存在于这一轮回放里**的记号:它出现在屏幕上 = 本轮对账真的落地了。
  // (原来这里靠 `__threadUrls.length > 0` 当前置 —— 那个从前面几幕起就是真,
  //  于是数气泡时对账可能还没跑,旧实现照样能"绿"。判据自己的时序洞,08-05 补。)
  const MARK2 = "第二轮回放的记号";
  await page.evaluate(({ before, beforeId, gap, dup, turnId, mark }) => {
    window.__thread = { schemaVersion: 3, sessionKey: "websocket:chat-e2e", messages: [
      { id: "u-1", role: "user", content: before, turnId: beforeId, turnPhase: "user" },
      { id: "a-1", role: "assistant", content: "收到" },
      { id: "a-2", role: "assistant", content: gap },
      { id: "u-dup", role: "user", content: dup, turnId, turnPhase: "user" },
      { id: "a-3", role: "assistant", content: mark },
    ] };
    window.__silent = true;   // 第二遍服务端不回也不记
  }, { before: BEFORE_TEXT, beforeId: beforeTurnId, gap: GAP_TEXT,
       dup: DUP_TEXT, turnId: dupTurnId, mark: MARK2 });

  await sendMessage(page, pane, DUP_TEXT);
  check(await until(async () =>
    (await page.locator(`${pane} .msg-user:has-text("${DUP_TEXT}")`).count()) === 2, 10000),
    "㉔b 前置:断线前屏幕上确实有两条一模一样的话");

  await page.evaluate(() => window.__killWS(1006));
  check(await until(() => page.locator(`${pane} .chat-meta`).isVisible(), 25000),
    "㉔c 掐断后自己连回来");
  check(await until(() => page.locator(pane).innerText()
    .then((t) => t.includes(MARK2)), 20000),
    "㉔d 前置:**本轮**回放已经落到屏幕上(只有这一轮的历史里才有这个记号)");
  // 本条就是本 track 的主判据
  const dupCount = await page.locator(`${pane} .msg-user:has-text("${DUP_TEXT}")`).count();
  check(dupCount === 2,
    `㉔ 对账后两条一样的话都还在(服务端记上的 + 本地独有的),实得 ${dupCount} 条`);
  const beforeCount = await page.locator(`${pane} .msg-user:has-text("${BEFORE_TEXT}")`).count();
  check(beforeCount === 1,
    `㉕ 服务端记过的老消息不许被对账弄重,实得 ${beforeCount} 条`);
  await page.evaluate(() => { window.__silent = false; });

  // ── track opendesign-turn-id ㉖:发不出去就别说发出去了 ──────────────────────
  //   ⚠️ **规范事实(08-05 四审 DeepSeek 指正,写在这里免得后人再误解)**:
  //   真浏览器的 `send()` 只在 CONNECTING/CLOSING/CLOSED 抛 InvalidStateError,
  //   而这三种状态都被实现里那行 readyState 预检先拦下了(㉙ 才是生产上真正走的那条);
  //   OPEN 的 socket 即使对端已经死了也**只会静默排队,不抛**。
  //   所以本幕测的是**兜底分支**:留着它是因为运行时不止浏览器一种(polyfill/未来变更),
  //   代价一行 try/catch;但**别拿本幕的绿去证明"真机上断网点发送一定有提示"** ——
  //   拔网线那种断法根本不触发它(验收清单 B 组已按两种结果分开写)。
  const LOST_TEXT = "这句根本没送出去";
  // 先等回到已连接态**再**动输入框:输入框是灰的时候 fill 会抛超时,
  // 报出来的是"异常"而不是"哪条断言错了"(㉒ 那条踩过同一个坑)。
  check(await until(async () =>
    (await page.locator(`${pane} .chat-meta`).isVisible())
    && !(await page.locator(`${pane} textarea`).isDisabled()), 25000),
    "㉖a 前置:此刻是已连接、输入框可用(不然判的就不是「发送失败」这件事)");
  await page.evaluate(() => { window.__sendThrows = true; });
  await page.locator(`${pane} textarea`).fill(LOST_TEXT);
  await page.locator(`${pane} .send-btn`).click();
  await new Promise((r) => setTimeout(r, 500));   // 给它一点时间去做错事
  check((await page.locator(`${pane} .msg-user:has-text("${LOST_TEXT}")`).count()) === 0,
    "㉖ 发送失败 ⇒ **不上屏假气泡**(界面不许说它发出去了)");
  const errText = await page.locator('[data-ui="chat-turn-error"]').innerText()
    .catch(() => "");
  check(errText.trim().length > 0,
    `㉗ 而且屏上有一句提示,不是静默吞掉(实得:${JSON.stringify(errText)})`);
  check(await until(async () => !(await page.locator(`${pane} .send-btn`).isDisabled()), 5000),
    "㉘ 失败之后输入没被永久锁住(还能再试)");
  await page.evaluate(() => { window.__sendThrows = false; });

  // ── ㉙:socket 还没死透(CLOSING)时点发送 —— 另一条失败路径 ─────────────────
  //   ㉖ 走的是"send() 抛异常";实现里还有一条**更早**的闸:`readyState !== OPEN`
  //   就直接不发。两条腿(MiMo/Kimi)都点出这条分支判据没覆盖 ——
  //   只有 try/catch 没有预检的实现,㉖ 照样全绿。这一幕专门问它。
  const CLOSING_TEXT = "socket 正在关的时候发的";
  await page.locator(`${pane} textarea`).fill(CLOSING_TEXT);
  await page.evaluate(() => { window.__ws.readyState = 2; });   // CLOSING,且 send 不抛
  await page.locator(`${pane} .send-btn`).click();
  await new Promise((r) => setTimeout(r, 500));
  check((await page.locator(`${pane} .msg-user:has-text("${CLOSING_TEXT}")`).count()) === 0,
    "㉙ readyState 不是 OPEN 时点发送 ⇒ 不上屏假气泡(不靠异常兜)");
  check(await page.evaluate((t) => !window.__sent.some((s) => s.includes(t)), CLOSING_TEXT),
    "㉙b 而且**一个字节都没往外发**(不是发出去了只是没上屏)");
  await page.evaluate(() => { window.__ws.readyState = 1; });   // 复原,后面几幕还要用

  // ── ㉚:连回来之后,那句"没发出去"的提示要自己消失(四审 DeepSeek 发现 3)──────
  //   否则连接明明好了,屏上还挂着"等它重新连接后再点一次发送",
  //   用户会以为还没好 —— 界面在说一件不再为真的事。
  check((await page.locator('[data-ui="chat-turn-error"]').count()) > 0,
    "㉚a 前置:此刻屏上确实还挂着那句失败提示");
  await page.evaluate(() => window.__killWS(1006));
  check(await until(() => page.locator(`${pane} .chat-meta`).isVisible(), 25000),
    "㉚b 前置:又自己连回来了");
  check(await until(async () =>
    (await page.locator('[data-ui="chat-turn-error"]').count()) === 0, 8000),
    "㉚ 重连成功后那句失败提示自己消失了");

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

  // ── ㉜:断线时正忙 + 重连后拉历史 404 ⇒ 发送键**必须**能再用 ────────────────
  //   0.75.0 四审判 BLOCK 的那条 P1 当时只修了"成功那条路":对账里清 busy 的那行
  //   写在 `if (!replay || messages.length === 0) return;` **之后**,而
  //   ChatPage.tsx:300 的注释自己就写着「新建的空会话拉历史必然 404,实测」——
  //   于是最常见的那条路径(新会话发第一句就断线)整条绕过清 busy:
  //   重连回来输入框能打字、**发送键永久 disabled,只能刷新**。
  //   发现渠道:08-05 那条超时无结论的 Kimi 腿的日志(又一次印证"失败腿的日志也要读")。
  //   此刻 __threadStatus 仍是 404(上一幕留下的),正是要问的那个形状。
  // 显式声明这一幕要的形状,不靠上一幕的残留(fast lane 评审建议:跨幕依赖难维护)
  await page.evaluate(() => { window.__threadStatus = 404; window.__silent = true; });
  await sendMessage(page, pane, "断线时还在等回复的那句");
  check(await until(async () => await page.locator(`${pane} .send-btn`).isDisabled(), 8000),
    "㉜a 前置:发出去还没回 ⇒ 此刻确实是忙(发送键 disabled)");
  await page.evaluate(() => window.__killWS(1006));
  check(await until(() => page.locator(`${pane} .chat-meta`).isVisible(), 25000),
    "㉜b 前置:又连回来了(且这一轮拉历史是 404)");
  await page.locator(`${pane} textarea`).fill("重连之后我还想说话");
  check(await until(async () => !(await page.locator(`${pane} .send-btn`).isDisabled()), 8000),
    "㉜ 断线时正忙 + 重连后拉历史 404 ⇒ 发送键恢复可用(不是永久变灰只能刷新)");
  await page.evaluate(() => { window.__silent = false; });
  await page.locator(`${pane} textarea`).fill("");

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
