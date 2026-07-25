# Design: opendesign-feedback-0724-ui

- Change: opendesign-feedback-0724-ui
- Status: draft

> 非开放架构分叉(六条都有唯一合理解),不跑 panel-explore。

## Approach

**① 新对话不清空(BUG,App.tsx)**
`newChat` 现在 `setResumeTarget(null)`;人已在新对话时 prev 本就是 null,
React setState(null→null) bail-out → ChatPage 连接 effect 依赖 `[session, attempt, resume?.nonce ?? 0]`
不变 → 不重连 → keep-mounted 的首页聊天保留旧消息。
改成**永远递增 nonce 的强制新开**(与 `newProjectChat` 同款):
`setResumeTarget((prev) => ({ sessionKey: "", chatId: "", nonce: (prev?.nonce ?? 0) + 1 }))`。
ChatPage:176 `resume && resume.chatId ? resume : null` → 空 chatId 仍走"新会话"分支;
连接 effect 开头 173 行 `setTranscript(emptyTranscript)` 随 nonce 清空。旧对话已进历史可点回,不丢。
同语义的另外两处一并对齐:⌘N(262)、deleteSession 删掉当前续聊目标那支(321)。

**② 图墙顺序(BUG,gallery.ts)**
`buildGallery` 里 ws 图 `sort((x,y) => y.mtime - x.mtime || x.rel.localeCompare(y.rel))`
= **mtime 降序**,与资源管理器默认的名称升序相反。改为按 rel 自然序升序:
`x.rel.localeCompare(y.rel, "zh", { numeric: true })` —— numeric 让 `2.jpg < 10.jpg`。
副作用(接受):相册**册序**也随之变成路径字母序(册序 = 首现序,由条目序派生),
比原先的"最近改过的册在前"更贴近资源管理器。封面 = 册内首项 = 名称最小的那张。

**③ 图墙返回不回原位(BUG,GalleryPage.tsx)**
进子相册前记下滚动容器的 scrollTop,`setOpenAlbum(null)` 回墙面后用 `useLayoutEffect` 恢复。
滚动容器 = `.page.gallery-page` 自身(见 app.css `.page{overflow-y:auto}`),用 ref 拿。
`useLayoutEffect` 而非 `useEffect`:必须在浏览器绘制前复位,否则闪一下顶端。

**④ 图墙四列不齐(app.css)**
`.g-wall { columns: 4 200px }` 是 CSS 多列流:图高不一 → 列高越积越偏,且阅读序是列优先。
改 `grid: repeat(auto-fill, minmax(200px, 1fr))` + 封面统一 `aspect-ratio: 4/3; object-fit: cover`
→ 行列对齐、阅读序恢复行优先。册内视图共用 `.g-wall`,一并统一(同一堵墙两层不该长得不一样)。

**⑤ 去「未分空间」(TodoPage.tsx:508 / ChangesColumn.tsx:759)**
`sec.space ?? "未分空间"` → space 为 null 时**整个小节眉不渲染**,条目直接列出;
有空间才出眉。两处同改(待办页/变更列同一语言)。

**⑥ 待办右栏款式(TodoRail.tsx + app.css)**
按参考图三条:(a) 日历区块补标题「日历」(复用 `.rail-title`,与"需要今天跟进""项目助手"
同级);(b) 三个区块标题脱白底 —— 白卡从 section 下沉到**内容**上:`.rail-cal`/`.rail-follow`
去掉卡片背景/边框/阴影,改由 `.follow-card`、`.rail-ask-row`(聊天框)持有白底;
(c) 日历本体不包白卡。`cal-dot` 圆点**已存在**(app.css:915-919,overdue/today/upcoming 三色),
本条只核实渲染效果达参考图,不重写。

**⑦ 变更筛选语义色(app.css + ChangesColumn.tsx)**
`.filter-pills .pill.on` 现在恒 `background: var(--ink)`(全黑)。只给**单一状态**的胶囊
上语义色:待确认=橙、进行中=蓝、已办结=绿/灰,与行内状态 pill 同 token;
「未办结」「全部」不是单一状态 → 保持中性墨。实现:pill 带 `data-status` 属性,CSS 按属性选择。

## Key trade-offs / risks

- **②的顺序取舍**:按名称升序假设用户资源管理器用默认排序。若用户实际按"修改日期"排,
  这次改动会让他觉得又反了。**这是规格层面的赌**,不是实现层面的 —— 已在 proposal 第一性段
  显式记下;验收时请用户确认一句。
- **④裁剪**:统一 4:3 封面会把竖图裁掉上下。整齐 vs 完整二选一,用户要的是整齐(原话
  "排列不整齐")。lightbox 里仍是完整图,信息不丢。
- **⑥白底下沉**:参考图上"需要今天跟进"的空态提示是**灰字无卡**,有卡片才是白底。
  实现要按 `follow.length === 0` 分支区别对待,不能一刀切给容器上白底。
- ①改动落在所有"开新对话"入口上;若某入口原本依赖"不重连"来保留草稿,会被清掉。
  已核:三处入口语义都是"我要新的",无草稿保留诉求。

## Alternatives considered

- ①用 `key` 强制 remount ChatPage:能清干净,但连接会整条重建、`onConnected` 时序变化,
  比 nonce 路线动的面大。nonce 是既有范式(newProjectChat 已在用),不引入第二套。
- ④用 JS masonry 库:能既整齐又不裁图,但引依赖 + 布局抖动,为一堵封面墙不值。
- ③把滚动位置提到 URL/全局 store:跨页保留更强,但本诉求只在"册↔墙"一层来回,
  组件内 ref 足够,不扩状态面。

## Test strategy (oracle)

新增 `tests/e2e/gallery_order.e2e.mjs` + `tests/test_gallery.mjs` 补例 + 扩 `tests/e2e/todo_rail.e2e.mjs`:

1. **纯逻辑(node --test,`tests/test_gallery.mjs`)**:`buildGallery` 对乱序 mtime 的 ws 图
   返回按 rel 自然序(含 `2.jpg` 在 `10.jpg` 前)的数组;`groupAlbums` 册内首项 = 名称最小者。
2. **e2e 真 chromium(`gallery_order.e2e.mjs`)**:
   - 相册墙 `.g-cell` 的**几何**:同一行的 cell `top` 相等(±2),即真的对齐;
     且第 5 个 cell 的 top > 第 1 个(四列换行)——不是只断言 CSS 属性字符串。
   - 点进子相册 → 图序 = 文件名升序;点「返回相册」→ 滚动容器 scrollTop 回到点进去之前的值(±2)。
3. **e2e(`todo_rail.e2e.mjs` 扩)**:日历区块存在 `.rail-title` 文本 = 「日历」;
   `.rail-cal` 的 computed `background-color` 与页面底色一致(= 没有白卡);
   跟进卡 `.follow-card` 仍是白底。
4. **e2e(`frontend_p1.e2e.mjs` 或新增)**:首页聊天里发一句 → 点侧栏「新对话」→ transcript 清空
   (消息数归零),这是 ①的直接判据。
5. 回归:`node --test tests/*.mjs`、`python -m pytest tests/`、`npm run build` 全绿。

**这个 oracle 能被什么骗过?**

- **④最危险**:07-24 的 `columnCount==="3"` 全绿而正文被压成竖排,就是"断言了 CSS 属性、
  没断言人眼看到的东西"。所以这次**断言几何(同行 top 相等 + 换行发生)而不是 CSS 字符串**,
  并且**必须亲自截图看一眼**——四列可以既"对齐"又"每格窄得没法看"。截图是唯一接得住的。
- **⑥同理**:断言 `background-color` 等于底色,能通过的"白底没了"有两种——
  正确的(卡片下沉到内容)和错误的(整个右栏连内容卡一起变透明,看起来散架)。
  断言只能挡住一半,另一半只有截图接得住。
- **①的假绿**:若测试点的是"项目列 + 新对话"(本来就没坏那个),断言会绿而用户点的
  侧栏「新对话」仍旧坏。判据必须绑 `[data-ui]` 精确到**侧栏那个按钮**。
- **②的假绿**:我的断言用的是我造的夹具文件名;真实文件名是中文 + 空格 + 括号
  (如 `翡翠湾-1801 主卧 (1).jpg`),`localeCompare("zh", {numeric:true})` 在这类名字上的
  次序未必等于 Windows 资源管理器的次序(资源管理器用的是 StrCmpLogicalW)。
  **夹具必须用真实风格的中文文件名**,否则绿了也不代表用户机器上对。
- 全部 oracle 都不覆盖"用户资源管理器实际按什么排序"——那是规格层面的赌,只有用户能答。
