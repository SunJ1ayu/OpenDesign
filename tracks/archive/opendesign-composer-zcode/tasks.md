# Tasks: opendesign-composer-zcode

- base-ref: 464b55a66b7ed183ff48420c4cafa2d502e943f4

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

- [x] T0 探针:/stop 三种时机的实时序列 + 回放行(evidence/20260925-probe-stop.txt)
- [x] T1 4c 方案挑战(GPT-5.6 sol)+ QA 设计(每个可用家族一条:7 家交卷、MiMo 基础设施失败),核实与取舍写进 design.md
- [x] T2 判据先行:单测 tests/test_composer_zcode.mjs + e2e tests/e2e/composer_zcode.e2e.mjs + 老判据的改动(逐条理由);单独 commit,红检收据
- [x] T3 实现:composerSkills.ts、ChatPage.tsx、SkillsPage.tsx、transcript.ts、modelError.ts、modelPicker.ts、inputHint.ts、TodoRail.tsx、样式
- [x] T4 判据转绿 + 变异红检 + run-all(web 构建、e2e)收据
- [x] T5 QA 执行:真网关 + 假厂商慢流 + 真工作台 + 真 chromium 录像;每个可用家族判卷;修完复测
- [x] T6 代码评审(standard = 1 家)+ 主裁 + 归档
