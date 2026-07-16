# Verify: opendesign-todo-v3

- Lane: fast(纯前端呈现层,主审 + submimo,同 0.13.0 先例)
- 结论:**PASS**

## 证据
- oracle:test_workbench_p4.mjs 23 例(groupByDate 3 新例先红后绿,groupBySpace
  用例随死代码删除);mjs 5 文件 78 全绿;pytest 283 过 7 skip(既有)。
- tsc rc=0(build 含 tsc -b);npm run build 绿,dist 重建进仓。
- 真起 ds_web 冒烟:/api/health version=0.18.0;/api/todos 契约字段不变。

## 仲裁
- 主审独立审阅(/root/aiwork/tasks/opendesign-todo-v3-review-my-review.md,先于
  employee 报告落盘):PASS,0 blocker;自审抓 1 对齐微调(meta/pill 顶对齐)已修。
- submimo:PASS/LGTM,0 新 finding;其"@ 非法项目名"论据不准(PROJECT_NAME_RE
  实际允许 @),但"无 key 冲突"结论经主审日期形状论证独立成立,收结论拒论据。

## 接受的取舍
- 折叠状态会话级不持久化;编辑中收起批次=编辑框隐藏、state 保留、展开恢复。
- 行内日期移除(批次头已含);e2e 不做(零协议/零后端面)。

## 用户验收断点(部署目标规则)
- git pull → start.ps1 stop → start.ps1 → Ctrl+F5,页脚/health 回显 **0.18.0**;
  待办页:卡片变宽、长事项全文换行显示、项目卡内按日期分批(最新展开,旧批次
  点头部展开),空间显示为行内小标签;按时间视图带日期组头。
