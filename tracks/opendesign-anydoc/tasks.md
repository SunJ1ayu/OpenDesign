# Tasks: opendesign-anydoc

- base-ref: 1b93067(见 `git log`,起 track 时的 HEAD)

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

- [ ] 规划双出:`gpt-5.6-sol` 对同一份需求独立出一版,对差异(权限面,不跳过)
- [ ] 判据先行(**先单独 commit**):路径越权 / 白名单 / 长度上限与截断告知 /
      扫描件与失败的明确回执 / 日期解析与排序 / 绑定缺失 —— 转换库用替身
- [ ] 判据:一条"真库在场才跑"的判据(本地 SKIP 且 SKIP 可见)
- [ ] 实现 `list_project_docs` + `read_project_doc`(只读;沿用现有 `_resolve` 咽喉)
- [ ] 接进 MCP 工具表(工具表快照闸会红一次,要同步基线)
- [ ] `bin/install.ps1` 加 `firecrawl-anydoc==<钉死版本>`
- [ ] 助手契约加一小段:读了必须报出处(**短**)
- [ ] verify:lane = **full**(碰权限面,硬规矩不打折)
- [ ] 真机:两台 Windows 各重跑装机脚本 → 让运行中的目标自己打印出它有这个能力
      → 打开一份真合同,看它报不报出处
