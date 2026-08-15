# Verify: opendesign-data-outside-install

- Date: 2026-08-15
- Verdict: <PASS | BLOCK | NEEDS_MORE_INFO>

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [ ] build passes
- [ ] tests pass
- [ ] no secrets / unsafe ops

**机器打印的**(不是我的转述)—— 判据用 `runlog` 跑,把它打印的收据行原样粘进来:

```
runlog -t opendesign-data-outside-install -- <判据命令>
```

```
<粘收据行,逐字节,别改数。**每次提交**都会跟 evidence/ 里的收据逐字节比对(5a);
 **归档时**还要求:最后跑的那一遍必须在这儿、跑红的那几遍一份都不许藏(5b)、
 收据得进 git(5d)。一份收据都没有的话,写一行
 「- 无机器证据:<理由>」认账 —— 沉默不算理由(5c)。>
```

## Review

- lane: **full**。命中两条硬规矩:**数据一致性**(业主的图库/档案换落点,搬错=他的东西
  在卸载时消失)+ **新写面语义**(所有写口的落点变了)。不降档。
  > **碰了新写口 / 权限 / auth / 钱 / 数据一致性 → full,针孔再薄也不打折**(硬规矩,别在这降档)。
  > fast = 主+1,中等风险;self = 主自审(闸③ + 截图 + 全量回归),
  > 限纯前端/纯观感、后端一字未动、只新增已过审针孔的调用方。
- 派给: **codex 腿 `-m gpt-5.6-sol`**(实现),oracle 与仲裁留在主 agent。
  **逐档问了一遍**(上一单 S1c 我在这一格写着"到那一步再判"然后直接自己开写、
  没留任何判断记录 —— 那笔账记在 opendesign-windows-installer/verify.md 里,这次不重犯):
  - **主 agent 直接干**:活的大头是 ~25 个调用点按"数据 / 代码"逐个分类改写 ——
    有真实工作量、纯文本、边界清楚,正是抽屉里写的"PR 级实现"形状。**派它省下的是我的额度,
    而这单最贵的东西(oracle 与仲裁)本来就外包不出去。** ⇒ 不自己干。
  - **submimo fix(微档)**:限 1-3 文件的窄口,这单跨 7 个文件。⇒ 不合档。
  - **Sonnet 腿(worktree)**:后备档,没有非用不可的理由(这单不需要开端口的考卷,
    见下)。⇒ 不用。
  - **codex `gpt-5.5` 还是 `gpt-5.6-sol`**:跨模块 + 判的是"哪些东西算业主的数据"这种
    语义边界,不是照着规格填空 ⇒ **升 5.6-sol**。
  - **判卷要不要起服务**:不要。不变量闸跑的是工具层写口(建项目/加参考图/set_workspace/
    整理计划),不起 gateway、不开端口 ⇒ **腿自己跑得了这份考卷**,不必主 agent 当测试机。
    (全量回归里那 36 条 e2e 要端口,但那是闸②我亲跑的事,不进任务书。)
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
