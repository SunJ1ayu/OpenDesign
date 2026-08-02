# Design: opendesign-workbench-p2

- Change: opendesign-workbench-p2
- Status: frozen(2026-07-11;不是开放分叉——设计已由 Claude Design 定稿,
  panel-explore 不适用;剩余全是工程落地决策,直接写)

## Approach

**设计单一真相源 = `handoff/README.md`**(布局、精确 token、交互均已给全);
`handoff/主工作区探索.dc.html` 最上方 `data-screen-label="2a 主工作区"` 画板可查
内联样式精确值。**1a/1b/1c 是早期探索,禁止实现。**

前端:重写 `App.tsx` 外壳为四列工作区(handoff §Overall Layout),`app.css`
token 换成暖纸面色板(handoff §Design Tokens)。聊天**逻辑层零改动**
(`chat/connection.ts` / `chat/transcript.ts` / `chat/markdown.ts` 原样复用,
各自 oracle 守着),只重排 `ChatPage.tsx` 视觉。路由保留 hash:`#/` = 工作区
(默认),待办/日历/技能/图墙走占位或既有页。

后端:`bin/ds_web.py` 新增**只读** GET 路由(沿用既有手写路由 + 白名单模式):

1. `GET /api/projects` — 扫 `<ds_root>/projects/*.md`,每项目返回
   `{key, name, stage, open_count, delivered, last_update}`。解析逻辑**复用/抽取
   ds_todo 的既有解析**(单一真相源,不另造第二套正则)。
2. `GET /api/projects/<key>/changes` — 该项目全量变更
   `{cnum, status, text, date, space?, source?}` + 沟通日志不在本 API(不需要)。
   `<key>` 校验沿用 T2 模式:先验字符集、拒 `.`/`..`/`%`,零路径走私面。
3. `GET /api/projects/<key>/refs` — 解析 `<ds_root>/refs-index.md`,过滤
   `用于:` 含该项目的条目,返回 `{id, style, space, file, note}` 列表。
4. `GET /api/refs/file/<path>` — 参考图静态服务,**唯一新增文件读出面,安全关键**:
   realpath 必须落在 `<ds_root>/refs/` 之内(先字符集白名单再 realpath 双闸)、
   只允许图片扩展名白名单、404 一律不回显路径、Content-Type 按扩展名映射,
   禁止目录列表。响应加 `Cache-Control`。

## Key trade-offs / risks

- **空间/来源字段**:现有 PKB 行格式 `- [状态] Cn 日期 内容` 没有「空间/来源」;
  定稿元信息行有(「玄关 · 7月9日 口头 · 现场」)。**决策:读侧宽容**——解析器把
  这两个字段设为可选,前端只渲染存在的字段;**不改 ds_tools 写入格式**(写侧
  schema 扩展另 track)。accepted deviation。
- **「✓ 标记完成」是写操作**,而 ds_web 只读是安全基线(盲评修过注入洞)。
  **决策:不加写 API**——hover 按钮点击 = 聊天输入框预填「把 C12 标记完成」,
  交 AI 走 ds_tools/ds-approve 既有闸。产品上也自洽(所有写都经对话)。
- **文件区**:真实文件在用户 Windows D 盘,本地无目录约定,发明约定=空想。
  **决策:空态占位**(按稿画区块,空态文案引导「首装后关联项目目录」)。
- **静态文件服务是本 track 唯一新攻击面** → oracle 先行 + verify full lane。
- 深色:定稿仅浅色;现有 dark 机制保留但工作区不换肤,设置里深色标「即将支持」。
  风险=用户开过深色 → 首次进入强制浅色,可接受。
- 画板 1440×860,实现须全屏自适应;窄窗(<1200px)伴随列/聊天列的收纳策略稿上
  未画 → 最小处理:聊天列可收起(稿上有 » 收起按钮),伴随列 min-width 保持,
  出横向滚动兜底。不做响应式重排。

## Alternatives considered

- 在现有五项侧栏壳里加「工作区」一页 → 否:定稿就是整个应用外壳,保留旧壳=
  两套 IA 并存,与用户反馈背道而驰。
- 图片缩略图走 base64 内联进 JSON → 否:大索引会炸内存/响应;静态路由 + 双闸
  校验更标准,且可缓存。
- 前端直接 fetch nanobot 端口拿会话列表 → 否:P1 已定一切经 ds_web 白名单代理。

## Test strategy (oracle)

- **后端(pytest,进 `tests/test_ds_web_api.py`,格式照 test_ds_web_proxy.py)**:
  - /api/projects:正常列表、open_count 与 ds_todo 一致、空目录、坏 md 宽容;
  - /api/projects/<key>/changes:四状态齐全解析、可选字段缺省、非法 key
    (`../`、`%2e`、空)404 且零文件读、未知项目 404;
  - /api/projects/<key>/refs:过滤正确、索引缺失=空列表;
  - **/api/refs/file/<path> 安全闸**:合法图片 200+正确 Content-Type、
    路径逃逸(`../`、绝对路径、symlink 指向 refs 外)404、非图片扩展 404、
    不存在 404 不回显路径。symlink 用例必须真建 symlink 测 realpath 闸。
  - red-check:至少对 key 校验、realpath 闸、扩展白名单三处做突变验红。
- **前端**:chat 逻辑层既有 oracle(17+14 条)必须原样全绿=「零改动」的机械证明;
  新布局不焊单测,走 Playwright 截图目检(四列总览/筛选切换/设置弹层开合/
  聊天流式)对照 `handoff/screenshots/`。
- **e2e**:P1 的真 gateway 登录→流式 6/6 流程在新 IA 里复跑。
- 全量既有测试(test_ds_tools / test_ds_web / test_ds_web_proxy / mjs)零红。
- verify lane:**full**(main+3;理由:新增文件读出面=安全敏感)。
