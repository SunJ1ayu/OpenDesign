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
import { updateLabel, releasePageUrl } from "../web/src/update.ts";

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

test("u6 发布页地址指向本仓那一版的 tag,且是 https", () => {
  const u = releasePageUrl("0.98.3");
  assert.ok(u.startsWith("https://"), u);
  assert.match(u, /SunJ1ayu\/OpenDesign/, u);
  assert.match(u, /win-installer-0\.98\.3$/, `tag 拼错了:${u}`);
});

test("u7 版本号缺失时不许拼出一个坏地址", () => {
  assert.equal(releasePageUrl(null), null);
  assert.equal(releasePageUrl(""), null);
});
