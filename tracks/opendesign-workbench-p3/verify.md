# Verify: opendesign-workbench-p3

- Date: 2026-07-12
- Verdict: **PASS**(fast lane 主审 + submimo 双 PASS;e2e 真 gateway 7/7 首跑全绿)

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 submimo/subsense/subglm,主 agent 主裁。
> build/test 跑通是机械检查。lane:full(主+3,高风险)/ fast(主+1,medium)/
> self(主自审,小改)。

## Mechanical checks

- [x] build passes(`npm run build`;dist 重构建后 `git status` 干净 = src/dist 一致)
- [x] tests pass(mjs oracle 31/31 = chat 逻辑层零改动机械证明;pytest 117 passed
      7 skipped;版本号升 0.4.0 后 test_ds_web_api 22/22 复跑过)
- [x] no secrets / unsafe ops(纯前端 track;bin/ 与 tests/ 既有文件 diff 为空,
      主 agent 亲手 `git diff --stat` 复核)

## e2e(真 gateway + 真 MiMo,新导航模型)

7/7 首跑全绿:默认落 3a+登录表单 / 登录→3a 空态(问候语+3 chip)/ 3a 发送→
流式→定稿解锁 / 切项目→2a 四列且 home 隐藏但消息仍挂载 / 回 3a 对话原样保留
(keep-mounted 核心断言)/ 2a 右列独立连接二轮(流式→定稿)/ 两实例会话互不串。
截图 /root/aiwork/logs/odw-p3-shots/e2e-0{1..5}.png。

## Review

- lane: **fast**(main + submimo;纯前端壳改、零新攻击面、后端零改动,
  照 design.md 冻结的 lane 决策)
- 主审(先于读任何 employee 输出,/root/aiwork/tasks/opendesign-p3-my-review.md):
  PASS。红线 5/5 亲手复核;F1 = 共享 ChatSession 疑点查实无害(connection.ts:121
  `openSocket()` 每调新建 ws+新 client_id,共享的只是凭据缓存,两实例两连接两会话,
  e2e 第 7 断言实证互不串);F2 = 首条消息发出瞬间 inputCard 换树位 textarea
  remount 一次,纯观感,接受。sub Claude 交付的 13 条取舍全部仲裁(全收,
  细目在 my-review),其中 #6(ChatColumn 收起改 CSS 隐藏)超字面 scope 但
  正中 keep-mounted 主旨,收且好。
- findings 仲裁(每条有据):
  - submimo PASS,0 findings(日志 /root/aiwork/logs/opendesign-p3-review.submimo.log;
    其红线核查、双连接安全分析、事件监听清理核查与主审一致,无需仲裁分歧)
- arbitrated verdict (主裁): **PASS**

## Accepted deviations

- 3a 顶部保留 chat-meta(已连接·模型/退出登录)——spec 写"除此之外不放任何内容",
  但这是唯一登出/状态入口;等用户真机反馈再定去留。
- 登录态不跨实例同步(首次登录在 3a 完成后,2a 右列仍停在登录表单,再点一次即连,
  口令已在 localStorage)——冻结设计"两个独立实例+连接路径不可动"的必然结果,
  T6/T7 会话管理范畴。
- 「新对话」= 回 3a 现状不重置(design.md 已定;真正"再开一条"靠刷新,T7 给显式入口)。
- 首条消息发出瞬间输入卡从 hero 换位到吸底,textarea remount 一次(焦点丢一瞬),
  纯观感。
