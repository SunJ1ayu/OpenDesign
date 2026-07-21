// track opendesign-frontend-p3-polish oracle:§I6 侧栏项目名显示 + §I4 recent 行分流。
// 跑法:node --test tests/test_project_name.mjs(Node 22+,原生 strip-types)
//
// 契约(design.md):
//   displayProjectName(name)  括号开头 → 优先显示右括号之后的内容;否则原样
//   openTargetFor(recent)     白名单内扩展名 → {kind:"file", rel};否则 → {kind:"folder", sub}
//
// red-check(commit message 附结果):
//   displayProjectName 直接 return name → 括号组变红
//   openTargetFor 去掉扩展名白名单判断 → test_open_target_executable 变红
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  displayProjectName,
  openTargetFor,
  OPEN_FILE_EXTS,
} from "../web/src/workspace/projectName.ts";

// ---- displayProjectName(§I6)---------------------------------------------

test("括号开头:优先显示右括号之后的内容", () => {
  assert.equal(
    displayProjectName("(20260612)周宁 龙腾世纪 12#1802"),
    "周宁 龙腾世纪 12#1802",
  );
});

test("全角括号开头:同规则", () => {
  assert.equal(
    displayProjectName("（20260612）周宁 龙腾世纪"),
    "周宁 龙腾世纪",
  );
});

test("半角/全角混用也认(设计师手打常见)", () => {
  assert.equal(displayProjectName("(20260612）保利中央公园"), "保利中央公园");
  assert.equal(displayProjectName("（20260612)保利中央公园"), "保利中央公园");
});

test("非括号开头:原样返回(括号在中间不触发)", () => {
  assert.equal(
    displayProjectName("保利中央公园 2803(主卧改造)"),
    "保利中央公园 2803(主卧改造)",
  );
});

test("括号后为空 → 退回原名(不返回空串)", () => {
  assert.equal(displayProjectName("(20260612)"), "(20260612)");
  assert.equal(displayProjectName("（20260612）"), "（20260612）");
  assert.equal(displayProjectName("(20260612)   "), "(20260612)   ");
});

test("只有左括号没有右括号 → 原样(不截断)", () => {
  assert.equal(displayProjectName("(20260612 周宁"), "(20260612 周宁");
});

test("空串 / 纯空白 → 原样,不炸", () => {
  assert.equal(displayProjectName(""), "");
  assert.equal(displayProjectName("   "), "   ");
});

test("括号后内容首尾空白裁掉", () => {
  assert.equal(displayProjectName("(A)  周宁  "), "周宁");
});

test("嵌套/多组括号:只吃开头那一组", () => {
  assert.equal(displayProjectName("(A)(B)周宁"), "(B)周宁");
});

// ---- openTargetFor(§I4 前端分流)-----------------------------------------

const rec = (name, category = "03-CAD", rel = undefined) => ({
  name, category, mtime: 1, size: 1,
  rel: rel ?? (category ? `${category}/${name}` : name),
});

// p3-polish 收货修复轮:rel 是后端给的**权威全路径**(含子目录),前端不许再拼。
// 拼 "类目/文件名" 对嵌套文件必然 404,同名不同子目录还会静默开错文件。
test("嵌套文件:直接用后端给的 rel,不再拼类目/文件名", () => {
  const r = rec("客厅.png", "06-效果图", "06-效果图/定稿/客厅.png");
  assert.deepEqual(openTargetFor(r), { kind: "file", rel: "06-效果图/定稿/客厅.png" });
});

test("嵌套文件 + 白名单外扩展名 → 仍退化为开文件夹,绝不开该文件", () => {
  const r = rec("跑批.bat", "03-CAD", "03-CAD/旧版/跑批.bat");
  assert.deepEqual(openTargetFor(r), { kind: "folder", sub: "03-CAD" });
});

test("白名单内扩展名 → 开文件,rel 带类目前缀", () => {
  const got = openTargetFor(rec("平面.dwg"));
  assert.deepEqual(got, { kind: "file", rel: "03-CAD/平面.dwg" });
});

test("无类目(项目根散文件)→ rel 不带前缀", () => {
  const got = openTargetFor(rec("说明.pdf", ""));
  assert.deepEqual(got, { kind: "file", rel: "说明.pdf" });
});

test("扩展名大小写不敏感", () => {
  assert.deepEqual(openTargetFor(rec("大写.PDF")), {
    kind: "file",
    rel: "03-CAD/大写.PDF",
  });
});

test("test_open_target_executable:可执行/脚本 → 退化为开所在文件夹", () => {
  for (const n of ["跑批.bat", "装机.exe", "脚本.ps1", "快捷方式.lnk", "宏.vbs", "矢量.svg"]) {
    assert.deepEqual(
      openTargetFor(rec(n)),
      { kind: "folder", sub: "03-CAD" },
      `${n} 必须退化为开文件夹,不许走开文件路径`,
    );
  }
});

test("无扩展名 → 退化为开所在文件夹", () => {
  assert.deepEqual(openTargetFor(rec("README")), { kind: "folder", sub: "03-CAD" });
});

test("双扩展名按真实末段判定:报价.pdf.bat → 文件夹", () => {
  assert.deepEqual(openTargetFor(rec("报价.pdf.bat")), {
    kind: "folder",
    sub: "03-CAD",
  });
});

test("白名单外 + 无类目 → 开项目根(sub undefined)", () => {
  assert.deepEqual(openTargetFor(rec("跑批.bat", "")), {
    kind: "folder",
    sub: undefined,
  });
});

test("白名单本身:不含任何可执行/脚本/快捷方式扩展名", () => {
  const forbidden = [
    ".exe", ".bat", ".cmd", ".com", ".scr", ".ps1", ".vbs", ".js", ".jse",
    ".wsf", ".msi", ".lnk", ".url", ".reg", ".dll", ".jar", ".sh", ".py",
    ".html", ".htm", ".svg", ".zip", ".rar", ".7z",
  ];
  for (const ext of forbidden) {
    assert.ok(
      !OPEN_FILE_EXTS.includes(ext),
      `${ext} 绝不允许出现在打开白名单里`,
    );
  }
});

test("白名单全为小写且带点(与后端 splitext().lower() 对齐)", () => {
  for (const ext of OPEN_FILE_EXTS) {
    assert.equal(ext, ext.toLowerCase(), `${ext} 必须小写`);
    assert.ok(ext.startsWith("."), `${ext} 必须带前导点`);
  }
});
