# Tasks: opendesign-file-organizer

- base-ref: <design-studio 不在 git 管理下,以 tests 全绿为准>

> 实现由主 agent 直接做(安全敏感的确认闸,不委托 submimo fix);
> panel-review 放 verify 阶段。oracle 归主 agent 所有。

- [x] tests-first:落 `tests/test_ds_organize.py`(design.md oracle 矩阵),先红后绿
- [x] 实现 `bin/ds_organize.py`(纯核心 + stdio MCP 包装)至全绿(venv 15/15)
- [x] 实现 `bin/ds-approve`(人工批准 CLI,+x)
- [x] 回归:`tests/test_ds_tools.py` 仍 13/13 绿
- [x] nanobot config 模板加 design-studio-organize mcpServer 条目(DS_ORGANIZE_ROOTS 留待部署时填,空=全拒)
- [x] verify.md:主 agent 先审 → panel-review(full)→ 主裁 PASS(TOCTOU 加固+GLM 抓的 makedirs 撞文件已修,18/18 绿)
