// track opendesign-cockpit oracle:驾驶舱纯逻辑(项目图排序/类目行/相对时间/状态机)。
// 跑法:node --test tests/test_cockpit.mjs(Node 22+,原生 strip-types)
//
// red-check(commit message 附结果):
//   projectImages 排序去掉 tie-break → test_images_tie 变红
//   categoryRows 的 capped 分支删掉 → test_rows_capped 变红
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  projectImages,
  relTimeFromEpoch,
  categoryRows,
  filesState,
} from "../web/src/workspace/cockpit.ts";

const mappedImages = (images) => ({ configured: true, mapped: true, images });
const mappedOverview = (categories) =>
  ({ configured: true, mapped: true, categories, recent: [] });

// ---- projectImages -------------------------------------------------------

test("projectImages:mtime 降序,同刻按 rel 名序", () => {
  const got = projectImages(mappedImages([
    { rel: "b/2.jpg", category: "渲染输出", mtime: 100 },
    { rel: "a/1.jpg", category: "01-资料", mtime: 200 },
    { rel: "a/0.jpg", category: "01-资料", mtime: 100 },
  ]));
  assert.deepEqual(got.map((i) => i.rel), ["a/1.jpg", "a/0.jpg", "b/2.jpg"]);
});

test("projectImages:降级态与 null 全部空数组", () => {
  assert.deepEqual(projectImages(null), []);
  assert.deepEqual(projectImages({ configured: false }), []);
  assert.deepEqual(projectImages({ configured: true, mapped: false }), []);
});

test("projectImages:不改原数组(纯函数)", () => {
  const raw = [
    { rel: "b.jpg", category: "", mtime: 1 },
    { rel: "a.jpg", category: "", mtime: 2 },
  ];
  projectImages(mappedImages(raw));
  assert.equal(raw[0].rel, "b.jpg");
});

// ---- relTimeFromEpoch ------------------------------------------------------

test("relTimeFromEpoch:今天/昨天/M-DD/空值", () => {
  const now = Math.floor(Date.now() / 1000);
  assert.equal(relTimeFromEpoch(now), "今天");
  assert.equal(relTimeFromEpoch(now - 86400), "昨天");
  const old = new Date("2020-03-05T12:00:00");
  assert.equal(relTimeFromEpoch(Math.floor(old.getTime() / 1000)), "3-05");
  assert.equal(relTimeFromEpoch(0), "");
  assert.equal(relTimeFromEpoch(null), "");
  assert.equal(relTimeFromEpoch(undefined), "");
});

// ---- categoryRows ----------------------------------------------------------

test("categoryRows:非模板类目名全链路可见(照现状认的判卷用例)", () => {
  const rows = categoryRows(mappedOverview([
    { name: "渲染输出", count: 3, capped: false, latest_mtime: Math.floor(Date.now() / 1000) },
  ]));
  assert.equal(rows.length, 1);
  assert.equal(rows[0].label, "渲染输出");
  assert.equal(rows[0].countLabel, "3");
  assert.equal(rows[0].activity, "今天");
});

test("categoryRows:capped 显示 N+ 且活跃度留空(宁缺勿假)", () => {
  const rows = categoryRows(mappedOverview([
    { name: "05-3DMAX", count: 2000, capped: true, latest_mtime: null },
  ]));
  assert.equal(rows[0].countLabel, "2000+");
  assert.equal(rows[0].activity, "");
});

test("categoryRows:散文件类目空名 → 未分类;服务端名序原样保留", () => {
  const rows = categoryRows(mappedOverview([
    { name: "", count: 1, capped: false, latest_mtime: null },
    { name: "01-资料", count: 2, capped: false, latest_mtime: null },
  ]));
  assert.deepEqual(rows.map((r) => r.label), ["未分类", "01-资料"]);
  assert.equal(rows[0].activity, "");  // latest_mtime null → 不显示
});

test("categoryRows:降级态与 null 全部空数组", () => {
  assert.deepEqual(categoryRows(null), []);
  assert.deepEqual(categoryRows({ configured: false }), []);
});

// ---- filesState ------------------------------------------------------------

test("filesState:四态状态机", () => {
  assert.equal(filesState(null), "loading");
  assert.equal(filesState({ configured: false }), "unconfigured");
  assert.equal(filesState({ configured: true, mapped: false }), "unmapped");
  assert.equal(filesState(mappedOverview([])), "ok");
});
