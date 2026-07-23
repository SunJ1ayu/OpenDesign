# Tasks: opendesign-todo-assistant

- base-ref: 92fd421e2ad47a2e21a694783a3412f2cf6c40f9(main,ds-web 0.37.0)
- oracle:`tests/e2e/todo_assistant.e2e.mjs`,执行腿**逐字节 off-limits**

> 执行腿 = Sonnet 5 worktree。判据由主 agent 拥有;不 push / 不 merge / 不归档。

## A. 待办页 keep-mounted(前置地基)

- [x] **T1 `App.tsx`**:`{route === "todos" && <TodoPage/>}` 改成常驻 +
      `<div className={`todos-pane${route === "todos" ? "" : " route-hidden"}`}>` 包裹,
      **写法照抄同文件里的 home-pane / ws-pane**,不要另创隐藏机制。
      新传两个 prop:`active={route === "todos"}`、`dataEpoch={dataEpoch}`。
      `skills` / `gallery` 两个路由**保持原样不动**(不在本单范围)。
- [x] **T2 `TodoPage.tsx`**:接 `active` / `dataEpoch`;取数 effect 改成
      `useEffect(() => { if (!active) return; …fetch… }, [reloadNonce, dataEpoch, active])`
      —— **照抄 `CompanionColumn` 已有的同款约定**(它就是这么写的)。
      得到:进入页面必取数、隐藏期间不取数、隐藏时不卸载。
      **除此之外不许有任何可被用户观察到的行为变化**(过滤态、批量选中、折叠态、
      toast、编辑态一律保持)。

## B. 右栏项目助手

- [x] **T3 `TodoRail.tsx`**:追加第三段 `[data-ui="rail-assistant"]`,两态。
      收起态:一句能力说明(**文案里要提示带项目名**,「记一下」的项目归属靠它)+
      单行输入 `[data-ui="rail-ask"]` + 文字按钮 `[data-ui="rail-send"]` +
      展开入口 `[data-ui="rail-expand"]`;展开态:`[data-ui="rail-collapse"]` 收回。
      展开时月历段与跟进段加 `route-hidden` 让位(**CSS 隐藏,不卸载**)。
- [x] **T4 `TodoRail.tsx` 挂 ChatPage**:`[data-ui="rail-chat"]` 包住 `ChatPage` 真身,
      **常驻挂载、收起态 CSS 隐藏**(卸载=丢对话,与 p3 keep-mounted 同规矩)。
      **绝不自写第二套聊天 UI。** 跨项目入口 → **刻意不传 `firstSendPrefix`**。
      需要 `session` 从 App 经 TodoPage 透传进来。
      variant 用 `"home"`(而非默认 `"column"`)——`column` 变体的登录卡藏在
      `ChatPage` 私有的 `bannerOpen` state 后面,外部够不着,无法满足 T5「未连接
      提交立即露出连接卡」;design.md 引的 ChatPage.tsx:372 早退分支本就专指
      `variant==="home"` 那支,与本选择一致。
- [x] **T5 提交行为(不吞字)**:已连接 → `dispatch={{text, nonce}}` 并清空输入框;
      **未连接 → 展开露出连接卡,输入框里的字原样留着**(ChatPage 在 login 态提前 return、
      根本没有输入框,所以不能用 prefill——详见 design.md)。
      连接态用 `ChatPage` 既有的 `onConnected` 回调在 TodoRail 内记 flag。
      ⚠️ 执行腿发现:`ChatPage` variant="home" 的登录态在 App 里同时存在两份
      (home-pane 常驻的那份 + 本单右栏这份),都带 `data-ui="connect-card"`——
      oracle `tests/e2e/todo_assistant.e2e.mjs:159` 用裸 `[data-ui="connect-card"]
      .first()`(未像 `frontend_p2_polish.e2e.mjs:113` 那样限定 `.home-pane` /
      `rail-chat` 前缀),`.first()` 恒定命中 home-pane 里隐藏的那份,5s 超时。
      已用临时脚本证实:限定到 `[data-ui="rail-chat"] [data-ui="connect-card"]`
      后行为完全正确(可见+不吞字)。判定为 oracle 选择器缺前缀限定的 bug,
      未改 oracle 一字节,交主 agent 裁决;详见交付报告。
- [x] **T6 `app.css`**:助手段样式(说明文案 / 输入卡 / 发送按钮 / 展开收起);
      展开态让聊天区占满右栏高度。**既有月历、跟进区、多列瀑布规则不动。**
      (320px 右栏比 3a 整片主页窄,额外收窄了 `variant="home"` 空态的留白/字号,
      纯样式微调,不改行为。)

## C. 收口

- [x] **T7 自检**:`node tests/e2e/todo_assistant.e2e.mjs` 21/22 项通过,1 项因
      上述 oracle 选择器问题超时(详见 T5 注 + 交付报告)+ 全量 mjs 199/199 +
      `tsc -b` rc=0 + `npm run build` 成功 + **相邻 e2e 全部不回归**
      (`todo_rail` / `todo_layout` / `todo_batch_space` / `duedate` /
      `frontend_p2_polish` / `frontend_p3_polish` / `cockpit` / `intake` 均
      ALL PASS)。
- [x] **T8 VERSION**:`bin/ds_web.py` VERSION → `0.38.0`(唯一允许的后端改动)。
