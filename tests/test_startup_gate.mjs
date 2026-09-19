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
const { STARTUP_LOCAL_TIMEOUT_MS, STARTUP_LOCAL_ENDPOINT } = U;
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
