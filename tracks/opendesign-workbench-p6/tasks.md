# Tasks: opendesign-workbench-p6

- base-ref: a260294183f9734273fb0d96537d4c2ff36de925

- [x] T1 transcript.ts:`hydrateFromThread` + `attachEnvelope` 纯函数;oracle 进
      tests/test_chat_transcript.mjs(先红后绿:5 新用例)
- [x] T2 ChatPage:`resume` prop(attach 流程 + thread 回放前插)+ `onTurnEnd` 回调
- [x] T3 App+Sidebar:hist-row onClick → openSession(路由 #/ + resume 目标);
      turn_end → sessionsEpoch 递增;新对话清 resume(非 resume 态 bail-out 保 p3)
- [x] T4 VERSION 0.7.0 + `npm run build` 重建 dist;mjs 51 + py 176 全绿
- [x] T5 e2e 真 gateway 3/3(①无 reload 出现②reload 后点历史回放③续发归同一会话);
      driver = scratchpad/e2e_p6.py,截图 /root/aiwork/logs/odw-p6-shots/;
      实抓 1 真 bug(encodeURIComponent vs 代理 _KEY_RE)当场修
- [ ] T6 verify:panel-review(fast lane)→ 收口归档
