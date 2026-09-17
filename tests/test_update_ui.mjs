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

test("u26 🔴 文首那行是两字符的 == / -- 时,不许把它印给业主", () => {
  // 变异 m4 逼出来的:原来有一句「上面没段落就放过」的豁免,我给它写的理由是假的
  // (`---` 本来就被分隔线规则接住),而它真正的作用是**让两字符的下划线漏进正文**。
  // 删掉豁免之后这条才绿 —— 它钉的是"别把那个豁免加回来"。
  for (const mark of ["==", "--"]) {
    const s = notesSummary(`${mark}\n\n修了打开软件时全白的那个 bug`);
    assert.doesNotMatch(s, /^[-=*_\s]+$/, `把「${mark}」印出来了:「${s}」`);
    assert.match(s, /白屏|全白/, `没往下找到正文:「${s}」`);
  }
});

// ─────────────────────────────────────────────────────────────────────────
// 第二刀「真去装」的界面那一半(track opendesign-in-app-update-install)。
//
// 🔴 这一批治的还是同一种病:**把失败说成成功**。
//    第一刀那条纪律(u3:查更新失败绝不许显示"已是最新")在这里的对应物是
//    **更新失败绝不许显示"更新已开始"** —— 而这一版的后果比第一刀重得多:
//    业主看到"更新已开始"就会关掉浏览器等着,而实际上软件根本不会关,
//    过一会儿接力脚本超时把新版删掉 —— 43MB 白下,他还不知道为什么。
//
// 用命名空间导入:实现还没落地时,**只让这一批红**,别把上面那 26 条一起拖红
// (整份 import 挂掉的话,红就埋在别处了,等于没红检过)。
import * as U from "../web/src/update.ts";

const WITH_ASSET = {
  current: "0.98.4", update_available: true, latest: "0.98.5",
  asset: { name: "OpenDesign-Setup-0.98.5.exe", url: "https://x/y", size: 1, digest: "sha256:aa" },
  notes: "", error: null, release_url: "https://github.com/x/releases/tag/win-installer-0.98.5",
};
const NO_ASSET = { ...WITH_ASSET, asset: null };
const NONE = { current: "0.98.5", update_available: false, latest: "0.98.5", asset: null, notes: "", error: null };

// 端点会回的全部 stage(bin/ds_web.py 的 _update_apply)。
const FAIL_STAGES = ["no_update", "digest", "download", "verify", "install",
                     "newtree", "handoff", "shell"];
// 业主不该在界面上看见的词。他不是程序员。
const JARGON = /sha256|stage|relay|NSIS|handoff|nonce|INSTDIR|\.new\b|traceback/i;

test("u27 没有新版就不出现「更新」按钮", () => {
  assert.equal(U.canApply(NONE), false, "已经是最新版,却给了一个「更新」按钮");
  assert.equal(U.canApply(null), false, "还没查过就给按钮");
});

test("u27b 有新版但没有安装包时也不给按钮", () => {
  // 点了必然失败的按钮比没有按钮更坏:他会以为是自己的机器有问题。
  assert.equal(U.canApply(NO_ASSET), false, "这一版没有安装包,按钮点了必然失败");
  assert.equal(U.canApply(WITH_ASSET), true, "有新版又有安装包,却不给更新的路");
});

test("u28 正在更新时那句话要说正在更新", () => {
  const s = U.applyLabel({ state: "applying", result: null });
  assert.match(s, /正在|更新中/, `「${s}」看不出正在做事`);
});

test("u29 🔴 失败必须有正向的失败语义,不许用成功同义词把他骗走", () => {
  // 攻题(2026-09-08,gpt-5.6-sol 只读腿)打穿了这条的第一版:
  // 我原来只禁了「已开始/开始更新/正在更新/成功」几个词,而
  //   "新版已就绪,请关闭浏览器等候"
  // 一个都不撞,业主照样关掉窗口干等。**黑名单只挡我想得到的那些词。**
  // ⇒ 改成正面要求:必须说出"失败/未能/取消",并禁掉几类误导句式。
  for (const stage of FAIL_STAGES.filter((x) => x !== "no_update")) {
    const s = U.applyLabel({ state: "done", result: { ok: false, stage, error: "x" } });
    assert.match(s, /失败|未能|没能|取消/, `stage=${stage} 没说清这是失败:「${s}」`);
    assert.doesNotMatch(s, /已开始|开始更新|正在更新|成功|已就绪|即将|马上|稍后/,
      `stage=${stage} 用成功同义词把他骗走了:「${s}」`);
    assert.doesNotMatch(s, /关闭.*等|等.*关闭/,
      `stage=${stage} 在叫他关掉软件等着:「${s}」`);
  }
});

test("u30 每个 stage 都要有业主看得懂、而且各不相同的话", () => {
  // 攻题打穿了第一版:我那份技术词黑名单(sha256/relay/nonce/…)漏掉了
  // digest / CDN / Authenticode / IPC / 退出码 / 目标树 —— 换个词就全绿。
  // ⇒ 不再靠黑名单穷举:①不许把**原始 stage 串和原始 error 串**漏出去;
  //   ②每个 stage 的话必须**互不相同**(一句万能话等于没解释);
  //   ③保留一份最小黑名单当兜底,但它不再是主要防线。
  const RAW_ERROR = "sha256 对不上:期望 aa,实得 bb";
  const seen = new Map();
  for (const stage of FAIL_STAGES) {
    const s = U.applyHint({ ok: false, stage, error: RAW_ERROR });
    assert.ok(s && s.length > 0, `stage=${stage} 没有给业主任何话`);
    assert.ok(!s.includes(stage), `stage=${stage} 把原始 stage 串印给了业主:「${s}」`);
    assert.ok(!s.includes(RAW_ERROR), `stage=${stage} 把原始报错原样甩给了业主:「${s}」`);
    assert.doesNotMatch(s, JARGON, `stage=${stage} 把技术词甩给了业主:「${s}」`);
    assert.doesNotMatch(s, /undefined|\[object/, `stage=${stage} 漏了占位:「${s}」`);
    if (seen.has(s)) {
      assert.fail(`stage=${stage} 和 ${seen.get(s)} 用了同一句话「${s}」——`
        + " 一句万能话等于没解释,他分不清是网络断了还是包被改过");
    }
    seen.set(s, stage);
  }
});

test("u30b 校验没过那一条必须说清是「为了安全没装」", () => {
  // 这是唯一一条"我们主动拒绝安装"的失败。不说清楚,业主会以为是网络问题反复重试;
  // 说清楚了,他才知道这是保护他(信任根只有 HTTPS+digest 一条,见 ds_update 模块头)。
  const s = U.applyHint({ ok: false, stage: "verify", error: "x" });
  assert.match(s, /安全|校验|不完整|被改/, `校验失败说得像普通错误:「${s}」`);
});

test("u31 🔴 成功那句:软件会自己关掉再打开,且不许说成「更新完成」", () => {
  // 攻题打穿两处:
  // ① 我原来只要求出现"关"或"重新打开" ⇒「请关闭浏览器」也能过,而那是在
  //    叫业主自己动手,他一关浏览器就什么都看不到了;
  // ② 🔴 **started 不等于更新完成** —— 端点只证明接力脚本起来了、外壳认了收摊,
  //    后面的改名和拉起仍可能失败。说"更新完成"是把没发生的事说成发生了。
  const s = U.applyLabel({ state: "done", result: { ok: true, stage: "started", latest: "0.98.5" } });
  assert.match(s, /(OpenDesign|软件|程序).{0,6}(会|将|自动)/, `没说是软件自己会动:「${s}」`);
  assert.match(s, /关/, `没说会关掉:「${s}」`);
  assert.match(s, /重(新)?(打开|启动)|自动打开/, `没说会重新打开:「${s}」`);
  assert.doesNotMatch(s, /更新完成|安装完成|已更新|已安装/,
    `started 只是「开始切换」,不是装好了:「${s}」`);
  assert.doesNotMatch(s, /请.{0,4}关闭/, `在叫业主自己关:「${s}」`);
});

test("u32 没见过的 stage 也要有兜底话术", () => {
  for (const stage of [null, undefined, "", "什么鬼", "started-ish"]) {
    const s = U.applyHint({ ok: false, stage, error: null });
    assert.ok(s && s.length > 0, `stage=${String(stage)} 什么都没说`);
    assert.doesNotMatch(s, /undefined|\[object/, `stage=${String(stage)}:「${s}」`);
    assert.match(s, /手动|自己下载|发布页/, `stage=${String(stage)} 没留出口:「${s}」`);
  }
});

test("u33 自动更新失败不许变成死路:出口必须是正向的、可执行的", () => {
  // 攻题打穿了第一版:我只要求出现"手动/发布页",于是
  //   "请勿手动处理,稍后再试"、"发布页也解决不了,请联系开发者"
  // 两句都能过 —— 一句在**禁止**他动手,一句直接告诉他没救。
  for (const stage of FAIL_STAGES.filter((x) => x !== "no_update")) {
    const s = U.applyHint({ ok: false, stage, error: "x" });
    assert.match(s, /(可以|请)(到|去|前往).{0,8}(发布页|下载)|手动(下载|安装)/,
      `stage=${stage} 没给一条他真能走的路:「${s}」`);
    assert.doesNotMatch(s, /请勿|不要|别去|也(解决不了|没用)|联系开发者/,
      `stage=${stage} 把唯一的出口堵死了:「${s}」`);
  }
});

test("u34 🔴 「会自动关掉」这句必须在**点下去那一刻**就说,不能等成功响应", () => {
  // 攻题第 11 条,最阴的一条:后端是**先起接力脚本、再请外壳收摊,然后才返回成功 JSON**。
  // 也就是说,那个 200 到达浏览器时,窗口可能已经在关了 ——
  // 把"软件会自己关掉"押在成功响应后的那一帧,业主很可能一眼都看不到,
  // 只看到窗口凭空消失。u31 只证明那句话写对了,证明不了它**上过屏**。
  const s = U.applyLabel({ state: "applying", result: null });
  assert.match(s, /正在|更新中/, `「${s}」看不出正在做事`);
  assert.match(s, /关/, `点下去那一刻没预告软件会关掉:「${s}」`);
  assert.doesNotMatch(s, /请.{0,4}关闭/, `在叫业主自己关:「${s}」`);
});

test("u35 canApply 对矛盾/残缺的数据要严,不许给一个注定失败的按钮", () => {
  // 攻题第 13 条:`!!(info.update_available && info.asset)` 正好通过 u27/u27b,
  // 但业主会拿到一个点了必然失败的按钮,然后以为是自己机器的问题。
  assert.equal(U.canApply({ ...WITH_ASSET, error: "查更新失败" }), false,
    "查更新本身就失败了,却给了更新按钮");
  assert.equal(U.canApply({ ...WITH_ASSET, asset: { name: "", url: "", size: 0, digest: null } }),
    false, "安装包信息是空的,却给了更新按钮");
  assert.equal(U.canApply({ ...WITH_ASSET, asset: { ...WITH_ASSET.asset, url: "" } }), false,
    "没有下载地址,却给了更新按钮");
  assert.equal(U.canApply({ ...WITH_ASSET, latest: null }), false,
    "不知道要更新到哪一版,却给了更新按钮");
});

test("u35b 🔴 canApply 永远不许抛 —— 它跑在渲染里,抛一次就是白屏", () => {
  // 闸③(2026-09-08 亲读 diff)抓到的,判据先行补上。**实测复现过,不是推论。**
  //
  // 后端 bin/ds_update.py 的 decide() 是 `asset.get("name")` /
  // `asset.get("browser_download_url")` —— 取不到就是 None,过 JSON 就是 **null**。
  // 而 `asset.name.trim()` 在 null 上抛 TypeError。
  // 🔴 canApply 在 Sidebar 的**渲染体**里被调用(`const showApply = canApply(updateInfo)`)
  //    ⇒ 抛一次 = React 卸掉整棵树 = **整页白**。
  //    这正是本项目栽得最狠的那个坑(0.94、0.98 两次白屏都是这个形状)。
  //
  // u35 只喂了"字段在、但是空串",喂不出这条路 —— **那是我考卷的洞,不是实现的锅**。
  const bads = [
    ["asset 是空对象", {}],
    ["name 是 null", { name: null, url: "u", size: 1, digest: "sha256:aa" }],
    ["url 是 null", { name: "n", url: null, size: 1, digest: "sha256:aa" }],
    ["缺 name 这个键", { url: "u", size: 1, digest: "sha256:aa" }],
    ["缺 url 这个键", { name: "n", size: 1, digest: "sha256:aa" }],
    ["name 不是字符串", { name: 1, url: "u", size: 1, digest: "sha256:aa" }],
    ["size 是 null", { name: "n", url: "u", size: null, digest: "sha256:aa" }],
  ];
  for (const [label, asset] of bads) {
    const info = { current: "0.98.4", update_available: true, latest: "0.98.5",
                   asset, notes: "", error: null };
    let out;
    try {
      out = U.canApply(info);
    } catch (e) {
      assert.fail(`${label}:canApply 抛了 ${e.constructor.name} —— 它跑在渲染里,`
        + "这一抛业主看到的是整页白,而不是「没有更新按钮」");
    }
    assert.equal(out, false, `${label}:安装包信息是坏的,却放行了更新按钮`);
  }
});

test("u35c 整个 info 是坏数据时也不许抛", () => {
  for (const info of [undefined, 0, "", [], { update_available: true }]) {
    try {
      U.canApply(info);
    } catch (e) {
      assert.fail(`canApply(${JSON.stringify(info)}) 抛了 ${e.constructor.name} ⇒ 白屏`);
    }
  }
});

test("u36 🔴 HTTP 200 + ok:false 不许被读成成功;坏 JSON/断网一律算失败", () => {
  // 攻题第 2、3 条。端点**任何业务失败都以 200 回**(那是 t9b 立的规矩,为了不让
  // 前端的通用错误路径弹东西给业主)⇒ 前端只看 HTTP 状态码就会把失败读成成功。
  assert.equal(U.readApplyResponse(200, { ok: false, stage: "verify", error: "x" }).ok, false,
    "200 + ok:false 被读成了成功");
  assert.equal(U.readApplyResponse(200, null).ok, false, "空响应被读成了成功");
  assert.equal(U.readApplyResponse(200, "不是 JSON").ok, false, "坏响应被读成了成功");
  assert.equal(U.readApplyResponse(200, { stage: "started" }).ok, false,
    "缺 ok 字段被读成了成功");
  assert.equal(U.readApplyResponse(500, { ok: true }).ok, false, "500 被读成了成功");
  assert.equal(U.readApplyResponse(0, null).ok, false, "断网被读成了成功");
  assert.equal(U.readApplyResponse(200, { ok: true, stage: "started" }).ok, true,
    "真的成功却被读成失败");
});

test("u37 点第二下不许再发一次请求", () => {
  // 攻题第 9 条:下载慢的时候业主会连点。两个更新流程并行 = 两份下载、两个接力脚本、
  // 两套改名互相打架。**真按钮的接线由闸③亲读 diff + Windows CI 的 e2e 把关**,
  // 这里钉的是它依赖的那个纯判断。
  assert.equal(U.beginApply("idle"), true, "第一下都不让点");
  assert.equal(U.beginApply("applying"), false, "正在更新时又发了一次请求");
});

// ── rl11:查不到的时候说清为什么(track opendesign-update-check-rate-limit)──────────────
// 🔴 由来:业主 09-15 夜点「检查更新」一直「查不到更新」,真原因(GitHub 未登录限流 403)只在接口的 error 字段里,
//    靠业主开 PowerShell 才拿到,来回三轮。界面上那一行下面要直接写出原因。
test("rl11a 查成了但线上说失败 ⇒ 原样给出 error(人话由后端写)", () => {
  const info = { ...NONE, update_available: false, latest: null,
                 error: "查更新失败:GitHub 限制了这个网络出口的查询次数(HTTP 403)" };
  assert.equal(U.updateReason({ state: "done", info }), info.error);
});

test("rl11b 查完了却什么都没拿到(软件后台不可达)⇒「软件后台没响应」", () => {
  assert.equal(U.updateReason({ state: "done", info: null }), "软件后台没响应");
});

test("rl11c 成功 / 检查中 / 还没查过 ⇒ 不显示原因", () => {
  assert.equal(U.updateReason({ state: "done", info: NONE }), "");
  assert.equal(U.updateReason({ state: "done", info: WITH_ASSET }), "");
  assert.equal(U.updateReason({ state: "checking", info: null }), "");
  assert.equal(U.updateReason({ state: "idle", info: null }), "");
});

// ── ac1~ac8:打开软件倒计时自动更新(track opendesign-auto-update-countdown)───────────────
// 主 agent 亲写。编号与问法的唯一权威在该 track 的 design.md。
// 🔴 这几个函数都会在渲染体里被叫 —— **永远不许抛**(0.94 / 0.98 两次整页白是同一个形状,u35b/u35c 同理)。
const AUTO_OK = { ...WITH_ASSET, auto_update: { eligible: true, why_not: null } };
const AUTO_TRIED = { ...WITH_ASSET, auto_update: { eligible: false, why_not: "attempted" } };
const GARBAGE = [null, undefined, "", "x", 0, 1, true, [], [AUTO_OK], {},
                 { ...WITH_ASSET, auto_update: null },
                 { ...WITH_ASSET, auto_update: "yes" },
                 { ...WITH_ASSET, auto_update: { eligible: "true", why_not: null } },
                 { ...WITH_ASSET, auto_update: { eligible: 1, why_not: null } }];

test("ac1 倒计时 10 秒(业主选的是「几秒」,定成 10 秒:看得清、来得及点取消)", () => {
  assert.equal(U.AUTO_UPDATE_SECONDS, 10);
});

test("ac2 可装 + 后端说 eligible 才倒计时;缺一样都不倒计时", () => {
  assert.equal(U.shouldCountdown(AUTO_OK), true, "装得了、后端也说可以,却不倒计时");
  assert.equal(U.shouldCountdown(AUTO_TRIED), false, "这个版本自动试过了,却又要倒计时 —— 正是业主怕的循环");
  assert.equal(U.shouldCountdown(WITH_ASSET), false, "后端没给 auto_update(老后端)也倒计时了");
  const noDigest = { ...AUTO_OK, asset: { ...AUTO_OK.asset, digest: null } };
  assert.equal(U.shouldCountdown(noDigest), false,
    "没有可信 sha256 的包也倒计时 —— 10 秒后必然报失败(界面不许只信后端一句 eligible)");
  assert.equal(U.shouldCountdown({ ...AUTO_OK, error: "查更新失败" }), false);
});

test("ac3 🔴 喂垃圾不抛,一律不倒计时", () => {
  for (const g of GARBAGE) {
    let r;
    assert.doesNotThrow(() => { r = U.shouldCountdown(g); }, `shouldCountdown(${JSON.stringify(g)}) 抛了 —— 渲染体里抛 = 整页白`);
    assert.equal(r, false, `shouldCountdown(${JSON.stringify(g)}) 居然是 ${r}`);
  }
});

test("ac4 倒计时那句话:哪一版、还剩几秒、要自动更新", () => {
  const s = U.countdownText("0.98.7", 7);
  assert.match(s, /0\.98\.7/, `「${s}」没说是哪一版`);
  assert.match(s, /(^|\D)7(\D|$)/, `「${s}」没说还剩几秒`);
  assert.match(s, /自动更新/, `「${s}」没说会自动更新 —— 业主不知道 10 秒后软件会自己关掉`);
  assert.doesNotMatch(s, JARGON);
});

test("ac5 不是失败、或者别处已在更新 ⇒ 横幅上什么都不说", () => {
  for (const r of [null, { ok: true, stage: "started", error: null },
                   { ok: false, stage: "auto_skipped", error: "attempted" },
                   { ok: false, stage: "busy", error: "更新已经在进行中,请稍候" },
                   { ok: false, stage: "no_update", error: "已经是最新版" }]) {
    assert.equal(U.autoFailureText(r), "", `${JSON.stringify(r)} 不该在横幅上报失败`);
  }
});

test("ac6 真失败 ⇒ 说人话(复用 applyHint 那句),并说明这个版本不会再自动更新", () => {
  const r = { ok: false, stage: "download", error: "HTTP 502" };
  const s = U.autoFailureText(r);
  assert.ok(s.includes(U.applyHint(r)), `「${s}」没带上那句失败原因「${U.applyHint(r)}」`);
  assert.match(s, /不会再自动/, `「${s}」没说以后不会再自动试 —— 业主会担心下次打开又来一遍`);
  assert.doesNotMatch(s, JARGON);
  for (const stage of FAIL_STAGES.filter((x) => x !== "no_update")) {
    const t = U.autoFailureText({ ok: false, stage, error: "x" });
    assert.notEqual(t, "", `${stage} 失败,横幅上却什么都没说`);
  }
});

test("ac7 记不下账 ⇒ 要说,但不许说「不会再自动」(它没记上,下次打开还会试)", () => {
  const s = U.autoFailureText({ ok: false, stage: "auto_unrecorded", error: "x" });
  assert.notEqual(s, "");
  assert.doesNotMatch(s, /不会再自动/, `「${s}」—— 这句是假的`);
  assert.doesNotMatch(s, JARGON);
});

test("ac8 设置里:这个版本自动试过没成 ⇒ 告诉业主可以手动点;其它情况不说,垃圾不抛", () => {
  const s = U.autoWhyNotHint(AUTO_TRIED);
  assert.notEqual(s, "", "自动试过没成,设置里一句解释都没有 —— 蓝点亮着却不再自动,业主不知道为什么");
  assert.match(s, /手动/);
  assert.doesNotMatch(s, JARGON);
  for (const why of ["no_update", "asset", "no_shell", "not_installed", "path_unsupported", "error", null]) {
    assert.equal(U.autoWhyNotHint({ ...WITH_ASSET, auto_update: { eligible: false, why_not: why } }), "", `why_not=${why}`);
  }
  assert.equal(U.autoWhyNotHint(AUTO_OK), "");
  assert.equal(U.autoWhyNotHint({ ...NONE, auto_update: { eligible: false, why_not: "attempted" } }), "",
    "没有新版(已经装上了)还说「自动更新没成」");
  for (const g of GARBAGE) {
    let r;
    assert.doesNotThrow(() => { r = U.autoWhyNotHint(g); }, `autoWhyNotHint(${JSON.stringify(g)}) 抛了`);
    assert.equal(r, "");
  }
});
