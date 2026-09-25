# Tasks: opendesign-chat-error-visible

- base-ref: 9040a34d3bce7d59f0cf90304921676a2ba12948

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

- [x] T0 探针:五类出错的实时序列 + 回放行 + 四家真 401 原文(evidence/20260925-probe-gateway-errors.txt)
- [x] T1 4c 方案挑战(Grok)+ QA 设计(DeepSeek + Grok),核实与取舍写进 design.md
- [ ] T2 判据先行:单测 tests/test_chat_model_error.mjs + e2e tests/e2e/chat_model_error.e2e.mjs + 设置页文案断言;单独 commit,红检收据
- [ ] T3 实现:web/src/chat/modelError.ts、transcript.ts、ChatPage.tsx(+样式)、settings/modelSettings.ts
- [ ] T4 判据转绿 + run-all(web 构建、e2e)收据
- [ ] T5 QA 执行:真网关 + 假厂商 + 真工作台 + 真 chromium 录像,两家测试员判卷;修完复测
- [ ] T6 代码评审(standard = 1 家)+ 主裁 + 归档
