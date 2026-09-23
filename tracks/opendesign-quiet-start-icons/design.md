# Design: opendesign-quiet-start-icons

- Change: opendesign-quiet-start-icons
- Status: approved(业主 09-23 两次拍板)

## Goal-to-design check

- 当前行为 → 拟改变的行为:冷启动顶上挂一条中文横幅几秒 ⇒ 什么都不显示;侧栏符号 ⇒ ZCode 同款线条图标。
- 检查深度与触发事实:**直接验证**。纯界面、局部可逆、不动契约/写口/权限;业主已看过 ZCode 对照并拍板。
- 关键前提:① ZCode 启动无文字 —— 源码 `packages/ui/src/root/RootStartupLoading.tsx` 只有居中 logo,文字只进 aria-label(已核);
  ② ZCode 侧栏用 lucide 图标 —— `WorkspaceSidebar.tsx` import Search/Blocks/CalendarClock,`NewTaskButtonGroup.tsx` MessageCirclePlus,
  `WorkspaceSidebarFooter.tsx:382` Settings(已核);③ 横幅只挂几秒 —— 业主真机原话「挂几秒差不多」。
- 完全实现仍可能失败:某次真遇到后台要等一两分钟时,业主只看到转圈、不知道为什么。**业主已知情并选择不留字**(我先提过「20 秒后才出小字」的折中,他答「这种东西肯定不能显示出来」)。
  若后台真起不来,管家 fatal / 意外退出仍会弹框并退出(bs4/bs5 不动),不会永远转圈。

## Approach

- `web/src/backendState.ts` 删掉;App.tsx 去掉横幅与只为横幅存在的 backendState 订阅;`.backend-banner` CSS 删掉。
  preload/main 的 `od:backend-state` 通道保留(bs*/s4 前半仍守着;以后若要做别的就绪动作可用)。
- 新 `web/src/workspace/icons.tsx`:五个 lucide 1.47.0 图标内联 SVG,`stroke="currentColor"`、`strokeWidth=2`、16px,文件头放 ISC 许可。
- Sidebar.tsx 五处 `.ico` 换成组件;历史行 `.ico` 去掉;CSS `.side-row .ico` 改成 flex 居中装 SVG。

## Test strategy (oracle)

新 `tests/test_quiet_start_icons.mjs`(node --test,静态读源码):
- q1 App.tsx 不再渲染 `backend-connecting` / 不 import backendState;web/src 里找不到「正在启动后台」。
- q2 Sidebar 五行各用 SVG 图标组件;侧栏里不再有 ✳⌕◎✦◷⚙ 这六个字符。
- q3 icons.tsx 里五个图标的 path 与 lucide 1.47.0 逐字相同(防手抄走样)、stroke=currentColor、带 ISC 许可头。
- q4 历史对话行不再有前置 `.ico`。
改旧判据(迁移账,verify 里逐条记):test_desktop_instant fb1/fb3 删(对象没了)、s4 后半改为「App 里没有横幅」;
e2-drive E2.connecting 反过来断言「窗口栏出来那一刻**没有**横幅」,E2.noreload 改用「后台就绪后整页只导航一次」判,不再借横幅消失。

**这个 oracle 能被什么骗过?** 静态断言全绿但:SVG 在 Windows 上没画出来 / 太大太小 / 颜色没继承 / 行高被撑歪。
要靠真渲染截图接:本地 vite build 后用 Chromium 截侧栏图亲眼看,云 Windows e2e 截图 e2-01-ui 再看一次。
