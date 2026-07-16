# Design: opendesign-owner-feedback

## D1 核心 log_communication(bin/ds_tools.py)
- 签名 `log_communication(project, text, source="", ds_root, today=None)`。
- text **不折行**(与 sanitize_field 相反——原文保真是本工具的存在理由):
  仅统一换行符 + strip;空 → `{"error":"empty_text"}`。
- source 走 sanitize_field + 截 16;可选。
- 条目格式(引用块杀结构注入):
  `- <date> 业主原文(<source>):` / 无 source `- <date> 业主原文:`
  原文每行前缀 `  > `(空行 `  >`)——`^-`(CHANGE_RE)/`^## `(段界)/
  `^最后更新`(footer 锚)全部无法命中,注入面焊死。
- 写入「## 沟通日志」段:段界 = 下一 `^## ` 或 `^---`;插到段内最后一条非空行后;
  段缺失 → 在 `---` 页脚前自动补建(旧手写档案兼容);bump_last_updated;
  locked_rw 排他锁,错误路径 write=False 文件原封不动。
- 返回 `{ok, project, date, lines}`。

## D2 MCP 注册(_run_mcp)
- `log_communication_tool(project, text, source="")`,docstring 写清三步纪律
  (docstring 是 LLM 真看的,git pull 即达;AGENTS.md 要 install 拷贝才生效)。

## D3 AGENTS.md(workspace/,部署副本)
- 工具表加 `log_communication` 行;规则区加"业主发来一段修改意见(贴原文)"三步:
  ①先 log_communication 存原文 ②确定要做的逐条 append_change(短句去废话,一条
  一件事,能标空间就标) ③摇摆/没拍板的**不记变更**,原样引用贴回对话请设计师定,
  定了再落。
- 呼应既有规则 1(单句口头改动直接 append_change 不变)。

## D4 版本/验证
- ds_web VERSION 0.19.0(部署回显;验收=对话问"你有哪些工具"应含 log_communication,
  需重启 gateway 注册)。
- oracle(先红后绿):正常多行写入/无 source/项目不存在/空文本/段缺失补建/
  **注入红检**(text 含伪变更行+伪 ## 段头+伪 最后更新 → 变更段逐字节不变、
  CHANGE_RE 计数不变、footer 只认真锚)/锁下文件错误路径不动/连续两次追加有序。
- verify lane = **full panel**(新增 PKB 写面,同 bind_project/rename_project 先例)。
