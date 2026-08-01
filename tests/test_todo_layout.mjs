// track opendesign-todo-layout oracle:待办「按项目」视图的纯函数契约。
// 主 agent 亲写,执行腿逐字节 off-limits。
//
// idleProjectKeys(allKeys, cardedKeys, staleKeys) —— 闲置项目 = 全部 − 有卡 − 已在
//   「档案 N 天没更新」独立行报过的;保持 allKeys 传入序。
//
// 跑法:node --test tests/test_todo_layout.mjs(Node 22+,原生 strip-types)
//
// ════════════════════════════════════════════════════════════════════════════
// 2026-08-01 track opendesign-todo-one-view:**本文件的 orderProjectCards 一节已迁走**
// (新契约在 tests/test_todo_one_view.mjs)。本项目的规矩是**改判据必须当场证明"不是
// 放松"**,所以逐条对账写在这里,不许只写一句"新的更全面"。
//
// 迁走的原因(不是"想改得好看",是旧断言编码了一个被证伪的指标):
//   旧的第一排序键 `stale` = 后端 ds_todo.py:119 算的「今天 − 档案页脚最后更新日」。
//   而 ds_common.bump_last_updated 被 append_change / set_change_status / **set_due_date** /
//   edit_change / log_communication / rename_project / **set_stage** / add_ref / link_ref /
//   update_ref 全都调用 ⇒ 它测的是「档案文件多久没被写过」,不是「这件事多久没人管」;
//   **用户点一下截止日它就归零**。拿它当卡序的首键 = 排一个错的东西。
//
//   ┌ 旧断言 ───────────────────────┬ 去向 ────────────────────────────────────┐
//   │ 超期卡整体排最前               │ **替换**:改成"有过期截止日的卡最前"。   │
//   │ (超期 = 档案没更新)           │ 同形状、换成不骗人的指标。one_view 里     │
//   │                                │ 「有过期条目的卡排最前」+ 四档位完整序。 │
//   │ 超期组内按 days 降序           │ **替换**:同档内按卡里**最早的 due** 升序。│
//   │ 非超期组内按 items.length 降序 │ **删**:条数不是紧急度(20 条鸡毛蒜皮排不 │
//   │                                │ 过 1 条明天到期)。替代品是档位 + 最老     │
//   │                                │ 记录日期,两者都直接编码"急"。            │
//   │ 全平局保持传入序(稳定)       │ **保留**,one_view 同名用例逐字保留。     │
//   │ 同天数之间保持传入序           │ **保留**(改为同 due 之间),同上。        │
//   │ 附 stale 天数,无超期为 null   │ **替换**:徽标改用 latestRecordAge(条目侧 │
//   │                                │ 算),并单独测 7 条(含跨月/未来日期钳 0)。│
//   │ items 原样带过(同引用)       │ **保留**,且**加严**:新用例额外断言组内   │
//   │                                │ 顺序不被卡序函数改动(旧的只断言了 cnum   │
//   │                                │ 序恰好等于构造序,构造时就是有序的=弱)。 │
//   │ 不改传入数组(无副作用)       │ **保留**,逐字。                          │
//   │ 空输入 = []                    │ **保留**,并新增"空 items 的卡不炸"。     │
//   │ 不凭空造卡                     │ **保留**(旧的靠 stale 列表多出一个项目来 │
//   │                                │ 测;新签名没有该入参,改由"多余入参不许    │
//   │                                │ 改变结果"那条覆盖同一个风险)。           │
//   └────────────────────────────────┴──────────────────────────────────────────┘
//
// **约束面净变化:11 条 → 20 条**(tests/test_todo_one_view.mjs),且新增了旧断言在
// 结构上**表达不出来**的两个维度:① 条目级的 due 档位(旧函数根本拿不到 due);
// ② 「用户真实形态:一条 due 都没有」的整组用例(旧夹具 date/due 恒 null,
// 那个形态在旧文件里是**默认值**而不是**被测对象**,等于没判)。
// 唯一真正减少的约束是"按条数降序",它被显式判定为错的排序意图,不是被绕开。
// ════════════════════════════════════════════════════════════════════════════
import { test } from "node:test";
import assert from "node:assert/strict";
import { idleProjectKeys } from "../web/src/todo.ts";

// ── idleProjectKeys ─────────────────────────────────────────────────────────

test("idleProjectKeys:减掉有卡的项目", () => {
  assert.deepEqual(idleProjectKeys(["A", "B", "C"], ["B"], []), ["A", "C"]);
});

test("idleProjectKeys:减掉超期项目(已在独立行报过,不重复说)", () => {
  assert.deepEqual(idleProjectKeys(["A", "B", "C"], [], ["C"]), ["A", "B"]);
});

test("idleProjectKeys:两个减法同时生效", () => {
  assert.deepEqual(idleProjectKeys(["A", "B", "C", "D"], ["A"], ["C"]), ["B", "D"]);
});

test("idleProjectKeys:保持 allKeys 传入序(不排序)", () => {
  assert.deepEqual(idleProjectKeys(["Z", "M", "A"], [], []), ["Z", "M", "A"]);
});

test("idleProjectKeys:全被减完 = []", () => {
  assert.deepEqual(idleProjectKeys(["A", "B"], ["A"], ["B"]), []);
  assert.deepEqual(idleProjectKeys([], ["A"], ["B"]), []);
});

test("idleProjectKeys:既有卡又超期的项目只算减一次(不报错、不残留)", () => {
  assert.deepEqual(idleProjectKeys(["A", "B"], ["A"], ["A"]), ["B"]);
});
