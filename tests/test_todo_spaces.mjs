// track opendesign-frontend-p2-polish oracle:待办「按项目」卡内按空间分小节(修改单 G1)。
// 契约:spaceSections(items) —— 按空间**首现序**分组;无空间(null)条目归一个
// space:null 小节**恒置末**(UI 渲染为「未分空间」);组内保持传入相对序;空输入 = []。
// 跑法:node --test tests/test_todo_spaces.mjs(Node 22+,原生 strip-types)
//
// red-check:实现前 todo.ts 无 spaceSections 导出,本文件整体红。
import { test } from "node:test";
import assert from "node:assert/strict";
import { spaceSections } from "../web/src/todo.ts";

const it = (space, text) => ({
  project: "翡翠湾-1801", line: 1, raw: "", status: "待确认",
  cnum: null, date: null, space, text,
});

test("spaceSections:按空间首现序分组", () => {
  const got = spaceSections([
    it("玄关", "a"), it("客厅", "b"), it("玄关", "c"),
  ]);
  assert.deepEqual(got.map((s) => s.space), ["玄关", "客厅"]);
  assert.deepEqual(got[0].items.map((x) => x.text), ["a", "c"]);
  assert.deepEqual(got[1].items.map((x) => x.text), ["b"]);
});

test("spaceSections:无空间条目归 null 小节且恒置末(即使首现)", () => {
  const got = spaceSections([
    it(null, "x"), it("玄关", "a"), it(null, "y"), it("客厅", "b"),
  ]);
  assert.deepEqual(got.map((s) => s.space), ["玄关", "客厅", null]);
  assert.deepEqual(got[2].items.map((x) => x.text), ["x", "y"]);
});

test("spaceSections:全无空间 = 单个 null 小节", () => {
  const got = spaceSections([it(null, "x"), it(null, "y")]);
  assert.deepEqual(got.map((s) => s.space), [null]);
  assert.deepEqual(got[0].items.map((x) => x.text), ["x", "y"]);
});

test("spaceSections:空输入 = []", () => {
  assert.deepEqual(spaceSections([]), []);
});
