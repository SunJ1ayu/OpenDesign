# Design: opendesign-todo-assistant

- Change: opendesign-todo-assistant(设计交付包 v4 §I.9 第三段 + 前置的路由改造)
- Status: decided(无开放架构分叉,未跑 panel-explore)

## Approach

两块,顺序有依赖:**A 先把待办页改成常驻路由,B 才能把聊天挂进右栏**。

### A. 待办页 keep-mounted(前置地基)

现状 `App.tsx:452` = `{route === "todos" && <TodoPage/>}`,离开即卸载
(源码注释:「无状态页,每次进入重建」)。挂 `ChatPage` 进去 = 切页丢对话
(track p3 花一整单治过的真机 bug)。

改法**照抄仓里已有的常驻页写法,不另立第二套**:

```tsx
<div className={`todos-pane${route === "todos" ? "" : " route-hidden"}`}>
  <TodoPage active={route === "todos"} dataEpoch={dataEpoch} … />
</div>
```

`.route-hidden { display:none !important }`(app.css:135)与 home-pane / ws-pane 同款。

**保鲜约定也照抄既有的**:`CompanionColumn` 已经在吃 `active` + `dataEpoch`
(App.tsx:426-427,组件内 `if (!active) return;` + deps `[…, dataEpoch, active]`)。
TodoPage 的取数 effect 同样改成:

```ts
useEffect(() => { if (!active) return; …fetch… }, [reloadNonce, dataEpoch, active]);
```

由此得到三条可断言的性质:
1. **进入页面必refetch**(与今天"卸载重建"的可观察行为一致);
2. **隐藏时不取数**(没打开过待办页就不该发这个请求);
3. **隐藏期间 DOM 不卸载**(这才是本单的目的)。

> **本单的铁律:keep-mounted 是一次重构,唯一允许被用户观察到的行为变化是
> 「右栏对话切页不丢」。数据新鲜度、过滤态、批量选中等一切其余行为必须不可区分。**

### B. 右栏项目助手

`TodoRail` 追加第三段 `[data-ui="rail-assistant"]`,两态:

- **收起态(默认)**:一句能力说明 + 单行输入卡 +「发送」文字按钮(统一输入范式)。
- **展开态**:`ChatPage` 真身占满右栏,月历与跟进区 `route-hidden` 让位;可收回。

**绝不写第二套聊天 UI**:展开态直接挂 `ChatPage`(560 行的真身)。App 里
home 与工作区列已经共享同一个 `ChatSession` 实例,**第三个实例结构上同构**,不是新架构。

`ChatPage` **常驻挂载、收起态用 CSS 隐藏**(与 p3 keep-mounted 同规矩):
卸载 = 丢对话,而"收起再展开对话还在"正是本单要交付的东西。

**不吞用户打的字(主 agent 加的约束,设计稿没写)**:提交时——
- 已连接 → `dispatch={{text, nonce}}`(程序化发送,复用 CompanionColumn「接入工作区」的既有通道)
  并清空右栏输入框;
- 未连接 → **展开露出连接卡,但右栏输入框里的字原样留着**,附一句提示。

> 曾考虑未连接时走 `prefill` 把文字塞进聊天输入框 —— **查了源码后否掉**:
> `ChatPage` 在 `view.kind === "login"` 时**提前 return 只渲染连接卡,根本没有输入框**
> (ChatPage.tsx:372),`prefill` 只会落进一个看不见的 state。用户视角 = 字被吃了。
> 留在右栏自己的输入框里,字看得见、连上后再按一次发送即可。

连接态由 `ChatPage` 既有的 `onConnected` 回调在 TodoRail 内记一个 flag。

**「记一下」需含项目名 / 识别不出则追问 = agent 行为,前端无事可做**:
右栏助手是跨项目入口,**刻意不传 `firstSendPrefix`**(工作区列才传项目前缀)。
前端能做的只有在说明文案里提示带项目名。该追问行为**无真 gateway 无法验证**,记入 verify。

## Key trade-offs / risks

- **第三个 ChatPage 实例**:三处共享同一 `ChatSession`。现有两处已证明可共存,但这是本单
  最大的未知面 → verify 走 **full 四审**,并要求评审重点看会话/attach 记账有无串扰。
- **常驻后首帧成本**:待办页 DOM 常驻(月历 42 格 + 卡片)。用 `active` 门住取数,
  没打开过就不发请求;DOM 常驻的内存代价可接受(home/ws 两个 pane 早已如此)。
- **无 gateway 的验证边界**:真正的"发出去并收到回复"必须有 gateway。本单 oracle 覆盖到
  「未连接时文字不丢 + 连接卡出现 + 收起展开不丢 DOM」为止,发送链路交装机验收。

## Alternatives considered

- **只在展开时挂 ChatPage**:省一个常驻实例,但收起就丢对话 —— 与本单目的直接矛盾。否。
- **右栏自己写一个轻量对话流**:第二套聊天 UI,注定与 ChatPage 漂移(markdown/流式/重连/
  attach 全要再实现一遍)。否。
- **「展开对话 →」跳到新对话页**:那是**另一条 thread**,点开看到的不是刚发的内容 = 撒谎。
  按设计稿截图,它就在助手区标题右侧 ⇒ 语义是**就地展开**。否(不做跳转)。
- **不做 keep-mounted,改成每次进入恢复对话**:要把 transcript 提到 App 或持久化,
  比常驻挂载复杂得多,且 p3 已经为这个问题选定了 keep-mounted 方案。否。

## Test strategy (oracle)

主 agent 亲写、先 commit 再派活,执行腿逐字节 off-limits。**无 gateway**(真发送交装机):

`tests/e2e/todo_assistant.e2e.mjs`
1. **keep-mounted 三性质**:①离开待办页后 `.todo-page` **仍在 DOM**(带 route-hidden 祖先);
   ②回到待办页 UI 态**保留**(日期过滤仍在、折叠的卡仍折叠)——这是"没被卸载"的行为面证据;
   ③**回到页面会重新取数**(测试直接改磁盘上的 .md 加一条变更 → 切走再切回 → 新条目出现);
   ④**隐藏期间不取数**(数 `/api/todos` 请求次数:停在别的页面时计数不涨,进入待办页才涨)。
   注意 ④ **不能**写成"没进过待办页时计数为 0" —— `api.ts:101` 有第二个调用方
   (侧栏未办结角标,App 挂载即拉),那样写会因合法原因红。
2. **右栏助手**:收起态有说明 + 输入 +「发送」;`ChatPage` 此时**已在 DOM 但隐藏**;
   点「展开对话」→ 展开且月历/跟进区让位;收起 → 月历回来且聊天节点**仍在 DOM**。
3. **不吞字(未连接)**:收起态输入文字 → 提交 → 助手展开、出现连接卡、
   且**刚打的文字出现在聊天输入框里**(没丢)。
4. **回归**:月历圆点/日期过滤/跟进区/主列表多列/批量选择在常驻化后全部不变
   (直接复跑既有 `todo_rail` 与 `todo_layout` 两份 e2e)。

红检:实现前 `.todo-page` 在离开后不存在 → 整份红。
