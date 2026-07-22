# Design: opendesign-todo-batch-space

- Change: opendesign-todo-batch-space
- Status: draft

> 非开放架构分叉 —— 三项都有明确单一走法,不跑 panel-explore。主 agent 方向已定如下。

## Approach

### #2a 待办页批量改状态(TodoPage.tsx + todo.ts;零新后端)

**核心决策:客户端串行调既有 `/api/changes/edit` 写针孔,不新开后端端点。**
理由:每条 `edit_change` 已自带锁+保格式(久经测试);批量状态改本就容许部分失败;新写口=更大
攻击面+并发坑(参 [[worktree-symlink-hazard]] 邻近的 amend 并发教训)。串行 await 逐条发,
不同项目=不同文件、同项目=串行不自撞,无并发损坏。

- **新纯函数** `todo.ts::batchEditRequests(items, newStatus)` —— 契约见
  `tests/test_todo_batch.mjs`(已 commit,off-limits):选中项 → `{project,cnum,new_status}[]`,
  跳过 `cnum===null`(残缺行不可寻址)与 `status===newStatus`(空操作),保持序,非法态抛。
- **选择模型(与分组解耦,两视图通用)**:选中集 = `Set<string>`,键 = `${project}:${line}`
  (与 row key 同源,唯一)。每条 `todo-row` 加复选框(`data-ui="todo-select"`);
  每个分组头(按时间的日期批次 `batch-head` + 按项目的空间小节 `space-sect-head`)加
  「全选本组 / 取消本组」。选择键与视图无关 → 切视图不丢选中也可(实现从简:切视图清空选中亦可,
  但两视图各自都要能选)。
- **浮动操作栏**:选中 ≥1 条时底部浮出 `data-ui="todo-batch-bar"`:「已选 N 条」+ 状态选择器
  (复用 `StatusPicker`,标签「改为…」)+「取消」。
- **应用**:`batchEditRequests` 产出逐条 await `editChange`;成功/失败计数;完成后清空选中 + `reload()`
  + toast「已改 N 条」(有失败追加「M 条失败」)。**目标为终态(已完成/已关闭)且 ≥2 条 → 先
  `window.confirm` 确认**(终态会把项从页面移除,批量不可逐条撤销,故前置确认;非终态直接应用)。
- 单条 pill 快捷改状态**保持现状不动**(批量是增量,不替换)。

### #2c 单项目变更列 时间/空间 分组切换(ChangesColumn.tsx + workspace/changes.ts)

- **新纯函数** `changes.ts::groupByDate` / `groupBySpace` —— 契约见
  `tests/test_change_grouping.mjs`(已 commit,off-limits):语义与 `todo.ts` 同口径
  (日期倒序·null 沉底;空间首现序·null 沉底;组内保序;空→[])。**镜像而非复用** todo.ts
  版本(那边是 OpenItem 类型、blast radius 大),本层用 Change 形状独立实现+独立 oracle。
- **UI**:filter pill 附近加分组切换「按时间 / 按空间」(默认**按时间**)。先 `filterChanges`(状态筛选
  保持现状)再分组渲染分节:节头=日期(`cnDate`)或空间名(null→「未标注日期」/「未分空间」)。
  分节不必折叠(v1 从简,纯展示分节即可);行渲染完全复用现有 `.change-row` 结构不动。

### #3 侧栏建档标记灰色化(workspace/Sidebar.tsx + app.css)

- `Sidebar.tsx:188-192` 删掉 `unregistered` 分支里的两个 span(`reg-link`「建档 →」+
  `n-unreg`「未建档」);`unregistered` class 与 `title`(已含 hover 提示)保留;`onClick` 不动
  (点击仍进项目视图触发建档流)。
- `app.css`:`.proj-row.unregistered .nm` 用中性灰(muted 类 token),已建档保持原色。**只加/改
  这一条规则**,不动别的 proj-row 样式。

## Key trade-offs / risks

- 客户端串行批量=**非原子**:中途失败会部分应用。缓解=逐条计数 + 明确 toast「已改 N / M 失败」+
  reload 拉回真相;不谎报全成功。(可接受:状态改是幂等可重试的。)
- 终态批量不可逐条撤销 → 用前置 `confirm` 兜底(仅终态 ≥2 条)。
- 选择键 `${project}:${line}`:line 是行号,同一 reload 内稳定;应用后立即 reload+清选,不跨 reload 复用。

## Alternatives considered

- **新后端批量端点** `/api/changes/batch-edit`:更原子/更省往返,但=新写针孔(更大审查面+并发坑),
  违背"最简方案"。否决——批量状态改容许部分失败,客户端串行足够。
- **把 todo.ts 的 groupByDate/spaceSections 泛型化复用**:DRY 但要动 TodoPage 依赖的共享函数签名,
  blast radius 大。否决——单项目层独立实现+独立 oracle,隔离风险。

## Test strategy (oracle)

主 agent 亲写、已 commit 先行、对执行腿 off-limits:
1. `tests/test_todo_batch.mjs`(7 例)—— `batchEditRequests` 全契约(序/跳空操作/跳残缺/非法抛/纯函数)。
2. `tests/test_change_grouping.mjs`(7 例)—— `groupByDate`/`groupBySpace`(倒序/首现/null 沉底/纯函数)。
3. **e2e**(执行腿写、主 agent 亲跑复核,非 byte-protected)`tests/e2e/todo_batch_space.e2e.mjs`:
   真 chromium + 真 ds_web,断言 —— 待办两视图各能选 2 条→浮栏→改状态→落盘+reload 生效;
   单项目切「按空间」出现空间分节;侧栏未建档项目**无**「建档/→」文字、`.nm` 取灰色 class 生效。
4. 回归:全量 mjs (`node --test tests/*.mjs`) + py 套件 + build 必须全绿。

verify lane = **full 四审**(#2a 是状态流转写路径面)。
