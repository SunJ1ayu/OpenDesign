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
import { updateLabel, safeReleaseUrl, autoCheckEnabled, notesSummary, hasUpdateBadge, downloadUrl, badgeTitle } from "../web/src/update.ts";

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

// ── 评审第二轮 F-C/F-D + submimo 补充 1 ──────────────────────────────
test("u15 地址被闸掉时也得给业主一条路(F-C:仓库改名会让下载行静默消失)", () => {
  // GitHub 在仓库改名后会把 html_url 换成新 full_name ⇒ 前缀闸拦下 ⇒ 下载行不渲染,
  // 而蓝点还亮着:业主看见"有新版",却没有任何地方可点。
  const u = downloadUrl("https://github.com/SomeoneElse/Renamed/releases/tag/x");
  assert.equal(u, "https://github.com/SunJ1ayu/OpenDesign/releases",
    "闸掉了别人的地址,却没给业主任何退路");
  assert.equal(downloadUrl(null), "https://github.com/SunJ1ayu/OpenDesign/releases");
  const real = "https://github.com/SunJ1ayu/OpenDesign/releases/tag/win-installer-1.0";
  assert.equal(downloadUrl(real), real, "正常地址被退路顶掉了");
});

test("u16 有新版但没版本号时,不许说成「已是最新」(F-D)", () => {
  const s = updateLabel({
    state: "done",
    info: { current: "0.98.1", update_available: true, latest: null,
            asset: null, notes: "", error: null, release_url: null },
  });
  assert.doesNotMatch(s, /已是最新/,
    `既说有新版又说已是最新,同时印在界面上:「${s}」`);
});

test("u17 正文以「这一版」开头时不许被当成标题跳掉(submimo 补充 1)", () => {
  const s = notesSummary("## 这一版改了什么\n\n这一版修了一个导致白屏的 bug");
  assert.match(s, /白屏/,
    `把正文当成标题跳掉了:「${s}」—— 跳过的依据应该是"它本来是个 markdown 标题",` +
    `不是"它以某几个词开头"`);
});

test("u18 issue 编号那种 `#123` 不许被当成标题记号剥掉", () => {
  const s = notesSummary("## 这一版改了什么\n\n#123 修复了导致白屏的那个 bug");
  assert.match(s, /#123/, `把 issue 编号的 # 剥掉了:「${s}」`);
});

// ── 第三轮自审 MR-2:F-D 只修了一半 ─────────────────────────────────────
// `updateLabel` 已经处理了"有新版但没版本号"(u16),而**同一屏上**那个蓝点的
// 悬停说明还是 `有新版 ${info?.latest}` —— 同一个组合下它印的是「有新版 null」。
// 一个 bug 只修一侧就是造新分叉(记忆 wq101-paper-trading 那次的形状)。
test("u19 🔴 没版本号时,蓝点的说明不许把 null 印给业主", () => {
  const s = badgeTitle({ update_available: true, latest: null });
  assert.doesNotMatch(s, /null|undefined/,
    `蓝点悬停说明印成「${s}」—— u16 修的是同一个组合,标签修了、这里没修`);
  assert.match(s, /有新版/, `「${s}」没说清是有新版`);
});

test("u20 有版本号时,蓝点的说明要带上它(别把上一条修成恒定串)", () => {
  assert.match(badgeTitle({ update_available: true, latest: "0.99.0" }), /0\.99\.0/);
});

// ── 第三轮评审 F1(subdeepseek 用 probe 实测出来的,工件里没有)────────────
// `notesSummary` 只认 ATX(`# `)那种标题。业主的 release 正文若用 setext 写法
// (标题下面一行 `===`),标题会被当成正文印出去 —— 和 submimo 补充 1 治的是同一种病,
// 只是形态不同。首行是 `---` 时更难看:界面上直接印一串横杠,还把"去发布页 ›"顶掉。
test("u21 setext 标题(下一行 ===)不许被当成正文印给业主", () => {
  const s = notesSummary("大版本标题\n==========\n\n修了打开软件时全白的那个 bug");
  assert.match(s, /白屏|全白/,
    `setext 标题被当成正文了:「${s}」—— ATX 认了、这种没认`);
});

test("u22 正文以分隔线开头时,不许把那串横杠印出来", () => {
  const s = notesSummary("---\n\n## 这一版改了什么\n\n修了打开软件时全白的那个 bug");
  assert.doesNotMatch(s, /^[-=*_\s]+$/, `印了一串分隔符:「${s}」`);
  assert.match(s, /白屏|全白/, `没往下找到正文:「${s}」`);
});

// ── 第四轮 panel 的 4 条 LOW 里的 3 条(第一刀判"接受不改",第二刀本来就要动这块)──
// 三条都是 setext 标题这一块没做完留下的,形态不同、根子是同一个:
// **`isSetext` 只问"我的下一行是不是下划线"**,既管不到下划线自己,
// 也管不到标题有好几行,还会把"下一行恰好是 `---`"的列表项误伤。

test("u23 🔴 setext 下划线只有 1~2 个字符时,不许把它自己当正文印出来", () => {
  // HORIZONTAL_RULE 要求"首字符 + 至少 2 个同样的" ⇒ `==` / `--` 漏网,
  // 标题被跳掉之后,下划线那一行自己成了"第一句有意义的话"。
  const s = notesSummary("大版本标题\n==\n\n修了打开软件时全白的那个 bug");
  assert.doesNotMatch(s, /^[-=*_\s]+$/, `把下划线本身印出来了:「${s}」`);
  assert.match(s, /白屏|全白/, `没往下找到正文:「${s}」`);
});

test("u24 🔴 多行 setext 标题不许只跳最后一行", () => {
  // setext 的标题是下划线**上面那整段**,不是只有紧挨着的那一行。
  const s = notesSummary("标题上半截\n标题下半截\n==========\n\n修了打开软件时全白的那个 bug");
  assert.match(s, /白屏|全白/,
    `多行标题只跳了最后一行,前半截被当正文印出来:「${s}」`);
});

test("u25 🔴 列表项紧贴 --- 时,第一条要点不许被当成标题吃掉", () => {
  // GitHub 把它渲染成"列表项 + 分隔线",不是标题 ——
  // 而这里会因为"下一行是 `---`"把业主最想看的那条要点吞掉。
  const s = notesSummary("- 修了打开软件时全白的那个 bug\n---\n\n其他零碎改动");
  assert.match(s, /白屏|全白/,
    `第一条要点被当成 setext 标题吃掉了:「${s}」`);
});

