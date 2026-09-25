// track opendesign-composer-zcode e2e(真 chromium + 真 ds_web + **stub 掉 ws / bootstrap / 历史两个接口**)。
// 主 agent 亲写。
//
// 断的是业主眼里的五条(业主 09-25 同意的对照图)+ 停止键的几种时机:
//   ①「+」是一个菜单:图片 + 三个技能;点技能在输入框补好开头、不发出去;「✎ 记一下」按钮没了;
//   ② 打 / 弹同一份技能表,按字筛,Enter 用、不发送;中文标点模式打出的「、」也算;筛不到 Enter 照常发;
//   ③ 模型按钮写「MiMo · mimo-v2.5」(厂商短名 · 模型名),悬停看全名;
//   ④ 发送是文字「发送」(09-25 业主改回;原为 ↑ 图标);回复中变 ■;点了 ⇒ 替身收到 `/stop`、屏上没有 “/stop” 气泡、半截回答留着、中文「已停止」、
//      输入框解锁;还在想(没出字)时停同样;三个聊天栏只停点的那一栏;回放(从侧栏点回那段)仍是同一句中文;
//   ⑤ 首页问候语按时间(页面时钟固定在 15:00 ⇒ 下午好)。
//
// 替身的帧序照本单探针(evidence/20260925-probe-stop.txt,真 nanobot 网关 + 假厂商):
//   回复中收到 /stop ⇒ goal_status:running → goal_status:idle → 无 kind message “Stopped 1 task(s).”,**不发 turn_end**。
// 代价写明:替身只证明「界面照真网关的帧形状做对了」,不证明真网关在别的时机也这样 —— 那条由 QA 执行(真网关 + 假厂商慢流)兜。
//
// 跑法:node tests/e2e/composer_zcode.e2e.mjs(自起 ds_web 于 8857;不需要 nanobot)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, waitConnected, waitSendable, check } from "./helpers.mjs";
import { WS_STUB_BASE } from "./_ws-stub.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8857;
const HOME = ".home-pane";
const WSP = ".ws-pane";

const STUB = () => {
  window.__sent = [];          // [{chat, frame}]
  window.__streams = {};       // chat_id -> { n, done, timer }
  window.__slow = false;       // true ⇒ 慢流(每 150ms 一段,共 60 段)
  window.__think = false;      // true ⇒ 先「想」4 秒再出第一个字
  const json = (obj) => Promise.resolve(new Response(JSON.stringify(obj),
    { status: 200, headers: { "Content-Type": "application/json" } }));
  const origFetch = window.fetch;
  window.fetch = (url, init) => {
    const u = String(url);
    if (u.includes("/api/chat/bootstrap")) {
      return json({ token: "stub-token", ws_path: "/ws", expires_in: 600, model_name: "stub-model" });
    }
    // 会话列表:带不带查询串都认(网关不读 limit,侧栏单 opendesign-sidebar-history 起前端不再拼 ?limit=10)
    if (u.includes("/api/chat/sessions?") || u.endsWith("/api/chat/sessions")) {
      window.__sessionsFetches = (window.__sessionsFetches || 0) + 1;
      return json({ sessions: [{ key: "websocket:chat-old", title: "停过的那次", updated_at: new Date().toISOString() }] });
    }
    // 回放:探针 mode=stream 的 webui-thread 逐字(半截回答一条、那句英文一条;/stop 本身不留用户行)
    if (u.includes("/thread")) {
      return json({ messages: [
        { id: "u-0-8f23c297", role: "user", content: "停过的那次", turnId: "turn-1", turnPhase: "user", turnSeq: 1, createdAt: 1 },
        { id: "buf-1-45a1ec93", role: "assistant", content: "第0段。第1段。", isStreaming: false, turnId: "turn-1",
          turnPhase: "answer", turnSeq: 3, createdAt: 2 },
        { id: "as-3-3b8730fb", role: "assistant", createdAt: 3, content: "Stopped 1 task(s).", turnId: "turn-stop",
          turnPhase: "answer", turnSeq: 1 },
      ] });
    }
    return origFetch(url, init);
  };
  let seq = 0;
  class StubWS extends window.__BaseStubWS {
    constructor(url) {
      super(url);
      this.chat = `chat-${++seq}`;
      setTimeout(() => {
        this.readyState = StubWS.OPEN;
        this.onopen?.({});
        this._emit({ event: "ready", chat_id: this.chat });
      }, 10);
    }
    send(data) {
      let m = null;
      try { m = JSON.parse(data); } catch { return; }
      window.__sent.push({ chat: this.chat, frame: m });
      if (m.type === "attach") {
        this.chat = m.chat_id;
        setTimeout(() => this._emit({ event: "attached", chat_id: m.chat_id }), 10);
        return;
      }
      if (m.type !== "message") return;
      const cur = window.__streams[this.chat];
      if (m.content === "/stop") {
        const running = cur && !cur.done;
        if (running) { clearInterval(cur.timer); clearTimeout(cur.wait); cur.done = true; cur.stopped = true; }
        setTimeout(() => {
          if (running) {
            this._emit({ event: "goal_status", chat_id: this.chat, status: "running", started_at: 1 });
            this._emit({ event: "goal_status", chat_id: this.chat, status: "idle" });
            this._emit({ event: "message", chat_id: this.chat, text: "Stopped 1 task(s).",
                         turn_id: m.turn_id, turn_phase: "answer", turn_seq: 1 });
          } else {
            this._emit({ event: "message", chat_id: this.chat, text: "No active task to stop.",
                         turn_id: m.turn_id, turn_phase: "answer", turn_seq: 1 });
          }
        }, 30);
        return;
      }
      const t = m.turn_id;
      const sid = `websocket:${this.chat}:${t}:0`;
      const total = window.__slow || window.__think ? 60 : 2;
      const st = { n: 0, done: false, stopped: false, timer: null, wait: null, sid };
      window.__streams[this.chat] = st;
      this._emit({ event: "goal_status", chat_id: this.chat, status: "running", started_at: 1 });
      const start = () => {
        st.timer = setInterval(() => {
          if (st.done) return;
          this._emit({ event: "delta", chat_id: this.chat, text: `第${st.n}段。`, stream_id: sid,
                       turn_id: t, turn_phase: "answer", turn_seq: st.n + 2 });
          st.n += 1;
          if (st.n >= total) {
            clearInterval(st.timer);
            st.done = true;
            this._emit({ event: "stream_end", chat_id: this.chat, stream_id: sid, turn_id: t, turn_seq: total + 2 });
            this._emit({ event: "turn_end", chat_id: this.chat, turn_id: t, turn_phase: "complete",
                         turn_seq: total + 3, goal_state: { active: false } });
          }
        }, window.__slow || window.__think ? 150 : 10);
      };
      st.wait = setTimeout(start, window.__think ? 4000 : 20);
    }
  }
  window.WebSocket = StubWS;
};

const tmp = mkdtempSync(join(tmpdir(), "composer-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
mkdirSync(ws, { recursive: true });
writeFileSync(join(dsRoot, "config", "workspace.json"), JSON.stringify({ root: ws, projects: {} }));
// 家目录带一把(假)MiMo key + 出货模板:没 key 时一打开就被带去设置页(产品既有行为),同 chat_model_error / model_picker。
const home = join(tmp, "home");
const cfgPath = join(home, ".nanobot", "config.json");
mkdirSync(join(home, ".openDesign"), { recursive: true });
writeFileSync(join(home, ".openDesign", "key.txt"), "sk-e2e-composer-zcode\n");
mkdirSync(join(home, ".nanobot"), { recursive: true });
const template = readFileSync(join(ROOT, "config", "nanobot.config.windows.jsonc"), "utf8")
  .split("\n").filter((ln) => !/^\s*\/\//.test(ln)).join("\n");
writeFileSync(cfgPath, JSON.stringify(JSON.parse(template), null, 2));

let failures = 0;
let browser = null;
let srv = null;
const step = async (label, fn) => {
  try { await fn(); } catch (e) { failures += 1; console.log(`  not ok - ${label}: ${e.message}`); }
};
async function until(fn, timeoutMs = 8000, stepMs = 100) {
  const t0 = Date.now();
  for (;;) {
    try { if (await fn()) return true; } catch { /* 还没出现 */ }
    if (Date.now() - t0 > timeoutMs) return false;
    await new Promise((r) => setTimeout(r, stepMs));
  }
}
const sentMessages = (page) => page.evaluate(() => window.__sent.filter((s) => s.frame.type === "message"));

try {
  srv = spawn("python3", [join(ROOT, "bin", "ds_web.py")], {
    env: { ...process.env, DS_ROOT: dsRoot, DS_WEB_PORT: String(PORT), DS_NANOBOT_CONFIG: cfgPath,
           HOME: home, USERPROFILE: home },
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
  // 页面时钟固定在下午 3 点(只改 Date,不冻结定时器)
  await page.clock.setFixedTime(new Date(2026, 8, 25, 15, 0, 0));
  await page.addInitScript(WS_STUB_BASE);
  await page.addInitScript(STUB);
  await page.goto(`${base}/#/`, { waitUntil: "domcontentloaded" });
  await page.locator(HOME).waitFor({ state: "visible", timeout: 15000 });
  await waitConnected(page, HOME);
  const ta = page.locator(`${HOME} textarea`);

  await step("⑤ 首页问候语按时间:下午 3 点 ⇒「下午好,今天想聊点什么?」", async () => {
    const g = (await page.locator(`${HOME} .home-greet`).innerText()).trim();
    check(g === "下午好,今天想聊点什么?", `问候语:${JSON.stringify(g)}`);
  });

  await step("占位字:聊设计、找参考;输入 / 选技能", async () => {
    const ph = await ta.getAttribute("placeholder");
    check(ph === "聊设计、找参考;输入 / 选技能", `占位字:${JSON.stringify(ph)}`);
  });

  await step("①「+」是菜单:图片 + 三个技能;「✎ 记一下」按钮不在", async () => {
    const card = page.locator(`${HOME} .chat-card`);
    check(!(await card.innerText()).includes("✎"), "输入卡里没有「✎ 记一下」");
    await page.locator(`${HOME} [data-ui="composer-plus"]`).click();
    const menu = page.locator(`${HOME} [data-ui="composer-menu"]`);
    await menu.waitFor({ timeout: 3000 });
    const items = (await menu.locator('[role="menuitem"]').allInnerTexts()).map((t) => t.trim());
    check(items.length === 4 && /图片/.test(items[0]) && /记一下/.test(items[1])
          && /整理文件夹/.test(items[2]) && /找参考图/.test(items[3]), `菜单四项:${JSON.stringify(items)}`);
    check(/拖进来/.test(items[0]) && /Ctrl\+V/.test(items[0]), "图片那一项写着也可拖进来 / Ctrl+V");
    const chooser = page.waitForEvent("filechooser", { timeout: 3000 });
    await menu.locator('[role="menuitem"]').first().click();
    await chooser;
    check(true, "点「图片」弹出选图");
  });

  await step("① 点技能补开头:原来的字留着、不叠两个开头、不发出去", async () => {
    await ta.fill("客厅改浅色");
    await page.locator(`${HOME} [data-ui="composer-plus"]`).click();
    await page.locator(`${HOME} [data-ui="composer-menu"] [role="menuitem"]`, { hasText: "记一下" }).click();
    check((await ta.inputValue()) === "记一下:客厅改浅色", `补开头:${JSON.stringify(await ta.inputValue())}`);
    check((await page.locator(`${HOME} [data-ui="composer-menu"]`).count()) === 0, "点完菜单关上");
    await page.locator(`${HOME} [data-ui="composer-plus"]`).click();
    await page.locator(`${HOME} [data-ui="composer-menu"] [role="menuitem"]`, { hasText: "找参考图" }).click();
    check((await ta.inputValue()) === "找参考图:客厅改浅色", `换开头不叠:${JSON.stringify(await ta.inputValue())}`);
    check((await sentMessages(page)).length === 0, "一条都没发出去");
  });

  await step("② 打 / 弹同一份技能表;按字筛;Enter 用、不发送", async () => {
    await ta.fill("");
    await ta.type("/");
    const pop = page.locator(`${HOME} [data-ui="slash-menu"]`);
    await pop.waitFor({ timeout: 3000 });
    check((await pop.locator('[role="option"]').count()) === 3, "打 / ⇒ 三个技能");
    await ta.type("参考");
    check(await until(async () => (await pop.locator('[role="option"]').count()) === 1), "打成 /参考 ⇒ 只剩一个");
    check(/找参考图/.test(await pop.innerText()), "剩下的是找参考图");
    await ta.press("Enter");
    check((await ta.inputValue()) === "找参考图:", `Enter 用技能:${JSON.stringify(await ta.inputValue())}`);
    check((await pop.count()) === 0, "用完表收起");
    check((await sentMessages(page)).length === 0, "Enter 没把 /参考 发出去");
  });

  await step("② 中文标点模式下 / 键打出的「、」也弹;Esc 关了之后草稿留着", async () => {
    await ta.fill("");
    await ta.type("、");
    const pop = page.locator(`${HOME} [data-ui="slash-menu"]`);
    check(await until(async () => (await pop.count()) === 1), "「、」开头 ⇒ 弹技能表");
    await ta.press("Escape");
    check(await until(async () => (await pop.count()) === 0), "Esc ⇒ 收起");
    check((await ta.inputValue()) === "、", "草稿没被动");
  });

  await step("② 筛不到 ⇒ 不弹,Enter 照常发送", async () => {
    await ta.fill("");
    await ta.type("/xyz");
    await new Promise((r) => setTimeout(r, 300));
    check((await page.locator(`${HOME} [data-ui="slash-menu"]`).count()) === 0, "/xyz 不弹");
    await ta.press("Enter");
    check(await until(async () => (await sentMessages(page)).some((s) => s.frame.content === "/xyz")),
      "Enter 把 /xyz 当普通话发出去");
    await page.waitForFunction((sel) => !document.querySelector(`${sel} .stop-btn`), HOME, { timeout: 8000 });
  });

  await step("③ 模型按钮:「MiMo · mimo-v2.5」,悬停看全名", async () => {
    const chip = page.locator(`${HOME} [data-ui="chat-model"]`);
    check(await until(async () => /MiMo\s*·\s*mimo-v2\.5/.test(await chip.innerText())),
      `按钮上的字:${JSON.stringify(await chip.innerText())}`);
    check(!(await chip.innerText()).includes("小米"), "按钮上是短名(括号部分去掉)");
    const title = (await chip.getAttribute("title")) || "";
    check(title.includes("MiMo(小米)"), `悬停提示带全名:${JSON.stringify(title)}`);
  });

  await step("④ 发送是 ↑ 图标;回复中变 ■,点了 ⇒ 替身收到 /stop、半截留着、中文「已停止」、解锁", async () => {
    const send = page.locator(`${HOME} .send-btn`);
    check((await send.getAttribute("aria-label")) === "发送", "发送键 aria-label=发送");
    // 业主 09-25 18:3x:「发送键用 ↑ 图标还是改回文字吧」(回到 07-19 修改单「文字发送」;track opendesign-send-text)
    check((await send.innerText()).trim() === "发送", `发送键上是文字「发送」(实际:${JSON.stringify(await send.innerText())})`);
    await page.evaluate(() => { window.__slow = true; });
    await ta.fill("讲个长故事");
    await waitSendable(page, HOME, 8000);
    await send.click();
    const stop = page.locator(`${HOME} .stop-btn`);
    await stop.waitFor({ timeout: 5000 });
    check((await page.locator(`${HOME} .send-btn`).count()) === 0, "回复中 ↑ 换成了 ■");
    check((await stop.getAttribute("aria-label")) === "停止这次回复", "■ 的 aria-label");
    await page.waitForFunction((sel) => /第2段/.test(document.querySelector(`${sel} .msg-ai.streaming`)?.textContent || ""),
      HOME, { timeout: 5000 });
    const fetchesBefore = await page.evaluate(() => window.__sessionsFetches || 0);
    await stop.click();
    check(await until(async () => (await sentMessages(page)).some((s) => s.frame.content === "/stop")), "替身收到 /stop");
    // 评审 R1:网关停下后不发 turn_end,侧栏历史 / 项目数据也要照样刷新(新对话首句就停,侧栏里要出现它)
    check(await until(async () => (await page.evaluate(() => window.__sessionsFetches || 0)) > fetchesBefore, 3000),
      "停下之后侧栏历史重新拉了一次");
    check(await until(async () => (await page.locator(`${HOME} .send-btn`).count()) === 1
      && (await page.locator(`${HOME} .stop-btn`).count()) === 0, 3000), "3 秒内 ■ 回到 ↑");
    const note = page.locator(`${HOME} [data-ui="chat-system-note"]`);
    check(await until(async () => (await note.count()) === 1), "出现一行系统小字");
    const nt = (await note.first().innerText()).trim();
    check(/已停止/.test(nt) && !/[A-Za-z]/.test(nt), `中文「已停止」、没有英文:${JSON.stringify(nt)}`);
    check((await page.locator(`${HOME} .msg-ai.streaming`).count()) === 0, "半截回答定稿(不再挂着流式)");
    const half = await page.locator(`${HOME} .msg-ai:not(.thinking)`).allInnerTexts();
    check(half.some((t) => /第0段。第1段。/.test(t)), "半截回答还在");
    check(!(await page.locator(`${HOME} .msg-user`).allInnerTexts()).some((t) => t.includes("/stop")), "没有 “/stop” 气泡");
    check(!(await page.locator(`${HOME} textarea`).isDisabled()), "输入框可用");
  });

  await step("④ 停完马上再发一句:正常回复", async () => {
    await page.evaluate(() => { window.__slow = false; });
    await ta.fill("还在吗");
    await waitSendable(page, HOME, 5000);
    await page.locator(`${HOME} .send-btn`).click();
    check(await until(async () => (await page.locator(`${HOME} .msg-user`, { hasText: "还在吗" }).count()) === 1
      && (await page.locator(`${HOME} .stop-btn`).count()) === 0, 5000), "发出去了、回复完了");
  });

  await step("④ 还在想(没出字)就停 ⇒ 解锁,没有空白助手气泡", async () => {
    await page.evaluate(() => { window.__think = true; });
    const before = await page.locator(`${HOME} .msg-ai:not(.thinking)`).count();
    await ta.fill("想一想再说");
    await waitSendable(page, HOME, 5000);
    await page.locator(`${HOME} .send-btn`).click();
    await page.locator(`${HOME} .stop-btn`).waitFor({ timeout: 3000 });
    await page.locator(`${HOME} .stop-btn`).click();
    check(await until(async () => (await page.locator(`${HOME} .send-btn`).count()) === 1, 3000), "解锁");
    check((await page.locator(`${HOME} .msg-ai.thinking`).count()) === 0, "思考动画收掉");
    const aiNotNote = await page.locator(`${HOME} .msg-ai:not(.thinking)`).count();
    check(aiNotNote === before, `没有多出助手气泡(前 ${before} 后 ${aiNotNote})`);
    check((await page.locator(`${HOME} [data-ui="chat-system-note"]`).count()) === 2, "多一行「已停止」");
    await page.evaluate(() => { window.__think = false; });
  });

  await step("④ 三个聊天栏:只停点的那一栏,首页那条照常说完", async () => {
    await page.evaluate(() => { window.__slow = true; });
    await ta.fill("首页这边慢慢说");
    await waitSendable(page, HOME, 5000);
    await page.locator(`${HOME} .send-btn`).click();
    await page.locator(`${HOME} .stop-btn`).waitFor({ timeout: 3000 });
    const homeChat = await page.evaluate(() => [...window.__sent].reverse().find((s) => s.frame.content === "首页这边慢慢说").chat);
    await page.goto(`${base}/#/workspace`, { waitUntil: "domcontentloaded" });
    await page.locator(WSP).waitFor({ state: "visible", timeout: 10000 });
    await waitConnected(page, WSP);
    await page.locator(`${WSP} textarea`).fill("项目这边也说");
    await waitSendable(page, WSP, 5000);
    await page.locator(`${WSP} .send-btn`).click();
    await page.locator(`${WSP} .stop-btn`).waitFor({ timeout: 3000 });
    const wsChat = await page.evaluate(() => [...window.__sent].reverse().find((s) => s.frame.content === "项目这边也说").chat);
    check(homeChat !== wsChat, "两栏各自一个聊天");
    await page.locator(`${WSP} .stop-btn`).click();
    check(await until(async () => (await page.locator(`${WSP} .send-btn`).count()) === 1, 3000), "项目栏停了");
    const stops = (await sentMessages(page)).filter((s) => s.frame.content === "/stop");
    check(stops.length > 0 && stops.at(-1).chat === wsChat, "这次的 /stop 发在项目栏自己的聊天上");
    const homeBefore = await page.evaluate((c) => window.__streams[c].n, homeChat);
    await new Promise((r) => setTimeout(r, 600));
    const homeAfter = await page.evaluate((c) => window.__streams[c].n, homeChat);
    check(homeAfter > homeBefore, `首页那条还在出字(${homeBefore} → ${homeAfter})`);
    await page.goto(`${base}/#/`, { waitUntil: "domcontentloaded" });
    await page.locator(HOME).waitFor({ state: "visible", timeout: 10000 });
    check(await until(async () => (await page.locator(`${HOME} .send-btn`).count()) === 1, 15000), "首页那条自己说完了");
    const homeText = (await page.locator(`${HOME} .msg-ai:not(.thinking)`).allInnerTexts()).join("\n");
    check(/第59段。/.test(homeText), "首页那条是完整说完的");
    await page.evaluate(() => { window.__slow = false; });
  });

  await step("④ 回放:从侧栏点回停过的那段 ⇒ 半截回答是普通回答,那句英文是同一句中文小字", async () => {
    const liveNote = (await page.locator(`${HOME} [data-ui="chat-system-note"]`).first().innerText().catch(() => "")).trim();
    await page.locator(".hist-row", { hasText: "停过的那次" }).first().click();
    await page.waitForFunction(
      (sel) => [...document.querySelectorAll(`${sel} .msg-user`)].some((n) => n.textContent.includes("停过的那次")),
      HOME, { timeout: 10000 });
    const note = page.locator(`${HOME} [data-ui="chat-system-note"]`);
    check(await until(async () => (await note.count()) === 1), "回放里一行系统小字");
    const rt = (await note.first().innerText()).trim();
    check(!/[A-Za-z]/.test(rt) && /已停止/.test(rt), `回放小字中文:${JSON.stringify(rt)}`);
    if (liveNote) check(rt === liveNote, `回放与实时同一句:实时 ${JSON.stringify(liveNote)} 回放 ${JSON.stringify(rt)}`);
    const ai = await page.locator(`${HOME} .msg-ai:not(.thinking)`).allInnerTexts();
    check(ai.some((t) => t.includes("第0段。第1段。")), "半截回答在");
    check(!ai.some((t) => /Stopped/.test(t)), "没有英文原句当回答");
  });

  check(errs.length === 0, `页面无未捕获异常:${errs.join(" | ")}`);
} catch (e) {
  failures += 1;
  console.log(`  not ok - 场景中断: ${e.message}`);
} finally {
  await browser?.close();
  srv?.kill();
  rmSync(tmp, { recursive: true, force: true });
}
console.log(failures === 0 ? "composer_zcode.e2e: OK" : `composer_zcode.e2e: ${failures} FAIL`);
process.exit(failures === 0 ? 0 : 1);
