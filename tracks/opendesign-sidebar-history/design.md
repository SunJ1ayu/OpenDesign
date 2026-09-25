# Design: opendesign-sidebar-history

- Change: opendesign-sidebar-history
- Status: agreed(4c 挑战 + QA 设计之后定稿)

## Goal-to-design check

- 当前行为 → 拟改变的行为:见 proposal「真问题」。事实:`Sidebar.tsx` `recent = sessions.slice(0, 2)`;「全部」无行为;只能删、不能置顶改名;
  项目栏按阶段分堆、点进工作区;项目小标只来自 localStorage 的项目对话映射。
- 检查深度与触发事实:**独立挑战 + QA 设计 + 小实验**。触发:新写口(置顶 / 改名写网关的侧栏状态文件)、新的跨模块读(ds_web 读网关的对话文件)、
  侧栏主结构改变(业主每天第一眼看的地方)。撤回代价中等(数据写在网关状态文件里,但只动 pinned_keys / title_overrides 两个字段)。
- 关键前提:
  - P1 对话碰过哪些项目可从 `<workspace>/sessions/websocket_*.jsonl` 读出:助手工具调用参数里有项目名。**已查**(本机 300 个对话文件 1.5MB;
    `mcp_design-studio_append_change_tool {"project": "翡翠湾-1801"}` 与项目列表 key 逐字相同;删掉的 e2e 项目对不上 ⇒ 忽略)。
    参数名不止 `project`:`read_project(name)`、`rename_project(old,new)`(4c C4)。分组项目 key =「组:名」,参数可能只写「名」⇒ key 与名字都认。
  - P2 网关会话列表**不认 limit**,一次返回全部(`nanobot/webui/ws_http.py:368-393`,4c 指出、我核实)⇒「显示更多」前端切片;App 现在拼的 `limit=10` 本来就没用。
  - P3 网关自带侧栏状态文件 `~/.nanobot/webui/sidebar-state.json`(`nanobot/webui/sidebar_state.py`):有 pinned_keys / title_overrides,规范化、标题上限 160 字;
    更新接口 `/api/webui/sidebar-state/update?state=<整份 JSON>`,**整份覆盖**(`ws_http.py:715-735`)⇒ ds_web 读 - 改 - 写只动两个字段、加锁。
  - P4 单文件 2000 条消息才截早期记录(`FILE_MAX_MESSAGES`)⇒ 正常用碰不到;项目对话另有映射兜底。
  - P5 项目没有界面改名入口(ds_web 无 rename);改名只经助手 `rename_project` ⇒ 从记录里读改名(旧 → 新)做别名即可。
- 完全实现仍可能失败:① 首页只在嘴上提了项目、助手没动项目工具 ⇒ 归「其他对话」(不承诺,proposal 写明);
  ② 极长的对话被网关截断后早期碰过的项目丢了(P4,延期);③ 业主在资源管理器里手改项目文件夹名 ⇒ 旧对话对不上(锤子砸墙类,不管)。
- 未解决项:无改变方向的。

## 4c 挑战记录(派发前我的方向已落盘在仓外 /root/aiwork/tasks/opendesign-sidebar-history-my-direction.md,未喂给腿)

一条外部腿:**GPT-5.6 sol high**(OpenAI,subcursor,读仓库),题面 `evidence/20260925-design-challenge-brief.md`,原文 `evidence/20260925-design-challenge-gpt.md`。结论「需改」。

| # | 挑战 | 核实 | 取舍 |
|---|---|---|---|
| C1 | 首页只嘴上提项目、没调工具 ⇒ 落「其他对话」;建议「⋯ → 关联项目」人工纠错 | 属实(项目前缀只在项目栏首句) | 不承诺(proposal 已写);人工关联是新功能 ⇒ **延期** |
| C2 | 项目改名后旧对话丢;现有项目对话映射按名字存、改名即丢 | 属实;但界面无改名入口,只有助手 `rename_project` | **采纳一半**:扫描时读 `rename_project(old,new)` 做别名(旧名 → 新名);localStorage 项目对话映射改名即丢是老行为,不在本单 |
| C3 | 长对话超 2000 条被截断,重扫会忘 | 属实(`manager.py:385-406`) | **延期**(正常用碰不到;项目对话另有映射) |
| C4 | 只认参数名 `project` 会漏 `read_project(name)` / `rename_project(old,new)` | 属实(`ds_tools_server.py:146,239`) | **采纳** |
| C5 | 「显示更多」后历史列表没自己的滚动,把项目栏挤出去 | 属实(`app.css` `.side-list` 无 overflow,`.proj-list` overflow:auto) | **采纳**:侧栏中间(置顶 + 历史 + 项目)一整块滚动 |
| C6 | 置顶 / 改名存浏览器存储,清缓存 / 重装就没了 | 属实(App 已把 localStorage 映射视为可丢) | **采纳**:存网关侧栏状态文件 |
| C7 | `limit=200` 不成立,网关列表不解析 limit | 属实(见 P2) | **采纳**:前端切片 |
| C8 | 改成「显式事件写持久索引,扫描只回填一次」 | 扫描得到的结果与索引等价(只差 C3 截断),索引要多维护一份会被改乱的数据 + 改名迁移 | **驳回**;按文件 mtime 缓存扫描结果 |
| C9 | 字段级补丁、锁内读最新状态、保留其余字段 | 属实(P3 整份覆盖) | **采纳** |
| C10 | 置顶后只在置顶区出现一次,不在下面重复 | QA 多家也问 | **采纳** |
| C11 | 删对话时同步清置顶 / 改名 | 合理 | **采纳**(ds_web 删除成功后清这两个字段里的 key) |

影响等级:新写口(ds_web → 网关侧栏状态)⇒ **impact-risk = high**,评审每轮两家不同家族。

## QA 设计(测试员,开发前黑盒,不计评审轮)

题面 `/root/aiwork/tasks/opendesign-sidebar-history-qa-design.md`(evidence 副本 `evidence/20260925-qa-test-design-brief.md`)。人选不固定、每个可用家族一条(业主 09-25):DeepSeek、Grok 4.7、GPT-5.6 terra、
Gemini 3.8 flash、Kimi K3、GLM 5.2、Composer 2.5(MiMo 这两天都挂在只读文件系统上、Kimi 直连周额度、Gemini 直连网络不通 —— 均由 Cursor 同家族覆盖;
直连 Grok / GLM 业主已停)。仓库参数给空目录 `/root/qa-blackbox-repo`。原文 `evidence/20260925-qa-design-*.md`。

七家反复问的,我定(实现细节,不问业主):

| 疑问 | 定 |
|---|---|
| 置顶的对话还出现在原位置吗 | 只在「已置顶」出现一次(C10);该行带项目小标 |
| 多条置顶的顺序 | 最近聊的在前 |
| 项目删了,它下面的对话去哪 | 项目不在列表里 ⇒ 关联忽略 ⇒ 回「其他对话」;项目对话同样 |
| 项目对话能不能置顶 / 改名 / 删除 | 能;删了之后项目页自动开一条新的(已有的自愈) |
| 改名空 / 超长 | 去首尾空格;**空 ⇒ 取消,名字不变**(QA Grok TC-10:手一滑清空回车,起好的名字不能没了;接口仍支持「空 = 清掉改名」,界面不发);最长 160 字(网关上限),显示省略 |
| 「其他对话」空了 | 不显示 |
| 只读过档案算不算碰过 | 算(read_project 也认) |
| 按时间视图碰过多个项目的小标 | 第一个(项目对话优先)+「+N」 |
| 聊天服务断开时 | 同现在:历史整组隐藏(sessions=null);置顶 / 改名 / 删除都碰不到 |
| 默认视图 | 按时间(最接近现在);切换记住(localStorage) |

## Approach

1. **纯逻辑** `web/src/workspace/sidebarModel.ts`:
   - `dayBucket(updated_at, now)` ⇒ 今天 / 昨天 / 更早(本机时区);`timeSections(sessions, now)`。
   - `displayTitle(s, overrides)`:改过的名字优先,否则网关标题 / 预览 /「(未命名对话)」。
   - `sessionProjects(sessionKey, derived, threadMap, projects)`:ds_web 派生的 + 项目对话映射,去重、只留当前项目列表里有的、项目对话在前。
   - `projectView(sessions, projectsOf, pinned)`:每个项目 ⇒ 它的对话(项目对话在前,其余按时间);没碰过项目的 ⇒ 其他;置顶的全部抽走。
   - `cleanRename(raw)`:去空格;空 ⇒ null(界面当取消);超 160 截断。
2. **ds_web**:
   - `GET /api/chat/session-projects` ⇒ `{"sessions": {"websocket:<id>": ["项目 key", …]}}`:读网关配置的 workspace/sessions/websocket_*.jsonl,
     收集 design-studio 工具调用参数(project / name(read_project)/ old,new(rename_project,顺带记别名))+ 首条用户消息「【当前项目:X】」;
     别名展开后按 key 或名字对上当前项目列表;按文件 mtime 缓存。只读。
   - `POST /api/chat/sessions/<key>/pin` `{"pinned": bool}`、`POST /api/chat/sessions/<key>/rename` `{"title": str}`:针孔同删除那一套
     (CT json、body 上限、key 正则、同站),在一把锁里 GET 网关 sidebar-state ⇒ 只改 pinned_keys / title_overrides ⇒ update 写回;返回这两个字段。
   - `GET /api/chat/sidebar-state` ⇒ 只回 `{pinned_keys, title_overrides}`(不把别的字段漏给前端)。
   - 删除针孔成功后,同一把锁里把这个 key 从 pinned_keys / title_overrides 去掉(C11)。
3. **App.tsx**:会话列表不再拼 limit;拉 session-projects 与 sidebar-state(随 sessionsEpoch 刷新 —— 每轮收尾都 bump,新对话首句让助手记账后马上出现在项目下,QA Grok TC-07);置顶 / 改名 / 删除后刷新。
4. **Sidebar.tsx**:置顶区 + 切换「按时间 | 按项目」+ 两种视图;每行「⋯」菜单(置顶 / 取消置顶、改名(行内输入框,Enter 存、Esc 放弃)、删除(沿用确认));
   按时间先 10 条、「显示更多」+20;按项目每个项目行一个 ▸(默认收起,显示条数),展开先 5 条 + 显示更多;「其他对话」同样。
   侧栏中间一整块滚动(C5)。项目行的点击、分堆、折叠不动。

## Key trade-offs / risks

- 置顶 / 改名写网关状态文件:新写口;只动两个字段、锁内读 - 改 - 写;网关没起 ⇒ 502,界面提示「没存上」。
- 扫对话文件:每次侧栏刷新都扫;mtime 缓存后只读变了的文件。业主机器上文件数未知 ⇒ QA / 真机看耗时。
- 碰过项目的判断不完美(C1、C3),不承诺。

## Alternatives considered

- 置顶 / 改名存 localStorage(无写口):清缓存 / 重装会丢,业主整理好的东西没了(C6)。没选。
- 显式事件写持久索引(C8):见上。没选。
- 完全照 ZCode 把项目栏换成「项目 → 对话」树、去掉按阶段分堆:推翻业主 07-28 定的分堆。没选。

## Test strategy (oracle)

- 单测 `tests/test_sidebar_history.mjs`(node --test):dayBucket 边界(今天 00:00 / 昨天 23:59 / 更早)、displayTitle 优先级、sessionProjects 合并去重与项目对话在前 /
  删掉的项目忽略、projectView(多项目都出现、其他对话、置顶抽走、项目对话在前)、cleanRename(空 / 空格 / 超长)。
- Python `tests/test_session_projects.py`:假 workspace + 手写对话文件(工具调用形状照本机真文件)⇒ 派生结果;read_project(name)、rename_project 别名、
  「【当前项目:X】」前缀、组:名 与只写名、对不上的忽略、坏行不崩、mtime 缓存;pin / rename / delete 针孔:用替身网关验证只改两个字段、其余字段原样、
  CT 不是 json 拒、key 非法拒、空标题 ⇒ 删改名、超长截断、删除后清理。
- e2e `tests/e2e/sidebar_history.e2e.mjs`(真 chromium + 真 ds_web + 替身网关接口):按时间分段与显示更多翻到最早;⋯ 置顶 ⇒ 进置顶区、下面不重复;
  改名 ⇒ 行上是新名、再拉一次状态仍在;删除 ⇒ 置顶 / 改名一起没了;切按项目 ⇒ 多项目对话在两个项目下都出现、其他对话;点对话回首页续聊;
  切换记住;项目行点击照旧进工作区。
- QA 执行:真管家 + 真网关 + 真工作台 + 假厂商(发工具调用让对话真碰项目)录像。

**这个 oracle 能被什么骗过?**
- 对话文件是我照本机真文件手写的;真网关写出来的形状若不同(如 arguments 不是字符串)⇒ Python 判据绿、真机空 ⇒ QA 执行用真网关 + 假厂商发真工具调用兜。
- 置顶「重开还在」e2e 用替身网关状态,证不了网关真写盘 ⇒ QA 执行重开软件看。
