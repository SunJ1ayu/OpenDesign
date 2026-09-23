// Electron 主进程里「能判的」那一层(track opendesign-electron-shell,T3;主 agent 亲写,判据先单独 commit)。
// 跑法:node --test tests/test_desktop_main.mjs
//
// 窗口、托盘、electron-updater 本身只有云 Windows 答得了(.github/workflows/electron-e2e.yml)。
// 这里钉的是主进程里**决定做什么**的逻辑 —— 它们一旦写错,Windows 上的症状全是安静的:
// 业主的报错变成空白框、外链在窗口里打开把工作台顶掉、下载失败时按钮永远不出现、
// 更新时 Python 还攥着文件。接缝见 design.md「Test strategy」表:
//   desktop/lib/{hostProtocol,versionCheck,navPolicy,updateState,lifecycle}.js
// **它们不许 require("electron")**:判据要在没装 node_modules 的 Linux 上跑。
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { EventEmitter } from "node:events";

const require = createRequire(import.meta.url);
const lib = (name) => require(`../desktop/lib/${name}.js`);

// ── 管家协议 ─────────────────────────────────────────────────────────
test("m1 管家发来的协议行认得出来", () => {
  const { parseHostLine } = lib("hostProtocol");
  assert.deepEqual(parseHostLine('{"event":"ready","web_port":8766,"version":"0.98.10"}'),
    { event: "ready", web_port: 8766, version: "0.98.10" });
  assert.deepEqual(parseHostLine('{"event":"fatal","message":"还没装好"}\r'),
    { event: "fatal", message: "还没装好" }, "Windows 管道带 \\r 也得认");
});

test("m2 坏行一律 null,不许抛(抛了主进程就崩)", () => {
  const { parseHostLine } = lib("hostProtocol");
  for (const bad of ["", "   ", "Traceback (most recent call last):", "{not json", "[1,2]",
    "null", "42", '"ready"', '{"no_event":1}', '{"event":3}']) {
    assert.equal(parseHostLine(bad), null, `「${bad}」该被当成非协议行`);
  }
});

test("m3 发给管家的命令:一行一个 JSON、以换行收尾、中文原样", () => {
  const { encodeCommand, parseHostLine } = lib("hostProtocol");
  const line = encodeCommand({ cmd: "report", event: "frontend.error", detail: "首帧\n之后" });
  assert.ok(line.endsWith("\n"));
  assert.equal(line.indexOf("\n"), line.length - 1, "detail 里的换行必须被转义,否则一条命令被切成两行");
  assert.deepEqual(JSON.parse(line), { cmd: "report", event: "frontend.error", detail: "首帧\n之后" });
  assert.equal(parseHostLine(encodeCommand({ cmd: "quit" })), null, "命令不是事件,别混用一个形状");
});

test("m4 管家退出时要不要弹框:收摊中、已经报过 fatal 的都不弹", () => {
  const { hostExitMessage } = lib("hostProtocol");
  assert.equal(hostExitMessage(0, { quitting: true, fatalShown: false }), null);
  assert.equal(hostExitMessage(1, { quitting: true, fatalShown: false }), null, "业主点退出时不许吓他");
  assert.equal(hostExitMessage(1, { quitting: false, fatalShown: true }), null,
    "fatal 已经弹过人话了,再弹一个「意外退出」= 同一个错两个框,且后一个说错了原因");
  const msg = hostExitMessage(3, { quitting: false, fatalShown: false });
  assert.ok(msg && /3/.test(msg), `没说退出码:${msg}`);
  assert.match(msg, /[\u4e00-\u9fff]/, "给业主的话要是中文");
});

// ── 版本自检(挑战 a4:旧更新器「版本号 + nonce」那道闸的替身) ─────────────
test("m5 版本一致不吭声", () => {
  const { versionMismatch } = lib("versionCheck");
  assert.equal(versionMismatch("0.98.10", "0.98.10"), null);
});

test("m6 版本对不上 ⇒ 人话,说清是哪两版、该怎么办", () => {
  const { versionMismatch } = lib("versionCheck");
  // 探路第二跑的真实标本:exe 0.98.11 而后台报 0.98.9(安装被打断的半新半旧同一个形状)
  const msg = versionMismatch("0.98.11", "0.98.9");
  assert.ok(msg);
  assert.match(msg, /0\.98\.11/);
  assert.match(msg, /0\.98\.9/);
  assert.match(msg, /重新运行安装包/);
});

test("m7 后台没报版本也算对不上(旧管家 / 被截断的 ready 不许蒙混过关)", () => {
  const { versionMismatch } = lib("versionCheck");
  for (const v of [undefined, null, ""]) assert.ok(versionMismatch("0.98.10", v), `后台版本 ${v} 被放过了`);
});

// ── 导航:窗口里只许停在本机工作台 ───────────────────────────────────
const ORIGIN = "http://127.0.0.1:8766";

test("m8 同源放行", () => {
  const { navDecision } = lib("navPolicy");
  assert.equal(navDecision("http://127.0.0.1:8766/?shell=1", ORIGIN), "allow");
  assert.equal(navDecision("http://127.0.0.1:8766/projects/a#b", ORIGIN), "allow");
});

test("m9 🔴 长得像同源的不算(探路版用 startsWith,这三个都会被放进窗口)", () => {
  const { navDecision } = lib("navPolicy");
  assert.equal(navDecision("http://127.0.0.1:87661/", ORIGIN), "external");
  assert.equal(navDecision("http://127.0.0.1:8766@evil.example/", ORIGIN), "external");
  assert.equal(navDecision("http://127.0.0.1:8766.evil.example/", ORIGIN), "external");
});

test("m10 外站交系统浏览器;非 http 一律拒", () => {
  const { navDecision, windowOpenDecision } = lib("navPolicy");
  assert.equal(navDecision("https://github.com/SunJ1ayu/OpenDesign/releases", ORIGIN), "external");
  for (const u of ["file:///C:/Windows/win.ini", "javascript:alert(1)", "data:text/html,x",
    "ms-settings:", "vbscript:x", "not a url"]) {
    assert.equal(navDecision(u, ORIGIN), "deny", `${u} 该拒`);
    assert.equal(windowOpenDecision(u), "deny", `${u} 该拒(新窗口)`);
  }
  assert.equal(windowOpenDecision("https://example.com/"), "external");
  assert.equal(windowOpenDecision(`${ORIGIN}/x`), "external", "我们从不开第二个窗口");
});

test("m11 工作台还没起来(没有 origin)时,只有 http(s) 能出去", () => {
  const { navDecision } = lib("navPolicy");
  assert.equal(navDecision("https://example.com/", null), "external");
  assert.equal(navDecision("http://127.0.0.1:8766/", null), "external");
  assert.equal(navDecision("file:///x", null), "deny");
});

test("m21 窗口打开的地址带外壳标记(旧判据 x10:前端首帧靠它决定画不画窗口栏),且与前端同一个字面量", async () => {
  const { SHELL_MARK } = lib("navPolicy");
  const { SHELL_MARK: FRONT } = await import("../web/src/shellWindow.ts");
  assert.equal(SHELL_MARK, FRONT, "两边的标记对不上 ⇒ 窗口栏整块不画,哪儿都不报错(0.89/0.90 两版)");
  const { APP_URL, APP_ORIGIN } = lib("appProtocol");
  assert.equal(APP_URL, `app://opendesign/?${FRONT}`, "track opendesign-instant-ui:窗口地址从 http://127.0.0.1:<端口> 换成 app://");
  assert.equal(lib("navPolicy").navDecision(APP_URL, APP_ORIGIN), "allow");
});

// ── 更新状态机(U3 = 照 ZCode:后台下好 → 他点「重启以更新」→ 向导) ──────────
test("m12 初始是 idle;查 → 有新版 → 下载中 → 下好,版本一路带着", () => {
  const { initialUpdateState, reduceUpdate } = lib("updateState");
  let s = initialUpdateState();
  assert.equal(s.phase, "idle");
  s = reduceUpdate(s, { type: "checking" });
  assert.equal(s.phase, "checking");
  s = reduceUpdate(s, { type: "available", version: "0.98.11" });
  assert.equal(s.phase, "downloading");
  assert.equal(s.version, "0.98.11");
  s = reduceUpdate(s, { type: "progress", percent: 42.4 });
  assert.equal(s.phase, "downloading");
  assert.equal(s.version, "0.98.11");
  assert.equal(Math.round(s.percent), 42);
  s = reduceUpdate(s, { type: "downloaded", version: "0.98.11" });
  assert.deepEqual([s.phase, s.version], ["downloaded", "0.98.11"]);
});

test("m13 🔴 只有 downloaded 才许装", () => {
  const { initialUpdateState, reduceUpdate, canInstall } = lib("updateState");
  let s = initialUpdateState();
  assert.equal(canInstall(s), false);
  for (const e of [{ type: "checking" }, { type: "available", version: "0.98.11" }, { type: "progress", percent: 99 }]) {
    s = reduceUpdate(s, e);
    assert.equal(canInstall(s), false, `${s.phase} 时就给装了 ⇒ 装的是半截文件`);
  }
  s = reduceUpdate(s, { type: "downloaded", version: "0.98.11" });
  assert.equal(canInstall(s), true);
});

test("m14 🔴 查不动 / 下载失败是 error,不是 latest(旧判据 u3 的保证搬过来)", () => {
  const { initialUpdateState, reduceUpdate } = lib("updateState");
  let s = reduceUpdate(initialUpdateState(), { type: "checking" });
  s = reduceUpdate(s, { type: "error", message: "net::ERR_CONNECTION_REFUSED" });
  assert.equal(s.phase, "error");
  assert.ok(s.error, "error 态要带原因(进日志、给「重试」旁边的说明)");
  s = reduceUpdate(reduceUpdate(initialUpdateState(), { type: "checking" }), { type: "not-available" });
  assert.equal(s.phase, "latest");
});

test("m15 下好之后再查出错,不许把「下好了」冲掉(按钮会消失,他就更新不了)", () => {
  const { initialUpdateState, reduceUpdate, canInstall } = lib("updateState");
  let s = reduceUpdate(initialUpdateState(), { type: "downloaded", version: "0.98.11" });
  s = reduceUpdate(s, { type: "checking" });
  s = reduceUpdate(s, { type: "error", message: "offline" });
  assert.equal(s.phase, "downloaded");
  assert.equal(canInstall(s), true);
});

test("m16 下次什么时候查:失败 15 分钟,平时 4 小时;第一次查不挡启动", () => {
  const { initialUpdateState, reduceUpdate, nextCheckDelayMs, FIRST_CHECK_DELAY_MS } = lib("updateState");
  const err = reduceUpdate(initialUpdateState(), { type: "error", message: "x" });
  assert.equal(nextCheckDelayMs(err), 15 * 60 * 1000, "挑战 a6:他常先开软件后开 VPN");
  const ok = reduceUpdate(initialUpdateState(), { type: "not-available" });
  assert.equal(nextCheckDelayMs(ok), 4 * 60 * 60 * 1000);
  assert.ok(FIRST_CHECK_DELAY_MS > 0 && FIRST_CHECK_DELAY_MS <= 60 * 1000,
    `首查延迟 ${FIRST_CHECK_DELAY_MS}ms:0 = 和启动抢(0.98.8 的教训),太久 = 他开一会儿就关了、永远查不到`);
});

test("m17 更新器的开关照 design D 设好", () => {
  const { configureUpdater } = lib("updateState");
  const u = { autoDownload: false, autoInstallOnAppQuit: true, disableWebInstaller: false, allowDowngrade: true };
  configureUpdater(u, { log: () => {} });
  assert.equal(u.autoDownload, true, "增量约 1MB,后台下");
  assert.equal(u.allowDowngrade, false, "旧判据 t3b:线上比本机旧时提示「更新」= 往回装");
  assert.equal(u.autoInstallOnAppQuit, false, "ZCode autoUpdater.ts:1502:退出后紧接着关机会装一半");
  assert.equal(u.disableWebInstaller, true);
});

// ── 收摊与交棒 ───────────────────────────────────────────────────────
class FakeChild extends EventEmitter {
  constructor({ exitsOnEof = true } = {}) {
    super();
    this.exitCode = null;
    this.killed = 0;
    this.stdinEnded = 0;
    this.stdin = { end: () => { this.stdinEnded++; if (exitsOnEof) setTimeout(() => this.#exit(0), 10); } };
  }
  kill() { this.killed++; setTimeout(() => this.#exit(1), 5); return true; }
  #exit(code) { if (this.exitCode === null) { this.exitCode = code; this.emit("exit", code); } }
}

test("m18 收摊:关管家 stdin、等它自己走完,不强杀", async () => {
  const { shutdownHost } = lib("lifecycle");
  const child = new FakeChild();
  await shutdownHost(child, { graceMs: 2000 });
  assert.equal(child.stdinEnded, 1);
  assert.equal(child.killed, 0, "它自己会走,强杀会跳过 Job 收整棵树那一步");
  assert.equal(child.exitCode, 0);
});

test("m19 管家赖着不走 ⇒ 过了宽限期强杀,不许永远卡住", async () => {
  const { shutdownHost } = lib("lifecycle");
  const child = new FakeChild({ exitsOnEof: false });
  const t0 = Date.now();
  await shutdownHost(child, { graceMs: 100 });
  assert.equal(child.killed, 1);
  assert.ok(Date.now() - t0 < 2000);
  const gone = new FakeChild();
  gone.exitCode = 0;
  await shutdownHost(gone, { graceMs: 100 });   // 已经退了:直接回来
  assert.equal(gone.stdinEnded, 0);
});

test("m22 收摊可以被叫两次(托盘「退出」与 before-quit 同时到):只关一次 stdin、两边都等得到结束", async () => {
  // 旧判据 ShellState f5/f8 的保证:退出幂等、后台只收一次。Node 是单线程事件循环,f8/f9 的线程竞态不存在,
  // 剩下的就是「并发两次调用」这一件。
  const { shutdownHost } = lib("lifecycle");
  const child = new FakeChild();
  await Promise.all([shutdownHost(child, { graceMs: 2000 }), shutdownHost(child, { graceMs: 2000 })]);
  assert.equal(child.stdinEnded, 1);
  assert.equal(child.killed, 0);
});

test("m20 🔴 装更新:先收管家、再 quitAndInstall() 零参数(U3 = 照 ZCode autoUpdater.ts:470)", async () => {
  const { installUpdate } = lib("lifecycle");
  const { initialUpdateState, reduceUpdate } = lib("updateState");
  const order = [];
  const child = new FakeChild();
  child.on("exit", () => order.push("host-exit"));
  const updater = { quitAndInstall: (...args) => order.push(`quitAndInstall/${args.length}`) };
  const ready = reduceUpdate(initialUpdateState(), { type: "downloaded", version: "0.98.11" });
  assert.equal(await installUpdate({ state: ready, host: child, updater, graceMs: 2000 }), true);
  assert.deepEqual(order, ["host-exit", "quitAndInstall/0"],
    "Python 还攥着安装目录里的文件就交给安装器 ⇒ 半新半旧(挑战 #1);带参数 = 不再是业主选的 C(静默/不拉起)");

  const early = reduceUpdate(initialUpdateState(), { type: "available", version: "0.98.11" });
  const child2 = new FakeChild();
  const calls = [];
  assert.equal(await installUpdate({ state: early, host: child2, updater: { quitAndInstall: () => calls.push(1) }, graceMs: 100 }), false);
  assert.equal(child2.stdinEnded, 0, "没下好就把后台收了 ⇒ 业主的软件无故没了");
  assert.deepEqual(calls, []);
});
