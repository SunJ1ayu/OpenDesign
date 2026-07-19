# Tasks: opendesign-frontend-p2-polish

- base-ref: b870363550fdd30f703f84450bb75a6083bbe272

分层流水线(AGENTS.md Tiered execution):主 agent 写 oracle 先行 commit → Sonnet 5
worktree 执行 T1–T3 → 收货三硬闸(oracle byte-diff / 亲跑 / 亲读)→ verify fast lane。

- [x] T0(主 agent)oracle 先行:frontend_p2_polish.e2e.mjs + test_todo_spaces.mjs
      新红;intake/frontend_p1 e2e 双态兼容化、cockpit e2e 中性化(改前仍绿);红检
      后 commit。
- [x] T1(执行腿)A 全局体系:app.css 输入范式/按钮三级/focus-visible/hover 120ms;
      存量裸 input(建档表单/就地编辑/bind 下拉/文件搜索/⌘K)收编。
- [x] T2(执行腿)重点两卡:B 快记单行输入卡(chip popover/toast/顶部高亮)+
      C 连接卡(新对话页居中卡 + 工作区横幅→modal)+ 发送按钮文字化。
- [x] T3(执行腿)D 伴随列减负(inbox 摘要行/速览 row1 删/stage-chip 挪中央列)+
      E 变更行图标按钮组 ✓ + F 空态动作 + G 待办空间小节 + H 小项(lightbox 方向键/
      侧栏建档链接/⌘K 样式);VERSION 0.31.0;npm build + dist 重建。
- [x] T4(主 agent)收货三硬闸 → 亲跑全量(py/mjs/e2e×5/build)→ verify fast lane
      (my-review + submimo)→ merge → push → 归档。
