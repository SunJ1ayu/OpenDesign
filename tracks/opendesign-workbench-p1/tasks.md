# Tasks: opendesign-workbench-p1

- base-ref: e2b5b11473e6e55178f17743ec0db228ce0632b2
- 状态:**plan v2 已冻结**(sub Claude 评审 11 findings 全采纳合并,
  仲裁记录在 design.md 尾部);等用户 go 开工

- **排期决定(2026-07-09 定):不必把 T4–T10 全做完再交付。**
  最小可装机集 = **T4 + 半个 T5(能看对话即可)**,达到即装到用户
  Windows,让用户第一天先用"打字→记业主改动"(后端 07-01 已验证跑通)。
  真实反馈 + 真实 D 盘目录结构随首装一起到,再决定后续 T6–T10 与
  下一件大事(文件工作区管理器,另起 track)。理由:真实反馈 > 继续空聊。

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

## 实施顺序

- [x] T0 协议基线快照 ✅ 2026-07-08 完成:enable_webui.py 部署形状真
      gateway 实抓全链路,`docs/nanobot-ws-protocol.md` 落盘;
      `tests/test_ws_protocol_smoke.py` gated 冒烟(实跑含 LLM 链 OK,
      gateway 停后 SKIP 路径验证 OK,config 已还原)。F11 答案:不带
      webui:true 也回补进历史但缺 turnId,前端一律带。token 一次性、
      attach、401 形状、分页全部实测确认与 plan v2 一致,零意外。
- [x] T1 oracle 先行 ✅ 2026-07-08:`tests/test_ds_web_proxy.py` 9 条
      (白名单映射×3/非法 key 零上游/白名单外 404/405 不变量/502/401
      透传/请求头白名单),mock 上游=记录型 stdlib server;red-check
      9/9 错(make_server 无 nanobot_port)。XSS 闸按其归属挪 T5/T9
      (前端渲染层,Python oracle 测不到)。未 commit——按 P0 惯例
      与 T2 实现同 commit 落仓,红测不单独上 main。
- [x] T2 ds_web 代理实现 ✅ 2026-07-08:三条白名单 GET 映射 + `<key>`
      不 unquote 先验字符集且拒 `./..`(% 直接闸外=零路径走私面)+
      查询串透传 + 请求头白名单 + 502/状态码透传;上游硬编码
      127.0.0.1(DS_NANOBOT_PORT 可覆盖)。oracle 9/9 绿,全量回归绿。
      oracle 修两处测试自身 bug:①Authorization 非 ASCII(http 头
      latin-1 约束)②裸空格/裸€ 请求行不合法到不了路由,wire 真实
      形状是 %xx(留 %20/%e2%82%ac 变体)。经代理打真 gateway 的
      端到端留 T10 verify 一并跑。
- [x] T3 视觉重皮肤 + IA 重排 ✅ 2026-07-08:app.css 全量换 nanobot
      token(浅/深两套 + 状态色语义变量深浅各配)、13px 基准、细滚动条、
      侧栏半档色差+圆角软高亮(弃 P0 墨侧栏/border-left/衬线 wordmark);
      App.tsx 侧栏改五项(聊天首屏含输入条壳/待办/日历占位/工具箱两张
      灰卡含 3D/设置含 auto-light-dark 三态切换存 localStorage);
      TodoPage 零改动(class 层换皮)。dist 重构建进仓;Playwright
      四截图(chat 浅深/todos 浅/toolbox 深)目检通过;回归绿。
      **修订(3f68275,用户双截图对比反馈)**:侧栏 220→256px(实测
      其 dist w-64)/五项补 lucide 内联图标+单行条目/设置钉左下角
      footer。教训:布局度量也要从 dist 实测,不只色彩 token。
      用户已在真机拉取查看,无进一步反馈,视觉基线以此为准。
- [x] T4 聊天登录/连接流 ✅ 2026-07-10:纯逻辑层 `web/src/chat/connection.ts`
      (fetch/WebSocket/storage/uuid 全依赖注入)+ `chat/ChatPage.tsx` 四态
      (登录表单/连接中/已连接/错误横幅含原版界面保底链接)。oracle =
      `tests/test_chat_connection.mjs` 14 条(node --test 原生跑,零新依赖;
      red-check:三处突变分别红 1/2/3 条)。端到端实检 7/7 双跑过:部署
      形状真 gateway(enable_webui.py)+ dist 经 ds_web,Playwright 走
      错口令→对口令→ready 已连接→刷新免登录→退出登录,截图目检与 T3
      视觉基线一致,config 已还原。自审抓到并修:①退出登录须触发 effect
      清理关 ws(否则悬挂 ws 断线会把登录页踢成错误横幅);②中文口令
      提前转明确登录错误(fetch header 只收 Latin-1,否则 TypeError 被
      误读成服务故障)。已知边界:ws 握手 401(bootstrap 与握手间口令
      被改)表现为"连接已断开"+重试,重试路径会正确落回登录。
- [ ] T5 聊天核心 UI:**流式渲染 = delta 增量(节流)+ stream_end 定稿
      + turn_end 收尾**;tool_hint/progress 安全降级;GFM markdown 用
      react-markdown(**禁 raw HTML,焊 oracle #4**;新依赖锁
      package-lock);输入框 Enter 查 isComposing(+229 兜底);
      message 信封带 webui:true+turn_id;错误横幅含"打开原版界面"链接
- [ ] T6 断线自愈:重连 = 重签 + 对新 ready 重发 attach(裸 chat_id)+
      refetch webui-thread 补缺口;指数退避上限 30s;mock 上游 401/断连
      oracle 转绿
- [ ] T7 会话列表:侧栏会话区 = 代理 sessions 渲染(key 的 `websocket:`
      前缀 ↔ attach 裸 chat_id 映射);切换会话 attach+拉历史(分页
      direction=latest);新建会话(new_chat)
- [ ] T8 Windows 物料:ds-nanobot.ps1 顺手拉起 ds_web(已跑跳过/端口
      占用明确报错);install-windows.md §5b 更新;README 一句
- [ ] T9 构建 dist 进仓 + Playwright(devDeps,开发机-only,写明装法/
      跑法)截图实检:聊天首屏/待办/深浅两态;侧栏五项路由可达
- [ ] T10 全量回归(92+新)+ **协议冒烟实跑(非 skip)** + verify.md
      收口(lane 建议 full:主+三审;聊天是门面 + ds_web 新出站面)

## 不在本期(防蔓延,见 proposal Non-goals)

日历/图片规整/3D 实现、PKB 写端点、katex、语音(transcribe_audio 信封
留在快照文档里但前端不做)、reasoning_delta 思维链展示(快照记形状,
前端 v1 忽略)、Tauri、移动端、动 nanobot 代码。
