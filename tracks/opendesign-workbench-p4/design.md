# Design: opendesign-workbench-p4

- Change: opendesign-workbench-p4
- Status: accepted
- 依据: `handoff/README.md`(Claude Design v3 五画板定稿,像素级规格)
- 不是开放架构分叉(照定稿实现,唯一真设计点是 D1 空间字段的落法)→ 不 spend panel-explore

## Approach

### D1 变更行「空间」字段(唯一 schema 改动,最贵,先定死)

**选型:内容头部可选 `【空间】` 前缀,单行契约不破。**

```
- [待确认] C13 2026-07-12 【玄关】玄关柜整体改到 2.4 米高
- [待确认] C14 2026-07-12 没有空间标注的旧式行照常合法
```

- `ds_todo.CHANGE_RE`(单一真相源)在日期组后加可选组:`(?:【([^【】]{1,16})】\s*)?`;
  `parse_change` 返回新增 `space` 键(旧行/无标注 → `None`)。ds_web `/api/todos`、
  `/api/projects/<p>/changes` 吃同一 parse → **前端自动拿到 space,零端点改动**。
- `append_change` 加可选参 `space`:`sanitize_field` 消毒后**再剥 `【` `】`**(防伪造闭合
  括号注入结构)、截 16 字符、空串视同 None。MCP schema 同步加可选参数;AGENTS.md 用法
  表补一句「记变更尽量带空间(玄关/客厅…)」。
- 老记录零迁移:space=None → 待办页归「未标注」小节(排空间组末尾)。

### D2 搜索面板 = 纯客户端过滤,零新后端表面

- 打开面板时一次性拉 `/api/projects` → 并行拉每项目 `changes` + `refs`,缓存至面板关闭;
  本地大小写不敏感子串过滤 + `<mark>` 高亮。数据量=几个 markdown 文件,客户端绰绰有余;
  不加 `/api/search` = 不加新读面 = 只读铁律零增面。
- 分类 tab:全部/变更/图片 可用;**文件/对话 置灰**(上游未建,README 结构天然支持渐进点亮)。
- 回车:变更 → 进对应项目工作区并高亮该条(现有 route + 高亮态);图片 → 进项目工作区
  (图墙未建,先定位到项目)。
- 入口:侧栏新增「搜索」行 + 全局 Cmd/Ctrl+K;esc/遮罩点击关闭。

### D3 模型显示 + set_model(近期队列①合并进来)

- `/api/health` 加 `"model"`:ds_web 只读 `~/.nanobot/config.json` 的
  `agents.defaults.model`,读不到 → `null`(健壮,不因 config 缺失炸探针)。
- 设置弹层「AI 模型」行显示该值;「检查更新」回显 VERSION(本轮 → 0.5.0)。
- `bin/set_model.py <model-id> [--config PATH]`:备份 `.bak` → 改 `agents.defaults.model`
  → 打印「重启 gateway 生效」。仓内脚本,浏览器无写端点(铁律不破)。

### D4 待办页重排(纯展示层,吃 /api/todos + D1 space)

- 项目卡(白底/边框/圆角 11)+ 卡头(状态点/项目名/N 条未办结/超期标签「⛑ N 天没动静」
  =collect().stale 现成数据/「去项目 →」)+ 卡内按 space 分小节(None→「未标注」末尾)。
- 「按项目 / 按时间」胶囊切换:按时间 = 全项目条目平铺按日期倒序。
- 底部「其余 N 个项目没有未办结事项」灰字;全空态居中轻提示。

### D5 技能页壳 + 设置弹层

- 技能卡 = **真实能力的静态清单**(记一下/整理文件夹/找参考图——不放 CAD 转 3D 等未接
  假卡,README 明说卡片数据是示例;点卡 → 3a 预填调用话术,复用 P2 prefill 钩子)+
  末位虚线「+ 添加技能」卡(本轮无行为)。
- 设置弹层照稿扩行:外观(浅色,静态)/AI 模型(D3 真值)/数据与备份(显示 DS_ROOT)/
  快捷键(静态)/检查更新(VERSION)。

## Key trade-offs / risks

- **D1 碰核心账本行格式**:风险=旧行解析回归/新前缀被伪造。缓解=单正则单一真相源只加
  可选组、space 值剥括号+red-check oracle、无 space 时行格式与 0.4.0 逐字节相同。
- **搜索客户端过滤**:项目数大了要改服务端。接受——当前量级(个位数项目)客户端最简,
  且不加读面;真到量级再加 /api/search 不迟。
- **技能卡静态清单**:加技能要改代码。接受——本轮就是壳,接入机制另 track。

## Alternatives considered

- D1 尾部 `@玄关` 标签 — 与自由文本撞车概率高,弃。
- D1 第二元数据行 — 破单行契约,ds_todo/append/status 全家重写,弃。
- D1 从内容 NLP 推断空间 — 不可靠;弱模型哲学=焊进结构不焊进猜测,弃。
- D2 服务端 /api/search — 多一个读面+多一份解析逻辑,当前数据量不值,弃(留量级触发)。
- D5 照稿放 CAD 转 3D 假卡 — 点了没用=欺骗用户,换成真实能力清单,弃。

## Test strategy (oracle)

- 后端 red-check(先写先红):① space 含 `】`/换行 无法破坏行结构;② 旧格式行 parse 出
  space=None 且 text 不变;③ append(space=玄关)→parse 回读 space=玄关;④ 无 space 时
  行输出与 0.4.0 逐字节相同(向后兼容物理证明)。+ set_model 回环 + 坏 config 时
  health 仍 200 且 model=null。全量 py + mjs 回归零红。
- 前端:搜索过滤/待办分组排序抽纯函数进 mjs oracle;e2e Playwright 真 gateway:⌘K 搜到
  变更并跳转、待办页项目卡+空间小节、技能卡预填、设置弹层显示 model + 0.5.0。
- **Verify lane = full**(D1 碰账本格式 = data-consistency 触发)。主 agent 先审、
  my-review 落 /root/aiwork/tasks/(仓外),oracle 先跑再读 panel。
