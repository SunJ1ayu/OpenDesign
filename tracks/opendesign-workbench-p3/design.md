# Design: opendesign-workbench-p3

- Change: opendesign-workbench-p3
- Status: frozen(2026-07-11;设计已由 Claude Design v2 定稿,无开放分叉,
  panel-explore 不适用;以下是工程落地决策)

## Approach

设计单一真相源 = `handoff/README.md`(v2)。定稿两画板:`3a 新对话`(t3,
默认首页)+ `2a 主工作区`(t2,进项目后);t1 早期探索禁止实现。
**2a 主体不动**——本 track 只动壳(路由/侧栏)+ 新增 3a 页 + 挂载策略。

### 路由与挂载(核心决策)

- Route: `home`(3a,默认 `#/`)| `workspace`(选中项目)| `todos` | `skills`。
  `calendar` 路由与页面删除。项目不进 URL(与 P2 一致,深链非目标)。
- **keep-mounted**:App 始终渲染两个聊天实例——`HomeChat`(3a 页聊天流)与
  `ChatColumn`(2a 右列)——非当前路由用 CSS `display:none` 隐藏,不卸载。
  transcript/ws 状态自然保留;协议每连接一会话,两实例各自独立会话,互不串。
- 「新对话」行为 = 回到 3a **现状**(进行中的对话还在);不重置。真正的
  "再开一条"目前靠刷新页面,会话管理是 T7。⌘N 同「新对话」(UI 不显示角标)。
- 3a 空态(无消息)显示问候语+大输入卡+三 chip;首条消息发出后就地转聊天流
  (样式同 2a 助手列),输入卡缩为常规底部卡。建议 chip = **预填不自动发**
  (与「标记完成」同一预填机制,发送权在人)。

### 侧栏 v2(共用组件,两屏一致)

- 全局操作组:新对话 / 搜索 / 待办事项(计数徽标)/ 技能(›)——日历行删除,
  「待办提醒」改名「待办事项」,技能从项目列表下方上移;快捷键角标(⌘N/⌘K)
  从 UI 移除,keydown 行为保留。
- 16px 图标列:所有行(菜单/历史/项目圆点)共用同宽图标容器居中对齐;
  历史对话行加 ◷(`#b0a996`);当前项目圆点 `#c46a4a`,当前行白底卡片。
- 「新对话」行在 3a 路由下呈当前态(白底卡片+描边+投影+加粗)。

### 聊天逻辑层

`connection.ts` / `transcript.ts` / `markdown.ts` **继续零改动**(硬约束)。
3a 复用 ChatPage 还是另写?——**决策:抽薄不 fork**。ChatPage 的
login/connecting/error/connected 四态与消息流对 3a 完全复用,只是空态与
输入卡尺寸不同 → ChatPage 加展示变体 prop(`variant: "column" | "home"`),
变体只影响 className 与空态 JSX,连接/收发路径一行不差(fork = 两份连接流
必然漂移)。

## Key trade-offs / risks

- **两个常驻 ws 连接**(3a + 2a 各一):gateway 多扛一条闲连接,可接受;
  好处是对话互不销毁、实现最简。不做"单连接共享多视图"(要动 transcript
  归属,T7 范畴)。
- 「新对话」不重置对话:与字面语义有偏差,但重置=亲手复刻"丢对话"事故;
  v2 README 原文是「回到 3a」。accepted deviation,T7 会话管理时再给显式
  "新开一条"。
- keep-mounted 后 TodoPage/SkillsPage 仍每次重建(无状态页,无所谓)。
- 侧栏删日历:功能将来融进待办页,入口先收敛。

## Alternatives considered

- 3a/2a 共享单条 ws 连接与 transcript → 否:要改 transcript 归属与连接编排
  (T6/T7 范畴),且"项目助手"与"总入口"语义本就是两条对话。
- fork 一个 HomeChatPage → 否:两份连接流会漂移,变体 prop 更薄。
- 「新对话」每次重置会话 → 否:等于亲手复刻切页丢对话。

## Test strategy (oracle)

- chat 逻辑层 mjs oracle 31 条原样全绿 = 零改动机械证明;
- 既有 pytest 全量零红(后端零改动,test_ds_web_api 22 条不动);
- Playwright:①3a 首页空态(问候语+三 chip,无日历行/无角标)②chip 预填
  ③3a 发送→流式 ④**切到项目再回 3a 对话仍在(keep-mounted 核心断言)**
  ⑤侧栏 v2 细节 ⑥2a 四列回归截图;
- e2e 真 gateway:3a 登录→发送→流式→切项目→回 3a 对话保留→2a 右列二轮;
- verify lane:**fast**(main + submimo;纯前端壳改、零新攻击面、后端零改;
  P2 用 full 是因为新增文件读出面,本次没有)。
