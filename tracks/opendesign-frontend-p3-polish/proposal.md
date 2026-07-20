# Proposal: opendesign-frontend-p3-polish

- Date: 2026-07-20
- Status: open
- Source: 设计交付包 v4 `优化修改单.md` **§I 第二轮(对照 v0.3x 截图)** 六条
  (zip `/root/OpenDesign 室内设计工作台.zip`,2026-07-19 23:44)

## Goal

把设计交付包 v4 修改单 §I 的六条落地到工作台前端,收口设计师对 v0.31.0 的第二轮反馈。

## Motivation

修改单 A–H 已由 track `opendesign-frontend-p2-polish` 落地(e5bac70,ds-web 0.31.0)。
设计师看过 0.31.0 截图后追加 §I 六条,代码库逐条核过**全未实现**。

| # | 条目 | 现状(已核) |
|---|---|---|
| I1 | 图墙页去掉「来源」chip 云,改描边下拉单选过滤 | `GalleryPage.tsx:143` 仍是 `<Chips>` 平铺 |
| I2 | 未建档页「建档」改主按钮(赤陶底白字) | `ChangesColumn.tsx:279` 用 `.btn-save` |
| I3 | 列宽重分配:伴随列 290→400px,助手列 340→300px | `app.css:748/1013` 仍 290/340 |
| I4 | 「最近更新」行必须可点(文件夹行已可点) | `CompanionColumn.tsx:393` 是不可点 `<div>` |
| I5 | 助手头部「已连接 · 模型」降噪 +「退出登录」收进 `…` 菜单 | `ChatPage.tsx:456-468` 常驻 + 内联 style |
| I6 | 侧栏项目名两行截断,括号开头优先显括号后内容,title 显全名 | `app.css:300` 单行 ellipsis,无 line-clamp |

## Scope

- in: 上表六条。I1/I2/I3/I5/I6 = 纯前端;**I4 唯一需要后端改动**(见 design.md 安全决策)。

## Non-goals

- 修改单 §A–H 与「其他小项(原 H)」:p2-polish 已覆盖。
- 图片上传:交付包外的独立大件,队列另排。
- 图墙「空间」「风格」两组 chip:修改单只点名「来源」,其余不动。

## 成功标准

1. 六条逐条可在 UI 事实上断言(oracle + e2e)。
2. I4 不引入可执行文件打开路径 —— 白名单外扩展名零 `OPEN_LAUNCHER` 调用。
3. 全量回归绿(py + mjs + build),`/api/health` 回显新版本号。
