// track opendesign-intake oracle:收件箱卡片纯逻辑(状态机/建议标签/plan 预览行)。
// 跑法:node --test tests/test_intake_ui.mjs(Node 22+,原生 strip-types)
//
// red-check(commit message 附结果):
//   intakeState 的 pending 优先分支删掉 → state_pending 变红
//   planPreview 的 dstDir 取目录逻辑改成整路径 → preview_rows 变红
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  intakeState,
  entrySuggestion,
  planPreview,
} from "../web/src/workspace/intake.ts";

const okData = (entries, pending, extra = {}) => ({
  configured: true, inbox: "00-收件箱", truncated: false,
  entries, pending, ...extra,
});

// ---- intakeState ---------------------------------------------------------

test("state:loading / unconfigured / empty / ok / pending", () => {
  assert.equal(intakeState(null), "loading");
  assert.equal(intakeState({ configured: false, reason: "inbox_not_found",
                             entries: [], pending: [] }), "unconfigured");
  assert.equal(intakeState(okData([], [])), "empty");
  assert.equal(intakeState(okData([{ name: "a.jpg", type: "file", size: 1,
                                     mtime: 1, category: null, project: null }],
                                  [])), "ok");
  // 有待确认 plan 时,即使收件箱已空(文件还在箱里其实没动,但以防万一)也要亮卡
  assert.equal(intakeState(okData([], [{ plan_id: "p", created: "", ops: [] }])),
               "pending");
});

// ---- entrySuggestion -----------------------------------------------------

test("suggestion:类目+项目、仅类目、待认领三态", () => {
  assert.equal(
    entrySuggestion({ name: "x.jpg", type: "file", size: 1, mtime: 1,
                      category: { id: "参考图", scope: "workspace",
                                  dir: "03-共享资源/参考图库", mode: "auto" },
                      project: null }),
    "→ 参考图",
  );
  assert.equal(
    entrySuggestion({ name: "x.dwg", type: "file", size: 1, mtime: 1,
                      category: { id: "CAD", scope: "project",
                                  dir: "03-CAD", mode: "suggest" },
                      project: "20260612 周宁 龙腾世纪 12#1802" }),
    "→ 龙腾世纪 12#1802 · CAD",
  );
  assert.equal(
    entrySuggestion({ name: "x.xyz", type: "file", size: 1, mtime: 1,
                      category: null, project: null }),
    "待认领",
  );
  assert.equal(
    entrySuggestion({ name: "一批图", type: "dir", size: 0, mtime: 1,
                      category: null, project: null }),
    "文件夹 · 待认领",
  );
});

test("suggestion:项目名去掉日期/人名前缀(短标签)", () => {
  // `日期 地点 楼盘 楼栋#户号` → 显示 `楼盘 楼栋#户号`(前两段剥掉)
  assert.equal(
    entrySuggestion({ name: "x.dwg", type: "file", size: 1, mtime: 1,
                      category: { id: "CAD", scope: "project", dir: "03-CAD",
                                  mode: "suggest" },
                      project: "怪名字项目" }),
    "→ 怪名字项目 · CAD",  // 不足四段的名字原样显示,不硬剥
  );
});

// ---- planPreview ---------------------------------------------------------

test("preview_rows:src 取文件名,dst 取目录;多 plan 保序", () => {
  const got = planPreview([
    { plan_id: "20260717-1", created: "2026-07-17T10:00:00",
      ops: [
        { op: "move", src_rel: "00-收件箱/参考.jpg",
          dst_rel: "03-共享资源/参考图库/参考.jpg" },
        { op: "move", src_rel: "00-收件箱/户型图.dwg",
          dst_rel: "01-项目/20260612 周宁 龙腾世纪 12#1802/03-CAD/户型图.dwg" },
      ] },
    { plan_id: "20260717-2", created: "2026-07-17T11:00:00", ops: [] },
  ]);
  assert.equal(got.length, 2);
  assert.equal(got[0].planId, "20260717-1");
  assert.deepEqual(got[0].rows, [
    { src: "参考.jpg", dstDir: "03-共享资源/参考图库" },
    { src: "户型图.dwg",
      dstDir: "01-项目/20260612 周宁 龙腾世纪 12#1802/03-CAD" },
  ]);
  assert.equal(got[0].count, 2);
});

test("preview_rows:Windows 反斜杠路径归一成 /", () => {
  const got = planPreview([
    { plan_id: "p", created: "",
      ops: [{ op: "move", src_rel: "00-收件箱\\参考.jpg",
              dst_rel: "03-共享资源\\参考图库\\参考.jpg" }] },
  ]);
  assert.deepEqual(got[0].rows,
                   [{ src: "参考.jpg", dstDir: "03-共享资源/参考图库" }]);
});
