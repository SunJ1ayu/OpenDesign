// track opendesign-chat-image 的 oracle(二)—— 聊天发图的纯逻辑层。
// 主 agent 亲写,executor off-limits。
// 跑法:node --test tests/test_chat_media.mjs
//
// 依据 = docs/nanobot-ws-protocol.md §2 `media` 一节(2026-07-26 补记,源码实抄):
//   media: [{data_url:"data:<mime>;base64,…", name?:string}]
//   服务端限额:≤4 图/条、单图 8MB、png/jpeg/webp/gif、**svg 排除**;
//   **任一项不合规 → 整条消息不发布**。
// ⇒ 所以前端必须自己先拦。拦不住的代价不是"报个错",是**用户的消息凭空消失**。
//
// 本文件只断纯逻辑。断言全绿仍可能丑到不能用(缩略图错位/输入卡被顶飞),
// 那一层由 e2e 的真截图接(见 design.md §oracle「能被什么骗过」)。
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  MAX_CHAT_IMAGES,
  MAX_CHAT_IMAGE_BYTES,
  pickChatImages,
  dataUrlBytes,
} from "../web/src/chat/media.ts";
import { messageEnvelope } from "../web/src/chat/transcript.ts";

const f = (name, size = 1024) => ({ name, size });

// ---- 限额常量必须与协议同档(抄错 = 消息静默不发布)--------------------
test("m01 限额常量 = 协议限额(4 张 / 8MB)", () => {
  assert.equal(MAX_CHAT_IMAGES, 4);
  assert.equal(MAX_CHAT_IMAGE_BYTES, 8 * 1024 * 1024);
});

// ---- 类型闸 -----------------------------------------------------------
test("m02 svg 被拒(协议显式排除:内嵌脚本 XSS 面)", () => {
  const r = pickChatImages([f("图标.svg")]);
  assert.equal(r.accepted.length, 0);
  assert.equal(r.rejected.length, 1);
  assert.equal(r.rejected[0].name, "图标.svg");
});

test("m03 图纸/文档类被拒(dwg/pdf/dxf 不是聊天发图的活)", () => {
  const r = pickChatImages([f("平面.dwg"), f("课件.pdf"), f("轴线.dxf")]);
  assert.equal(r.accepted.length, 0);
  assert.equal(r.rejected.length, 3);
});

test("m04 扩展名大小写不敏感(相机出图常是 .JPG)", () => {
  const r = pickChatImages([f("DSC_0001.JPG"), f("客厅.PNG"), f("动图.GIF")]);
  assert.equal(r.accepted.length, 3, JSON.stringify(r.rejected));
  assert.equal(r.rejected.length, 0);
});

test("m05 四种合规扩展名全放行,且顺序与入参一致", () => {
  const input = [f("a.png"), f("b.jpg"), f("c.jpeg"), f("d.webp"), f("e.gif")];
  const r = pickChatImages(input.slice(0, 4));
  assert.deepEqual(r.accepted.map((x) => x.name), ["a.png", "b.jpg", "c.jpeg", "d.webp"]);
});

// ---- 体积闸 -----------------------------------------------------------
test("m06 单张超 8MB 被丢下(不静默截断)", () => {
  const r = pickChatImages([f("小.png", 1024), f("单反原图.jpg", 9 * 1024 * 1024)]);
  assert.deepEqual(r.accepted.map((x) => x.name), ["小.png"]);
  assert.equal(r.rejected.length, 1);
  assert.equal(r.rejected[0].name, "单反原图.jpg");
});

test("m07 正好 8MB 放行(闸是 ≤ 不是 <)", () => {
  const r = pickChatImages([f("刚好.png", MAX_CHAT_IMAGE_BYTES)]);
  assert.equal(r.accepted.length, 1);
});

test("m08 0 字节被拒(拖到半截/空文件)", () => {
  const r = pickChatImages([f("空.png", 0)]);
  assert.equal(r.accepted.length, 0);
  assert.equal(r.rejected.length, 1);
});

// ---- 条数闸 -----------------------------------------------------------
test("m09 第 5 张起被丢下,且**明确告知**(不是静默截断)", () => {
  const r = pickChatImages([f("1.png"), f("2.png"), f("3.png"), f("4.png"), f("5.png")]);
  assert.equal(r.accepted.length, 4);
  assert.deepEqual(r.rejected.map((x) => x.name), ["5.png"]);
});

test("m10 已有 n 张时追加,名额按已有的算(拖两次不能突破 4 张)", () => {
  const r = pickChatImages([f("3.png"), f("4.png"), f("5.png")], 2);
  assert.deepEqual(r.accepted.map((x) => x.name), ["3.png", "4.png"]);
  assert.deepEqual(r.rejected.map((x) => x.name), ["5.png"]);
});

test("m11 名额已满 → 全拒,accepted 为空且不抛", () => {
  const r = pickChatImages([f("x.png")], MAX_CHAT_IMAGES);
  assert.equal(r.accepted.length, 0);
  assert.equal(r.rejected.length, 1);
});

// ---- 被拒理由必须是人话 ------------------------------------------------
test("m12 每条拒绝理由都是人话(不把裸错误码怼给设计师)", () => {
  const r = pickChatImages(
    [f("图标.svg"), f("大.png", 9 * 1024 * 1024), f("1.png"), f("2.png"),
     f("3.png"), f("4.png"), f("5.png")],
  );
  assert.ok(r.rejected.length >= 3);
  for (const x of r.rejected) {
    assert.equal(typeof x.why, "string");
    assert.ok(x.why.length >= 4, `理由太短:${x.why}`);
    assert.ok(/[一-龥]/.test(x.why), `理由必须是中文人话:${x.why}`);
    assert.ok(!/^[a-z_]+$/.test(x.why), `不许直接给错误码:${x.why}`);
  }
});

// ---- data URL 字节数(真实体积,不靠 File.size 猜)----------------------
test("m13 dataUrlBytes:base64 解码后的真实字节数(含 padding 两种)", () => {
  // "abc" → YWJj(无 padding,3 字节);"ab" → YWI=(1 个 =,2 字节)
  assert.equal(dataUrlBytes("data:image/png;base64,YWJj"), 3);
  assert.equal(dataUrlBytes("data:image/png;base64,YWI="), 2);
  assert.equal(dataUrlBytes("data:image/png;base64,YQ=="), 1);
});

test("m14 dataUrlBytes:不是 data URL / 不是 base64 → -1(调用方据此拒,不当 0 放行)", () => {
  for (const bad of ["", "http://x/y.png", "data:image/png,notbase64", "data:;base64,"]) {
    assert.equal(dataUrlBytes(bad), -1, `应判非法:${bad}`);
  }
});

// ---- 出站信封:老形状逐字节不变 ----------------------------------------
test("m15 不带图 → 信封里**不出现** media 键(老形状一字不改)", () => {
  const env = messageEnvelope("chat-1", "你好", "turn-1");
  assert.deepEqual(env, {
    type: "message",
    chat_id: "chat-1",
    content: "你好",
    webui: true,
    turn_id: "turn-1",
  });
  assert.ok(!("media" in env));
});

test("m16 传空数组 → 也不出现 media 键(空 media 不发)", () => {
  const env = messageEnvelope("chat-1", "你好", "turn-1", []);
  assert.ok(!("media" in env));
});

test("m17 带图 → media 形状照协议:[{data_url, name}]", () => {
  const media = [
    { data_url: "data:image/png;base64,YWJj", name: "客厅.png" },
    { data_url: "data:image/jpeg;base64,YWJj", name: "主卧.jpg" },
  ];
  const env = messageEnvelope("chat-1", "看这两张", "turn-1", media);
  assert.deepEqual(env, {
    type: "message",
    chat_id: "chat-1",
    content: "看这两张",
    webui: true,
    turn_id: "turn-1",
    media,
  });
});

test("m18 带图但没文字 → content 仍是字符串(空串,不是 undefined/null)", () => {
  const env = messageEnvelope("chat-1", "", "turn-1",
    [{ data_url: "data:image/png;base64,YWJj", name: "a.png" }]);
  assert.equal(typeof env.content, "string");
  assert.equal(env.content, "");
});
