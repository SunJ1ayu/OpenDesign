# Tasks: chat-busy-stuck

- base-ref: df527f2

- [x] 判据先行:`chat_reconnect.e2e.mjs` 补 ㉜(修复前红,两条前置全绿)—— `6a54a4b`
- [x] 修复:`pullThread` 在 reconcile 模式下拉不到历史也清 busy/thinking/activity
- [x] build + 该判据全绿 + 版本 0.77.0
- [x] verify(lane: fast,submimo PASS)+ 仓库级总跑全绿 —— 主裁 PASS(代码面)
- [ ] **真机验收**(只有机主能做):新会话发第一句时拔网线/停 gateway,
      等它自己连回来,看发送键是不是能再用。
