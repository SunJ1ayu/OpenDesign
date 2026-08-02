# Tasks: opendesign-todo-ux

- base-ref: cf788adcade4ed2cbb5892fa50e0e30f07c7de47

> 主 agent 自实现(前端 + 文案,范围窄)。纯逻辑先写测试。

- [x] T1 todo.ts:加 `isTerminalStatus` + `STATUS_HINT`(纯逻辑)
- [x] T2 mjs oracle:isTerminalStatus / STATUS_HINT 用例(先红→绿,共 22 用例)
- [x] T3 TodoPage.tsx:状态 pill 可点 → 快捷菜单直接改状态(A1);终态次级显眼度(.term)
- [x] T4 TodoPage.tsx:终态变更后撤销 toast(A2,与 T3 同单元)
- [x] T5 TodoPage.tsx:备注保存后乐观回显(A3,noted map)
- [x] T6 TodoPage.tsx + todo.ts:pill/菜单含义提示(A4 前端,STATUS_HINT 同源)
- [x] T7 workspace/AGENTS.md:状态语义(待确认=球在业主/进行中=球在我/已关闭=作废)
- [x] T8 app.css:pill 按钮 / 状态菜单 / toast / 备注行 样式
- [x] T9 版本 bump 0.9.0 → 0.10.0;build 绿(tsc -b + vite)
- [x] T10 verify:PASS(fast lane 主+submimo)。mjs 全绿 + pytest 236 passed + 真起 ds_web
       全链路通过(health=0.10.0);submimo 复审 PASS(两观察=已知取舍);verify.md 已填。
