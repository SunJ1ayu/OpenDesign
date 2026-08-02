# Design: opendesign-todo-ux2

- Change: opendesign-todo-ux2
- Status: draft

> 非开放架构分叉(既定 UI 二轮 + 复核早有结论:回滚落项目视图),不跑 panel-explore。

## Approach

### 共享组件 StatusPicker(消除两处菜单副本)
可点 pill + 快捷菜单抽成 `web/src/StatusPicker.tsx`,待办页与变更列共用。自管开合 + fixed backdrop
点外收起;`onPick(next)` 交调用方决定写口径与后续(待办页=撤销 toast;变更列=直接改 + 重拉)。

### #1 备注在原文上改
- TodoPage.startEdit 预填 `note = noted[eid] || ""`(本会话乐观备注);save 传 originalNote 同源。
- todo.ts `buildEditRequest(item, draft, originalNote="")`:note trim 非空**且 != originalNote.trim()** 才带。
  向后兼容(默认 ""=新加备注,行为不变)。

### #2 删待办编辑框状态下拉
editor 只留 正文 + 备注 + 存/取消;状态改统一走 pill。draft.status 不再设/用。

### #3 变更列可点回滚(已办结项的家)
- ChangesColumn 每个 cnum!=null 行的 pill 换 StatusPicker;"全部"筛选下已完成/已关闭也在 → 点回滚。
- pickStatus → `editChange({project: project.key, cnum, new_status})` → `onEdited()`;错误就地 actionErr。
- 去掉冗余「✓ 标记完成→交 AI」按钮(pill 已能直接改;写口径同 /api/changes/edit)。
- App.tsx:删 onMarkDone/prefillCol;colPrefill 降常量占位(仍满足 ChatColumn 契约);
  ChangesColumn 改收 `onEdited={()=>setDataEpoch(n=>n+1)}` → projects 重拉 → changes effect 跟着重拉。

## Key trade-offs / risks

- **待办页 vs 变更列的写后行为不同**:待办页改到终态该项会消失,故给撤销 toast;变更列"全部"下不消失,
  故不给 toast、直接可再点回滚。两者共用 StatusPicker、语义由调用方 onPick 决定——刻意设计。
- **StatusPicker 每实例自管 open**:多菜单理论可同开,但 backdrop 点外即收,切换二次点击。可接受,不升单例。
- **去 mark-done 改变了"改状态经 AI"的老设计决策**:因写针孔已存在且用户要直接改,直接写更顺;非只读回退。

## Alternatives considered

- 保留 mark-done + 加 pill:否——正是用户 #2 抱怨的冗余;两条"标记完成"路径(交 AI vs 直接)徒增困惑。
- 把回滚做进待办页(显示已完成折叠区):否——待办页语义=未办结;已办结管理属项目视图(复核早有结论)。
- 扩 /api/todos 带 note 让备注跨会话预填:否——破坏 collect 单一真相源;本会话乐观预填已覆盖用户场景。

## Test strategy (oracle)

- mjs(先红后绿):buildEditRequest originalNote==则不带 / 改了仍带;既有契约不回归。
- py:后端未改,web_api/tools/todo 子集绿(全量与上轮同)。
- e2e(真起 ds_web v0.11.0):置已完成→待办页不见→变更列全量含已完成→点 pill 回滚待确认→待办页重现。
- 部署目标:真机 pull + rebuild(dist 已提交),页脚回显 0.11.0。
