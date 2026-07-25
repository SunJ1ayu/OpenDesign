# Tasks: opendesign-feedback-0724-ui

- base-ref: 1860b40df453b95934b231c5315daafe6405c4c8

> oracle 先行:下列 5 个判据文件先红检、先 commit,再动实现。
> oracle 文件对任何执行腿 off-limits。

## Oracle(先行,已红检)

- [x] `tests/test_gallery.mjs` 补自然序判据 + 改封面期望(红:2 fail)
- [x] `tests/e2e/gallery_order.e2e.mjs` 新增(红:第一行 4 格顶边 70/285/484 不齐)
- [x] `tests/e2e/todo_rail.e2e.mjs` 补右栏款式判据(红:标题只有 ["需要今天跟进"])
- [x] `tests/e2e/todo_batch_space.e2e.mjs` 补 #6/#5 判据(红:仍出现「未分空间」)
- [x] `tests/e2e/new_chat.e2e.mjs` 新增(红:探针实证——发一条后点新对话,转录不清空)

## 实现(全部完成于 4c5d426,ds-web 0.43.0)

- [x] #9 新对话:App.tsx `newChat` 改 nonce 递增强制新开;⌘N / deleteSession 两处对齐;
      侧栏按钮补 `data-ui="side-new-chat"`
- [x] #10a 图墙顺序:gallery.ts `buildGallery` ws 图改 rel 自然序升序(localeCompare numeric)
- [x] #10b 图墙返回原位:GalleryPage 记 scrollTop + useLayoutEffect 复位
- [x] #2 图墙四列:app.css `.g-wall` columns → grid + 封面统一 aspect-ratio/object-fit
- [x] #6 去「未分空间」:TodoPage.tsx:508 与 ChangesColumn.tsx:759 空间为 null 时不写名字
      (分节与「全选本组」保留)
- [x] #8 右栏款式:TodoRail 补「日历」「项目助手」标题(展开对话移到标题行)、
      白底从 section 下沉到内容(跟进卡 / 输入卡),app.css 同步
- [x] #5 筛选语义色:pill 带 data-status,单状态用 --st-*-fg(原定 --st-*-dot,主审
      对比度自查后改深一档),未办结/全部保持中性

## 收货

- [x] 五个 oracle 全绿 + 回归:node --test 200/200、pytest 571 passed、build 绿、
      真 chromium e2e 14/14(全套,不只本单五个)
- [x] **亲自截图看**(scratchpad/shots/):封面墙 1280=四列对齐 / 1680=六列(格 ~210px,
      没被压扁)/ 册内 (1)(2)(10) 正序 / 右栏纯标题+内容卡不散架 / 筛选四态语义色可读。
      截图顺手抓到一处主审 finding:选中态原用 --st-*-dot 打底,纸色 12px 小字对比度
      仅 2.7~3.4:1 → 换 --st-*-fg(4.4~5.5:1)
- [ ] verify.md(fast lane:主审 + submimo)
