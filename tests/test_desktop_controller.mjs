// Electron 主进程的「接线」判据(track opendesign-electron-shell,T3 攻题后补;主 agent 亲写)。
// 跑法:node --test tests/test_desktop_controller.mjs
//
// 由来:攻题(`…-t4-attack.out` #1 #2 #7 #8 #10 #11)—— test_desktop_main.mjs 只测纯函数,
// 而纯函数写对了、main.js **根本不调**,考卷照样全绿:版本对不上照常加载页面、15 分钟重查没接上、
// 管道分块把一行 JSON 切成两半、装更新失败留下一个空壳窗口、外链「全部拒绝」而不是交给浏览器。
// ⇒ 主进程里「收到什么 → 做什么」收进一个可注入的控制器 `desktop/lib/controller.js`,
//   main.js 只剩把 Electron 的东西(窗口、对话框、spawn、electron-updater、shell)接进来(c10 静态钉 main.js 真用它)。
//
// 接缝(design.md「Test strategy」表):
//   createController(deps) → { hostStdout(chunk), hostExit(code), setQuitting(), navigate(url),
//                              startUpdates(), checkNow(), updateState(), installUpdate(host) }
//   deps = { appVersion, loadWorkbench(url), showWindow(), showError(msg), revealFile(path), openExternal(url),
//            log(msg), updater, pushUpdateState(state), setTimeout, clearTimeout, relaunch(), graceMs? }
//   desktop/lib/hostProtocol.js 另给 createHostDecoder(onEvent) → { push(chunk), end() }
//   desktop/lib/menus.js 给 trayMenuTemplate({onOpen,onExport,onQuit}) / contextMenuTemplate(params)
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { EventEmitter } from "node:events";

const require = createRequire(import.meta.url);
const lib = (name) => require(`../desktop/lib/${name}.js`);
const tick = () => new Promise((r) => setImmediate(r));

// ── 假件 ─────────────────────────────────────────────────────────────
function fakeClock() {
  let seq = 0;
  const pending = new Map();
  return {
    setTimeout: (fn, ms) => { const id = ++seq; pending.set(id, { fn, ms }); return id; },
    clearTimeout: (id) => { pending.delete(id); },
    pending: () => [...pending.values()],
    fire: async () => {       // 触发最早排上的那一只
      const [id, t] = [...pending.entries()][0] ?? [];
      if (!id) throw new Error("没有排着的定时器");
      pending.delete(id);
      await t.fn();
      await tick();
    },
  };
}

class FakeUpdater extends EventEmitter {
  constructor() { super(); this.checks = 0; this.installs = []; this.rejectNext = null; this.throwOnInstall = null; }
  checkForUpdates() {
    this.checks++;
    if (this.rejectNext) { const e = this.rejectNext; this.rejectNext = null; return Promise.reject(e); }
    return Promise.resolve(null);
  }
  quitAndInstall(...args) { if (this.throwOnInstall) throw this.throwOnInstall; this.installs.push(args); }
}

class FakeChild extends EventEmitter {
  constructor() { super(); this.exitCode = null; this.stdinEnded = 0; this.killed = 0;
    this.stdin = { end: () => { this.stdinEnded++; setTimeout(() => this.#exit(0), 5); } }; }
  kill() { this.killed++; setTimeout(() => this.#exit(1), 5); return true; }
  #exit(c) { if (this.exitCode === null) { this.exitCode = c; this.emit("exit", c); } }
}

function harness(over = {}) {
  const rec = { loaded: [], shown: 0, errors: [], revealed: [], external: [], logs: [], states: [], relaunched: 0 };
  const clock = fakeClock();
  const updater = new FakeUpdater();
  const { createController } = lib("controller");
  const c = createController({
    appVersion: "0.98.10",
    loadWorkbench: (u) => rec.loaded.push(u),
    showWindow: () => { rec.shown++; },
    showError: (m) => rec.errors.push(String(m)),
    revealFile: (p) => rec.revealed.push(p),
    openExternal: (u) => rec.external.push(u),
    log: (m) => rec.logs.push(String(m)),
    updater,
    pushUpdateState: (s) => rec.states.push(s),
    setTimeout: clock.setTimeout,
    clearTimeout: clock.clearTimeout,
    relaunch: () => { rec.relaunched++; },
    graceMs: 500,
    ...over,
  });
  return { c, rec, clock, updater };
}
const line = (o) => JSON.stringify(o) + "\n";

// ── 管道:一行一个 JSON,但管道不按行给你 ──────────────────────────────
test("mc1 一行 JSON 被切成三块、两行挤在一块、中文 UTF-8 从字节中间切开,都照样认", () => {
  const { createHostDecoder } = lib("hostProtocol");
  const got = [];
  const d = createHostDecoder((e) => got.push(e));
  const a = Buffer.from(line({ event: "fatal", message: "还没装好:找不到配置文件" }), "utf8");
  const cut = a.indexOf(Buffer.from("装", "utf8")) + 1;          // 切在「装」这个字的三个字节中间
  d.push(a.subarray(0, 5));
  d.push(a.subarray(5, cut));
  d.push(a.subarray(cut));
  d.push(Buffer.from(line({ event: "show" }) + line({ event: "ready", web_port: 8766, version: "0.98.10" }), "utf8"));
  assert.deepEqual(got.map((e) => e.event), ["fatal", "show", "ready"]);
  assert.equal(got[0].message, "还没装好:找不到配置文件", "中文被切开后拼错了 ⇒ 业主看到乱码");
});

test("mc2 坏行夹在好行中间只丢那一行;最后一行没换行、管道关了也要认", () => {
  const { createHostDecoder } = lib("hostProtocol");
  const got = [];
  const d = createHostDecoder((e) => got.push(e));
  d.push(line({ event: "show" }) + "Traceback (most recent call last):\n" + line({ event: "show" }));
  d.push('{"event":"backend-died","names":["网关"],"message":"网关 意外退出了"}');   // 没换行
  d.end();
  assert.deepEqual(got.map((e) => e.event), ["show", "show", "backend-died"]);
});

// ── 管家事件 → 界面 ─────────────────────────────────────────────────
test("mc3 ready 且版本一致 ⇒ 加载带外壳标记的工作台", () => {
  const { c, rec } = harness();
  c.hostStdout(line({ event: "ready", web_port: 8767, version: "0.98.10" }));
  assert.deepEqual(rec.loaded, ["http://127.0.0.1:8767/?shell=1"]);
  assert.deepEqual(rec.errors, []);
});

test("mc4 🔴 版本对不上 ⇒ 弹一次人话、记日志、**不加载工作台**(挑战 a4:半新半旧不许蒙混)", () => {
  const { c, rec } = harness();
  c.hostStdout(line({ event: "ready", web_port: 8767, version: "0.98.9" }));
  assert.deepEqual(rec.loaded, [], "半新半旧照常加载 ⇒ 这道闸形同虚设");
  assert.equal(rec.errors.length, 1);
  assert.match(rec.errors[0], /重新运行安装包/);
  assert.ok(rec.logs.some((l) => /0\.98\.9/.test(l) && /0\.98\.10/.test(l)), "日志里没留两个版本号");
});

test("mc5 fatal 弹它带来的那句话;之后管家退出不再弹「意外退出」", () => {
  const { c, rec } = harness();
  c.hostStdout(line({ event: "fatal", message: "还没装好:找不到配置文件" }));
  c.hostExit(1);
  assert.deepEqual(rec.errors, ["还没装好:找不到配置文件"], "同一个错两个框,且后一个说错了原因");
});

test("mc6 管家无故退出 ⇒ 说人话带退出码;收摊中退出不吭声", () => {
  const a = harness();
  a.c.hostExit(3);
  assert.equal(a.rec.errors.length, 1);
  assert.match(a.rec.errors[0], /3/);
  const b = harness();
  b.c.setQuitting();
  b.c.hostExit(0);
  assert.deepEqual(b.rec.errors, []);
});

test("mc7 alert / backend-died 弹它们的话;show 叫出窗口;诊断包交给系统去定位", () => {
  const { c, rec } = harness();
  c.hostStdout(line({ event: "alert", message: "key 已经存好了,但后台没能自己重启" }));
  c.hostStdout(line({ event: "backend-died", names: ["网关"], message: "网关 意外退出了" }));
  c.hostStdout(line({ event: "show" }));
  c.hostStdout(line({ event: "diagnostics", path: "C:\\Users\\x\\AppData\\Local\\OpenDesign\\OpenDesign-诊断-ab12cd.zip" }));
  c.hostStdout(line({ event: "diagnostics", error: "磁盘满了" }));
  assert.deepEqual(rec.errors, ["key 已经存好了,但后台没能自己重启", "网关 意外退出了", "磁盘满了"]);
  assert.equal(rec.shown, 1);
  assert.deepEqual(rec.revealed, ["C:\\Users\\x\\AppData\\Local\\OpenDesign\\OpenDesign-诊断-ab12cd.zip"]);
});

test("mc8 already-running ⇒ 中文人话", () => {
  const { c, rec } = harness();
  c.hostStdout(line({ event: "already-running" }));
  assert.equal(rec.errors.length, 1);
  assert.match(rec.errors[0], /[\u4e00-\u9fff]/);
});

// ── 导航:真把外站交给系统浏览器,而不是一律拒掉 ───────────────────────
test("mc9 外站 ⇒ openExternal 恰好一次并拦住窗口;同源放行;非 http 拦住且不外开", () => {
  const { c, rec } = harness();
  c.hostStdout(line({ event: "ready", web_port: 8766, version: "0.98.10" }));
  assert.equal(c.navigate("http://127.0.0.1:8766/projects/x"), false, "同源被拦 ⇒ 工作台自己的跳转全坏");
  assert.equal(c.navigate("https://github.com/SunJ1ayu/OpenDesign/releases"), true);
  assert.deepEqual(rec.external, ["https://github.com/SunJ1ayu/OpenDesign/releases"]);
  assert.equal(c.navigate("file:///C:/Windows/win.ini"), true);
  assert.equal(c.navigate("http://127.0.0.1:8766@evil.example/"), true);
  assert.deepEqual(rec.external, ["https://github.com/SunJ1ayu/OpenDesign/releases", "http://127.0.0.1:8766@evil.example/"]);
});

// ── 更新调度:首查不挡启动、失败 15 分钟、平时 4 小时、永远只排一只 ─────────
test("mc10 首查排在 FIRST_CHECK_DELAY_MS 之后,不是立刻", async () => {
  const { FIRST_CHECK_DELAY_MS } = lib("updateState");
  const { c, clock, updater } = harness();
  c.startUpdates();
  assert.equal(updater.checks, 0, "启动当下就查 = 和开窗口抢(0.98.8 的教训)");
  assert.deepEqual(clock.pending().map((t) => t.ms), [FIRST_CHECK_DELAY_MS]);
  await clock.fire();
  assert.equal(updater.checks, 1);
});

test("mc11 🔴 查失败 ⇒ 状态 error、15 分钟后自己再查(挑战 a6:先开软件后开 VPN)", async () => {
  const { c, rec, clock, updater } = harness();
  c.startUpdates();
  await clock.fire();
  updater.emit("checking-for-update");
  updater.emit("error", new Error("net::ERR_INTERNET_DISCONNECTED"));
  await tick();
  assert.equal(c.updateState().phase, "error");
  assert.equal(rec.states.at(-1).phase, "error", "error 态没推给前端 ⇒ 界面停在「检查中」");
  assert.deepEqual(clock.pending().map((t) => t.ms), [15 * 60 * 1000], "失败后没排下一次 / 排了不止一只");
  await clock.fire();
  assert.equal(updater.checks, 2);
});

test("mc12 checkForUpdates 既 reject 又发 error ⇒ 仍然只排一只定时器", async () => {
  const { c, clock, updater } = harness();
  c.startUpdates();
  updater.rejectNext = new Error("offline");
  await clock.fire();
  updater.emit("error", new Error("offline"));
  await tick();
  assert.equal(clock.pending().length, 1, `排了 ${clock.pending().length} 只 ⇒ 一天下来叠出几百次查询`);
});

test("mc13 没有新版 ⇒ 4 小时后再查;手动「重试」立刻查且不叠定时器", async () => {
  const { c, clock, updater } = harness();
  c.startUpdates();
  await clock.fire();
  updater.emit("update-not-available", { version: "0.98.10" });
  await tick();
  assert.deepEqual(clock.pending().map((t) => t.ms), [4 * 60 * 60 * 1000]);
  c.checkNow();
  await tick();
  assert.equal(updater.checks, 2, "点了重试没去查");
  assert.ok(clock.pending().length <= 1);
});

test("mc14 下载途中出错 ⇒ error(有版本)、不许装;每一步都推给前端", async () => {
  const { c, rec, clock, updater } = harness();
  c.startUpdates();
  await clock.fire();
  updater.emit("update-available", { version: "0.98.11" });
  updater.emit("download-progress", { percent: 37 });
  updater.emit("error", new Error("ECONNRESET"));
  await tick();
  const s = c.updateState();
  assert.equal(s.phase, "error");
  assert.equal(s.version, "0.98.11", "下载失败要记得是哪一版(界面据此说「下载失败」并亮圆点,du8)");
  assert.deepEqual(rec.states.map((x) => x.phase).slice(-3), ["downloading", "downloading", "error"],
    "每一步都要推给前端(之前推不推「检查中」随实现)");
  const child = new FakeChild();
  assert.equal(await c.installUpdate(child), false);
  assert.equal(child.stdinEnded, 0, "没下好就把后台收了");
});

test("mc15 下好了 ⇒ 装:先收管家、再 quitAndInstall() 零参数", async () => {
  const { c, clock, updater } = harness();
  c.startUpdates();
  await clock.fire();
  updater.emit("update-downloaded", { version: "0.98.11" });
  await tick();
  const child = new FakeChild();
  assert.equal(await c.installUpdate(child), true);
  assert.equal(child.stdinEnded, 1);
  assert.deepEqual(updater.installs, [[]]);
});

test("mc16 🔴 交给安装器那一下失败了 ⇒ 说人话并把软件重新拉起来,不留空壳(攻题 #8)", async () => {
  const { c, rec, clock, updater } = harness();
  c.startUpdates();
  await clock.fire();
  updater.emit("update-downloaded", { version: "0.98.11" });
  await tick();
  updater.throwOnInstall = new Error("spawn EACCES");
  const child = new FakeChild();
  assert.equal(await c.installUpdate(child), false);
  assert.equal(rec.errors.length, 1);
  assert.match(rec.errors[0], /[\u4e00-\u9fff]/);
  assert.equal(rec.relaunched, 1, "管家已经收了、安装器没起来 ⇒ 不重新拉起就是一个连不上后台的空窗口");
  assert.ok(rec.logs.some((l) => /EACCES/.test(l)), "失败原因没进日志");
});

// ── 托盘与右键菜单 ─────────────────────────────────────────────────
test("mc17 托盘三项:打开 / 导出本次启动诊断 / 退出,点哪项叫哪个", () => {
  const { trayMenuTemplate } = lib("menus");
  const called = [];
  const items = trayMenuTemplate({ onOpen: () => called.push("open"), onExport: () => called.push("export"), onQuit: () => called.push("quit") })
    .filter((i) => i.label);
  assert.deepEqual(items.map((i) => i.label), ["打开 OpenDesign", "导出本次启动诊断", "退出"]);
  items.forEach((i) => i.click());
  assert.deepEqual(called, ["open", "export", "quit"]);
});

test("mc18 右键:输入框里有剪切/复制/粘贴/全选;只选中了字就只有复制;什么都没有就不弹(旧版 WebView2 自带,不做就是回归)", () => {
  const { contextMenuTemplate } = lib("menus");
  const roles = (p) => contextMenuTemplate(p).filter((i) => i.role).map((i) => i.role);
  assert.deepEqual(roles({ isEditable: true, selectionText: "", editFlags: { canCut: true, canCopy: true, canPaste: true, canSelectAll: true } }),
    ["cut", "copy", "paste", "selectAll"]);
  assert.deepEqual(roles({ isEditable: false, selectionText: "翡翠湾", editFlags: { canCopy: true } }), ["copy"]);
  assert.deepEqual(contextMenuTemplate({ isEditable: false, selectionText: "", editFlags: {} }), []);
  const labels = contextMenuTemplate({ isEditable: true, selectionText: "", editFlags: { canCut: true, canCopy: true, canPaste: true, canSelectAll: true } })
    .filter((i) => i.role).map((i) => i.label);
  assert.deepEqual(labels, ["剪切", "复制", "粘贴", "全选"], "菜单是给业主看的,中文");
});
