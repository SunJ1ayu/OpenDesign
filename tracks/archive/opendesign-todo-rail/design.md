# Design: opendesign-todo-rail

- Change: opendesign-todo-rail(设计交付包 v4 §I.9 的前两段)
- Status: decided(无开放架构分叉,未跑 panel-explore)

## Approach

设计稿 §I.9 要求待办页加 320px 右栏,三段:①日程月历 ②需要今天跟进 ③项目助手。
**本单只做 ①②(+ 右栏骨架),③ 拆到紧接着的下一单 `opendesign-todo-assistant`。**

### 为什么拆(结构性依赖,不是砍范围)

`App.tsx:453` = `{route === "todos" && <TodoPage/>}` —— **待办页不是 keep-mounted**
(源码注释:「无状态页:每次进入重建」)。而 §I.9 要求项目助手「发送后就地展开成对话流」,
把 `ChatPage`(560 行,持有 ws 会话 / resume / project-thread 记账)挂进一个会被卸载的
页面 = **切页丢对话** —— 正是 track p3 做 keep-mounted 要治的那个真机 bug。
正确做法要先把待办页改成常驻路由并接 session 管线,那是独立的一块工作与独立的风险面
(需真 gateway e2e)。①② 则是 `due` 的纯派生,零连接依赖、可离线判定。
**两单连做,顺序 = 先地基后集成。** 右栏容器 `TodoRail.tsx` 本单建好,③ 直接往里加一段。

### 1. 逻辑 → 新文件 `web/src/schedule.ts`(三个纯函数)

```ts
export type CalCell = { date: string; inMonth: boolean };
export function monthGrid(year: number, month: number): CalCell[];   // 恒 42 格,周一起始
export function dueDates(items: OpenItem[]): string[];               // 去重升序
export function followUpItems(items: OpenItem[], today: string): OpenItem[];
```

**关键第一性:圆点不发明新分类。** 红/琥珀直接用 todo.ts 既有的
`dueStatus(date, today) → overdue | today | upcoming`,月历只需回答「哪些日期有到期事项」
(`dueDates`)。同一个问题(某日期相对今天算什么)不留第二个答案。

`monthGrid`:周一起始(表头 一二三四五六日),恒 6×7=42 格铺满,前后补邻月并标
`inMonth:false`。**圆点跟数据走,邻月补格照样带点**——补格是看得见的真日期,
在它上面藏点等于撒谎,还要多写按月特判。

`followUpItems`:只取 `overdue` + `today`;超期在前且越久越前(due 升序),今天到期垫后;
同 due 保持传入序(稳定)。

### 2. 组件 → 新文件 `web/src/TodoRail.tsx`

状态边界:自己持有「当前显示月份」(纯展示态),把「选中日期」上提给 TodoPage
(因为它要过滤主列表)。两段:日程概览 / 需要今天跟进(下一单在其后追加项目助手)。

### 3. TodoPage:日期过滤

新增 `dateFilter: string | null`;过滤谓词 = `it.due === dateFilter`,**两个视图都过滤**
(点日期是全局意图,不是某个视图的局部开关)。再点同一日期取消。
过滤生效时在主区顶部显示一条 `[data-ui="todo-date-filter"]` 过滤条(带 ✕ 清除)——
设计稿没画,但**列表凭空变短而无任何提示会让人困惑**,补一条是诚实成本。

### 4. 布局

`.todo-page` 改 `display:flex`:主区 `flex:1 min-width:0`(既有多列瀑布不动)+
`.todo-rail { flex:none; width:320px }`。§I.9 说「≥1600px 时中间三列、右栏仍 320px」——
既有 `@media (min-width:1600px){ columns:3 }` 是**视口宽**判据,右栏占掉 320px 后主区
自适应,无需改。

## Key trade-offs / risks

- **「与主列表互补不重复」**:设计稿这句是相对它旧稿的「今日待办=复读主列表前三条」而言。
  本单的跟进区是**另一套判据**(超期+今天到期)的跨项目视图,与主列表天然有交集;
  **不会从主列表里剔除这些条目**——主列表的完整性优先。记为 accepted deviation。
- **月历格用 `data-date` 精确寻址**(而非"数字 15"),否则邻月补格的同数字会撞。
- 项目助手拆走 → 本单右栏底部留白,视觉上不完整。可接受(下一单补齐)。

## Alternatives considered

- **月历自己再判一次超期/未来**:会出现第二套日期分类,与 `dueStatus` 漂移。否。
- **日期过滤只作用于「按时间」视图**:点月历是全局意图,分视图会让人以为坏了。否。
- **不加过滤提示条**:照设计稿字面,但用户会看到列表莫名变短。否(加一条)。
- **邻月补格不画圆点**:更"干净",但在看得见的日期上藏信息,且要多写按月特判。否。

## Test strategy (oracle)

主 agent 亲写、先 commit 再派活,执行腿逐字节 off-limits:

1. `tests/test_schedule.mjs`(19 例):`monthGrid` 42 格/周一起始/首日恰为周一不补前导/
   闰年平年/跨年/日期严格连续;`dueDates` 去重升序、无 due 不参与、无副作用;
   `followUpItems` 判据、排序、稳定性、同引用、无副作用。
   **月历算术已用 Python `date` 独立核对**(2026-07-01 是周三 → 首格 06-29;第 42 格 08-09)。
2. `tests/e2e/todo_rail.e2e.mjs`(真 chromium + 真 ds_web,`DS_TODAY=2026-07-22`):
   右栏 320px + 主区仍多列;月份头/今天高亮/42 格;四个到期日的圆点与着色;
   邻月补格带点但标非本月;月份前后翻(用只存在于 8 月网格的 8/20 证明真换了网格);
   点日期过滤主列表 + 选中态 + 过滤条 + 再点取消;跟进区三条的内容/顺序/文案/项目名;
   **反应性**:批量把这三条改「已完成」→ 圆点消失 + 跟进区落到空态文案。
   夹具已实跑核对(6 条未办结,`⏳` token 全部解析出 due)。
