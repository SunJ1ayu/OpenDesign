# design-studio agent — Spec (Phase 0)

> 命门文档。先改这里,再写代码。任何工具行为以本文为准,与 `README.md` 操作契约一致。
> 状态:v1(2026-06-30,经主 agent + SenseNova + GLM 三审合并)。

## 1. 目标与范围

**目标**:把已落地的 Markdown 记忆后端,套一个能日用的 agent——设计师用聊天软件(飞书)
说一句话,agent 就替他**记住业主的修改需求、推进状态、每早提醒未跟进事项**。

**本期范围(MVP)**:记忆 + 状态 + 主动提醒,4 个工具。
**不在本期**:cad-to-3d(P2)、效果图(P4)、几何修复、业主直接发消息进来(DM 配对)。

## 2. 架构决策(已定)

- **底座 = Nanobot**(HKUDS,~4000 行 Python,44.9k★,v0.2.2 Durability,飞书 WebSocket 内置)。
  推翻早先「手写循环 + OpenClaw」:手写的唯一理由是换脑自由,Nanobot 的多 provider 已交付;
  loop 安全(max rounds / 重试 / 持久化)由 Nanobot 负责,不自造。
- **记忆后端不变** = 纯本地 Markdown(`projects/` `clients/` `index.md`),换脑不影响。
- **换脑自由** = Nanobot provider 配置,起步接强模型(Claude / GLM,均工具调用可靠),
  纯本地小模型暂不指望其结构化工具调用。配置项:`provider / apiBase / model / key`。
- **工具 = 我们写**,挂到 Nanobot(MCP server 或原生 skill,见 §7 待定项)。
  工具契约本身与底座无关——即便将来换底座,§4/§5 不变。

## 3. 数据格式契约(冻结,工具必须遵守)

引自 `schema/SCHEMA.md`,工具解析/写入只认这两处:

- **变更行**:`- [状态] C<n> YYYY-MM-DD 内容`,状态 ∈ {`待确认`,`进行中`,`已完成`,`已关闭`}。
- **末行**:`最后更新: YYYY-MM-DD`。
- **铁律**:不删变更行(取消用 `[已关闭]`);每次写动作都更新「最后更新」为当天。

## 4. 工具契约(4 个)

> `DS_ROOT` = `/root/.openclaw/workspace/projects/design-studio`(可配置)。
> 所有工具**只读/写 `DS_ROOT/projects/` 与 `DS_ROOT/clients/` 内的文件**。

### 4.1 append_change(project, content) — 核心
追加一条新变更(对治「会忘」的头号活)。
- **入参**:`project`(项目 slug)、`content`(变更内容,自由文本)。
- **行为**:content 先消毒成单行(换行/回车折叠为空格,ds_common.sanitize_field;
  2026-07-03 全库盲评加的契约——多行 content 等于伪造任意账本行)→ 读
  `projects/<project>.md` 变更记录区 → 算 `next = max(已有 C 编号)+1`(无则 1)
  → 追加 `- [待确认] C<next> <今天> <content>` → 更新「最后更新」为今天
  (行首锚定、最后一处 = 页脚,写读同源)。
- **返回**:`{ok, change_id: "C<next>", line}`。
- **错误**:项目不存在 → `error: project_not_found`(不创建);
  content 折叠后为空 → `error: empty_content`(文件不动)。

### 4.2 set_change_status(project, change_id, status)
推进单条变更状态,**不删行**。
- **入参**:`project`、`change_id`(如 `C2`)、`status`(四词表之一)。
- **行为**:**锚定匹配** `^- \[.*?\] C<change_id>\b`(`\b` 防 `C2` 误伤 `C12`)→ 只改方括号内状态
  → 更新「最后更新」。
- **返回**:`{ok, old_status, new_status, line}`。
- **错误**:
  - `status` 不在词表 → `error: invalid_status`(拒绝)。
  - 命中 0 行 → `error: change_not_found`。
  - 命中 >1 行(数据损坏/重复 id)→ `error: ambiguous_change`(拒绝,不猜)。

### 4.3 read_project(name)
- **入参**:`name`(项目 slug)。
- **行为**:返回 `projects/<name>.md` 全文(MVP 不截断——项目文件极小)。
- **返回**:`{ok, content}` 或 `error: project_not_found`。

### 4.4 list_todos(stale_days=7)
- **入参**:`stale_days`(默认 7)。
- **行为**:调现成 `bin/ds-todo <stale_days>`,**原文本返回**(中文项目符号列表;
  起步是强模型,直接解析无碍。转 JSON 列为 P-later,非 MVP)。
- **返回**:`{ok, text}`。

## 5. 安全边界(工具实现必须强制,非口头约定)

1. **路径 allowlist**:任何 `project/name` 拼成路径后,`os.path.realpath` 必须 `startswith`
   允许目录(`projects/`、`clients/`),否则拒绝。防 `../../etc/passwd` 逃逸。
2. **写串行化**:append_change / set_change_status 写文件前 `fcntl.flock` 加锁
   (防飞书消息与 cron 同时触发的竞态;cron 只读 list_todos,风险低但加锁便宜)。
3. **状态校验**:status 必须精确等于四词表之一,不做模糊匹配/纠错。
4. **不删行**:任何写操作不得减少变更行数(可由 oracle ⑨ 守)。
5. **本地不留存**:LLM 每次只借相关项目片段,文件永在本机。

## 6. 循环与停止条件(Nanobot 负责,此处记录期望)

底座层(Nanobot,不自写):max tool rounds、工具报错回塞重试、token/超时控制、持久化。
应用层(Serena 7 要素,写进系统 prompt):
- **目标**:把业主口述的改动准确落成变更行 / 正确推进状态 / 报全未跟进项。
- **检查**:写后复述「我记了 C<n>: ...,对吗?」让设计师确认。
- **停止**:工具返回 ok 且向用户复述完即结束本轮;连续工具报错 2 次则停下说明卡点。
- **系统 prompt** = `README.md` 操作契约 + 阶段词表 + 状态词表 + 上面三条。

## 7. 落实结果(2026-06-30 读 HKUDS/nanobot docs 核定)

- **工具挂载 = stdio MCP server(已决)**。nanobot 自定义工具一等路径是 MCP
  (`tools.mcpServers`,stdio `command`+`args` 或 http `url`);docs 未暴露轻量原生
  Python 工具 API(`my-tool.md` 是内置自省工具,非自写)。→ 4 工具写成一个 stdio
  MCP server(Python 官方 `mcp` SDK),nanobot `command: python args:[bin/ds_mcp.py, tools]`
  拉起(2026-08-03 起统一入口;登记层在 `bin/ds_*_server.py`,业务模块不再当入口)。
  利好:MCP server 可移植(挂任何 MCP 宿主),工具层也不锁 nanobot。
- **飞书 = WebSocket 长连接(已决)**,不需公网 IP。配 `channels.feishu`(见 §9)。
- **起步 provider/model(仍待用户拍)**:Claude 或 GLM,给 `apiBase+model+key`。
  ⚠️ 重名陷阱:用 **HKUDS/nanobot**(Python/飞书/`~/.nanobot/config.json`),
  **非** nanobot-ai/obot 那个 Go 的 `nanobot.yaml`。

## 9. config.json 骨架(可抄,`~/.nanobot/config.json`)

```jsonc
{
  "providers": {
    "anthropic": { "apiKey": "${ANTHROPIC_API_KEY}", "apiBase": "https://api.anthropic.com/v1" },
    "glm":       { "apiKey": "${ZHIPU_API_KEY}",     "apiBase": "https://open.bigmodel.cn/api/paas/v4" }
  },
  "modelPresets": {
    "primary": {                       // 起步二选一:把 provider/model 换成你要的脑
      "provider": "anthropic", "model": "claude-opus-4-8",
      // "provider": "glm",    "model": "glm-4.6",
      "maxTokens": 8192, "contextWindowTokens": 200000, "temperature": 0.1
    }
  },
  "agents": { "defaults": { "modelPreset": "primary" } },
  "tools": {
    "mcpServers": {
      // 三个 server 共用一个入口 bin/ds_mcp.py,靠第二个参数(tools/organize/refs)分流。
      // ⚠️ 少写那个 key 会让 server 起不来(argparse 直接退出);完整版见
      //    config/nanobot.config*.jsonc(带 env 段与整理白名单说明),那两份才是装机用的模板。
      "design-studio":          { "command": "python", "args": [".../design-studio/bin/ds_mcp.py", "tools"] },
      "design-studio-organize": { "command": "python", "args": [".../design-studio/bin/ds_mcp.py", "organize"] },
      "design-studio-refs":     { "command": "python", "args": [".../design-studio/bin/ds_mcp.py", "refs"] }
    }
  },
  "channels": {
    "feishu": {
      "enabled": true, "appId": "cli_xxx", "appSecret": "xxx",
      "allowFrom": ["ou_设计师自己的open_id"], "groupPolicy": "mention",
      "domain": "feishu", "streaming": true
    }
  }
}
```
> model id 以实际可用为准(Claude 强模型 / GLM `glm-4.6`,二者工具调用均可靠);
> 系统 prompt(§6)走 agent 指令位,不进 config。

## 8. 验证 — 测试 oracle 矩阵(主 agent 写,不交给弱模型)

每个工具 pass/fail oracle,覆盖正例 + 反例:

| # | 用例 | 期望 |
|---|------|------|
| ① | append_change 正常 | 新增 `[待确认] C<max+1> <今天>`,行数 +1,最后更新=今天 |
| ② | append_change 项目不存在 | error project_not_found,不建文件 |
| ③ | append id 连续 | 已有 C1..C4 → 新增 C5(不撞、不跳) |
| ④ | set_status 正常 | 只改方括号,行内容/编号/日期不变 |
| ⑤ | set_status 非法 status(如 `done`) | error invalid_status,文件不变 |
| ⑥ | set_status change_id 不存在 | error change_not_found,文件不变 |
| ⑦ | set_status `C2` 不误伤 `C12`/`C20` | 锚定只命中 C2 |
| ⑧ | set_status 命中多行(造重复 id) | error ambiguous_change,文件不变 |
| ⑨ | 任意写操作 | 变更行数不减少(不删行) |
| ⑩ | 路径逃逸(project=`../../etc/passwd`) | 拒绝,不读写 |
| ⑪ | 端到端冒烟 A | 「翡翠湾太太想把主卧门改到顶」→ 自动 append_change |
| ⑫ | 端到端冒烟 B | 「翡翠湾 C2 改成已完成」→ 自动 set_change_status(C2→已完成) |
