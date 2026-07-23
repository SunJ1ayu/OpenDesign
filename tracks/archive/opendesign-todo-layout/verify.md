# Verify: opendesign-todo-layout

- Date: 2026-07-23
- Verdict: PASS

## Mechanical checks

- [x] build passes(`npx tsc -b` rc=0 · `npm run build` 成功 · dist 重建)
- [x] tests pass(本单 oracle 17/17 · 全量 mjs **180/180** · py 套件 **23/23** ·
      本单 e2e `todo_layout` **44 条 ALL PASS** · 相邻 e2e `todo_batch_space` /
      `duedate` / `frontend_p2_polish` 三条均 ALL PASS)
- [x] no secrets / unsafe ops(**零后端改动**,唯一 Python 变更 = `ds_web.py` VERSION
      0.35.0 → 0.36.0;零新写口、零 schema 改动;`/api/health` 实起实测回显 0.36.0)

## 三硬闸(主 agent 亲验,执行腿自述一概不作数)

- **闸① oracle 逐字节 diff**:`git diff 10212c9 worktree-agent-... -- tests/test_todo_layout.mjs
  tests/e2e/todo_layout.e2e.mjs` → **空**。执行腿 worktree 基线落后于 oracle commit
  (它自行 merge 372391c 补入),这道闸因此是唯一防"改考卷"的防线,已走,零改动。
  另 `git diff --summary` 无 `create mode 120000` → **无符号链接**(worktree merge 覆盖
  主仓 node_modules 事故的防线)。
- **闸② 亲跑**:见上 Mechanical checks,全部主 agent 自己跑。
- **闸③ 逐行读 diff**:抓到两条,均已自修(843634d),详见下。

## Review

- lane: **fast**(纯展示 + 纯前端逻辑;零新后端写口、零 auth/钱/数据一致性面 → 按
  AGENTS.md「fast lane 只给纯展示/纯逻辑改动」)= 主审 + submimo
- findings:
  - **[F1 · 主审闸③ · 我的 oracle 自己错 · 已修]** e2e 的 hover 断言是**空断言**。
    原写法在两次 `toggle1.click()` 之后直接采样 `bgBefore`:鼠标因 click 仍停在按钮上,
    且 `transition: background-color` 在途(实测采到 `rgba(247,245,239,0.97)` 半程色),
    于是 `bgHover !== bgBefore` 比的是「半程 vs 全程」,**没有证明静止态 ≠ hover 态**——
    实现若漏写 hover 底色照样会绿。修:鼠标挪开 + 等落定采静止态,再 hover 等落定采终态,
    并直接钉住「静止=完全透明、hover=真上色(alpha>0.9)」。重跑实测
    `rgba(0, 0, 0, 0) → rgb(247, 245, 239)`。**实现本来就对,虚的是判据。**
    执行腿把这个异常报了上来(虽把成因误解为"页面背景透色")——**报异常这个动作是对的**。
  - **[F2 · 主审闸③ · 已修]** `staleDays` 被本单孤儿化:`orderProjectCards` 已把 stale
    天数附在卡上,该函数零生产调用者,只剩自己的测试在用。同一个问题(项目名→超期天数)
    留两个答案 = 屎山第一块砖 → 删函数 + 删 `test_workbench_p4.mjs` 对应用例与 import
    (契约由 `test_todo_layout.mjs`「附 stale 天数,无超期为 null」一例接管)。
    **反证其确为死代码:删除后 `web/dist` 逐字节无变化(本就被 tree-shake)。**
  - **[F3 · 主审闸③ · 已核 · 非问题]** 折叠态下批量选中集不清空(收起的卡内仍有选中项)。
    核:①浮栏「已选 N 条」数字诚实;②终态 ≥2 条仍走 `window.confirm`;③与文件管理器
    "折叠目录不清选择"通行语义一致。判为可接受,不改。**submimo 独立复核同结论。**
  - **[F4 · 主审闸③ · 已核 · 正确]** 结构面:`GroupToggle` 内只含 span,「去项目 →」
    「全选本组」为兄弟节点 → 无嵌套 `<button>`(e2e 机械化钉住);折叠复用既有 `toggled`
    Set + XOR,**零新增 state**;`orderProjectCards` 先 map 后 sort → 不改入参、`items`
    保持同引用;CSS 已删净 `.batch-head .batch-toggle` 与 `.todo-card .card-head .grow`
    (后者唯一使用者随本单删除),**无两套折叠样式并存**。
  - **[submimo · nit · 拒]** e2e 只在首卡首行验了 StatusPicker 菜单可见,未验中间卡在
    fragmented column 里的菜单。拒:`.st-menu` 是 `absolute` 相对 `.st-cell` 的 `relative`,
    二者同一 containing block,列分片在结构上不可能裁到它(主审已独立核过定位模型);
    加断言不产生新信息。
  - **[submimo · 已核 · 非本单]** `app.css` 唯一一处 `!important`(`.route-hidden`)
    来自 07-12 keep-mounted 路由改造(`114c38d`),非本单引入,合理。
- arbitrated verdict(主裁):**PASS**。submimo 独立 PASS 且零 finding,但**未因此降低主审
  自己的判断**——本单两条真发现(F1/F2)都是主审闸③亲读抓的,submimo 均未提。
  再次印证:panel 是补盲点的网,不是通行证。

## Accepted deviations

- **折叠态下选中集不清空**(F3):判为正确 UX,不改;留真机使用暴露。
- **占位卡不截断项目名**:`idleNames.join("、")` 全量列出。用户当前 7 个项目长度可控;
  几十个项目时是一张长卡,不影响正确性。不提前造截断规则(YAGNI)。
- **占位卡只在「按项目」视图出现**:它是项目维度摘要,时间轴视图里没有位置;
  「⛑ N 天没动静(无未办结条目)」独立行仍在两视图都显示(那是警示不是摘要)。
- **多列瀑布观感仅在 headless chromium 1440/1700 两档验过**:真机分辨率下的观感属设计
  验收范畴,交装机时看。
- **超期组内按天数降序**:规格只说「有超期标签的排最前」,组内序由本单定(最久没动静的
  最前),已写进 oracle 契约。
