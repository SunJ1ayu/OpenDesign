# Tasks: opendesign-gate-doc-sync

- base-ref: 23de411

- [x] 扫活文档(排除 logs / attack-logs / tracks/archive 这些史料),按名字而不是凭印象
- [x] `tests/e2e/README.md`:补新闸说明 + 去掉会漂的「六段」 + 说明那段 build 输出是正常的
- [x] `tests/run-all.sh` ⑤ 段:写明它**也是本仓库唯一的类型检查**,并记下它的 fail-open
- [x] `tests/e2e/check-dist-fresh.sh`:写明与 ⑤ 段的分工(防被当重复删掉)
- [x] `docs/backlog.md`:两道闸并存 + ⑤ 段 fail-open + 「tsc 该有独立段」记账
- [x] 变异锚点唯一性自查(加注释可能撞锚点,`replace(...,1)` 会改错地方)
- [x] 判据重跑(改了判卷防线的注释就得跑它自己的判据)
- [x] 红检重跑(证明锚点没被注释撞坏)
