# Tasks: opendesign-intake

- base-ref: 97e0c5495911cb0d185f8c122314a2174c634e38

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

- [x] T1 类目规则表:`config/taxonomy.default.json`(taxonomy v1.0 机读版)+
      `bin/ds_intake.py` 规则解析/建议函数(默认+用户覆盖合并;扩展名→类目;
      auto|suggest-only;未知扩展=无建议)。py oracle 先红后绿。
- [x] T2 收件箱核心:`list_inbox()`(收件箱候选名容错/文件列举/建议类目+建议项目
      token 唯一命中)+ `stage_intake()`(assignments→operations→ds_organize.
      stage_plan 直调)+ MCP 工具挂 design-studio-organize server。py oracle。
- [x] T3 ds_web:GET `/api/intake`(清单+建议+pending plans)+ POST 针孔④
      `/api/intake/approve`(posture 同 edit-change;approve_plan+apply_plan 一气)。
      py oracle 先红后绿 + 突变红检。
- [x] T4 前端收件箱卡片(伴随列第五块):预览列表+「确认执行」;`intake.ts` 纯逻辑
      进 mjs oracle;dataEpoch 刷新;ds-web 版本 bump 0.25.0。
- [x] T5 e2e 真 gateway(丢3文件→建议→stage→卡片预览→POST确认→磁盘归位+audit)
      + resolver eval 新工具计分 + 部署文档(AGENTS.md 工具段/DS_ORGANIZE_ROOTS
      含工作区根的说明/install 物料)。
- [ ] T6 verify:主审先落 my-review(仓外)→ full panel 四腿首跑 → 仲裁 →
      verify.md 落verdict。
