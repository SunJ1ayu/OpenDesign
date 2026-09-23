// 冷启动不再挂「正在启动」(track opendesign-instant-ui;主 agent 亲写,判据先单独 commit)。
// 跑法:node --test tests/test_desktop_instant.mjs(Node 22+,原生 strip-types)
//
// 业主:「为什么启动都会有一个正在启动,zcode好像没有这个吧」→「直接学吧」。
// 做法(design.md):窗口一创建就加载 app://opendesign/?shell=1 —— 界面文件由主进程从包里的
// resources/ds/web/dist 直接给;/api/* **挂起到后台就绪**再转给 http://127.0.0.1:<web_port>。
// 云探针 run 35820084450 已证:挂起/上传/图片/ws 直连/系统代理/localStorage 持久在真 Windows 上都成立。
//
// 这份判据钉的是那些**一旦写错、Windows 上全是安静症状**的地方:
//   · 静态文件越界(..%5c、%00)⇒ 页面能读安装目录外的文件;
//   · /api 没挂起就转发 ⇒ 后台没好时每个页面钉死红字(挑战腿:项目/待办/key 只挂载时拉一次);
//   · 转发时把页面的 Origin/Sec-Fetch-* 带过去 ⇒ ds-web 同站检查 403 全部写操作;
//   · 伪装主机名 app://evil/ 也被代理 ⇒ 多一条进后台的门;
//   · 管家还没起来时的 window-shown / 首帧上报被丢 ⇒ 90 秒后写一份假的「界面没画出来」诊断。
// 真 Windows 那一半在 .github/scripts/electron-e2e/e2-drive.mjs 的 E2.instant / E2.connecting / E2.noreload。
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

const require = createRequire(import.meta.url);
const lib = (name) => require(`../desktop/lib/${name}.js`);
const read = (rel) => readFileSync(new URL(`../${rel}`, import.meta.url), "utf8");

const DIST = path.resolve("/opt/od/resources/ds/web/dist");
const FILES = new Map([
  [path.join(DIST, "index.html"), "<!doctype html><title>OpenDesign</title>"],
  [path.join(DIST, "assets", "index-abc.js"), "console.log(1)"],
  [path.join(DIST, "assets", "index-abc.css"), "body{}"],
  [path.join(DIST, "assets", "logo.webp"), "RIFF"],
]);

function deferred() {
  let resolve;
  const promise = new Promise((r) => { resolve = r; });
  return { promise, resolve };
}

function appHarness(over = {}) {
  const rec = { reads: [], fetches: [], logs: [] };
  const port = deferred();
  const { createAppHandler } = lib("appProtocol");
  const handler = createAppHandler({
    distRoot: DIST,
    readFile: async (abs) => {
      rec.reads.push(abs);
      if (!FILES.has(abs)) { const e = new Error("ENOENT"); e.code = "ENOENT"; throw e; }
      return Buffer.from(FILES.get(abs), "utf8");
    },
    backendPort: () => port.promise,
    fetch: async (url, init) => { rec.fetches.push({ url, init }); return new Response('{"ok":true}', { status: 200 }); },
    log: (m) => rec.logs.push(String(m)),
    ...over,
  });
  return { handler, rec, port };
}
const tick = (ms = 20) => new Promise((r) => setTimeout(r, ms));
const within = (abs) => abs === DIST || abs.startsWith(DIST + path.sep);

// ── 界面文件:和 ds-web `_static` 同一套规矩(bin/ds_web.py _static) ─────────────
test("a1 首页 = 包里的 index.html,入口页不缓存、nosniff", async () => {
  const { handler } = appHarness();
  const r = await handler(new Request("app://opendesign/?shell=1"));
  assert.equal(r.status, 200);
  assert.equal(r.headers.get("content-type"), "text/html; charset=utf-8");
  assert.equal(r.headers.get("cache-control"), "no-cache", "入口页被缓存 ⇒ 更新后还跑旧界面(本机栽过两次的「盘上新、跑着旧」)");
  assert.equal(r.headers.get("x-content-type-options"), "nosniff");
  assert.match(await r.text(), /OpenDesign/);
});

test("a2 带哈希的资源长缓存、类型对", async () => {
  const { handler } = appHarness();
  const js = await handler(new Request("app://opendesign/assets/index-abc.js"));
  assert.equal(js.status, 200);
  assert.equal(js.headers.get("content-type"), "application/javascript; charset=utf-8", "类型错 ⇒ 模块脚本不执行 ⇒ 整页白");
  assert.equal(js.headers.get("cache-control"), "public, max-age=31536000, immutable");
  const css = await handler(new Request("app://opendesign/assets/index-abc.css"));
  assert.equal(css.headers.get("content-type"), "text/css; charset=utf-8");
  const other = await handler(new Request("app://opendesign/assets/logo.webp"));
  assert.equal(other.headers.get("content-type"), "application/octet-stream");
});

test("a3 🔴 越界一律拒,且从不去读 dist 以外的路径(..%2f / ..%5c / %00 / 绝对路径)", async () => {
  const { handler, rec } = appHarness();
  for (const u of [
    "app://opendesign/..%2f..%2f..%2fWindows%2fwin.ini",
    "app://opendesign/assets/..%5c..%5c..%5ckey.txt",
    "app://opendesign/assets/%2e%2e/%2e%2e/%2e%2e/key.txt",
    "app://opendesign/index.html%00.js",
    "app://opendesign/C:%5cWindows%5cwin.ini",
    "app://opendesign/%2fetc%2fpasswd",
  ]) {
    const r = await handler(new Request(u));
    assert.ok(r.status === 400 || r.status === 404, `${u} ⇒ ${r.status}`);
  }
  const outside = rec.reads.filter((p) => !within(path.resolve(p)));
  assert.deepEqual(outside, [], `读到了 dist 外面:${outside.join(", ")}`);
});

test("a4 不存在的文件 404,不回落首页(工作台是 #/ 路由,ds-web 也不回落)", async () => {
  const { handler } = appHarness();
  assert.equal((await handler(new Request("app://opendesign/assets/nope.js"))).status, 404);
  assert.equal((await handler(new Request("app://opendesign/projects/x"))).status, 404);
});

test("a5 🔴 冒名主机 app://别的/ 既不给文件也不进后台", async () => {
  const { handler, rec, port } = appHarness();
  port.resolve(8766);
  for (const u of ["app://evil/index.html", "app://evil/api/health", "app://opendesign.evil/api/health"]) {
    assert.equal((await handler(new Request(u))).status, 404, u);
  }
  assert.equal(rec.fetches.length, 0, "冒名主机被转进了后台");
});

// ── /api:挂起到就绪 → 转给 ds-web ────────────────────────────────────
test("a6 🔴 后台没好时 /api 请求挂着、不失败;就绪后原样转给 127.0.0.1:<端口>(路径与查询串不丢)", async () => {
  const { handler, rec, port } = appHarness();
  let settled = false;
  const p = handler(new Request("app://opendesign/api/projects/a%20b/changes?limit=10&x=%E4%B8%AD")).then((r) => { settled = true; return r; });
  await tick(30);
  assert.equal(settled, false, "没就绪就回了 ⇒ 页面拿到错误钉死红字(挑战腿:项目/待办只挂载时拉一次)");
  assert.equal(rec.fetches.length, 0, "没就绪就去连后台");
  port.resolve(8767);
  const r = await p;
  assert.equal(r.status, 200);
  assert.equal(rec.fetches.length, 1);
  assert.equal(rec.fetches[0].url, "http://127.0.0.1:8767/api/projects/a%20b/changes?limit=10&x=%E4%B8%AD");
});

test("a7 🔴 转发时去掉页面身份头(Origin/Referer/Sec-Fetch-*),业务头照带", async () => {
  const { handler, rec, port } = appHarness();
  port.resolve(8766);
  await handler(new Request("app://opendesign/api/changes/edit", {
    method: "POST",
    headers: {
      Origin: "app://opendesign", Referer: "app://opendesign/?shell=1",
      "Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Dest": "empty",
      "Content-Type": "application/json", Authorization: "Bearer t0k",
    },
    body: '{"a":1}',
  }));
  const h = new Headers(rec.fetches[0].init.headers);
  for (const k of ["origin", "referer", "sec-fetch-site", "sec-fetch-mode", "sec-fetch-dest"]) {
    assert.equal(h.get(k), null, `${k} 被带去 ds-web ⇒ 同站检查 403 所有写操作`);
  }
  assert.equal(h.get("content-type"), "application/json");
  assert.equal(h.get("authorization"), "Bearer t0k", "聊天接口靠 Bearer,丢了就 401");
});

test("a8 方法与请求体原样转发(上传走流,duplex=half);GET 不带体", async () => {
  const { handler, rec, port } = appHarness();
  port.resolve(8766);
  await handler(new Request("app://opendesign/api/upload", { method: "POST", body: "x".repeat(1000) }));
  const post = rec.fetches[0].init;
  assert.equal(post.method, "POST");
  assert.ok(post.body, "上传体没带过去");
  assert.equal(post.duplex, "half", "流式体不带 duplex ⇒ fetch 直接抛");
  await handler(new Request("app://opendesign/api/health"));
  assert.equal(rec.fetches[1].init.method, "GET");
  assert.equal(rec.fetches[1].init.body, undefined);
});

test("a9 后台连不上(死了/重启中)⇒ 502 JSON,不抛(抛了页面拿到的是无法解释的网络错误)", async () => {
  const { handler, rec, port } = appHarness({ fetch: async () => { throw new Error("ECONNREFUSED"); } });
  port.resolve(8766);
  const r = await handler(new Request("app://opendesign/api/health"));
  assert.equal(r.status, 502);
  assert.equal(r.headers.get("content-type"), "application/json; charset=utf-8");
  assert.ok((await r.json()).error);
  assert.ok(rec.logs.some((m) => /ECONNREFUSED/.test(m)), "原因要进日志");
});

test("a10 只有 /api/ 开头才进后台:/apix、/api 本身都按文件处理", async () => {
  const { handler, rec, port } = appHarness();
  port.resolve(8766);
  assert.equal((await handler(new Request("app://opendesign/apix"))).status, 404);
  assert.equal((await handler(new Request("app://opendesign/api"))).status, 404);
  assert.equal(rec.fetches.length, 0);
});

test("a11 窗口地址 = app://opendesign/?shell=1,外壳标记与前端同一个字面量", async () => {
  const { APP_ORIGIN, APP_URL } = lib("appProtocol");
  const { SHELL_MARK } = await import("../web/src/shellWindow.ts");
  assert.equal(APP_ORIGIN, "app://opendesign");
  assert.equal(APP_URL, `app://opendesign/?${SHELL_MARK}`, "首个地址不带标记 ⇒ 整段会话没有窗口按钮(inDesktopShell 只读一次)");
});

// ── 导航:源站换成 app://opendesign ────────────────────────────────────
test("n1 🔴 站内(app://opendesign)放行;冒名主机拒、不外开;http(s) 交系统浏览器", () => {
  const { navDecision } = lib("navPolicy");
  const { APP_ORIGIN } = lib("appProtocol");
  assert.equal(navDecision("app://opendesign/?shell=1", APP_ORIGIN), "allow");
  assert.equal(navDecision("app://opendesign/#/workspace", APP_ORIGIN), "allow");
  // Node 的 URL 对非特殊协议给 origin === "null":拿 origin 比 ⇒ 任何 app:// 都会被当成站内
  for (const u of ["app://evil/", "app://opendesign.evil/", "app://opendesign@evil/", "app://evil/?shell=1"]) {
    assert.equal(navDecision(u, APP_ORIGIN), "deny", u);
  }
  assert.equal(navDecision("https://github.com/SunJ1ayu/OpenDesign/releases", APP_ORIGIN), "external");
  assert.equal(navDecision("http://127.0.0.1:8766/", APP_ORIGIN), "external", "窗口不许被带去别的源");
  assert.equal(navDecision("file:///C:/Windows/win.ini", APP_ORIGIN), "deny");
});

// ── 管家通道:起来之前的消息先攒着 ─────────────────────────────────────
function fakeChild() {
  const lines = [];
  return { exitCode: null, stdin: { writable: true, write: (s) => { lines.push(s); return true; } }, lines };
}

test("hs1 🔴 管家还没起来时发的(window-shown / 首帧上报)先攒着,接上后按原顺序补发", () => {
  const { createHostSender } = lib("hostSender");
  const { encodeCommand } = lib("hostProtocol");
  const s = createHostSender({ log: () => {} });
  s.send({ cmd: "window-shown" });
  s.send({ cmd: "report", event: "frontend.frame_submitted", detail: "" });
  const child = fakeChild();
  s.attach(child);
  assert.deepEqual(child.lines, [encodeCommand({ cmd: "window-shown" }),
    encodeCommand({ cmd: "report", event: "frontend.frame_submitted", detail: "" })],
    "丢了 ⇒ 90 秒首帧看门写一份假的「界面没画出来」(挑战腿)");
  s.send({ cmd: "quit" });
  assert.equal(child.lines.at(-1), encodeCommand({ cmd: "quit" }), "接上之后直接写");
});

test("hs2 管家已退出 / stdin 不可写 / 写时抛 ⇒ 丢弃并记日志,不抛", () => {
  const { createHostSender } = lib("hostSender");
  const logs = [];
  const s = createHostSender({ log: (m) => logs.push(m) });
  const dead = fakeChild(); dead.exitCode = 1;
  s.attach(dead);
  assert.doesNotThrow(() => s.send({ cmd: "report", event: "x", detail: "" }));
  assert.equal(dead.lines.length, 0);
  const boom = fakeChild(); boom.stdin.write = () => { throw new Error("EPIPE"); };
  s.attach(boom);
  assert.doesNotThrow(() => s.send({ cmd: "window-shown" }));
  assert.ok(logs.some((m) => /EPIPE/.test(m)));
});

test("hs3 攒的有上限(管家永远起不来时不无限长)", () => {
  const { createHostSender } = lib("hostSender");
  const s = createHostSender({ log: () => {} });
  for (let i = 0; i < 1000; i++) s.send({ cmd: "report", event: "e", detail: String(i) });
  const child = fakeChild();
  s.attach(child);
  assert.ok(child.lines.length > 0 && child.lines.length <= 200, `补发了 ${child.lines.length} 条`);
});

// ── 控制器:ready 不再换页,只放行挂着的请求 ────────────────────────────
function ctl(over = {}) {
  const rec = { ready: [], backend: [], errors: [], loaded: [], external: [], quits: 0 };
  const { createController } = lib("controller");
  const c = createController({
    appVersion: "0.98.10",
    backendReady: (port) => rec.ready.push(port),
    pushBackendState: (s) => rec.backend.push(s),
    loadWorkbench: (u) => rec.loaded.push(u),
    showWindow: () => {}, showError: (m) => rec.errors.push(m), revealFile: () => {},
    openExternal: (u) => rec.external.push(u), log: () => {},
    updater: { on() {}, checkForUpdates: async () => {} },
    pushUpdateState: () => {}, setTimeout: () => 0, clearTimeout: () => {},
    relaunch: () => {}, quitApp: () => { rec.quits++; }, graceMs: 10,
    ...over,
  });
  return { c, rec };
}
const line = (o) => JSON.stringify(o) + "\n";

test("bs1 🔴 一开始就是「后台启动中」;ready 且版本一致 ⇒ 放行端口一次、推「就绪」,**不再整页换地址**", () => {
  const { c, rec } = ctl();
  assert.deepEqual(c.backendState(), { phase: "starting" });
  c.hostStdout(line({ event: "ready", web_port: 8767, version: "0.98.10" }));
  assert.deepEqual(rec.ready, [8767]);
  assert.deepEqual(rec.backend, [{ phase: "ready" }]);
  assert.deepEqual(c.backendState(), { phase: "ready" });
  assert.deepEqual(rec.loaded, [], "就绪后再 loadURL ⇒ 业主看到整页再来一次(挑战腿:会看成第二次启动)");
});

test("bs2 版本对不上 ⇒ 不放行(挂着的请求永远不进半新半旧的后台),弹框退出", () => {
  const { c, rec } = ctl();
  c.hostStdout(line({ event: "ready", web_port: 8767, version: "0.98.9" }));
  assert.deepEqual(rec.ready, []);
  assert.deepEqual(c.backendState(), { phase: "starting" });
  assert.equal(rec.errors.length, 1);
  assert.equal(rec.quits, 1);
});

test("bs3 站内跳转在后台就绪之前就放行(源站创建窗口时就定了)", () => {
  const { c, rec } = ctl();
  assert.equal(c.navigate("app://opendesign/#/workspace"), false);
  assert.equal(c.navigate("https://example.com/"), true);
  assert.deepEqual(rec.external, ["https://example.com/"]);
});

// ── 前端:后台没好时的那一条横幅 ─────────────────────────────────────
test("fb1 启动中有一句中文横幅;就绪、浏览器里(没有外壳)都不显示", async () => {
  const { backendBanner } = await import("../web/src/backendState.ts");
  assert.match(backendBanner({ phase: "starting" }) ?? "", /[\u4e00-\u9fff]/);
  assert.equal(backendBanner({ phase: "ready" }), null);
  assert.equal(backendBanner(null), null);
  assert.equal(backendBanner(undefined), null);
});

test("fb2 外壳桥:新 preload 给 backend;旧 preload 没有 backend 也照样认得出外壳(窗口按钮不能因此消失)", async () => {
  const { shellApi, backendApi } = await import("../web/src/desktopShell.ts");
  const fn = () => {};
  const base = { minimize: fn, toggleMaximize: fn, close: fn, windowState: fn, onWindowState: fn, reportStartup: fn,
    update: { check: fn, install: fn, state: fn, onState: fn } };
  assert.ok(shellApi({ odShell: base }), "没有 backend 的旧桥也得认");
  assert.equal(backendApi({ odShell: base }), null);
  assert.ok(backendApi({ odShell: { ...base, backend: { state: fn, onState: fn } } }));
  assert.equal(backendApi({}), null);
});

// ── 接线(静态):上面的零件真的接进了主进程 / preload / 界面 ─────────────
test("s1 🔴 app 协议在模块顶层注册成特权协议(standard/secure/supportFetchAPI/stream),先于 whenReady", () => {
  const src = read("desktop/main.js");
  const reg = src.search(/^protocol\.registerSchemesAsPrivileged\(/m);
  assert.ok(reg >= 0, "没在顶层注册 ⇒ app:// 不是标准协议,localStorage/fetch 都不认");
  assert.ok(reg < src.indexOf("app.whenReady("), "注册必须在 ready 之前");
  const block = src.slice(reg, src.indexOf(");", reg));
  for (const k of ["standard: true", "secure: true", "supportFetchAPI: true", "stream: true"]) {
    assert.ok(block.includes(k), `缺 ${k}`);
  }
  assert.match(src, /protocol\.handle\(\s*"app"/);
  assert.match(src, /path\.join\(resources,\s*"ds",\s*"web",\s*"dist"\)/, "界面文件要从包里 ds\\web\\dist 取(和 ds-web 同一份)");
});

test("s2 🔴 窗口一创建就加载 APP_URL;加载页整个删掉", () => {
  const src = read("desktop/main.js");
  const cw = src.slice(src.indexOf("function createWindow"), src.indexOf("function ", src.indexOf("function createWindow") + 10));
  assert.match(cw, /win\.loadURL\(APP_URL\)/);
  assert.ok(!/loading\.html/.test(src), "main.js 还在引用加载页");
  assert.ok(!existsSync(new URL("../desktop/loading.html", import.meta.url)), "desktop/loading.html 还在");
  assert.ok(!/loadWorkbench/.test(src), "还留着就绪后换地址的接线");
});

test("s3 管家通道全走 hostSender(主进程里不再直接写 host.stdin)", () => {
  const src = read("desktop/main.js");
  assert.ok(!/host\.stdin\.write/.test(src), "直接写 ⇒ 管家起来之前的消息照丢");
  assert.match(src, /createHostSender/);
});

test("s4 后台状态经 preload 到界面,界面有那条横幅", () => {
  const pre = read("desktop/preload.js");
  assert.match(pre, /backend:\s*\{/);
  assert.match(pre, /"od:backend-state"/);
  assert.match(pre, /"od:backend-state-changed"/);
  const main = read("desktop/main.js");
  assert.match(main, /ipcMain\.handle\("od:backend-state"/);
  assert.match(main, /"od:backend-state-changed"/);
  const appTsx = read("web/src/App.tsx");
  assert.match(appTsx, /backendBanner\(/);
  assert.match(appTsx, /data-ui="backend-connecting"/);
});
