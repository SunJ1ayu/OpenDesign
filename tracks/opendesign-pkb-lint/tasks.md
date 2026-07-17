# Tasks: opendesign-pkb-lint

- base-ref: 2e45502d45c4d49bbbaa0afe00a8e01e3573f5d0

> 工艺:模型分层试跑第一单。主 agent(Fable5)已写 oracle(tests/test_ds_lint.py,
> 先红已验证)并 commit;Opus 4.8 worktree 承包 T1–T5 实现;oracle 文件 off-limits;
> submimo fix 收尾红灯(如需);verify fast lane(主审+submimo)。

- [x] T1 `ds_tools.list_projects(ds_root)` 核心函数 + MCP 工具注册(只读枚举:
      project/client/stage/last_updated,排序,坏编码进 errors 不拖垮)
- [x] T2 index.md 废弃:删 repo 内 sample index.md;SCHEMA.md/模板/AGENTS.md 部署版
      去掉"挂一行"承诺;rename/delete 里 index.md 防御性代码不动(部署机可能有残留)
- [x] T3 `bin/ds_lint.py` + `lint_pkb` 只读 MCP 工具:八项确定性检查
      (broken_link/duplicate_content/bad_stage/duplicate_anchor/refs_dangling/
      refs_missing_file/workspace_dangling_mapping/deprecated_index + unreadable 隔离);
      词表/正则复用 ds_tools/ds_todo/ds_refs 单一真相源,不自造第二份
- [x] T4 create_project stage 词表闸(bad_stage 拒,对齐 set_stage)
- [x] T5 `_upsert_header_field` 抽取:update_client/set_stage 收敛单一实现,零行为
      变化(现有套件为回归 oracle);若有第三处拷贝一并收敛,没有则在报告里说明
- [x] T6 文档/路由:工具 docstring(resolver eval 风格:触发词进描述,纪律句不含
      典型场景关键词)、AGENTS.md 部署版瘦路由行、resolver eval 新工具用例(不跑)
- [x] T7 verify:oracle 全绿 + 全量回归 + resolver eval(主 agent 跑)+ fast lane
