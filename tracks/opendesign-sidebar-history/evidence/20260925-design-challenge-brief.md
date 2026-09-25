# 方案挑战:OpenDesign 侧栏「历史对话 + 项目」照 ZCode 改(方案一 + 方案二一起)

你是独立的方案挑战者。仓库在当前目录(design-studio,产品名 OpenDesign:室内设计师用的本地桌面助手,Electron 窗口里是 React 网页 `web/src`,
本机后台 `bin/ds_web.py`(Python,代理到 nanobot 网关),聊天经 WebSocket 连本机 nanobot 网关)。业主不是程序员,Windows 11 安装版,单人使用。
**不要联网;不要改任何文件;不要读 `tracks/*/verify.md`、`tracks/*/design.md`、`tracks/*/proposal.md` 与任何 `*my-review*` / `*my-direction*` 文件。**
nanobot 源码在 `/root/.venvs/design-studio/lib/python3.12/site-packages/nanobot/`(读得到就读;读不到请明说,别猜)。

## 来由(区分业主原话和我们的推导)
- 业主 09-24/25 看 ZCode 后:「历史对话和项目怎么参考一下zcode」;看完我们给的两个方案的对照图后:「直接方案一和方案二一起做吧」。
- **两个方案的内容是我们提的**:
  方案一 = 历史对话看得全(按 今天 / 昨天 / 更早 分段,多了点「显示更多」)、常用的能置顶、每条右边「⋯」:置顶 / 改名 / 删除;项目栏不动。
  方案二 = 照 ZCode「按项目」:每个项目下面挂着和它有关的对话,没碰过项目的放「其他对话」;能切「按时间」。

## 现状(已核实)
- 侧栏 `web/src/workspace/Sidebar.tsx`:历史对话只显示最近 2 条(`recent = sessions.slice(0, 2)`),「全部」按钮没做;每条可删(确认在 App);
  碰过「项目对话」映射的对话有项目小标。项目栏按阶段分堆(折叠状态存 localStorage),点项目进工作区。
- `web/src/App.tsx:322` 经 ds_web 代理拉 `/api/chat/sessions?limit=10&direction=latest`(网关 `/api/sessions`,支持 limit;无 offset)。
- 「项目对话」:每个项目一条工作对话,项目→chat_id 映射存 localStorage(`web/src/chat/projectThread.ts`);项目对话首句带前缀「【当前项目:X】」。
- 对话存在网关工作区 `<workspace>/sessions/websocket_<chat_id>.jsonl`;助手调用项目工具(`bin/ds_tools_server.py`:append_change / set_stage /
  log_communication / read_project(name) / rename_project(old,new) … 多数参数名 `project`)时,参数原样记在对话文件里。单文件 2000 条消息后才截早期记录。
- 网关自带一个侧栏状态文件 `~/.nanobot/webui/sidebar-state.json`(`nanobot/webui/sidebar_state.py`:pinned_keys / archived_keys / title_overrides /
  tags_by_key / collapsed_groups / view;HTTP `/api/webui/sidebar-state` 与 `/update`,整份覆盖写、会做规范化)。ds_web 现在不代理它。
- 标题由网关用模型生成(`nanobot/session/webui_turns.py`)。

## 拟议的改变(被挑战的对象)
用户层:侧栏一个切换「按时间 | 按项目」(记住上次选的,默认按时间)。「已置顶」区在最上。
按时间 = 方案一(历史对话分段 + 显示更多 + ⋯ 菜单),下面项目栏照旧;按项目 = 项目栏照旧,每个项目行能展开它的对话(项目对话在前),最下「其他对话」。
规则:一段对话碰过哪个项目,就在哪个项目下都出现。
机制:对话列表一次多拉(如 200 条);ds_web 新增只读接口,扫对话文件里项目工具调用参数 + 首句前缀,得出「对话 → 碰过的项目」,并上前端的项目对话映射;
置顶 / 改名存网关自带的侧栏状态文件(ds_web 开窄写口,读-改-写只动 pinned_keys / title_overrides),或存本机浏览器存储(无新写口,重装 / 清缓存会丢)—— 待定。
不改 nanobot。

## 请回答(先从业主目标推演,再挑机制;没有就说没有,不必凑)
1. 这个改变**完全照做**之后,业主的目标仍会怎样失败?(具体到操作步骤与会看到什么)
2. 哪个前提若为假,就得推倒重做?请尽量读代码核实,给出 `文件:行` 证据;核实不了的标「未核实」。
3. 有没有更简单或更稳的方向?用什么**最小实验**能分辨它和拟议方案?尤其:置顶 / 改名存哪。

输出:按 1/2/3 分节,每条一句结论 + 证据;最后一行写 `结论: 可行 / 需改 / 不可行`。
