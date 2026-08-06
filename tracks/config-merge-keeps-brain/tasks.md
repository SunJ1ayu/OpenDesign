# Tasks: config-merge-keeps-brain

- base-ref: 28c2504

- [x] 判据先行(修复前 2 处红)—— `39bc321`
- [x] 修复 + 版本 0.78.0 —— `8d1d161`
- [x] full 四审 → 判据补 3 条(回落逻辑此前零断言)+ 悬空预设优先用机主自己的预设
- [x] 仓库级总跑:node 342 / python 872 / MCP 闸绿 / e2e 32 PASS 0 FAIL 2 SKIP
- [ ] **真机验收**(只有机主能做):在 Windows 上重跑一次装机/合配置,
      回车不填 ⇒ 大脑仍是你自己选的那个;`/api/health` 显示 0.78.0
