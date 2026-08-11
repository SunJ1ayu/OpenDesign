# Tasks: opendesign-note-clear

- base-ref: d22f8a2acc783e0fd88cc299e2d123e1ea59831b

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

- [ ] T0 复现存档(已做):`repro_note_clear.py` 两层各自复现,结论进 proposal
- [ ] T1 判据先行:核心 pytest(清空/空白/邻居锚/no-op/回归锚)
- [ ] T2 判据先行:`tests/test_workbench_p4.mjs` buildEditRequest 清空用例
- [ ] T3 判据先行:e2e G(工作区清空落盘)+ H(待办页不留空标签)
- [ ] T4 红检(退回基线跑判据,必须红)→ 判据单独 commit
- [ ] T5 实现三处(ds_tools `_remove_note` / todo.ts / TodoPage 乐观回显)
- [ ] T6 亲跑:pytest 全量 + node 单测 + e2e 相关 + build(tsc/vite)
- [ ] T7 bump 版本号 + 真机验收清单加一条(业主按原动作复验)
- [ ] T8 verify lane=full(panel-review)→ 主裁 → 归档
