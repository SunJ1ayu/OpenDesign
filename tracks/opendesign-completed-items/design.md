# Design: opendesign-completed-items

- Change: opendesign-completed-items
- Status: done

> 非开放架构分叉(纯呈现层),未跑 panel-explore。深浅由用户拍板:
> 「已办结筛选 + 项目进度一览」(否掉"只加筛选"的更浅版)。

## Approach

- **抽纯逻辑** `web/src/workspace/changes.ts`(仿 todo.ts):`changeCounts`(四态计数 +
  open/done/all 聚合,一遍扫描,未知态只进 all)、`filterChanges`(按筛选取子集,保序)、
  `OPEN_SET`/`DONE_SET`/`PROGRESS_ORDER`/`StatusKey`/`Filter`。oracle 直测。
- **ChangesColumn** 改用纯逻辑(删内联 counts/shown useMemo + 内联 OPEN_SET/Filter);
  筛选栏 未办结/待确认/进行中/**已办结**/全部;项目标题下加**进度一览**(PROGRESS_ORDER 序,
  只显 count>0 的态,色点复用 `--st-*-dot`)。
- **回滚正交**:每行 StatusPicker 不受 filter 影响,「已办结」/「全部」下仍可点回任意态(A2 能力保留)。

## Key trade-offs / risks

- **已办结 = 已完成 + 已关闭**(一个聚合 pill,不拆两个)——匹配"翻回已办结项"语义,避免 6-7 个
  pill 挤爆;完成 vs 作废由每行 status pill 区分。
- 未办结/已办结两个聚合 + 待确认/进行中子项 = 计数重叠(子项算进未办结)。沿用既有"未办结=待确认+进行中"
  的聚合+子项模式,不算新困惑。
- 纯前端、后端零改动;风险面 = 呈现层,fast lane 足矣。

## Alternatives considered

- 只加「已办结」筛选(不加进度一览):用户否掉,要一眼看进度。
- 已完成/已关闭拆两个 pill:否——挤 + 与聚合模式不一致。
- 逻辑留在组件内联:否——不可 oracle 直测;抽 changes.ts 与 todo.ts 对称。

## Test strategy (oracle)

- mjs `tests/test_completed_items.mjs` 11 例:计数/聚合互补/未知态只进 all/筛选保序/null 安全/
  常量契约。red-check:DONE_SET 缺 已关闭 → 4 红。
- build(tsc -b)+ 真起 ds_web /api/changes 契约对齐(状态串 = 四态,open/done/all 与逻辑一致)。
- fast lane(主 + submimo)。
