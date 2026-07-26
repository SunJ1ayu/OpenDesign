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

// ── 上游拒图时必须说人话(修复轮,track opendesign-chat-image)──────────────
// 病根:`applyEvent` 的 `case "error"` **只解锁 busy,什么都不显示**
// (transcript.ts:139-142)。而 nanobot 拒图时是发 `error` 事件 +
// `detail:"image_rejected"` + `reason∈{too_many_images,too_many_videos,mime,size,
// decode,malformed}`(实读 nanobot/channels/websocket.py:596-640,724-740)。
// 于是用户看到的是:自己的气泡在屏上、没有回复、没有解释 —— **这才是真正的
// "消息静默消失"**(不是限额抄错,而是上游好好说了我们没转达)。
import { chatErrorMsg } from "../web/src/chat/media.ts";

test("m19 image_rejected 的每个 reason 都翻成人话(不是裸码)", () => {
  for (const reason of ["too_many_images", "too_many_videos", "mime", "size",
                        "decode", "malformed"]) {
    const s = chatErrorMsg({ event: "error", detail: "image_rejected", reason });
    assert.equal(typeof s, "string");
    assert.ok(s.length >= 6, `太短:${s}`);
    assert.ok(/[一-龥]/.test(s), `必须是中文人话:${s}`);
    assert.ok(!s.includes(reason), `不许把裸 reason 怼给用户:${s}`);
  }
});

test("m20 尺寸/张数被拒时,提示要指出是图的问题(用户才知道去删图重发)", () => {
  assert.match(chatErrorMsg({ event: "error", detail: "image_rejected", reason: "size" }), /图/);
  assert.match(
    chatErrorMsg({ event: "error", detail: "image_rejected", reason: "too_many_images" }), /图/);
});

test("m21 未知 reason 也要给话(协议会长,不认识的不能变成空白)", () => {
  const s = chatErrorMsg({ event: "error", detail: "image_rejected", reason: "brand_new" });
  assert.ok(/[一-龥]/.test(s) && s.length >= 6, s);
});

test("m22 missing content 这类非图错误照样转达", () => {
  const s = chatErrorMsg({ event: "error", detail: "missing content" });
  assert.ok(/[一-龥]/.test(s) && s.length >= 4, s);
});

test("m23 不是 error 事件 → null(调用方据此不显示任何东西)", () => {
  assert.equal(chatErrorMsg({ event: "turn_end" }), null);
  assert.equal(chatErrorMsg({ event: "delta", text: "x" }), null);
  assert.equal(chatErrorMsg(null), null);
  assert.equal(chatErrorMsg("error"), null);
});

// ── 修复轮 ②:前端闸的单位必须与上游闸的单位对齐 ────────────────────────────
// subkimi 的最强一条:前端按**扩展名**判类型,而 nanobot 判的是 **data URL 里的 mime**
// (`_extract_data_url_mime` → `_UPLOAD_MIME_ALLOWED`,实读 websocket.py:614-621)。
// 两者会分叉:某些环境下 `File.type` 是空的 → data URL 变成 `data:;base64,…` →
// 上游 mime 认不出 → `_abort("decode")` → **整条消息被拒**。扩展名再对也没用。
// ⇒ 判据锁"发出去之前先看 data URL 的 mime",而不是只看名字。
import { isSendableDataUrl } from "../web/src/chat/media.ts";

test("m24 data URL 的 mime 必须在上游白名单内(与 nanobot 同一判据)", () => {
  assert.equal(isSendableDataUrl("data:image/png;base64,YWJj"), true);
  assert.equal(isSendableDataUrl("data:image/jpeg;base64,YWJj"), true);
  assert.equal(isSendableDataUrl("data:image/webp;base64,YWJj"), true);
  assert.equal(isSendableDataUrl("data:image/gif;base64,YWJj"), true);
});

test("m25 mime 缺失(File.type 为空)→ 拒。名字对也不行,上游按 mime 判", () => {
  assert.equal(isSendableDataUrl("data:;base64,YWJj"), false);
  assert.equal(isSendableDataUrl("data:base64,YWJj"), false);
});

test("m26 svg / bmp / 视频 mime → 拒(白名单之外)", () => {
  for (const u of ["data:image/svg+xml;base64,YWJj", "data:image/bmp;base64,YWJj",
                   "data:video/mp4;base64,YWJj", "data:application/pdf;base64,YWJj"]) {
    assert.equal(isSendableDataUrl(u), false, u);
  }
});

test("m27 mime 大小写不敏感(浏览器一般给小写,但别赌)", () => {
  assert.equal(isSendableDataUrl("data:IMAGE/PNG;base64,YWJj"), true);
});

// ── 修复轮 ③:上传报"没有收件箱"时,要告诉人按钮在哪 ──────────────────────
// 0.49.0 加了「帮我建收件箱」按钮,但真正撞上 inbox_not_found 的地方(图墙拖拽、
// 气泡存图)的提示仍是"先建一个" —— 等于让人自己去 F 盘建文件夹,而按钮就在旁边。
import { uploadErrMsg } from "../web/src/api.ts";

test("m28 inbox_not_found 的提示要指向那个按钮,不是让人自己去建", () => {
  const s = uploadErrMsg("inbox_not_found");
  assert.match(s, /帮我建收件箱/);
});
