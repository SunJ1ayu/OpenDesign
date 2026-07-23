# Verify: opendesign-todo-rail

- Date: 2026-07-23
- Verdict: PASS

## Mechanical checks

- [x] build passes(`npx tsc -b` rc=0 · `npm run build` 成功 · dist 重建)
- [x] tests pass(本单 oracle 19/19 · 全量 mjs **199/199** · py **23/23** ·
      e2e 七条全 ALL PASS:`todo_rail` / `todo_layout` / `todo_batch_space` / `duedate` /
      `frontend_p2_polish` / `frontend_p3_polish` / `cockpit`)
- [x] no secrets / unsafe ops(**零后端改动**,唯一 Python 变更 = VERSION 0.36.0 → 0.37.0;
      零新写口;数据全部来自既有 `/api/todos`)

## 三硬闸(主 agent 亲验,执行腿自述一概不作数)

- **闸① oracle 逐字节 diff** → **空**;并把整个 `tests/` 目录一起 diff(防偷改上一单
  oracle)→ 也空。`git diff --summary` 无 `create mode 120000` → 无符号链接。
- **闸② 亲跑** → 见上 Mechanical checks。
- **闸③ 逐行读 diff + 真 chromium 截图** → 抓到四条,全部已修(`3c91d68` / `db07fa0`)。

## Review

- lane: **fast**(纯展示 + 纯前端派生;零新后端写口、零 auth/钱/数据一致性面)= 主审 + submimo
- findings(主审在读 submimo 之前已落盘
  `/root/aiwork/tasks/opendesign-todo-rail-review-my-review.md`):

  ### 主审闸③ 抓到的(submimo 一条未提)

  - **[F1 · 实现真 bug · 已修 · 只有截图接得住]** 1700 视口三列 → 每列 339px,
    `.todo-row` 里固定宽兄弟节点把正文挤到几乎为零,**变更正文被压成一列一个字的竖排**。
    根因是第一性错误:**列数被绑在视口宽度上**(`@media(min-width:1600px){columns:3}`),
    而真正决定列数的是**主区可用宽度** —— 加了 320px 右栏后视口媒体查询必然失准。
    修:`columns: 360px 3`(column-width 驱动)+ 删媒体查询。实测
    1280→1列628px / 1440→2列386px / 1700→2列516px / 2000→3列439px / 2560→3列625px,
    复测截图确认竖排消失。**e2e 当时是绿的(`columnCount === "3"`)——数字对、结果错。**
  - **[F2 · oracle 代理断言 · 已修]** 上一单的 `clientWidth > 880` 验的是"去掉 880 限宽"
    的附带后果而非性质;右栏落地后该后果算术上不可能(1136−320=816)。改为直接验性质
    (`max-width:none` + 左右 margin 非 auto + 填满可用宽度)。
  - **[F3 · oracle 测量方式错 · 已修]** `getComputedStyle().columnCount` 在 column-width
    驱动下返回**声明上限**,实际列数 CSSOM 不暴露 → 改量子元素真实左边界;
    并把"列数=N @某视口"换成不变量(任何视口每列 ≥355px、封顶 3 列、@2000 确实到 3 列)。
  - **[F4 · DRY · 已修]** `followUpItems` 用 `due <= today` 筛而卡片文案用 `dueStatus` 判,
    是同一边界的两处编码 → 筛选也走 `dueStatus`。顺带按仓库既有约定(`gallery.ts`)修正
    值导入需带 `.ts` 扩展名(Node 原生 TS 剥离下类型导入会被擦除,所以之前没暴露)。

  ### submimo 的 6 条 —— 逐条裁决

  - **[#1 Low 翻月后选中日期失去视觉锚点]** → **接受为设计取舍,不改**。
    过滤条 `[data-ui="todo-date-filter"]` 兜底且已被 e2e 断言;主审 F5 独立记过同一点。
  - **[#2 Medium 缺 useMemo]** → **拒**。依据:`monthGrid` 是 42 次循环,`followUpItems`
    是 O(n log n),n = 未办结条数(用户当前量级 <100)。且真实成本在 React 重建 42 个
    元素上,`useMemo` 只缓存数组、**不阻止元素重建**(那要 `React.memo`),加了是 cargo cult。
  - **[#3 Low 缺"多条今天到期"的稳定排序用例]** → **拒**。依据:比较器对
    overdue/today **不分支**(`da !== db ? … : a.i - b.i`),既有「同 due 保持传入序」
    用例走的就是同一条分支,新增用例不产生新信息。
  - **[#4 Medium 单 catch 导致首个失败即跳过后续断言]** → **成立,但不在本单修**。
    依据:这是**全部 10+ 份 e2e 共有的既定模式**(源自 `todo_batch_space`),改它是跨文件
    基建变更;且 e2e 步骤前后依赖(点击→断言→点击),失败后继续常产出级联垃圾,
    fail-fast 本身站得住。**记入工具债队列**,单独一单做"分段独立报告"。
  - **[#5 Low 无客户端时钟冻结(当前安全)]** → **采纳**。已在 e2e 顶部加注释钉住该隐含
    依赖:前端全程用服务端 `data.today`、零 `new Date()`(duedate 单踩过这个坑);
    将来有人引入客户端时钟导致断言漂移时,那是信号不是 flaky。
  - **[#6 Trivial `trail-e2e-` 拼写]** → **拒**。依据:同目录兄弟是 `tbs-e2e-`
    (todo_batch_space)、`tlayout-e2e-`(todo_layout),`trail-` = t + rail,**符合既有约定**。

- arbitrated verdict(主裁):**PASS**。submimo 独立 PASS;其 6 条中 1 条采纳、1 条记债、
  4 条附依据拒绝;而**本单四条真发现全部由主审闸③ + 截图抓到,submimo 一条未提** ——
  再次印证 panel 是补盲点的网、不是通行证。

## Accepted deviations

- **§I.9 第三段「项目助手」不在本单**:待办页当前不是 keep-mounted 路由
  (`App.tsx` 里 `{route === "todos" && …}`),挂 `ChatPage` 进去会切页丢对话(p3 治过的
  真机 bug)。需先做路由改造 + session 管线 → 紧接着的下一单 `opendesign-todo-assistant`。
  本单右栏容器已建好,下一单直接追加一段。
- **偏离设计稿「≥1600px 中间三列」**:实测该规格在有右栏时产生 339px 的不可读列(见 F1)。
  改为按可用宽度自适应(每列 ≥360px、最多 3 列),**约 1900px 视口才到三列**。
  这是对设计意图(宽屏多利用)的忠实实现、对字面像素规格的偏离,显式记录在此。
- **跟进区与主列表有交集**:设计稿「不重复主列表」是相对它旧稿「今日待办=复读前三条」
  而言;本单跟进区是另一套判据(超期+今天到期)的跨项目视图,**不从主列表剔除**——
  主列表完整性优先。
- **过滤态下头部计数 / 闲置占位卡 / 「⛑ N 天没动静」行不跟着过滤**:它们是项目级完整性
  信号,与具体到期日无关;跟着过滤会让人误以为项目没有未办结事项。
- **e2e 单 catch 结构**:见 submimo #4 裁决,记债不在本单修。
- **右栏观感只在 headless chromium 1280–2560 五档验过**,真机分辨率交装机验收。
