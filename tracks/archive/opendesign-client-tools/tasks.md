# Tasks: opendesign-client-tools

- base-ref: b739eaa0683560af9f5cba3e4f7bb43a472d7949

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

- [x] T1 oracle 先红:ReadClientOracle(4)+ UpdateClientOracle(9),13 用例
      对未实现核心全红(存量 107 绿)。
- [x] T2 核心实现:read_client + update_client,120/120 绿 + pytest 全套
      315 passed。
- [x] T3 突变红检 2/2:白名单校验注 → uc05 红;sanitize 去除 → uc07 红;已还原。
- [x] T4 路由:MCP 两工具注册 + AGENTS.md 工具表两行 + 规则 4 话术。
- [x] T5 resolver eval:探针翻转 + 2 新断言,实跑 19/19 ALL PASS。
- [x] T6 VERSION 0.22.0(前端从 /api/health 读版本,无前端改动免 build)+
      pytest 全套绿。
- [x] T7 verify full panel:主审先行(PASS+3nit)→ 四方 PASS(submimo/
      subsense 内容 PASS gate 误判/subglm 火山腿首战+2LOW)→ 仲裁零改动,
      verify.md PASS。
