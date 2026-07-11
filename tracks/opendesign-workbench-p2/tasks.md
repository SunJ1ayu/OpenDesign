# Tasks: opendesign-workbench-p2

- base-ref: 416fabdea70c368298f4739ccb03af0e0f7f8c12
- 执行方式:主 agent 定计划与验收,**sub Claude(worktree 隔离)承包 T1–T4 实现**,
  主 agent 审 diff + 复跑测试后合并,再走 verify full lane(panel-review)。

## 实施顺序

- [ ] T1 后端只读 API + oracle 先行:`tests/test_ds_web_api.py`
      (projects / changes / refs 列表 / refs 静态文件安全闸,含 symlink 逃逸
      用例与 red-check)→ `bin/ds_web.py` 实现四条 GET 路由;解析复用/抽取
      ds_todo,不造第二套正则。既有 test_ds_web*.py 零红。
- [ ] T2 前端四列工作区外壳:`app.css` 暖纸面 token 全套 + `App.tsx` 重写为
      四列布局;侧栏(品牌/新对话/搜索占位/待办计数=api/todos/日历占位/
      历史对话=api/chat/sessions/项目列表=api/projects/技能占位/设置弹层
      向上弹出);中央变更记录列(api/changes 真数据 + 筛选胶囊:未办结=
      待确认+进行中/待确认/进行中/全部;状态胶囊四色;hover「✓ 标记完成」=
      聊天预填,不写库)。像素规格全按 handoff/README.md。
- [ ] T3 伴随列 + 聊天列重排:图片区(参考/效果分段切换 + 2×2 缩略格接
      api/refs + 静态路由,空索引空态;「+N 图墙」入口占位)、文件区
      (按稿画壳,空态占位文案)、ChatPage 视觉照稿(用户消息低对比右对齐/
      AI 无气泡/赤陶流式光标/组合输入卡/「记一下」chip 预填),
      connection/transcript/markdown 三个逻辑文件**一行不改**。
- [ ] T4 集成收口:hash 路由(#/ 工作区默认,todos/日历/技能占位页保留)、
      `npm run build` dist 重构建进仓、Playwright 截图(四列总览/筛选/
      设置弹层/聊天流式)对照 handoff/screenshots、既有 mjs+pytest 全量绿。
- [ ] T5 verify(主 agent,不外包):e2e 真 gateway 登录→流式复跑、
      主审落 my-review、panel-review **full lane**、verify.md 收口。

## 验收红线(sub 交付时主 agent 逐条查)

1. `web/src/chat/connection.ts` / `transcript.ts` / `markdown.ts` diff 为空;
2. `tests/` 既有测试文件只增不改(改既有断言 = BLOCK,先问);
3. ds_web 无任何非 GET 路由、无写文件代码路径;
4. refs 静态服务三闸齐全(字符集白名单 / realpath 前缀 / 扩展白名单)且
   oracle 有对应用例各自验红过;
5. dist 与 src 一致(重构建后 git status 干净)。
