# Tasks: opendesign-note-clear

- base-ref: d22f8a2acc783e0fd88cc299e2d123e1ea59831b

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

- [x] T0 复现存档:两层各自复现(`repro_note_clear.py`),结论进 proposal
- [x] T0b 规划双出(`gpt-5.6-sol`,禁读本目录)→ 抓到第二个根因「重复备注行」,
      自己复现证实(`repro_dup_note.py`)→ 折进 design/判据
- [x] T1 判据:核心 pytest ⑤b 清空 / ⑤c 空白 / ⑤d no-op 逐字节 / ⑤e 清后可再写 /
      ⑤f 重复行归一(含读侧断言)/ ⑤g 重复行全清 / ⑤h 全角冒号
- [x] T2 判据:HTTP 面 `test_edit_note_clear_removes_note`(写口 + 读侧 /changes 一起验)
- [x] T3 判据:`test_workbench_p4.mjs` buildEditRequest 清空三例
- [x] T4 判据:e2e G(工作区清空落盘)+ H(待办页不留空标签)
- [x] T5 红检:core 5 红 / HTTP 1 红 / node 2 红 / e2e 5 红(A–F 仍绿,红在目标断言上)
- [ ] T6 判据单独 commit(不夹带实现)
- [ ] T7 实现:`ds_tools`(`_remove_note` + 归一 + `if note is not None`)/
      `todo.ts`(去掉 `n &&`)/ `TodoPage.tsx`(空串删键)
- [ ] T8 **build 出 web/dist 并入库**(ds_web 服务的是 dist,源码改完不 build = 真机没修)
- [ ] T9 亲跑:`tests/run-all.sh`(python 全量 + node 单测 + dist 闸)+ 本单 e2e
- [ ] T10 bump 版本号(ds_web.py VERSION)+ 真机验收清单加一条(业主按原动作复验)
- [ ] T11 verify lane=full(panel-review)→ 主裁 → 归档
- [ ] T12 backlog 记三条(待办页 note 真相源 / expected_note 并发 / 写入原子性)
