// 换壳后前端这一侧(track opendesign-electron-shell,T3;主 agent 亲写,判据先单独 commit)。
// 跑法:node --test tests/test_desktop_ui.mjs(Node 22+,原生 strip-types)
//
// 两件事:
//   ① 更新一栏说什么话 —— 接的是主进程推来的状态(desktop/lib/updateState.js 同形),
//      U3 = 照 ZCode:下好了才出现「重启以更新」,他点了才装;
//   ② 窗口栏接 `window.odShell`(preload 给的),拖动交给 Chromium 的 app-region,八个自绘把手删掉。
// 旧判据 u3「查不动不许说已是最新」、s-w1「浏览器里一个按钮都不画」原样搬过来(判据迁移账)。
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  desktopUpdateLabel, showRestart, showRetry, hasDesktopUpdateBadge, RESTART_HINT,
} from "../web/src/desktopUpdate.ts";
import { shellApi } from "../web/src/desktopShell.ts";

const S = (phase, extra = {}) => ({ phase, ...extra });
const PHASES = [
  S("idle"), S("checking"), S("latest"), S("downloading", { version: "0.98.11", percent: 37 }),
  S("downloaded", { version: "0.98.11" }), S("error", { error: "net::ERR_CONNECTION_REFUSED" }),
  S("error", { error: "ECONNRESET", version: "0.98.11" }),          // 知道有新版、下到一半断了
];
const downloadFailed = (s) => s.phase === "error" && !!s.version;

// ── ① 更新一栏 ─────────────────────────────────────────────────────
test("du1 没查过时显示当前版本,不是空白", () => {
  assert.match(desktopUpdateLabel(S("idle"), "0.98.10"), /0\.98\.10/);
});

test("du2 查的时候有反应", () => {
  assert.match(desktopUpdateLabel(S("checking"), "0.98.10"), /检查中|查询中/);
});

test("du3 查过、没有新版:说已是最新", () => {
  assert.match(desktopUpdateLabel(S("latest"), "0.98.10"), /已是最新/);
});

test("du4 🔴 查不动 / 下载失败不许说「已是最新」(旧判据 u3)", () => {
  const s = desktopUpdateLabel(S("error", { error: "net::ERR_CONNECTION_REFUSED" }), "0.98.10");
  assert.doesNotMatch(s, /已是最新|最新版/, `查不动时说「${s}」= 把失败伪装成成功`);
  assert.match(s, /没查到|查不到|失败/);
  assert.doesNotMatch(s, /ERR_|net::/, "英文错误码不给业主看(进日志)");
});

test("du4b 下载到一半失败:说是哪一版没下完,不说「已是最新」也不说「没查到」(那会让他以为没有新版)", () => {
  const s = desktopUpdateLabel(S("error", { error: "ECONNRESET", version: "0.98.11" }), "0.98.10");
  assert.match(s, /0\.98\.11/);
  assert.match(s, /下载/);
  assert.doesNotMatch(s, /已是最新|没查到|查不到/);
  assert.doesNotMatch(s, /ECONNRESET/, "英文错误码不给业主看(进日志)");
});

test("du5 下载中、下好了:都说出是哪一版", () => {
  assert.match(desktopUpdateLabel(S("downloading", { version: "0.98.11", percent: 37 }), "0.98.10"), /0\.98\.11/);
  assert.match(desktopUpdateLabel(S("downloaded", { version: "0.98.11" }), "0.98.10"), /0\.98\.11/);
});

test("du6 🔴「重启以更新」只在 downloaded 出现(没下好就装 = 装半截)", () => {
  for (const s of PHASES) assert.equal(showRestart(s), s.phase === "downloaded", `${s.phase}`);
});

test("du7 失败了要有「重试」(挑战 a6:先开软件后开 VPN;下载失败不许静默)", () => {
  for (const s of PHASES) assert.equal(showRetry(s), s.phase === "error", `${s.phase}`);
});

test("du8 侧栏「设置」行上的圆点:下好了、或下载失败(知道有新版却没拿到)时亮;单纯查不到不亮(挑战 a5 / 攻题 #14)", () => {
  // 攻题 #14:只在 downloaded 亮 ⇒ 下载失败时设置弹层收着、侧栏毫无动静 = 「下载失败不许静默」落空。
  // 反过来单纯「查不到」(他常先开软件后开 VPN)每次开机都亮一个点 = 骚扰,而且我们根本不知道有没有新版。
  for (const s of PHASES) {
    assert.equal(hasDesktopUpdateBadge(s), s.phase === "downloaded" || downloadFailed(s), `${s.phase} version=${s.version}`);
  }
  assert.equal(hasDesktopUpdateBadge(null), false);
  assert.equal(hasDesktopUpdateBadge(undefined), false);
});

test("du9 按钮旁写明要多久、别关机(向导进度页取消不了,关机会装一半)", () => {
  assert.match(RESTART_HINT, /2 ?分钟/);
  assert.match(RESTART_HINT, /关机/);
});

test("du10 每个状态都有话说,且不是 undefined/null 拼出来的", () => {
  for (const s of [...PHASES, S("downloading", {}), S("downloaded", {})]) {
    const t = desktopUpdateLabel(s, "0.98.10");
    assert.ok(t && t.trim(), `${s.phase} 没话说`);
    assert.doesNotMatch(t, /undefined|null|NaN/, `${s.phase}:「${t}」`);
  }
});

// ── ② 窗口栏 ─────────────────────────────────────────────────────
const FULL = {
  minimize() {}, toggleMaximize() {}, close() {}, windowState() {}, onWindowState() {}, reportStartup() {},
  update: { check() {}, install() {}, state() {}, onState() {} },
};

test("du11 shellApi 只认 preload 给的 odShell,齐了才给", () => {
  assert.equal(shellApi({ odShell: FULL }), FULL);
  assert.equal(shellApi({}), null);
  assert.equal(shellApi(null), null);
  assert.equal(shellApi({ pywebview: { api: FULL } }), null, "pywebview 那套已经退役");
  const half = { ...FULL };
  delete half.toggleMaximize;
  assert.equal(shellApi({ odShell: half }), null, "缺一个方法就当没有 —— 不许渲染一个按下去会抛错的按钮");
});

test("du12 窗口栏 CSS:拖动带交给 Chromium,按钮不许被拖动吃掉,八个自绘把手删光", () => {
  const css = readFileSync(new URL("../web/src/app.css", import.meta.url), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
  const rule = (sel) => {
    const m = css.match(new RegExp(`(^|[},\\s])${sel.replace(".", "\\.")}\\s*\\{([^}]*)\\}`, "m"));
    return m ? m[2] : "";
  };
  assert.match(rule(".win-bar"), /-webkit-app-region\s*:\s*drag/, "拖动带没有 app-region:drag ⇒ 窗口拖不动");
  assert.match(rule(".win-btns"), /-webkit-app-region\s*:\s*no-drag/, "按钮区没有 no-drag ⇒ 点按钮 = 拖窗口");
  assert.doesNotMatch(css, /\.win-grip/, "自绘缩放把手会压在系统缩放边上(表 #10)");
  const tsx = readFileSync(new URL("../web/src/workspace/WindowChrome.tsx", import.meta.url), "utf8");
  assert.doesNotMatch(tsx, /win-grip|RESIZE_EDGES|begin_resize|begin_drag/);
});
