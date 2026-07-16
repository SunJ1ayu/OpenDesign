# Verify: opendesign-connect-ux

- Date: 2026-07-16
- Verdict: PASS

## Mechanical checks

- [x] build passes(tsc -b + vite,dist 进仓)
- [x] tests pass(mjs 5 套件 76 pass/0 fail;py 面仅 VERSION 行)
- [x] e2e 真 gateway + 真 MiMo 6/6 首跑全绿:③未连接降级草稿→登录→①表单确认
      即发送+表单收起→②思考指示出现→回复后消失;截图 3 张(scratchpad
      odw-connectux-shots)。测后全还原:ws disabled、8765/8766/18790 清、
      config/projects 零写入(set_workspace 被 root_not_dir 拒=写侧闸顺带实测)
- [x] no secrets / unsafe ops(路径纯文本进消息,.msg-user 文本节点渲染无注入面)

## Review

- lane: fast(主审 + submimo,PANEL_DIFF_BASE=0ac9ce8)
- 主审(先落盘 /root/aiwork/tasks/opendesign-connect-ux-my-review.md):PASS,
  0 BLOCK/0 MUST;核过 dispatch effect(StrictMode 双跑/陈旧闭包/双击)、
  sendText 零行为变化、思考指示无卡死路径(error 解锁/attach 回放/空消息)、
  colPrefill 删净、表单跨项目保留=语义正确。
- submimo:PASS,核心四面独立核对与主审一致。仲裁:
  - SHOULD 表单状态随 projectKey 重置 → **拒**(接入的是全局工作区非项目,
    保留半填路径是正确语义,重置丢用户输入;主审已预判同点);
  - NIT AGENTS.md 措辞矛盾 → **拒**(时序关系非并列矛盾:一问是第一反应,
    追问是工具调完仍 0 的下一步)。
- arbitrated verdict(主裁): **PASS**

## Accepted deviations

- dispatch 未连接/busy 时降级为预填不排队重发(设计取舍,e2e ③实测降级路径)。
- e2e driver 在 scratchpad 未进仓(p6 同先例);连续两 track 手搓 chat e2e,
  值得沉淀进 tests/,记 O1 留待下次顺手做。
- AGENTS.md 话术更新须随 install 拷贝到 %USERPROFILE%\.nanobot\workspace 才对
  运行 agent 生效(既有 deviation;①②前端改动 git pull 即生效)。
