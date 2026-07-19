# Design: opendesign-frontend-p2-polish

- Change: opendesign-frontend-p2-polish
- Status: final(无架构分叉,不跑 panel-explore——像素级规格已由设计包给死)

## Approach
照优化修改单 A–H 直译成组件改动,规格冲突以修改单文字为准(> 6a 画板 > README)。
按面拆:

- **A 全局体系(app.css 主战场)**:输入统一类 `.input-std`(白底 #fff/边框 #ddd8ca/
  圆角 10–14px/聚焦转 #c46a4a 无默认 outline);按钮三级 `.btn-primary`(#c46a4a 底白字
  hover #a04f2e,600,每屏至多一个)/`.btn-secondary`(白底描边 #ddd8ca 字 #5c574c
  hover 底 #f3f1ea)/`.link-act`(#a04f2e 文字链);:focus-visible 2px #c46a4a 外圈;
  一切可点 cursor:pointer + 120ms ease;esc 关一切弹层(设置弹层/StatusPicker/连接
  modal/lightbox——后两者本轮新增或已有)。存量类(edit-text/btn-save 等)就地收编改
  样式,不强行全局改名。
- **B 快记单行输入卡**(ChangesColumn):`[data-ui=quicknote-card]` 圆角 12 卡 =
  ✎(#c46a4a)+ 单行 input + 内嵌「空间 ⌄」chip(`[data-ui=quicknote-space]`,28px
  描边胶囊,点开 popover `[data-ui=quicknote-space-pop]`:统一范式输入 + 本项目已有
  空间名建议行;选中后 chip 显示空间名)+ 主色「记一条」按钮。回车提交;成功后
  `[data-ui=quicknote-toast]`「已记入 C13」绿色 2s 淡出 + 新行插列表顶部短暂高亮
  #f7ecd8(复用 hl-flash 机制)。**不做 AI 猜空间**:不选 = 无前缀(拍板见 proposal)。
  注:提交后 onEdited 整列重拉,新行编号从 addChange 响应拿(api.ts 已返回 cnum)。
- **C 连接卡两处**(ChatPage login 视图重排 + ChatColumn):连接卡抽成一个受控形态
  `[data-ui=connect-card]`(360px 白底圆角 16 投影:标题 + 说明——必须含「变更记录、
  图墙、文件不受影响,现在就能用」——+ 口令输入统一范式 + 主按钮「连接」+ 小字
  「口令在 nanobot WebUI 设置页获取」;失败行内红字 12px 不弹 alert)。新对话页 =
  居中这张卡;项目工作区聊天列 = **不放表单**,顶部琥珀横幅 `[data-ui=connect-banner]`
  「未连接聊天服务 · 连接」→ 点开 modal `[data-ui=connect-modal]`(同一张卡,esc/遮罩
  关),中间留白,底部置灰输入卡照旧。连接成功入口全消失。**connection.ts 逻辑层
  零改动**,只动视图层组装。
- **发送按钮**:`.send-btn` ↑ → 文字「发送」(主色底白字圆角 8 600;未连接置灰同形
  底 #e8d5cb)。
- **D 伴随列减负**(CompanionColumn/InboxCard):收件箱默认一行摘要
  `[data-ui=inbox-summary]`「收件箱 N · [扫描整理]」点行展开明细(展开后 .inbox-plan
  等结构不变——既有 e2e 契约);cockpit 速览 row1 删(阶段 chip 挪中央列标题旁
  `[data-ui=stage-chip]`,业主/相对时间不再展示),status_note 保留;组标题/计数/链接
  三档字号统一(13.5/600、11.5 #98917f、#a04f2e);文件夹行与组头 10.5px #b0a996。
- **E 变更行操作**(ChangesColumn):hover 图标按钮组 = ✎`[data-ui=change-edit]`
  (保留 .edit-trigger 类名——frontend_p1 e2e 契约)+ ✓`[data-ui=change-done]`
  (28px 方形描边,✓ hover 转绿,点击 = editChange new_status 已完成),仅未办结行出
  ✓;StatusPicker pill 补 title「点击修改状态」,菜单卡片化;行 hover 底 #f9f7f1。
- **F 空态动作**:变更空态 + 次按钮「记第一条变更」`[data-ui=empty-add-first]`
  (聚焦快记 input);项目图空态(已映射)+ 次按钮「打开文件夹」;参考图空态
  「登记参考图」改 #a04f2e 可点(预填聊天)`[data-ui=empty-reg-ref]`;bind 下拉统一
  输入范式;侧栏历史对话组未连接**整组隐藏**(连接后无对话显示「暂无对话」)。
- **G 待办页**(TodoPage/todo.ts):「按项目」卡内**按空间分小节**(新纯函数
  `spaceSections(items)`:按空间首现序分组,无空间的归「未分空间」置末——oracle
  test_todo_spaces.mjs),小节眉 = 空间名 + 浅分隔线 #f0ede4,**该视图去日期折叠**;
  「按时间」维持日期批次折叠;内容区 max-width 880px 居中,卡距 14px。
- **H 小项**:⌘K 输入行统一范式、结果行 hover #f3f1ea/选中 #ece9e0;图墙封面 hover
  translateY(-2px)+投影加深,lightbox 补左右键切换(esc/遮罩已有);侧栏未建档行
  hover 出「建档 →」`[data-ui=side-reg-link]`(点击即选中该项目,中央列已是建档表单);
  设置弹层版本号/「深色即将支持」保留。

## Key trade-offs / risks
- 砍 AI 猜空间:偏离修改单 B 一句话,拍板依据在 proposal(用户未回按主审倾向)。
- cockpit 速览删业主/时间:信息减配来自设计判断,若用户不适应可低成本回加。
- 既有 e2e 选择器 = 兼容契约:.edit-trigger/.skip-btn/.bind-form/.bind-select/
  .inbox-plan/.plan-row 类名必须保留;intake/frontend_p1 e2e 由主 agent 预改为
  「有摘要行先点开」的双态兼容写法(改前改后都绿)。
- cockpit.e2e.mjs 的「速览含阶段/业主」断言与本轮冲突:主 agent 预改为中性
  (阶段断言挪去新 e2e 严格版;业主断言删,负向断言进新 e2e)。

## Alternatives considered
- 空间 chip 做成纯下拉(仅已有空间):新项目第一条永远选不了空间,故 popover 里
  保留自由输入。
- AI 猜空间:见 proposal 拍板,砍。

## Test strategy (oracle)
主 agent 亲写、先红检、先 commit,对执行腿逐字节 off-limits:
1. **tests/e2e/frontend_p2_polish.e2e.mjs**(新,真 chromium + 真 ds_web 无 gateway):
   B 提交流(Enter → toast 已记入 → 新行 hl-flash → 磁盘无【前缀)/空间 popover;
   C 新对话页连接卡(含「现在就能用」文案)+ 工作区横幅→modal→esc 关;发送按钮文字
   =「发送」;侧栏未连接无历史对话组;D inbox 摘要行默认收起点开展开、中央列
   stage-chip、伴随列不含业主名;E ✎/✓ 按钮 + ✓ 点击落盘已完成;F 三处空态动作 +
   聚焦断言;G 按项目视图空间小节眉 + 无日期折叠头、按时间有;H lightbox 右键切换
   src 变 + esc 关、侧栏未建档行建档链接。
2. **tests/test_todo_spaces.mjs**(新):spaceSections 纯函数契约(首现序/未分空间
   置末/空输入)。
3. 既有全量回归:py 全套 + mjs 全套 + intake/frontend_p1/cockpit/project-thread e2e
   (主 agent 预改双态兼容/中性化后,改前改后都须绿)+ npm build + dist 重建。
