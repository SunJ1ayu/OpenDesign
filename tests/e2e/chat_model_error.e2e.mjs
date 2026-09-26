// track opendesign-chat-error-visible e2e(真 chromium + 真 ds_web + **stub 掉 ws / bootstrap / 历史两个接口**)。
// 主 agent 亲写。
//
// 病:模型出错(key 错 / 欠费 / 限流 / 厂商出错 / 连不上)时网关发一条**没有 kind** 的 message(整句原文),
// 界面把它丢了 ⇒ 业主发完一句「没反应」;切到那段历史对话回看,又冒出英文原文当正文。
//
// 替身重放的是**本单探针抓到的真帧**(evidence/20260925-probe-gateway-errors.txt,真 nanobot 网关 + 假厂商;
// 报错体是 MiMo 真厂商对假 key 的原文),历史回放也照探针抓到的 webui-thread 形状。
// 代价写明:替身只证明「界面照真网关的帧形状显示对了」,**不证明真网关在别的出错路径也发这个形状** ——
// 那一条由 QA 执行(真网关 + 假厂商 + 真界面)兜。
//
// 断的是业主眼里的三件事:
//   ① 发完一句,当场出现一条**看得出是出错**的中文说明(不是空白、不是英文),原文以纯文本小字附着;
//   ② 输入框随即可用,再发一句正常回复照常来、不带出错样式、不多气泡;
//   ③ 从侧栏「历史对话」点回那段对话(走 webui-thread 回放),看到的是**同一句中文**,没有英文原文当正文。
//
// 跑法:node tests/e2e/chat_model_error.e2e.mjs(自起 ds_web 于 8853;不需要 nanobot)
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { launchBrowser, waitConnected, waitSendable, check } from "./helpers.mjs";
import { WS_STUB_BASE } from "./_ws-stub.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const PORT = 8853;
const HOME = ".home-pane";
// 探针逐字:MiMo 真厂商对假 key 的 401 报错体,经 nanobot 网关后的样子
const RAW = "Error: {'message': 'Invalid API Key', 'param': 'Please provide valid API Key', 'code': '401', 'type': 'invalid_key'}";

const STUB = (RAW) => {
  window.__sent = [];
  window.__mode = "error";
  const json = (obj) => Promise.resolve(new Response(JSON.stringify(obj),
    { status: 200, headers: { "Content-Type": "application/json" } }));
  const origFetch = window.fetch;
  window.fetch = (url, init) => {
    const u = String(url);
    if (u.includes("/api/chat/bootstrap")) {
      return json({ token: "stub-token", ws_path: "/ws", expires_in: 600, model_name: "stub-model" });
    }
    // 历史对话列表:一段「错 key 那次」的旧对话
    // 会话列表:带不带查询串都认(网关不读 limit,侧栏单 opendesign-sidebar-history 起前端不再拼 ?limit=10)
    if (u.includes("/api/chat/sessions?") || u.endsWith("/api/chat/sessions")) {
      return json({ sessions: [{ key: "websocket:chat-old", title: "上次那句", updated_at: new Date().toISOString() }] });
    }
    // 回放:探针抓到的 webui-thread 形状,assistant 行就是英文原文
    if (u.includes("/thread")) {
      return json({ messages: [
        { id: "u-0-4b07db61", role: "user", content: "上次那句", turnId: "turn-old", turnPhase: "user", turnSeq: 1, createdAt: 1 },
        { id: "as-2-1670ef59", role: "assistant", content: RAW, latencyMs: 1475, turnId: "turn-old",
          turnPhase: "answer", turnSeq: 3, isStreaming: false, createdAt: 2 },
      ] });
    }
    return origFetch(url, init);
  };
  class StubWS extends window.__BaseStubWS {
    constructor(url) {
      super(url);
      setTimeout(() => {
        this.readyState = StubWS.OPEN;
        this.onopen?.({});
        this._emit({ event: "ready", chat_id: "chat-e2e" });
      }, 10);
    }
    send(data) {
      window.__sent.push(data);
      let m = null;
      try { m = JSON.parse(data); } catch { return; }
      if (m.type === "attach") {
        setTimeout(() => this._emit({ event: "attached", chat_id: m.chat_id }), 10);
        return;
      }
      if (m.type !== "message") return;
      const t = m.turn_id;
      if (window.__mode === "error") {
        // 探针 401 那一轮的真帧序:running → stream_end(之前没有任何 delta)→ 无 kind 的 message → turn_end
        setTimeout(() => {
          this._emit({ event: "goal_status", chat_id: "chat-e2e", status: "running", started_at: 1 });
          this._emit({ event: "stream_end", chat_id: "chat-e2e", stream_id: "websocket:chat-e2e:1:0",
                       turn_id: t, turn_phase: "answer", turn_seq: 2 });
        }, 10);
        setTimeout(() => {
          this._emit({ event: "message", chat_id: "chat-e2e", text: RAW, latency_ms: 1305,
                       turn_id: t, turn_phase: "answer", turn_seq: 3 });
          this._emit({ event: "turn_end", chat_id: "chat-e2e", latency_ms: 1305, goal_state: { active: false },
                       turn_id: t, turn_phase: "complete", turn_seq: 4 });
          this._emit({ event: "goal_status", chat_id: "chat-e2e", status: "idle" });
        }, 300);
        return;
      }
      setTimeout(() => {
        const sid = `ok-${window.__sent.length}`;
        this._emit({ event: "delta", text: "好的,", stream_id: sid, turn_id: t, turn_phase: "answer", turn_seq: 1 });
        this._emit({ event: "delta", text: "已经记下了。", stream_id: sid, turn_id: t, turn_phase: "answer", turn_seq: 2 });
        this._emit({ event: "stream_end", stream_id: sid, turn_id: t, turn_seq: 3 });
        this._emit({ event: "turn_end", turn_id: t, turn_phase: "complete", turn_seq: 4, goal_state: { active: false } });
      }, 10);
    }
  }
  window.WebSocket = StubWS;
};

const tmp = mkdtempSync(join(tmpdir(), "chaterr-e2e-"));
const dsRoot = join(tmp, "ds");
const ws = join(tmp, "ws");
mkdirSync(join(dsRoot, "projects"), { recursive: true });
mkdirSync(join(dsRoot, "config"), { recursive: true });
mkdirSync(ws, { recursive: true });
writeFileSync(join(dsRoot, "config", "workspace.json"), JSON.stringify({ root: ws, projects: {} }));
// 家目录带一把(假)key + 出货模板配置:没 key 时一打开就被带去「设置 · 模型设置」(产品既有行为),
// 首页被 route-hidden,输入框点不着(第一次红检就栽在这,红的是台面不是实现)。同 model_picker.e2e。
const home = join(tmp, "home");
const cfgPath = join(home, ".nanobot", "config.json");
mkdirSync(join(home, ".openDesign"), { recursive: true });
writeFileSync(join(home, ".openDesign", "key.txt"), "sk-e2e-chat-model-error\n");
mkdirSync(join(home, ".nanobot"), { recursive: true });
const template = readFileSync(join(ROOT, "config", "nanobot.config.windows.jsonc"), "utf8")
  .split("\n").filter((ln) => !/^\s*\/\//.test(ln)).join("\n");
writeFileSync(cfgPath, JSON.stringify(JSON.parse(template), null, 2));

let failures = 0;
let browser = null;
let srv = null;
/** 打字 → 等发送键真的可点(连上 + 不在忙 + 有字;helpers.waitSendable 要在**打完字之后**等)→ 点。 */
async function typeAndSend(page, text, timeout = 20000) {
  await page.locator(`${HOME} textarea`).fill(text);
  await waitSendable(page, HOME, timeout);
  await page.locator(`${HOME} .send-btn`).click();
}
const step = async (label, fn) => {
  try { await fn(); } catch (e) { failures += 1; console.log(`  not ok - ${label}: ${e.message}`); }
};

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
  await page.addInitScript(WS_STUB_BASE);
  await page.addInitScript(STUB, RAW);
  await page.goto(`${base}/#/`, { waitUntil: "domcontentloaded" });
  await page.locator(HOME).waitFor({ state: "visible", timeout: 15000 });
  await waitConnected(page, HOME);

  const errBubble = page.locator(`${HOME} [data-ui="chat-model-error"]`);

  await step("① 发完一句 ⇒ 当场一条出错说明(中文、指去模型设置重填 key 并点测试)", async () => {
    await typeAndSend(page, "你好");
    await errBubble.first().waitFor({ timeout: 10000 });
    check((await errBubble.count()) === 1, "恰好一条出错说明");
    const text = (await errBubble.first().innerText()).trim();
    check(/API Key/.test(text) && /重新填/.test(text) && /模型设置/.test(text) && /测试/.test(text),
      `说明里带着去哪儿、做什么:${JSON.stringify(text)}`);
    check(!/充值|余额|稍等/.test(text.split("原文")[0]), `key 错时没把人指去充值 / 干等:${JSON.stringify(text)}`);
    check((await page.locator(`${HOME} .msg-ai.thinking`).count()) === 0, "说明出来后思考动画已收掉");
  });

  await step("① 原文以纯文本小字附着(下划线不被当成 markdown 强调吞掉)", async () => {
    const raw = page.locator(`${HOME} [data-ui="chat-model-error-raw"]`);
    check((await raw.count()) === 1, "有且只有一行原文小字");
    const t = await raw.first().innerText();
    check(t.includes("'type': 'invalid_key'") && t.includes("Invalid API Key"), `原文逐字在:${JSON.stringify(t)}`);
    check((await errBubble.first().locator("em, strong").count()) === 0, "出错气泡里不该有 markdown 渲染出的强调");
  });

  await step("① 正文区不许出现英文原文当回复(那是修之前「切回来」的样子)", async () => {
    const plain = await page.locator(`${HOME} .msg-ai:not([data-ui="chat-model-error"])`).allInnerTexts();
    check(!plain.some((t) => /Error:/.test(t)), `没有英文原文被当成普通回复:${JSON.stringify(plain)}`);
  });

  await step("② 出错后输入框可用;再发一句正常回复照常来、不带出错样式、不多气泡", async () => {
    await page.evaluate(() => { window.__mode = "ok"; });
    await typeAndSend(page, "现在呢", 5000);   // 5 秒内发送键可点 = 出错那轮已解锁
    await page.waitForFunction(
      (sel) => [...document.querySelectorAll(`${sel} .msg-ai:not(.streaming):not(.thinking)`)]
        .some((n) => n.textContent.includes("已经记下了")),
      HOME, { timeout: 10000 });
    const ai = await page.locator(`${HOME} .msg-ai:not(.thinking)`).count();
    check(ai === 2, `助手气泡 = 出错说明 1 + 正常回复 1,实得 ${ai}`);
    check((await errBubble.count()) === 1, "正常回复没被标成出错");
  });

  await step("③ 从侧栏点回那段历史(走回放)⇒ 同一句中文,没有英文原文当正文", async () => {
    const liveText = (await errBubble.first().innerText()).trim();
    await page.locator(".hist-row", { hasText: "上次那句" }).first().click();
    await page.waitForFunction(
      (sel) => [...document.querySelectorAll(`${sel} .msg-user`)].some((n) => n.textContent.includes("上次那句")),
      HOME, { timeout: 10000 });
    await errBubble.first().waitFor({ timeout: 10000 });
    const replayText = (await errBubble.first().innerText()).trim();
    check(replayText === liveText, `回放与实时是同一句:\n实时 ${JSON.stringify(liveText)}\n回放 ${JSON.stringify(replayText)}`);
    const plain = await page.locator(`${HOME} .msg-ai:not([data-ui="chat-model-error"])`).allInnerTexts();
    check(!plain.some((t) => /Error:/.test(t)), `回放里没有英文原文当正文:${JSON.stringify(plain)}`);
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
console.log(failures === 0 ? "chat_model_error.e2e: OK" : `chat_model_error.e2e: ${failures} FAIL`);
process.exit(failures === 0 ? 0 : 1);
