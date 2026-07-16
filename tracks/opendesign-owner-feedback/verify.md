# Verify: opendesign-owner-feedback

- Lane: full panel(新增 PKB 写面)
- 结论:**PASS**

## Oracle(panel 前先跑,PANEL_ORACLE_CMD 已录)
- LogCommunicationOracle 10 用例(7 先红后绿 + panel 后补 3):多行保真/无 source/
  错误契约(path_escape/bad_name/empty_text/project_not_found 零副作用)/
  **注入红检 lc04**(伪变更行+伪段头+伪页脚全失锚,变更段逐字节不变)/段缺失补建/
  时序/CRLF/空段插入/无页脚老文件/source 消毒(剥括号+折行+截16)。
- 全量回归 pytest 293 过 7 skip(既有)+ mjs 78 绿。

## 仲裁(主审 my-review 先行落盘,基于 /root/aiwork/tasks/opendesign-owner-feedback-review-my-review.md)
- 主审:PASS,0 blocker。
- submimo:PASS「可以合并,无阻塞项」。收:测试缺口 3 例(空段/无页脚/source 截断,
  已补 lc08-lc10);拒:磁盘满 truncate=全体读改写工具通用预存债,非本 PR 引入。
- subsense(DeepSeek agent 腿,自读仓库全卷):PASS。收:#1 source 剥括号
  (ds_tools.py 已修,同 append_change 剥【】先例)+#5 MCP docstring 补回执行;
  拒:#4 _COMM_HEADER 与模板字面量重复=与 _CHANGE_HEADER 同款既有 debt。
- subglm:缺席(百炼 429 余额不足,工具债,2/3 到卷符合单缺席 fallback)。
- 无 employee 发现主审漏掉的行为缺陷;全部收项为"行为对但没锁"与格式打磨。

## 接受的取舍
- text 无长度上限(同 append_change 口径);沟通日志前端不展示(二期)。

## 用户验收断点
- git pull → start.ps1 stop → start.ps1(**须重启 gateway 才注册新工具**)→
  版本回显 0.19.0;对话贴一段业主改意见 → 助手应:存原文(答复里说明)+
  确定项逐条落变更(待办页出现总结短句)+ 摇摆句引用贴回请你拍板。
- AGENTS.md 是部署副本:公司/家里机器需重跑 install.ps1(或手拷 workspace/AGENTS.md
  到 %USERPROFILE%\.nanobot\workspace)才吃到 1b 规则;MCP docstring 里的三步纪律
  git pull 即达,不拷也有基本行为。
