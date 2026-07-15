# Tasks: opendesign-todo-ux2

- base-ref: 3a8e6e26d73a9b8a6cb7d4fce820bbbd00188faf

> 主 agent 自实现(前端 + 组件抽取 + App 清理)。纯逻辑先写测试。

- [x] T1 StatusPicker.tsx:抽共享可点 pill + 快捷菜单(自管开合/backdrop/term 次级)
- [x] T2 todo.ts:buildEditRequest 加 originalNote(备注没变不重写);mjs 用例(先红→绿)
- [x] T3 TodoPage.tsx:备注预填 + 删状态下拉 + statusCell 改用 StatusPicker + 拔 menuFor
- [x] T4 ChangesColumn.tsx:每行 StatusPicker 可回滚 + 删「✓ 标记完成」+ pickStatus + onEdited + actionErr
- [x] T5 App.tsx:删 onMarkDone/prefillCol;colPrefill 降常量;ChangesColumn 改收 onEdited(bump dataEpoch)
- [x] T6 app.css:删死 .mark-done 样式
- [x] T7 版本 bump 0.10.0 → 0.11.0;build 绿(tsc -b + vite,296 模块)
- [x] T8 verify:PASS(fast lane 主+submimo)。mjs 65 + pytest 子集 99 + 真起 ds_web 回滚全链路(health=0.11.0);
      submimo 独立复审无阻塞。verify.md 已填。
