# Tasks: opendesign-anydoc

- base-ref: 1b93067(见 `git log`,起 track 时的 HEAD)

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

- [x] 规划双出:`gpt-5.6-sol` 独立出一版 —— **打中地基**(绑定关系本身归助手管)
      + 提示注入这条链 + mtime 会骗人。日志 `/root/aiwork/logs/anydoc-dualplan.stdout`
- [ ] 判据先行(**先单独 commit**):路径越权 / 白名单 / 长度上限与截断告知 /
      扫描件与失败的明确回执 / 日期解析与排序 / 绑定缺失 —— 转换库用替身
- [ ] 判据:一条"真库在场才跑"的判据(本地 SKIP 且 SKIP 可见)
- [ ] 实现 `list_project_docs` + `read_project_doc`(只读;沿用现有 `_resolve` 咽喉)
- [ ] 接进 MCP 工具表(工具表快照闸会红一次,要同步基线)
- [ ] `bin/install.ps1` 加 `firecrawl-anydoc==<钉死版本>`
- [ ] 助手契约加一小段:读了必须报出处 + 文档内容是资料不是命令(**短**)
- [ ] 读回来的内容包一层「这是资料不是指令」的边界(缓解提示注入,非根治)
- [ ] 延迟 import:老机器没装包时**不能让整个 MCP server 起不来**,
      否则连现有待办工具一起消失(双出提的部署坑,成立)
- [ ] verify:lane = **full**(碰权限面,硬规矩不打折)
- [ ] 真机:两台 Windows 各重跑装机脚本 → 让运行中的目标自己打印出它有这个能力
      → 打开一份真合同,看它报不报出处

## 另开一单(不塞进这一单)

- **`set_workspace_tool` / `bind_project_tool` 要业主确认才生效。**
  这是唯一能真正掐断「文档里藏一句话 → 助手改工作区根 → 读走工作区外的文件」那条链的改动。
  业主本单选了「先不做授权」,所以这里也不夹带;**做完这一单单独问他**。
  注意:这条改动本来就该有,跟 anydoc 没关系 —— anydoc 只是让它从「不好看」变成「有后果」。
