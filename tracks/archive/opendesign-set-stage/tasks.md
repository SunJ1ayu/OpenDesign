# Tasks: opendesign-set-stage

- base-ref: d81a657(client-tools 归档后)

- [x] T1 oracle 先红(SetStageOracle 7 例,后扩至 8)
- [x] T2 实现 PROJECT_STAGES + set_stage,127/127 绿
- [x] T3 突变红检(词表校验注掉 → ss02+ss06 红,还原绿)
- [x] T4 MCP 注册 + AGENTS.md(工具表行+词表段话术)
- [x] T5 resolver eval +1(万科城开始量房→set_stage),实跑 20/20 ALL PASS
- [x] T6 VERSION 0.23.0 + pytest 全套 324 绿
- [x] T7 verify full panel:主审先行(PASS+2观察)→ 三家 PASS;GLM 2 LOW 全收
      (错误优先级测试锁+ss06 显式零副作用);**panel 修复轮抓真 bug:[::] 全角
      冒号 typo(两家独立标)→ [:\uff1a] 修复+ss08/uc10 先红后绿,129 全绿**
