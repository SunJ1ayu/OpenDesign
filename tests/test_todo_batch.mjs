// track opendesign-todo-batch-space oracle:待办批量改状态的请求装配纯函数。
// 契约:batchEditRequests(items, newStatus) —— 把选中项映射成逐条 /api/changes/edit 的
// 请求体(客户端串行发,复用既有写针孔,不新开后端)。规则:
//   ① 跳过 cnum===null 的残缺行(不可寻址,无法定位到具体变更行);
//   ② **不再**按前端看到的状态跳过"已是目标态"的条目(track opendesign-note-source:
//      "变没变"由后端在文件锁里判 —— 前端看到的状态可能已经过期,拿它当判据就是
//      用陈旧数据做决定;后端对同值状态是逐字节 no-op,不写盘、不 bump 页脚);
//   ③ 保持传入相对序;④ 每条只带 {project, cnum, new_status};
//   ⑤ newStatus 非合法状态 → 抛(防手滑把任意串写进账本)。
// 跑法:node --test tests/test_todo_batch.mjs(Node 22+ 原生 strip-types)
//
// red-check:实现前 todo.ts 无 batchEditRequests 导出,本文件整体红。
import { test } from "node:test";
import assert from "node:assert/strict";
import { batchEditRequests } from "../web/src/todo.ts";

const it = (project, cnum, status) => ({ project, cnum, status });

test("batchEditRequests:选中项 → 逐条请求体,保持序", () => {
  const got = batchEditRequests(
    [it("翡翠湾-1801", 5, "待确认"), it("星河名邸-2302", 3, "进行中")],
    "已完成",
  );
  assert.deepEqual(got, [
    { project: "翡翠湾-1801", cnum: 5, new_status: "已完成" },
    { project: "星河名邸-2302", cnum: 3, new_status: "已完成" },
  ]);
});

// 契约在 track opendesign-note-source 改了:看着"已是目标态"的条目也照发。
// 前端手里那个 status 是上一次 reload 的快照,可能已经过期 —— 用它决定"不用发",
// 就是拿陈旧数据替档案做主。后端同值 no-op 已实测(文件逐字节不动、页脚不 bump)。
test("batchEditRequests:看着已是目标态的条目也照发(判定归后端)", () => {
  const got = batchEditRequests(
    [it("A", 1, "已完成"), it("A", 2, "待确认")],
    "已完成",
  );
  assert.deepEqual(got, [
    { project: "A", cnum: 1, new_status: "已完成" },
    { project: "A", cnum: 2, new_status: "已完成" },
  ]);
});

test("batchEditRequests:跳过 cnum===null 的残缺行", () => {
  const got = batchEditRequests(
    [it("A", null, "待确认"), it("A", 7, "待确认")],
    "进行中",
  );
  assert.deepEqual(got, [{ project: "A", cnum: 7, new_status: "进行中" }]);
});

test("batchEditRequests:看着全是空操作也照发(唯一被跳过的只有不可寻址)", () => {
  assert.deepEqual(batchEditRequests([it("A", 1, "进行中")], "进行中"),
    [{ project: "A", cnum: 1, new_status: "进行中" }]);
});

test("batchEditRequests:空输入 → []", () => {
  assert.deepEqual(batchEditRequests([], "已完成"), []);
});

test("batchEditRequests:非法目标态 → 抛", () => {
  assert.throws(() => batchEditRequests([it("A", 1, "待确认")], "乱写状态"));
});

test("batchEditRequests:不改传入数组(纯函数)", () => {
  const input = [it("A", 1, "待确认")];
  const snap = JSON.parse(JSON.stringify(input));
  batchEditRequests(input, "已关闭");
  assert.deepEqual(input, snap);
});
