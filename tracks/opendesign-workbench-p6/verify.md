# Verify: opendesign-workbench-p6

- Date: 2026-07-13
- Verdict: **PASS**(主审 + submimo 双 PASS,fast lane)

## Mechanical checks

- [x] build passes(`tsc -b && vite build` 零错;dist 进仓,VERSION 0.7.0)
- [x] tests pass(mjs 51/51 = transcript 22 含 p6 新 5 条先红后绿 + connection 14 +
      gallery 7 + p4 8;py 176 passed 7 skipped 全量)
- [x] no secrets / unsafe ops(纯前端接线 + VERSION;ds_web.py 代理/闸零改动;
      attach chat_id 三重闸:前端 websocket: 前缀白名单 + JSON 转义 + 服务端
      _is_valid_chat_id;thread URL 受代理 _KEY_RE/_THREAD_RE 段界限)

## e2e(真 gateway + 真模型,ds-web 0.7.0)

3/3 PASS(driver = scratchpad/e2e_p6.py,截图 /root/aiwork/logs/odw-p6-shots/):
① 首页聊一轮(MiMo 真回复)→ 侧栏历史对话**无 reload**出现(turn_end 自动刷新);
② reload 模拟「下次打开」→ 3a 空态 → 点历史行 → 旧消息回放可见 + attach 已连接;
③ 续发一条 → thread API 证实两条用户消息同会话(归位,非新开)。
环境:enable_webui 临时 token,测完 config 已还原(websocket disabled+token 空),
端口清。e2e 实抓 1 真 bug 当场修:ChatPage thread URL encodeURIComponent 把
websocket: 编成 %3A 被代理 _KEY_RE 拒 → 404 静默无回放;改裸 key+注释钉住,复跑过。
另:e2e 剧本第一版点「新对话」期望空态与 p3「非 resume 态不重置」冲突——产品行为
对、剧本错,改 reload 取证。

## Review

- lane: **fast**(纯前端接线、零后端/安全面改动、oracle+e2e 全绿;主审+submimo)
- 主审(先于读任何 employee 报告落盘):/root/aiwork/tasks/opendesign-p6-review-my-review.md
  —— verdict PASS,七个面逐条 file:line 核过(resume 竞态/回放前插/attached 前
  error 窗口/turn_end 不吞事件/chat_id 注入面/hooks 依赖边界/p3 约定)。
- submimo:**PASS**(日志 /root/aiwork/logs/opendesign-p6-review.submimo.log)——
  六个面完整交卷(竞态/泄漏、回放前插、turn_end 范围、注入面、hooks 依赖、p3 兼容)
  全 PASS,与主审逐条一致。
- findings 仲裁:唯一可选建议(turn_end 加 `if (!target || attached)` 守卫)**拒,有据**:
  设想的"attach 前默认会话 turn_end"不可达——默认 chat_id 从未被发消息,无轮次可
  结束;守卫属死代码。其"另一实例 socket closed/idle"推理不准(keep-mounted 两连接
  都活),但结论无碍:一轮 turn_end 只属一条连接,无重复触发。
- arbitrated verdict (主裁): **PASS**——主审七面亲核 + submimo 六面独立复核一致;
  oracle(mjs 51/py 176)与 e2e 真 gateway 3/3 在读报告前已 rc=0。

## Accepted deviations

- nanobot /api/sessions 忽略 limit 参数(上游行为,前端 slice(0,2) 自保,带宽量级无害)。
- thread 回放丢弃非 string content 的用户消息(媒体)——前端本就不能发媒体,对齐降级。
- 点「当前正在聊」的历史行会重连打断进行中的流式回复——窄边 UX,回放/续聊语义仍正确。
- 「全部对话」入口维持「即将支持」(proposal Non-goals)。
