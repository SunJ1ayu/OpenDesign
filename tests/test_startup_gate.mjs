// track opendesign-startup-not-blocked-by-update oracle:打开软件那一刻等什么。
// 主 agent 亲写。跑法:node --test tests/test_startup_gate.mjs
//
// 由来(业主 2026-09-19):「现在每次打开都会弹出正在检测更新,这严重拖慢了我们开软件的速度」。
// 后端实测最坏 20.1 秒(收据在 track 的 evidence/),而前端把整个工作区挡在那后面。
//
// 🔴 **本卷防的头号作弊:把 35000 改小就宣称修好了。**
//    那仍然是在启动路径上联网 —— 网一慢照样等,只是等得短一点。
//    sg1 钉上限、sg5 钉"启动只许问本地那一个接口",两条一起才拦得住。
import { test } from "node:test";
import assert from "node:assert/strict";
// 🔴 用命名空间导入,不用具名导入:ESM 的具名导入在导出不存在时**整份文件编译期就崩**,
//    只报 1 个 fail —— 而判据先行唯一要证明的就是"哪几条会咬"。逐条红才数得出来。
import * as U from "../web/src/update.ts";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const SRC = (f) => readFileSync(join(dirname(fileURLToPath(import.meta.url)), "..", "web", "src", f), "utf-8");
const { STARTUP_LOCAL_TIMEOUT_MS, STARTUP_LOCAL_ENDPOINT, STARTUP_PREPARE_ENDPOINT } = U;
const startupAction = (...a) => {
  if (typeof U.startupAction !== "function") {
    throw new Error("update.ts 还没有导出 startupAction —— 判据先行,此刻应当红");
  }
  return U.startupAction(...a);
};

test("sg1 启动只等本地读,上限必须是几百毫秒量级,不是几十秒", () => {
  assert.ok(STARTUP_LOCAL_TIMEOUT_MS <= 1000,
    `启动等待上限 ${STARTUP_LOCAL_TIMEOUT_MS}ms 太长 —— 这是本地读盘,不是联网`);
  assert.ok(STARTUP_LOCAL_TIMEOUT_MS > 0);
});

test("sg2 后端说该装,才进更新界面", () => {
  assert.equal(startupAction({ action: "install", reason: "ready", version: "0.98.8" }), "install");
});

test("sg3 后端说进工作区 ⇒ 进工作区", () => {
  for (const reason of ["no_state", "not_ready", "package_missing", "digest_mismatch", "not_newer"]) {
    assert.equal(startupAction({ action: "enter", reason }), "enter", reason);
  }
});

test("sg4 🔴 任何读不懂的回应都必须进工作区,绝不许卡住", () => {
  // 后端没起来、超时、返回垃圾、字段缺失 —— 一律进工作区。
  // 本项目四次"打不开"的前科都是这一类:某个前置步骤没按预期返回,界面就再也不往下走。
  for (const junk of [null, undefined, {}, [], "install", 42, true,
                      { action: "INSTALL" }, { action: "" }, { action: null },
                      { reason: "ready" }, { action: ["install"] }]) {
    assert.equal(startupAction(junk), "enter", JSON.stringify(junk));
  }
});

test("sg5 启动问的必须是本地那个只读接口,不是查更新", () => {
  // 钉死端点本身:把它改回 /api/update/check 就等于把联网搬回启动路径。
  assert.equal(STARTUP_LOCAL_ENDPOINT, "/api/update/startup");
  assert.ok(!STARTUP_LOCAL_ENDPOINT.includes("check"),
    "启动路径不许问查更新接口 —— 那会重新引入 20 秒干等");
});

test("sg6 startupAction 永远不抛", () => {
  const nasty = { get action() { throw new Error("getter 炸了"); } };
  assert.doesNotThrow(() => startupAction(nasty));
  assert.equal(startupAction(nasty), "enter");
});

test("sg7 后台备货的端点和启动那个必须是两个,别混成一个", () => {
  // 混成一个就等于把"下 46MB"搬回启动路径 —— 比原来的 20 秒还糟。
  assert.equal(STARTUP_PREPARE_ENDPOINT, "/api/update/prepare");
  assert.notEqual(STARTUP_PREPARE_ENDPOINT, STARTUP_LOCAL_ENDPOINT);
});

test("sg8 启动回包里的版本号要能读出来,读不出一律 null", () => {
  // 为什么需要它:启动路径上**不查更新**,所以 updateInfo 是 null ——
  // "正在更新到 0.99.0" 这句话的版本只能来自启动回包本身(后端 startup_decision 带了 version)。
  // 读不出来就显示"新版本",绝不许因此抛或者卡住。
  const startupVersion = (...a) => {
    if (typeof U.startupVersion !== "function") {
      throw new Error("update.ts 还没有导出 startupVersion —— 判据先行,此刻应当红");
    }
    return U.startupVersion(...a);
  };
  assert.equal(startupVersion({ action: "install", reason: "ready", version: "0.99.0" }), "0.99.0");
  // 不是在装的,就没有"正在更新到"这回事
  assert.equal(startupVersion({ action: "enter", reason: "no_state", version: "0.99.0" }), null);
  for (const junk of [null, undefined, {}, [], 42, true, "0.99.0",
                      { action: "install" }, { action: "install", version: 42 },
                      { action: "install", version: "" }]) {
    assert.equal(startupVersion(junk), null, String(JSON.stringify(junk)));
  }
  assert.doesNotThrow(() => startupVersion({ action: "install", get version() { throw new Error("炸"); } }));
  assert.equal(startupVersion({ action: "install", get version() { throw new Error("炸"); } }), null);
});

test("sg9 首次后台查更新的等待时间:一个数,一个地方,而且真有人用它", () => {
  // 🔴 由来(2026-09-20 自审):这个数原来在 App.tsx 里硬写一份(60_000),
  //    后端 ds_update_startup 里还有一份 FIRST_CHECK_DELAY_S=60,**两份都没有对方**,
  //    而后端那份根本没有调用方。同一个数两处各写一份,这个项目已经栽过
  //    (写侧五处把变更号拼进正则、读侧按数认)。
  const ms = U.BACKGROUND_FIRST_CHECK_MS;
  assert.equal(typeof ms, "number", "update.ts 还没导出 BACKGROUND_FIRST_CHECK_MS —— 判据先行,此刻应当红");
  assert.ok(ms >= 5000, `首次后台查更新只等了 ${ms}ms —— 那等于换个地方接着抢启动资源`);
  assert.ok(ms <= 10 * 60 * 1000, "等太久 ⇒ 短会话永远备不上货");
  // 不许在 App.tsx 里再写一份
  assert.ok(!/const\s+BACKGROUND_FIRST_CHECK_MS\s*=/.test(SRC("App.tsx")),
    "App.tsx 又自己写了一份 —— 两份迟早对不上");
});

test("sg10 启动界面不许声称自己在查更新", () => {
  // 业主原话:「不应该让用户看到这个界面才对啊,应该是有更新才显示和进度条」。
  // 启动路径已经不查更新了(只读一次本地盘),那句「正在检查更新…」既是谎话,
  // 又正好是他指着说不想看见的那块东西。读盘那 0~500ms 只许是一块没有断言的启动画面。
  // 🔴 只看**去掉注释之后**的源码:问的是"界面会不会这么说",
  //    不是"文件里有没有这几个字"。第一版没剥注释,连我解释「为什么删掉它」的那句
  //    说明也算成了界面文案 —— 那种判据会逼人把话说不清楚。
  const code = SRC("App.tsx")
    .replace(/\/\*[\s\S]*?\*\//g, "")     // 块注释(含 JSX 里的 {/* … */})
    .replace(/^\s*\/\/.*$/gm, "");          // 行注释
  assert.ok(!code.includes("正在检查更新"),
    "启动界面还写着「正在检查更新…」—— 启动根本不查更新了");
});
