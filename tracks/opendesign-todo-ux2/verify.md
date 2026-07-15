# Verify: opendesign-todo-ux2

- Date: 2026-07-15
- Verdict: PASS

> lane: fast(主 agent + submimo)。纯前端 + 组件抽取 + App 清理,后端写口径未动(复用 /api/changes/edit)。

## Mechanical checks

- [x] build passes — `cd web && npm run build`(tsc -b + vite,296 模块)零错;dist 重建。
- [x] tests pass — `node --test tests/*.mjs` 全绿(65,含新增 originalNote 用例);
      pytest 子集(web_api/tools/todo)99 passed(后端未改,全量与上轮同)。
- [x] no secrets / unsafe ops — 无秘密;未新增写口,editChange 仍打既有 /api/changes/edit。
- [x] deployment-target 校验 — 真起 ds_web v0.11.0(隔离 DS_ROOT):health=0.11.0;
      置 C1 已完成 → 待办页 open=空(不见)→ 项目工作区 changes 全量含已完成 C1 →
      POST edit 改回待确认(=变更列点 pill 回滚)→ 待办页 C1 待确认重现。运行态与磁盘一致。

## Review

- lane: fast(主 agent + submimo)。oracle 先跑(build/mjs/pytest 全绿,见上)。
- 主 agent 独立评审(读 employee 前落,/root/aiwork/tasks/opendesign-todo-ux2-my-review.md):
  逐条核 #1(备注预填 + originalNote 不重写)、#2(删下拉)、#3(StatusPicker 抽取 + 变更列回滚 +
  project.key 作 editChange project 参数正确 + onEdited 刷新链 + 死代码清理)。初判 PASS,自留 3 点存疑当 blind-spot 网。
- employee(submimo,mimo-v2.5-pro)独立复审 → **无阻塞(PASS)**:独立读 StatusPicker/todo.ts/api.ts/App.tsx/
  ChangesColumn/测试,逐条确认——StatusPicker 语义正确、`project.key` 匹配 Project.key、originalNote 比较精确、
  dataEpoch→projects→changes 刷新链完整、mark-done 按钮+CSS+onMarkDone/prefillCol+menuFor 全清干净、测试到位。
- 主裁(逐条给基):submimo 无独有 finding,仅逐项确认主 agent 评审;主 agent 自留 3 存疑(多菜单同开/加载态一闪/
  筛选下改状态该项从当前筛选消失)submimo 亦未标,均已知 UX 取舍非缺陷。**合议 PASS,零改动。**

## Accepted deviations

- **备注跨会话不预填**:预填源=本会话乐观 noted[eid];换会话后编辑,备注框空(仍可新写,持久真相在 /changes)。
  不扩 /api/todos(collect 单一真相源)——延续 accepted deviation。用户场景(写完→再进去改)已覆盖。
- **不支持清空/删除备注**:buildEditRequest 空备注视同不改(pre-existing,用户未要求)。
- **StatusPicker 每实例自管 open**:切换菜单需二次点击(backdrop 先收);无害,不升单例。
- **UI 渲染无提交版浏览器 e2e**:逻辑面由 mjs 覆盖,状态机/回滚由真起 ds_web API 级链路覆盖,渲染由 tsc + 目测。
