# Tasks: opendesign-workbench-p1

- base-ref: e2b5b11473e6e55178f17743ec0db228ce0632b2
- 状态:**plan v2 已冻结**(sub Claude 评审 11 findings 全采纳合并,
  仲裁记录在 design.md 尾部);等用户 go 开工

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

## 实施顺序

- [x] T0 协议基线快照 ✅ 2026-07-08 完成:enable_webui.py 部署形状真
      gateway 实抓全链路,`docs/nanobot-ws-protocol.md` 落盘;
      `tests/test_ws_protocol_smoke.py` gated 冒烟(实跑含 LLM 链 OK,
      gateway 停后 SKIP 路径验证 OK,config 已还原)。F11 答案:不带
      webui:true 也回补进历史但缺 turnId,前端一律带。token 一次性、
      attach、401 形状、分页全部实测确认与 plan v2 一致,零意外。
- [ ] T1 oracle 先行(red-check):设计 Test strategy 七条中 1-4
      (白名单+key 字符集/502/401 透传+hop-by-hop 剥离/XSS 闸),
      mock 上游 fixture(stdlib http.server 线程)
- [ ] T2 ds_web 代理实现:三条白名单 GET 映射
      `/api/chat/bootstrap→/webui/bootstrap`、
      `/api/chat/sessions→/api/sessions`、
      `/api/chat/sessions/<key>/thread→/api/sessions/<key>/webui-thread`;
      `<key>` 按 `[A-Za-z0-9_:.-]{1,128}` 先验;查询串透传;上游硬编码
      127.0.0.1:8765(DS_NANOBOT_PORT 可覆盖);纯管道零秘密;T1 转绿
- [ ] T3 视觉重皮肤 + IA 重排:nanobot token 两套变量落 `web/src`,
      13/14px + cjk 行高 + 零阴影边框;侧栏五项(聊天首屏/待办/日历占位/
      工具箱占位卡片页/设置占位含深浅切换);待办页换皮不动逻辑
- [ ] T4 聊天登录/连接流(按 v2 token 模型):口令一次 → localStorage →
      每次开 ws 前经 bootstrap 新签一次性 token(多标签页/StrictMode
      双连各自独立签);前端用 ws_path+已知端口自拼地址(ws_url 只作
      参考);HTTP 401 → 透明重 bootstrap;重签仍 401 → 弹回登录
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
