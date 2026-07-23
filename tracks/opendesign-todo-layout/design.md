# Design: opendesign-todo-layout

- Change: opendesign-todo-layout
- Status: decided(无开放架构分叉,未跑 panel-explore)

## Approach

第一性拆解:这单里**只有一件事是"逻辑"**(卡序 + 谁算闲置项目),其余全是布局与可点性。
按这条线切,才不会把排序规则写死在 JSX 里、也不会出现两套折叠样式。

### 1. 逻辑 → `web/src/todo.ts` 两个纯函数(唯一新增可测面)

```ts
export type ProjectCard = { project: string; items: OpenItem[]; stale: number | null };

/** I.7 卡序。groups 原样带过(project/items 不改),附 stale 天数。 */
export function orderProjectCards(groups: ProjectGroup[], stale: StaleItem[]): ProjectCard[];

/** 闲置项目 = 全部项目 − 有卡的 − 已在「⛑ N 天没动静」独立行报过的。保持 allKeys 传入序。 */
export function idleProjectKeys(allKeys: string[], cardedKeys: string[], staleKeys: string[]): string[];
```

`orderProjectCards` 排序契约(**稳定**,全平局时保持 `groupByProject` 的传入序):

1. `stale !== null` 的卡**整体在前**;
2. 超期组内按 `stale` 天数**降序**(最久没动静的最前 —— 规格只说"超期最前",组内序由本单定:
   天数降序比任意序有用);
3. 非超期组内按 `items.length` **降序**(未办结多的先看);
4. 以上全相等 → 保持传入序。

`idleProjectKeys` 之所以要减掉 `staleKeys`:超期但无未办结的项目**已经**有一条
「⛑ N 天没动静(无未办结条目)」独立行,再进占位卡就是同一件事说两遍。

### 2. 折叠 → 新组件 `web/src/GroupToggle.tsx`,两处复用(用户硬约束的落点)

现有 `.batch-head` 的结构本来就是对的:`<button>` 只包 chev + 标签,**"全选本组"留在按钮外**
(整行做 button 会吞掉卡头里的「去项目 →」,且嵌套 `<button>` 非法)。所以本单不是发明新控件,
是**把它提取成组件 + 一套 class(`.grp-toggle`),项目卡头复用,旧的 `.batch-toggle` 那套删掉不留双份**。

```tsx
type Props = { open: boolean; onToggle: () => void; children: ReactNode };
// 渲染:<button class="grp-toggle" data-ui="group-toggle" aria-expanded={open}>
//        <span class="chev">▾ / ▸</span>{children}<span class="rule" /></button>
```

**可见性修复(反馈 #1)= 让"可点区域"等于"用户以为是一行的区域"**:把原本作为兄弟节点的
`.rule`(细横线)**挪进按钮内**并 `flex:1`,于是按钮横跨整行(只把右侧的「全选本组」/「去项目 →」
留在外面)。这样"整行 hover 背景"与"hover 到的就是能点的"是同一件事,不会 over-claim。
配套:chev 9px → 11px、按钮 hover 有底色 `#f7f5ef`、`cursor:pointer`。

**默认态由调用方给,组件不管策略**(关注点分离):
- 「按时间」日期批次:维持现状 —— 最新一批(gi===0)默认展开,其余收起;
- 「按项目」项目卡:**默认全部展开**(用户是来看待办的,默认藏起来等于倒退)。

折叠状态复用现有 `toggled: Set<string>` + XOR 默认的机制,**不新增 state**;
key 命名空间:时间批次 `@time|<date>`(现状不变)、项目卡 `@proj|<projectKey>`。

### 3. 布局 → `app.css`,两视图各自一个布局 class(不靠覆盖)

```css
.todo-cards.by-project { columns: 2; column-gap: 16px; max-width: none; margin: 0; }
.todo-cards.by-project > * { break-inside: avoid; margin-bottom: 16px; }
@media (min-width: 1600px) { .todo-cards.by-project { columns: 3; } }
.todo-cards.by-time { display: flex; flex-direction: column; gap: 14px; max-width: none; margin: 0; }
```

`.todo-rest`(「⛑ …天没动静」独立行)同步去 880 限宽,否则与铺满的卡片错位。

### 4. 占位卡

「按项目」瀑布**末尾**一张虚线卡 `[data-ui="todo-idle-card"]`:
`{闲置项目名、顿号连接} 没有未办结事项`。项目名取 `projects.find(key)?.name ?? key`(与项目卡同源)。
**只在「按项目」视图出现**(它是项目维度的摘要,时间轴视图里没有位置);它取代原来那行
「其余 N 个项目没有未办结事项」,该行删除。

## Key trade-offs / risks

- **多列 + 弹层**:`columns` 会做 fragmentation,历史上浏览器对多列内 `position:absolute`
  弹层有过 bug。StatusPicker 菜单在「按项目」视图里必须还能开、还可见 → **写进 e2e 当回归防线**。
- **多列改变阅读顺序**(列优先:上→下→换列)。规格明确要瀑布,接受。
- **占位卡列全部闲置项目名不截断**:用户当前 7 个项目,长度可控;真到几十个时是一张长卡,
  不影响正确性。记为已知取舍,不提前造截断规则。
- **超期无卡项目**不进占位卡(见上),避免同一事实两处报。

## Alternatives considered

- **整行 `<div onClick>` 当折叠触发**:能拿到"整行可点",但丢无障碍语义(role/aria/键盘),
  且卡头里的「去项目 →」会嵌在可点区内产生冒泡歧义。否。
- **hover 背景铺满 `.batch-head` 而按钮仍只包 chev+标签**:视觉上"整行可点"但实际只有一小段
  可点,是骗人的 affordance。否 —— 改成让按钮真的横跨整行。
- **CSS grid / JS 测高瀑布**:grid 做不出真瀑布(等高行),JS 测高引入布局抖动与新依赖。
  原生 `columns` 就是规格要的语义,且零依赖。否。

## Test strategy (oracle)

主 agent 亲写、**先 commit 进 main 再派活**,执行腿逐字节 off-limits:

1. `tests/test_todo_layout.mjs` —— 两个纯函数的契约(排序四层键 / 稳定性 / 闲置集三减法 / 空输入)。
2. `tests/e2e/todo_layout.e2e.mjs` —— 真 chromium + 真 ds_web(`DS_TODAY` 冻结今天),验:
   - 「按项目」`column-count` = 2 @1440、3 @1700;「按时间」不多列;两视图都 > 880px 宽;
   - 卡序 = 超期(天数降序)在前、其余未办结数降序(**断言精确顺序**);
   - 占位卡:含闲置项目名、不含超期无卡项目、不含有卡项目、在「按时间」视图不出现;
   - **一致性硬约束机械化**:两视图的折叠触发器同为 `.grp-toggle[data-ui=group-toggle]`,
     且 chev 字号相同、`cursor:pointer` 相同;
   - 折叠行为:项目卡折叠 → 卡内行归零 → 再点恢复;时间批次折叠仍工作;
   - **回归防线**:多列下 StatusPicker 菜单能开且可见;多列下批量勾选仍出浮栏。

红检:实现前 `todo.ts` 无这两个导出 → mjs 整体红;e2e 因无 `.by-project`/`.grp-toggle` 而红。
