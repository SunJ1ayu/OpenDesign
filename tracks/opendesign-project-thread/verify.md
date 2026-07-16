# Verify: opendesign-project-thread

- Lane: fast(前端+AGENTS.md,零后端/零协议改动)+ 真 gateway e2e
- 结论:**PASS**

## 证据
- oracle:test_project_thread.mjs 9 例先红后绿;mjs 全家 87 绿;pytest 抽
  web_api+tools 139 绿;build(tsc -b)绿。
- **e2e 真 gateway+真 MiMo 7 步全过(最终轮含真 AI 回复整轮)**:①前缀上屏
  ②A 映射入 localStorage ③B 全新上下文(转录清空)④B 映射独立 ⑤切回 A
  attach 回放命中+chat_id 稳定 ⑥虚会话再入不卡死+映射自愈+不误伤 A。
  gateway 日志实证 agent 收到【当前项目】前缀后自主调 read_project(翡翠湾-1801)
  =AGENTS 规则 6 端到端生效。config/端口测后还原实证(restored: False '')。
- e2e 基建沉淀 tests/e2e/(helpers+README+场景),O1 工具债还清;
  tests/*.mjs glob 扫不到,常规回归不误红。

## 仲裁(主审 my-review 先行:/root/aiwork/tasks/opendesign-project-thread-review-my-review.md)
- 主审:PASS。**自审抓到并修掉 1 真竞态**——连接建立中切项目,colProjectRef 方案
  会把 A 的 chat_id 记到 B 名下;改回调按 colChat 闭包绑定项目(effect 捕获发起时
  回调),晚到回调记正确项目;onAttachFailed 加 selKeyRef「仍在该项目才重连」。
- submimo:Approve(821 行真卷,审的是 refactor 后代码)。收:step7 断言太弱
  →已加映射自愈+不误伤断言并重跑全绿;拒:dispatch effect 无依赖数组
  (既有文档化模式,dispatchedRef 去重,非本 track);记 follow-up:
  「+ 新对话」/deleteSession 清映射/dispatch 前缀的 e2e 缺口(纯逻辑已有 oracle)。

## 接受的取舍
- eager 记账(选中即连即记;虚会话自愈兜底,e2e 实证);映射本机不跨设备
  (丢=重开,PKB 零损失);每项目多条对话管理=非目标;启动时列实例多一次废弃
  连接(无消息会话不落历史);「≡ 历史对话(即将支持)」死占位换成「+ 新对话」。
- 观察项:历史页点开项目会话=home 实例续聊,与列实例可能双 attach 同一
  chat_id(既有 p6 行为面,未观察到冲突)。

## 用户验收断点
- git pull → start.ps1 stop → start.ps1 → Ctrl+F5 回显 **0.20.0**;
  ①项目 A 聊一句(消息带【当前项目:A】前缀)→ 切项目 B:聊天列全新对话
  → 切回 A:刚才的对话还在;②侧栏历史对话里项目会话带项目名小标;
  ③聊天列头部「+」=该项目重开新对话。
