# Proposal: opendesign-pkb-lint

- Date: 2026-07-17
- Status: open

## Goal

PKB 自动体检(ds_lint)+ index.md 废弃(以 list_projects 工具替身)+ 两项审计遗留加固
(create_project stage 闸、_upsert_header_field 抽取)。

## Motivation

对照 Karpathy LLM-Wiki 九条自查的产出:
1. **PKB 没有健康检查**(第 VIII 条空缺):重复档案、断链、手改档案的坏字段全靠人眼。
   07-16 改名事故(7 对重复档案人眼发现)为真实事故背书。
2. **index.md 是说谎工件**(第 I/II 条双真相源):模板承诺"新增业主/项目挂一行",但聊天
   大脑的内置文件工具已禁用(disable_builtin_file_tools),架构上就没人能维护它;现内容
   停在 06-29 示例数据。且聊天大脑没有任何"列出所有项目/业主"的工具(仅 list_todos 间接
   覆盖有未结项的项目)。
3. create_project 的 stage 参数无词表闸(set_stage 有,不对称;tool-audit 遗留)。
4. 头部字段 upsert 逻辑重复(update_client / set_stage 各一份,漂移风险;tool-audit 遗留)。

## Scope

- in: T1 list_projects 只读 MCP 工具;T2 index.md 废弃(删 sample+改 SCHEMA/模板承诺,
  防御性代码不动);T3 bin/ds_lint.py + lint_pkb 只读 MCP 工具(确定性检查,只报告);
  T4 create_project stage 词表闸;T5 _upsert_header_field 抽取(零行为变化)。

## Non-goals

- 不做自动修复(--fix):v1 只报告;修复动作走既有工具(状态机/organize 闸)。
- 不做 UI 面(驾驶舱挂 lint 卡片等真实使用反馈)。
- 不碰已部署机器的 index.md 文件(lint 报告提示,删不删归机主)。
- 不给 lint 加模型辅助的矛盾检查(远期,等确定性版用出反馈)。

## 工艺备注(模型分层试跑第一单)

主 agent(Fable5)出 plan+oracle(先红),Opus 4.8 worktree 承包实现,submimo fix 收尾
红灯,verify fast lane(主审+submimo)。oracle 文件对 executor off-limits。
