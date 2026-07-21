// track opendesign-stage-history oracle:变更修改历史(#9)的纯逻辑层
// + 图墙条目对参考图 id/备注的透传(#8 编辑区的数据来源)。
//
// 跑法:node --test tests/test_change_history.mjs
//
// 契约(design.md §9):后端 `/api/changes` 每条变更**已经**返回
// `history: [{date, old}]`(时序=后端顺序,前端不重排)与可选 `note`;
// 本层只把它们变成可渲染的字符串,零 DOM、零 fetch。
//
// red-check:`web/src/workspace/history.ts` 尚不存在 → import 失败,整份红。

import test from "node:test";
import assert from "node:assert/strict";

import {
  historySummary,
  formatHistoryEntry,
  historyEntries,
} from "../web/src/workspace/history.ts";
import { buildGallery } from "../web/src/gallery.ts";

const change = (over = {}) => ({
  cnum: 3,
  status: "待确认",
  text: "主卧灯位右移",
  date: "2026-07-01",
  space: null,
  source: null,
  history: [],
  ...over,
});

// ── historySummary:折叠态那一行的文案 ──────────────────────────────────────
test("无历史 → 空串(调用方据此不渲染入口)", () => {
  assert.equal(historySummary(change()), "");
  assert.equal(historySummary(change({ history: undefined })), "");
});

test("有历史 → 改过 N 次", () => {
  assert.equal(historySummary(change({ history: [{ date: "2026-07-02", old: "旧" }] })),
    "改过 1 次");
  assert.equal(
    historySummary(change({
      history: [
        { date: "2026-07-02", old: "旧一" },
        { date: "2026-07-03", old: "旧二" },
      ],
    })),
    "改过 2 次",
  );
});

test("history 字段不是数组时不炸(后端异常/老缓存)", () => {
  assert.equal(historySummary(change({ history: null })), "");
  assert.equal(historySummary(change({ history: "2" })), "");
  assert.equal(historySummary(change({ history: {} })), "");
});

// ── historyEntries:取出可渲染列表,顺序=后端给的时序 ────────────────────────
test("条目顺序原样保留(时序是后端的事,前端不重排)", () => {
  const c = change({
    history: [
      { date: "2026-07-03", old: "第二版" },
      { date: "2026-07-02", old: "第一版" },
    ],
  });
  assert.deepEqual(historyEntries(c).map((e) => e.old), ["第二版", "第一版"]);
});

test("非数组/空 → 空数组(渲染层可以无脑 .map)", () => {
  assert.deepEqual(historyEntries(change()), []);
  assert.deepEqual(historyEntries(change({ history: null })), []);
  assert.deepEqual(historyEntries(change({ history: [1, "x", null] })), [],
    "结构不对的条目直接丢,不渲染半条");
});

test("缺 old 的条目丢掉,缺 date 的保留(日期是附加信息,原文才是主体)", () => {
  const c = change({
    history: [{ date: "2026-07-02" }, { old: "没日期但有原文" }],
  });
  assert.deepEqual(historyEntries(c), [{ date: null, old: "没日期但有原文" }]);
});

// ── formatHistoryEntry:单条的展示文本 ──────────────────────────────────────
test("日期走中文短格式 + 原文前缀", () => {
  assert.equal(formatHistoryEntry({ date: "2026-07-02", old: "灯位左移" }),
    "7月2日 原:灯位左移");
});

test("无日期 → 只出原文,不留空格头", () => {
  assert.equal(formatHistoryEntry({ date: null, old: "灯位左移" }), "原:灯位左移");
});

test("坏日期原样透出(与 cnDate 同口径,不猜不补)", () => {
  assert.equal(formatHistoryEntry({ date: "07/02", old: "x" }), "07/02 原:x");
});

test("原文里的换行不参与渲染(索引层已消毒,这里只做兜底)", () => {
  const s = formatHistoryEntry({ date: "2026-07-02", old: "上\n下" });
  assert.ok(!s.includes("\n"), `不该带换行:${JSON.stringify(s)}`);
});

// ── gallery 透传:#8 的编辑区靠这两个字段找到索引条目 ────────────────────────
const ref = (over = {}) => ({
  id: "r1",
  style: ["奶油风"],
  space: ["客厅"],
  file: "refs/奶油风/客厅/a.jpg",
  note: "弧形吊顶",
  ...over,
});

test("refs 条目透传 refId 与 note(编辑区据此定位/回填)", () => {
  const [item] = buildGallery("翡翠湾-1801", [ref()], []);
  assert.equal(item.refId, "r1");
  assert.equal(item.note, "弧形吊顶");
  assert.equal(item.id, "ref:r1", "稳定 key 不变");
});

test("空备注透传成空串,不变成 undefined(编辑区要区分'没备注'与'不可编辑')", () => {
  const [item] = buildGallery("翡翠湾-1801", [ref({ note: "" })], []);
  assert.equal(item.note, "");
  assert.equal(item.refId, "r1");
});

test("工作区图没有 refId —— 它不在索引里,不给编辑入口", () => {
  const [item] = buildGallery(
    "翡翠湾-1801",
    [],
    [{ rel: "06-效果图/客厅.png", category: "06-效果图", mtime: 1 }],
  );
  assert.equal(item.refId, undefined);
  assert.equal(item.style.length, 0);
});

test("既有形状不回归:标签/分组/顺序照旧", () => {
  const items = buildGallery(
    "翡翠湾-1801",
    [ref()],
    [{ rel: "06-效果图/客厅.png", category: "06-效果图", mtime: 1 }],
  );
  assert.equal(items.length, 2);
  assert.equal(items[0].group, "参考图库");
  assert.equal(items[0].label, "弧形吊顶");
  assert.equal(items[1].group, "06-效果图");
});
