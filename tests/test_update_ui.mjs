// track opendesign-in-app-update oracle:查更新那一行在界面上说什么。
// 主 agent 亲写。跑法:node --test tests/test_update_ui.mjs
//
// 由来:`Sidebar.tsx` 里**本来就有一个「检查更新」按钮,而它没有 onClick** ——
// 业主点它只会觉得"没反应"。这一单把它做成真的,而这份判据钉的是**它说的话**。
//
// 🔴 最要紧的一条是 u3:**查更新失败时,绝不许显示"已是最新"**。
//    那是把失败伪装成成功 —— 业主会以为自己在最新版上,而实际上可能落后好几版。
//    本单从头到尾治的就是这一类"安静的谎",判据自己更不能生产一个。
import { test } from "node:test";
import assert from "node:assert/strict";
import { updateLabel, safeReleaseUrl, autoCheckEnabled, notesSummary, hasUpdateBadge } from "../web/src/update.ts";

const NEWER = {
  current: "0.98.1", update_available: true, latest: "0.98.3",
  asset: { name: "OpenDesign-Setup-0.98.3.exe", url: "https://x/y", size: 1, digest: "sha256:aa" },
  notes: "", error: null,
};
const SAME = { current: "0.98.3", update_available: false, latest: "0.98.3", asset: null, notes: "", error: null };
const FAILED = { current: "0.98.3", update_available: false, latest: null, asset: null, notes: "", error: "查更新失败:OSError: no route to host" };

test("u1 有新版时,那句话里必须带着版本号", () => {
  const s = updateLabel({ state: "done", info: NEWER });
  assert.match(s, /0\.98\.3/, `「${s}」没说是哪一版 —— 业主没法判断值不值得更新`);
});

test("u2 已是最新就说已是最新,不许说成有新版", () => {
  const s = updateLabel({ state: "done", info: SAME });
  assert.doesNotMatch(s, /有新版/, `已经是最新了,却说「${s}」`);
  assert.match(s, /最新/);
});

test("u3 🔴 查不动的时候不许说「已是最新」", () => {
  const s = updateLabel({ state: "done", info: FAILED });
  assert.doesNotMatch(
    s, /已是最新|最新版/,
    `查更新失败了,界面却说「${s}」—— 把失败伪装成成功,` +
    `业主会以为自己在最新版上,而他可能落后好几版`);
  assert.match(s, /查不到|失败|没查到/, `「${s}」没说清楚是"没查成",而不是"没有新版"`);
});

test("u4 点下去要有反应(这个按钮原来的病就是没反应)", () => {
  const s = updateLabel({ state: "checking", info: null });
  assert.match(s, /检查中|查询中/, `点了之后显示「${s}」,和没反应一样`);
});

test("u5 还没查过时显示的是版本号,不是空白", () => {
  const s = updateLabel({ state: "idle", info: null, version: "0.98.3" });
  assert.match(s, /0\.98\.3/, `没查过时该显示当前版本,却显示「${s}」`);
});



// ── S1 的界面侧:两处对"什么是合法版本号"的口径必须一致 ──────────────

// ── S3:自动查更新要能关掉 ────────────────────────────────────────
test("u9 默认自动检查(业主没表过态时,帮他查)", () => {
  assert.equal(autoCheckEnabled({}), true);
});

test("u10 🔴 显式关掉之后就不许再自动往外发请求", () => {
  assert.equal(autoCheckEnabled({ "update.autoCheck": false }), false,
    "业主关掉了自动检查,软件却还是每次打开都往 GitHub 发一次请求");
  assert.equal(autoCheckEnabled({ "update.autoCheck": true }), true);
});

// ── S4:取了就要用,不许留个"取了不显示"的字段假装做了 ──────────────
test("u11 更新说明取第一句有意义的话,去掉 markdown 记号", () => {
  const s = notesSummary("## 这一版改了什么\n\n**双击之后的等待**从 9 秒降到 1.5 秒");
  assert.doesNotMatch(s, /^#|\*\*/, `没洗掉 markdown 记号:「${s}」`);
  assert.match(s, /9 秒/, `没取到正文:「${s}」`);
});

test("u12 更新说明太长要截断,空的要给空串", () => {
  assert.equal(notesSummary(""), "");
  assert.equal(notesSummary(null), "");
  const long = notesSummary("x".repeat(500));
  assert.ok(long.length <= 80, `截断没生效:${long.length} 字`);
});

// ════════════════════════════════════════════════════════════════════════
// 评审 F1(subdeepseek 抓到、我自己复现确认)——**我修 S1 时自己造出来的 bug**:
// 补零把 `1.0` 变成 `1.0.0`,而真实 tag 是 `win-installer-1.0` ⇒ 拼出来的下载链接 404。
// 旧的 u6/u7/u8 已删:它们测的是 releasePageUrl("1.0"),**而运行时永远不会传两段进去**
// (后端给的一直是补零后的形式)——判据在测一条走不到的路,等于没测。
// 新做法:**地址不再由我们拼,用 GitHub 自己给的 html_url;我们只负责验它。**
test("u6 只放行本仓 releases 下的 https 地址", () => {
  const real = "https://github.com/SunJ1ayu/OpenDesign/releases/tag/win-installer-1.0";
  assert.equal(safeReleaseUrl(real), real);
});

test("u7 别人给的地址一律不放行(界面上那个链接是要业主去点的)", () => {
  assert.equal(safeReleaseUrl("http://github.com/SunJ1ayu/OpenDesign/releases/tag/x"), null,
    "http 明文也放行了");
  assert.equal(safeReleaseUrl("https://evil.example.com/releases/tag/x"), null,
    "别的域名也放行了 —— 后端一旦被骗,业主就会点到别人家去");
  assert.equal(safeReleaseUrl("https://github.com/SunJ1ayu/OpenDesign/issues/1"), null,
    "不是 releases 下的地址也放行了");
  assert.equal(safeReleaseUrl(null), null);
  assert.equal(safeReleaseUrl(""), null);
});

// ── 评审 F2:那句"有新版"藏在收起来的设置里,等于没说 ──────────────
test("u13 🔴 有新版时,设置那一行必须挂个记号(不然业主根本看不到)", () => {
  assert.equal(hasUpdateBadge({ update_available: true, latest: "1.0.0" }), true,
    "有新版却不在收起来的设置行上留任何记号 —— 业主永远不会知道");
  assert.equal(hasUpdateBadge({ update_available: false, latest: "1.0.0" }), false);
  assert.equal(hasUpdateBadge(null), false);
});

// ── 评审 F3:查完了但没拿到东西,不许长得像"还没查过" ────────────────
test("u14 done + 空结果要说查不到,不许伪装成没查过", () => {
  const s = updateLabel({ state: "done", info: null, version: "0.98.3" });
  assert.match(s, /查不到/, `查完了却什么都没拿到,界面显示「${s}」—— 和没查过一模一样`);
});
