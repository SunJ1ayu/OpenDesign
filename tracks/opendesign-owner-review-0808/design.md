# Design: opendesign-owner-review-0808

- Date: 2026-08-08
- Base ref: (filled by `track new`)

## 选定方向(非架构分叉,不开 panel-explore)

三处修改,互相独立,不冲突:

### A. AGENTS.md:建档前先核对

`workspace/AGENTS.md` §4(约第123行)加一句:遇到消息里提到一个项目/业主,但**没有**
`【当前项目:X】`前缀锁定时,先 `list_projects` 或 `read_project` 核对是不是已经建过档
(按业主名/项目名两头对),明确查过、确实找不到才 `create_project`;查到疑似已存在但
名字对不上,问设计师,不许直接认定是新项目。

### B. AGENTS.md:工具做不到时必须先问

`workspace/AGENTS.md` §5 附近加一句(呼应现有"拿不准就问,别臆造"):设计师要求的动作
**当前没有对应工具**时(比如"删除"在补 delete_change 之前根本不存在),必须明说"这个我
做不到,只能 XX,你要哪个",不许自己挑一个动作顶上再回报"做完了"。

### C. 单条变更软删除(核心工作量)

**数据模型**:复用现有"状态"字段,新增第五个状态字面量 `已删除`(不新开一套字段/
不建独立的 trash 文件,变更行还是那一行,只是状态位改写)。这与 `delete_project` 的
"回收站式、不真删、可捞回"是同一心智模型的最小版本——**捞回不做成一键工具**(和
`delete_project` 现状一致,那个也没有对应的"restore"工具,捞回是"文件还在、手改得回来"
级别的可逆,不是"点一下按钮变回来"级别;真需要一键恢复,等真需求出现再加,不在本次
scope)。

**唯一真相源的两处解析必须同步改**(否则出现"两份状态词表"分裂,ds_todo 7-06 panel
已经踩过这类坑):
- `bin/ds_tools.py:39` `STATUSES` **不加** `"已删除"` —— 那个词表是 `set_change_status`/
  `edit_change` 的校验面(词表内四态互转),`已删除` 只有 `delete_change` 一个专用出口
  能写。见下"为什么单开工具",以及锁死这条的 `test_dc06`。
  > (2026-08-08 四审 DeepSeek/Kimi 双腿同时指出:这一行原来写的是"`STATUSES` 加
  > `已删除`",与下面第 49 行"不加"自相矛盾。实现跟的是"不加"这一侧并有判据锁定,
  > 是这一行的文字错了,不是实现漂移 —— 照原文去改代码会当场被 test_dc06 打脸。)
- `bin/ds_todo.py:20-25` `STATUS_WORDS`/`CHANGE_RE` 加 `已删除`,否则打上这个状态的行
  在 `parse_change` 眼里直接"不存在"(正则不命中,C 编号、日期全部读不出来),
  会连带破坏 `_changes` 端点的"四状态全量"承诺和其他扫描该行的代码(哪怕当前没有,
  以后新增功能扫全量变更行时会静默漏掉这些行——宁可让它们"可见但被过滤掉",
  不要让它们对解析器"隐形"）。

**为什么单开 `delete_change` 工具,不直接开放 `set_change_status(..., status="已删除")`**:
- AGENTS.md 里 agent 的操作契约把"删除"和"改状态"当成两件事讲给设计师听
  ("我做不到删除,只能改状态"这句解释就是这次问题的根)。既然产品决定要有真正的
  删除入口,就应该有一个语义对应的工具名,agent 才能在决策时直接匹配"用户说删除→
  调 delete_change",不用再去踩"状态里混进一个「已删除」到底算不算改状态"这种
  语义模糊(现有契约§2"状态只进不删"讲的是待确认→进行中→已完成/已关闭这条线,
  "已删除"不是这条线上的一环,是另一件事,工具分开、语义才干净)。
- `set_change_status` 的四态校验(`bin/ds_tools.py:240`)不加 `已删除`
  到它能接受的调用参数里(即:`set_change_status` 报错时的 `STATUSES`
  提示仍只列四个可推进状态;`delete_change` 内部才允许写入第五个字面量)。
  实现上：`delete_change` 复用 `set_change_status` 的行定位+加锁写入逻辑(不重写
  一遍正则/加锁),但对外是独立函数/独立 MCP 工具,校验路径不共享。

**delete_change(project, change_id) 行为**:
- 定位到 `C<change_id>` 那一行(复用 `set_change_status` 现成的 `line_re` 定位逻辑),
  找不到 → `change_not_found`(与 `set_change_status` 一致的错误面)。
  项目不存在 → `project_not_found`。
- 把该行 `[状态]` 位改写成 `[已删除]`,**不删行、不改行内其余内容**(C 编号/日期/
  正文原样保留,和其它状态转换的写法完全对称)。
- 返回 `{"ok": True, "old_status", "new_status", "line", "cnum"}`(= 与
  `set_change_status`/`set_due_date` 同族的返回形状,因为落地那一步是共用的
  `_rewrite_change_status`)。
  > (2026-08-08 四审 Kimi 指出:这一行原来写的是 `{"ok", "project", "change_id"}`,
  > 与实现不符。实现的形状与相邻写口一致、更自洽,是这份设计稿写岔了。)

**展示层跟着改**(否则"删了"但列表里还看得见,等于没删):
- `bin/ds_todo.py` `OPEN_STATUS` 不用动(`已删除`本来就不在"未办结"里,`list_todos`
  自动不显示——这条白拿)。
- `bin/ds_web.py` `_changes` 端点(约903行,"四状态全量,单一真相源")**要把
  `已删除` 从返回列表里过滤掉**——现有注释说"四状态全量"是历史表述,产品决定
  从"全量"变成"全量减已删除",这处注释要跟着改,别留一句和代码对不上的话。
- 新增写口 `/api/changes/delete`(POST),对齐现有 `EDIT_CHANGE_PATH`/`ADD_CHANGE_PATH`/
  `DUE_DATE_PATH` 的精确匹配 + 校验模式,内部调 `ds_tools.delete_change`。

**前端(ds-web)**:
- `TodoPage.tsx` 每条待办加一个删除按钮(图标即可,不用文字站位)。
- 点击 → 二次确认弹窗(确定/取消),这是用户本轮明确要的交互,防误触。
- 确定 → 调新端点 `/api/changes/delete`,成功后本地从列表移除(不用整页刷新)。
- 同步补 `web/src/api.ts`/`web/src/workspace/changes.ts` 里对应的请求封装,
  和其它三个写口(edit/add/due)保持同一套错误处理/loading 模式,不另起一套。

## Oracle(主 agent 亲自写,先 commit)

Python 侧(pytest):
1. `test_ds_tools.py`(或新开 `test_ds_change_delete.py`,视现有文件组织决定):
   - `delete_change` 把目标行状态改成 `已删除`,其余字段(C 编号/日期/正文)逐字节不变。
   - 项目不存在 → `project_not_found`;change_id 不存在 → `change_not_found`。
   - 删除后原地再读文件:该行确实还在(没被物理删除),只是状态位变了。
2. `test_ds_todo.py`:
   - 一条 `已删除` 状态的行,`list_todos`/`collect` 的 `open` 列表里看不到它
     (哪怕它是全项目唯一一行,也不能报错或漏别的行)。
   - `parse_change` 对 `已删除` 行必须命中(不是 None),字段解析和其它状态一致——
     这条专门锁"正则要认得这个新状态"，防止以后有人只改 `STATUS_WORDS` 常量、
     忘了正则跟着改(或反过来)。
3. `test_ds_web_api.py`(或 `test_ds_tools_server.py` 视现有分工):
   - `/api/projects/<key>/changes` 全量端点,一条 `已删除` 的行**不出现**在返回里,
     其余状态原样都在(专门锁"过滤掉已删除,不是过滤掉别的")。
   - `/api/changes/delete` 成功路径 + 项目不存在/编号不存在的失败路径(状态码对齐
     现有三个写口的约定,照抄不新发明)。

前端(mjs,对齐现有 `test_todo_batch.mjs` 等的跑法):
4. `test_todo_delete.mjs`(新增):
   - 待办条目渲染出删除按钮。
   - 点删除 → 出现确认/取消弹窗,**点取消不发请求、条目还在**(这条专门防"忘了接
     取消分支,点哪个都在删"这种低级 bug)。
   - 点确定 → 调用删除接口,成功后条目从列表消失。

以上 4 类判据全部**先写、先跑红**(确认当前代码真的过不了),再进 tasks.md 的实现步骤。

## 风险 / 边界

- 现有 78+ 处 `.md` 变更行是纯文本,新状态字面量不需要迁移脚本——旧文件里没有
  `已删除` 这个词,新增枚举值对存量数据零影响。
- `ds_lint.py` 没有引用状态词表(已核实,见调查记录),这次改动不用碰它。
- 前端 `web/src/todo.ts`/`app.css`/`api.ts` 里可能已有基于四态的类型/样式枚举
  (TS union type、状态色板),实现阶段要搜一遍这几个文件,`已删除` 状态**不需要**
  加进"可显示"的枚举——它在 UI 里永远不会被渲染成一个状态徽标,只会导致条目
  从列表消失,所以 TS 类型层面不用加第五个值,除非类型检查因为后端多返回一种
  状态字符串而报错(视实现时 tsc 结果决定要不要放宽类型)。
