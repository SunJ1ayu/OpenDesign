# Verify: opendesign-delete-project

- Lane: full panel(新增 PKB 删除面)
- 结论:**PASS**

## Oracle(panel 前先跑,PANEL_ORACLE_CMD 已录 105 绿;终态 107)
- DeleteProjectOracle 9 例(7 先红后绿 + panel 后补 2):回收站保真(逐字节)/
  引用只清点不改/映射摘除保真/无 config 不硬造/错误契约零副作用/同名不覆盖/
  删后各读面不可见/refs「用于」段精确计数(超串不误伤)/坏 workspace.json 静默降级。
- 全量回归 pytest 302 过 7 skip + mjs 87 绿。

## 仲裁(主审 my-review 先行;panel 的 my-review 闸拦下过一次抢跑发卷,按设计工作)
- 主审:PASS。**自审抓到并修掉崩溃残局顺序**——先摘映射后挪档案,中间崩溃残局
  =档案在+映射掉(可见/可重试);反序=档案没+映射悬空吃掉文件夹(隐形)。
- submimo(806 行真卷):实质 PASS,「建议合并前修复 refs-index 计数口径,其余
  增强项」。收:refs 计数改 ds_refs._used_segment 分段精确项(与 rename ② 同
  口径,dp08 锁)+ 坏 config 测试(dp09);拒/记录:删后同名重建引用自然指向新
  项目=正确语义非 bug(本段记录);删后 rename 行为=exists 闸契约保证不另测。
- subsense(DeepSeek agent 腿,154 行):PASS。收:①回收站序号跳 1(-2 起)
  修为 -1 起;②refs 计数同上;拒:.trash 空目录残留(无害,扫描面全隔离)。
- subglm:缺席(百炼 429 余额不足,连续第 4 个 track,债)。

## 接受的取舍
- 不动 clients/index 的 [[引用]](删除=下架,引用是历史痕迹;计数播报);
  不做恢复工具/清空回收站/批量删;误调防线=MCP docstring+AGENTS.md 双层
  "明确要求+复述确认"(回收站可恢复,不上 ds-approve 硬闸——那是护不可再生
  机器文件的)。

## 用户验收断点
- git pull → start.ps1 stop → start.ps1(重启 gateway 注册新工具)→ 回显 0.21.0;
  对话:「把重复的新名档案删掉:XXX、YYY…(7 个)」→ 助手复述确认 → 逐个删
  (报 .trash 路径+残留引用数)→ 再「用 rename_project 把 7 个项目改名」一次清完。
