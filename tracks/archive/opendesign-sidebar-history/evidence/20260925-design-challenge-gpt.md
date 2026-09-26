Direction:
只做一个方向：保留「按时间｜按项目」双视图，但把对话归属改成“显式事件写入持久索引”，历史扫描仅用于一次性回填；置顶、改名统一存 nanobot 的 sidebar-state，视图与折叠偏好才存 localStorage。

Core bet:
业主真正要的是能稳定找到并续聊，而不是形式上复刻 ZCode；假设单人 Windows 环境允许本机窄写口，代价是增加一个 OpenDesign 管理的关系索引和“关联项目”纠错入口。

How it works:

1. 完全照做仍会怎样失败
- 在首页谈到某项目但助手没调用项目工具时，该对话会落入“其他对话”，因为项目前缀只在项目列第一条消息发送，见 `web/src/chat/ChatPage.tsx:690-705`。
- 项目改名后，旧对话可能从新项目下消失或显示旧项目，因为现有映射以可变项目名为键且注释明确承认改名会丢映射，见 `web/src/chat/projectThread.ts:6-9`、`bin/ds_tools_server.py:239-244`。
- 一条长对话早期碰过项目、后来超过 2000 条消息时，重扫可能忘掉该项目，因为会话文件会裁掉旧前缀，见 `nanobot/session/manager.py:28`、`nanobot/session/manager.py:385-406`。
- 仅按参数名 `project` 扫描会漏掉 `read_project(name)` 与 `rename_project(old,new)`，见 `bin/ds_tools_server.py:147-150`、`bin/ds_tools_server.py:239-244`。
- “显示更多”后侧栏可能把项目和设置挤出首屏，因为历史列表没有独立滚动，而只有项目列表设置了 `overflow:auto`，见 `web/src/app.css:258-311`。
- 若置顶、改名选 localStorage，用户清缓存或重装后会看到全部恢复原样；仓库现有项目会话映射已明确把这种存储视为可丢数据，见 `web/src/App.tsx:138-148`。

2. 必须推倒重做的前提
- 必须推倒的是“当前会话文件可作为完整、稳定的对话—项目真相源”这一前提，因为文件会截断、项目名可变，而且不同工具的项目参数结构不一致，证据见上述 `nanobot/session/manager.py:385-406` 与 `bin/ds_tools_server.py:147-150,239-244`。
- “会话列表支持 limit=200”也未核实成立：App 和 ds_web 虽传递查询串，但 nanobot 列表接口不解析它、直接返回全部会话，只有单会话 thread 接口解析 limit，见 `web/src/App.tsx:322-327`、`bin/ds_web.py:2477-2480`、`nanobot/webui/ws_http.py:368-393,430-453`。
- 项目没有不可变 ID，前端模型只有可改名的 `key/name`，所以任何持久关系索引都必须处理 rename 迁移，见 `web/src/api.ts:5-8`。
- `review.diff` 为空，因此目前只有方案、没有可审查实现，所有并发与迁移行为仍属未核实。

3. 更简单、更稳的机制
- 新项目对话在 `onColChatId` 已同时知道 chatId 和项目，应立即写入关系索引，而非日后猜测，见 `web/src/App.tsx:176-181`。
- 在线收到项目工具事件时追加关系，收到 rename 时迁移旧键；首页无明确事件的对话留在“其他对话”，并通过“⋯ → 关联项目”人工纠错。
- 旧会话只扫描一次用于回填，之后索引增量维护；删除会话时同步清理关系、置顶和标题记录。
- 会话列表直接使用网关已经返回的全集，前端先显示固定数量、点击“显示更多”扩大本地切片，不再虚构后端分页。
- 置顶与标题存 nanobot sidebar-state：它已有 `pinned_keys/title_overrides`、规范化和原子替换，见 `nanobot/webui/sidebar_state.py:35-49,132-147,167-194`。
- ds_web 应提供字段级 patch，在锁内读最新状态后只改这两个字段并保留其余字段，因为原生更新接口接收并覆盖整份状态，见 `nanobot/webui/ws_http.py:711-735`。
- 「按时间｜按项目」与折叠状态可留 localStorage，丢失只会回到默认“按时间”，不会损失用户整理成果。

Best at:
适合当前单人、本机、会话量有限但要求重启、清缓存后仍可靠的 Windows 安装版，并避免每次刷新扫描大量 JSONL。

Sacrifices:
首页里仅口头提到项目的对话不会自动百分百归类，需要一次人工关联；同时要维护一个关系索引及项目改名迁移逻辑。

Blind spots in the brief:
置顶对话是否还应在项目下重复出现没有定义；建议置顶后只在顶部出现一次，否则多项目对话会形成大量重复行，另外真实会话数量、项目改名频率及业主对“碰过项目”的理解均未核实。

Smallest first step:
只做两条真实对话的纵向实验：一条从项目列创建、一条从首页谈同一项目但不调工具，将前者显式写入关系索引、后者手动关联，并把两条的置顶/改名写入 sidebar-state，然后清空 localStorage、重启并改项目名；若关系与标题仍正确且其他 sidebar-state 字段未被覆盖，即能区分该方向与“反复扫历史＋浏览器存储”。

结论: 需改
