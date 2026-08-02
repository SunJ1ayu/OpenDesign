# Verify: opendesign-todo-ux

- Date: 2026-07-15
- Verdict: PASS

> lane: fast(主 agent + submimo)。理由:纯前端 + AGENTS.md 文案,后端写口径未动
> (复用已过 todo-edit 完整 panel-review 的 `/api/changes/edit` 针孔),无新端点/攻击面/数据一致性面。

## Mechanical checks

- [x] build passes — `cd web && npm run build`(tsc -b + vite)零错;dist 重建。
- [x] tests pass — `node --test tests/*.mjs` 全绿(64 用例,含新增 isTerminalStatus/STATUS_HINT);
      `python3 -m pytest tests/ -q` = 236 passed / 7 skipped。
- [x] no secrets / unsafe ops — 无秘密;未新增写口,editChange 仍打既有 `/api/changes/edit`。
- [x] deployment-target 校验 — 真起 ds_web v0.10.0(隔离 DS_ROOT),curl 走通用户点击驱动的状态机:
      health 回显 0.10.0 → /api/todos 有 C1 待确认 → 改『已完成』(终态)→ 该项离开 /api/todos(空)
      → 撤销改回待确认 → 项回来 → 加备注 → changes 端点带回 note。运行态与磁盘一致。

## Review

- lane: fast(主 agent + submimo)。oracle 先跑并记录(build/mjs/pytest 全绿,见上)。
- 主 agent 独立评审(读 employee 前落 findings,见 /root/aiwork/tasks/opendesign-todo-ux-my-review.md):
  逐条核 A1(no-op 不发/cnum=null 退化/终态次级显眼度)、A2(prevStatus=变更前快照、toast 独立于列表 state、
  仅终态弹撤销)、A3(noted map key=project:Ccnum 不串、持久留痕在 /changes)、A4(STATUS_HINT 单一真相 +
  AGENTS.md 语义)、回归(未改后端写口径/未加端面)。初判 PASS,自留 3 点存疑当 blind-spot 网。
- employee(submimo,mimo-v2.5-pro)独立复审 → **PASS**(真读 TodoPage/todo.ts/api.ts/ds_web.py/测试;
  确认状态机边界、toast 独立、prevStatus 正确、无后端面扩张)。两条非阻断观察:
  - **[ACCEPT-as-known] 并发改状态下 prevStatus 陈旧**:双客户端并发时撤销可能回到过时态。
    基:north-star 明确单设计师本地单用户,并发非真实场景;且结果对用户可见可再改。非本组正确性缺陷。
  - **[ACCEPT-as-known] toast 6s 窗口**:读得慢可能错过撤销。基:有手动 ✕ 关闭 + 新变更会重弹;
    刻意的瞬时提示取舍。撤销窗口关掉后改回属 #7 第一刀(项目级视图)范畴。
- 主裁(逐条给基):submimo 两观察均为已知取舍非缺陷(依据同上),与主 agent 自留存疑重合;
  无被证伪的主 agent finding;无遗漏的 employee 独有 finding。**合议 PASS,零改动。**

## Accepted deviations

- **备注/看原文为本会话乐观留痕**,刷新即失;持久真相在项目 .md 变更历史段(工作台变更列 /changes 可见)。
  有意不扩 `/api/todos`(collect 单一真相源,爆炸面大)——延续 todo-edit 的 accepted deviation。
- **UI 层(菜单开合/backdrop/toast 渲染)无提交版浏览器 e2e**:逻辑面由 mjs oracle 覆盖,
  状态机由真起 ds_web 的 API 级链路覆盖,渲染由 tsc + 目测覆盖。单用户展示型 UI,可接受。
- **快捷菜单改到非终态时 setToast(null)** 会顺手清掉别 item 遗留的 undo toast:无害轻微副作用,
  新动作清旧瞬时提示合理,不改。
