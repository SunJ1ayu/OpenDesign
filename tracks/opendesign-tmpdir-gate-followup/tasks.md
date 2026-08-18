# Tasks: opendesign-tmpdir-gate-followup

- base-ref: 46fbbe87c351a08f5b23a9393faddec06a937694

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。
> **本单没有委托** —— 改的全是判据本身,`oracle 永远由主 agent 亲自写`。

## 第一轮:收上一轮四审的 12 条

- [x] 1. 判据先行(`a4e1e46`):⑭ `mapfile` 缺席必须 rc=2、截断记号两节都要有
      —— 两条都**先跑红**,收据 `20260818T032759Z-01` / `20260818T032803Z-01`
- [x] 2. A(真洞):`_selfcheck=()`,把「闸在 mapfile 缺席时报绿(rc=0)」堵死(`b550dc5`)
- [x] 3. B/C/D/H 四条陈旧或指错门的注释/诊断文案(`b550dc5`)
- [x] 4. E/F/G 死断言闸三条:删掉办不到的消歧建议、ALLOW_WIDE 补印 `命中:file:line`、
      截断记号抽成 `clip()` 两节共用(`b550dc5`)
- [x] 5. 三条「接受分析但不改」写进 proposal,附代码级理由

## 第二轮:收本轮两条腿的发现

- [x] 6. 判据先行(`208db51`):补「短行不许挂截断记号」的反面;
      **变异红检**(把 `clip()` 改成无条件加记号)当场红,收据 `20260818T040323Z-01`
- [x] 7. `tests/run-all.sh` 段号重排的 ⓪ 残留(`7cecd00`)—— **我自审漏的那条**
- [x] 8. `tests/e2e/README.md` 会漂的序号,换成按名字指(`7cecd00`)
- [x] 9. 全仓扫同类陈旧引用,确认没有第四处

## 收口

- [x] 10. 两条评审腿(submimo / subdeepseek)跑完,逐条仲裁进 verify.md
- [x] 11. 权威那一遍总跑(工作树干净、`dirty=no`),收据进 verify.md
- [ ] 12. 归档 + push
