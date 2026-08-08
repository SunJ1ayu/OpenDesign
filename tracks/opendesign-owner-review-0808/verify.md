# Verify: opendesign-owner-review-0808

- Date: 2026-08-08
- Verdict: PENDING(等主 agent 裁决——本轮执行方只写证据,不下最终结论,见下方说明)

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [ ] build passes
- [ ] tests pass
- [ ] no secrets / unsafe ops

**机器打印的**(不是我的转述)—— 判据用 `runlog` 跑,把它打印的收据行原样粘进来:

```
runlog -t opendesign-owner-review-0808 -- <判据命令>
```

```
<粘收据行,逐字节,别改数。**每次提交**都会跟 evidence/ 里的收据逐字节比对(5a);
 **归档时**还要求:最后跑的那一遍必须在这儿、跑红的那几遍一份都不许藏(5b)、
 收据得进 git(5d)。一份收据都没有的话,写一行
 「- 无机器证据:<理由>」认账 —— 沉默不算理由(5c)。>
```

## Review

- lane: full
  > delete_change 是全新的写操作(单条变更软删除),碰了新写口 —— 硬规矩,不降档。
- 派给: 主 agent 直接干(偏离了 tasks.md 原定的「codex/gpt-5.5」)。
  > 原因:开工前设计阶段(design.md)已经把每个改动的确切文件/函数/行为逐条钉死
  > (定位复用 set_change_status 的 line_re、展示层要改哪两处、前端按钮插在
  > TodoPage.tsx 哪一行),写一份能让 codex 独立干活的任务书,信息量已经约等于
  > 直接实现——"切碎反而更贵"(delegate skill 原话)。执行这段的是同一个已经
  > 带着完整上下文的 agent(fork),不存在"省 Claude 额度给规划"的取舍前提
  > (那是主会话调外部腿才有的量)。收货仍按三道硬闸走(diff/亲跑/亲读),
  > 只是没有"外部腿"这一环,直接对着 oracle 自己实现自己核对。
- 规格自查(读任何 panel 输出之前先答):<如果规格本身就是错的,会错成什么样、我怎么发现?
  panel 只验"实现合不合规格",验不了"规格对不对" —— 四腿齐 PASS 不等于题是对的。>
- 腿的花名册: <把 `<日志前缀>.roster` 里那一行**原样粘过来**,别手写>
  > panel-review 收尾自己写这个文件(off / FAIL(rc) / 降级 都在里面)。
  > 08-06 立这条的理由:08-05 我在这里手写了"三条腿一致 PASS",而 Kimi 根本没出结论
  > (同一页第 90 行我自己还写着它没出报告)—— 手抄一份终端上的东西,抄错那次没人会发现。
- findings:
  - <...>
  > 只写发现。腿的身份/降级不在这儿抄第二遍:日志自带身份牌(降级横幅 + 视野边界),
  > 花名册在上一格,查工件不查自述。
- arbitrated verdict (主裁): <...>
  > **归档时这一条和顶部的 `Verdict:` 都不许还是占位符**,`track-guard` 规矩3 会挡;
  > 没归档但已经合并上线的,`track list` 会打 ⚠️(stage-timer 就这么漏了两个月)。

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>
