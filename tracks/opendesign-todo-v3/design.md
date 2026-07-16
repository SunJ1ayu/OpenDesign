# Design: opendesign-todo-v3

- 纯前端呈现层,零后端/零 schema 改动。数据源 /api/todos 不变。

## D1 纯逻辑:groupByDate(todo.ts)
- `groupByDate(items) -> DateGroup[]`,`DateGroup = { date: string|null; items }`。
- 日期倒序;无日期(null)恒沉底;组内保持传入相对序(稳定)。
- oracle 直测(test_workbench_p4.mjs),先红后绿;groupBySpace + 其用例删除。

## D2 项目视图(TodoPage)
- 项目卡内:空间小节 → 日期批次小节。批次头 = `M月D日 · N 条` + 折叠箭头,
  点击切换;**每卡最新一批默认展开,其余收起**;无日期组头显示「未标注日期」。
- 折叠态 = 组件内 `Set<`${project}:${date}`>`(记"被点过反转"的组,相对默认取反,
  会话级,不持久化)。
- 空间改行内标签:row 里 cnum 后加 `【空间】` 小 chip(有才显示)。
- 行日期冗余:批次头已有日期,row meta 里的日期仅在时间视图保留(项目视图去掉)。

## D3 时间视图
- `sortByDateDesc` 后套 `groupByDate` → 跨项目按日期组头,同样可折叠、
  最新默认展开;行带项目链接(现状保留)。

## D4 布局 CSS(app.css)
- `.todo-cards` / `.todo-rest` max-width 860 → 1100px。
- `.todo-row .txt`:去 nowrap/ellipsis,`white-space:normal; word-break:break-word;`
  `.todo-row` `align-items:flex-start`(多行时 pill/meta 顶对齐);编辑态不变。

## D5 版本
- ds_web.py VERSION → 0.18.0;dist 重建进仓。

## 验证
- oracle:node --test tests/*.mjs 全绿(groupByDate 新用例先红);npm run build 绿;
  真起 ds_web 冒烟 /api/todos 契约不变。
- verify lane = fast(纯呈现层,主审+submimo,同 0.13.0 先例)。
