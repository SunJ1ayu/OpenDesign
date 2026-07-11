# Tasks: opendesign-workbench-p3

- base-ref: 02f3f8acc1bf2fc1cf9fad397d04a98a663b1f84
- 执行方式:主 agent 定计划与验收,**sub Claude(worktree 隔离)承包 T1–T3 实现**,
  主 agent 审 diff + 复跑测试后合并,再走 verify **fast lane**(main + submimo)。

## 实施顺序

- [ ] T1 路由与挂载改造:Route 增 `home`(默认 `#/`)删 `calendar`;App 常驻
      两个聊天实例(3a HomeChat + 2a ChatColumn),非当前路由 CSS 隐藏不卸载
      (keep-mounted);「新对话」/⌘N = 回 3a 现状不重置;ChatPage 加
      `variant: "column" | "home"` 展示变体(只动 className 与空态 JSX,
      连接/收发路径零改动)。
- [ ] T2 3a 新对话页:空态 = 问候语「今天想聊点什么?」(Noto Serif SC 26px/700)
      + 620px 大输入卡(圆角 16px,占位「聊设计、找东西,或直接说「记一下…」」,
      `+`/`✎ 记一下`/`↑`)+ 三建议 chip(「新建一个项目」「这周有哪些变更没
      确认?」「找一张客厅参考图」,预填不自动发);首条消息后就地转聊天流,
      输入卡缩常规底部卡。像素规格按 handoff/README.md §5。
- [ ] T3 侧栏 v2:删日历行;「待办提醒」→「待办事项」;技能上移进全局操作组;
      去 ⌘N/⌘K 角标(keydown 行为保留);16px 图标列全行对齐;历史对话行 ◷;
      项目圆点进图标列、当前=赤陶 `#c46a4a`;「新对话」行在 home 路由呈当前态
      (白底卡片+加粗)。CalendarPage 组件与 `#/calendar` 一并删除。
- [ ] T4 集成收口(sub):`npm run build` dist 进仓;Playwright 截图
      (3a 空态/chip 预填/3a 聊天流/keep-mounted 往返/2a 四列回归)对照
      handoff/screenshots;全量 mjs+pytest 零红。
- [ ] T5 verify(主 agent,不外包):e2e 真 gateway(3a 登录→流式→切项目→
      回 3a 对话保留→2a 二轮)、主审落 my-review、panel fast lane、
      verify.md 收口、合 main 推送。

## 验收红线(sub 交付时主 agent 逐条查)

1. `web/src/chat/connection.ts` / `transcript.ts` / `markdown.ts` diff 为空;
2. `bin/` 与 `tests/` 既有文件 diff 为空(纯前端 track,后端零改动);
3. keep-mounted 用 CSS 隐藏实现,聊天组件不得因路由切换 unmount
   (key 变化 = unmount,同罪);
4. ChatPage 变体只允许出现在 className / 空态 JSX / 输入卡外层样式;
   连接 effect、send、节流缓冲、Enter 判定的代码路径逐字不变;
5. dist 与 src 一致(重构建后 git status 干净)。
