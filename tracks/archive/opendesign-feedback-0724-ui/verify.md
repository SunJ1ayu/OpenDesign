# Verify: opendesign-feedback-0724-ui

- Date: 2026-07-25
- Verdict: **PASS**(ds-web 0.43.0,commit 4c5d426 + 边界修 1 处)

## Mechanical checks(全部主 agent 亲跑)

- [x] build passes:`npm run build` 绿(tsc -b + vite)
- [x] tests pass:`node --test tests/*.mjs` 200/200、`pytest` 571 passed / 8 skipped、
      真 chromium e2e **14/14**(含本单 5 个 oracle:test_gallery / gallery_order /
      new_chat / todo_rail / todo_batch_space)
- [x] no secrets / unsafe ops:纯前端展示 + CSS,不碰写口/权限/key/钱/数据一致性
- [x] **亲自截图看**(design.md 明写"断言只能挡住一半,另一半只有截图接得住"):
      封面墙 1280=四列真对齐、1680=六列(格 ~210px 没被压扁)、册内 (1)(2)(10) 正序、
      待办右栏纯标题+内容卡(没有"白底没了=散架")、筛选四态语义色可读

## Review

- lane: **fast**(主审 + submimo)。理由:六条全是展示层(React 渲染分支 + CSS),
  唯一的状态语义改动(#9 nonce)不落盘、不过网关写口,不触发"新写口/权限/auth/钱/
  数据一致性必 full"那条硬规矩。
- 规格自查(先于任何 employee 输出写下,全文在
  `/root/aiwork/tasks/opendesign-feedback-0724-ui-my-review.md`):
  1. **#10a 排的是"资源管理器按名称升序"这个假设**。用户若实际按修改日期排,
     这次改完他会觉得又反了 —— oracle 覆盖不了口径,只能真机确认。
  2. **#2 统一 4:3 裁剪是我替用户做的取舍**(整齐 vs 完整)。竖构图会裁上下;
     退路 = `aspect-ratio: 1` 或 contain + 底色。
  3. **#8「标题脱白底」可能过头**:若用户本意只是"标题别那么重"而非"整块别是卡",
     观感会与他预期不同。截图已存,验收时给他看。

### findings

主审(读 submimo 输出之前):

1. **[已修] #5 选中态对比度不足** —— 原实现 `--st-*-dot` 打底 + 纸色 12px 小字,
   实测 2.7~3.4:1(低于 AA 4.5)。改同族深一档 `--st-*-fg` = 4.4~5.5:1,颜色语言不变,
   oracle 不硬编码色值所以照绿。截图复核可读。
2. **[已修] #10b 切项目的边界漏了** —— `GalleryPage` 里换项目的 effect 会
   `setOpenAlbum(null)` 触发复位,而"清零 wallScroll"只挂在 `setFilter` 那条路上;
   本来就没筛选时 `setFilter(EMPTY)` 被 React bail-out 吃掉 → **开着子相册切项目,
   新项目的墙会沿用上一个项目的滚动位置**。修:换项目的 effect 里直接
   `wallScroll.current = 0`。oracle 没覆盖(夹具只有一个项目),靠读代码抓到。
3. **[已修·夹具] project-thread e2e 假红** —— 它在「已连接」出现的瞬间读 localStorage,
   而记账比那晚一两帧(50ms 探针实测 2-4ms)。同一份代码基线 3/3 绿、新构建 3/3 红
   (git stash 对照实证)= 纯时序,不是功能回归。改 `waitForFunction` 等落盘,判据强度不变。
4. **[已修·夹具] todo_batch_space 颜色比对假红** —— 过渡收尾时同色读成 `rgba(...,0.992)`、
   静止读 `rgb(...)`,字符串比对随机翻红 → 等 alpha 收敛后比 RGB 三元组。
5. **[已修·过时考卷] frontend_p2_polish** 仍断言「未分空间」= 本单被用户否掉的文案 →
   改断"该节存在且无空间名",主判据留在 todo_batch_space。

submimo(fast lane 唯一评审腿,`/root/aiwork/logs/panel-0724ui-211412.submimo.log`):
**Conclusion: PASS**,逐条核对六个反馈点 + 五处夹具改动,两条 non-blocking observation。

### 仲裁(逐条给依据)

- submimo 的两条 observation **接受但无需动作**:①`newChatTarget` 的参数类型比
  state 类型宽,函数式 updater 的参数是逆变位,TS 合法(核过 `App.tsx:49-54`,真的);
  ②`deleteSession` 里显式传 `prev` 与另两处的 updater 简写等价(核过 `App.tsx:330`,真的)。
- **submimo 对 #10b 的清白理由是错的,拒收**:它写"Project switch: component remounts
  (keyed by project), `wallScroll` ref reinitializes to 0"。核 `App.tsx:481` =
  `<GalleryPage project={selected} />`,**没有 key,不会 remount**;项目切换靠
  `GalleryPage.tsx:83-90` 那个 effect 手工重置 state。也就是说它给出的"安全"结论建立在
  一个不存在的前提上,而真实存在的正是主审 finding 2 那个洞 —— 弱模型的典型假阴性,
  这条也是本单 panel 的负面样本:**一条 PASS 不能降低主审自己的标准**。
- 主审 findings 1/2 是 submimo 完全没提的两条(一条对比度、一条状态边界),
  按"我标它没标 → 依然成立,它的沉默不是清白"处理,均已修并复跑绿。

## Accepted deviations

- **4:3 封面裁剪**:竖构图被裁上下,换整墙对齐(用户原话是"排列不整齐")。
  lightbox 仍是完整图,信息不丢。真机若嫌裁得难看 → `aspect-ratio: 1` / contain。
- **册序变字母序**:#10a 改条目序后册序由首现序派生,从"最近改过在前"变成路径字母序。
  截图看更贴资源管理器,合直觉。
- **无空间那节只剩一条 rule + 「全选本组」**:#6 要求"没空间就不写名字",分节头因此
  看着像空行。截图确认不突兀,保留分节以免"全选本组"失去归属。
- **#10a 的排序口径未被任何 oracle 覆盖**(用户资源管理器实际按什么排序只有他能答)
  → 列入真机验收问题清单。
