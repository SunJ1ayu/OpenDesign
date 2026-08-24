# Verify: opendesign-gate-doc-sync

- Date: 2026-08-24

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录
> `decision.json`；这里保留检查、理由、发现与主 Agent 仲裁说明，不复制枚举。

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

> 本单**不改任何行为**,只改文档与注释。但它动的是判卷防线所在的文件,
> 所以判据与红检照跑 —— 「改了判卷工具就得跑它自己的判据」。

- [x] **变异锚点唯一性自查**:给闸加注释有可能撞上红检的变异锚点,而
      `replace(old, new, 1)` 只换第一处 ⇒ 撞了就会**改错地方而红检照样绿**。
      四个锚点逐个数过,在各自文件里都恰好 1 次。
- [x] tests pass:8 条 oracle 全绿(28.5s)
- [x] 红检:**6 条变异咬住 6、漏网 0** ⇒ 注释没撞坏锚点
- [x] 跑完仓库零污染(`web/dist` 仍是 3 个文件)
- [x] no secrets / unsafe ops(只动 .md / .sh 注释 / backlog)

**机器打印的**(不是我的转述):

```
runlog: oracle-after-docsync rc=0 commit=23de411 dirty=yes at=2026-08-24T02:57:25Z file=tracks/opendesign-gate-doc-sync/evidence/20260824T025725Z-01-oracle-after-docsync.txt
runlog: redcheck-after-docsync rc=0 commit=23de411 dirty=yes at=2026-08-24T02:58:16Z file=tracks/opendesign-gate-doc-sync/evidence/20260824T025816Z-01-redcheck-after-docsync.txt
```

**机器打印的**(不是我的转述)—— 判据用 `runlog` 跑,把它打印的收据行原样粘进来:

```
runlog -t opendesign-gate-doc-sync -- <判据命令>
```

```
<粘收据行,逐字节,别改数。**每次提交**都会跟 evidence/ 里的收据逐字节比对(5a);
 **归档时**还要求:最后跑的那一遍必须在这儿、跑红的那几遍一份都不许藏(5b)、
 收据得进 git(5d)。一份收据都没有的话,写一行
 「- 无机器证据:<理由>」认账 —— 沉默不算理由(5c)。>
```

## Review

- **规格自查**:这一单的"规格"是「把上一单改变的事实同步到每一处」。
  它最可能错的形态是 **搜漏了** —— 而那正是它要防的病本身。
  为此按 memory `panel-roster-doc-sync-track` 的教训**明确排除了史料**
  (`/root/aiwork/refs/` 下的 `claude-md-retired-*`、`ctxdiet-backup-*`:
  那些是退役备份,**故意保留当时的措辞**,改了反而毁掉史料价值),
  并确认 `aiwork/bin/` 里提到 design-studio 的四处全是注释里的举例、不是硬编码流程。
  **仍可能漏的**:我搜的是关键词(`run-all` / `dist` / `新鲜度` / `llm_key` / `六段`),
  换个说法描述同一件事的地方搜不到。
- 腿的花名册: <把 `<日志前缀>.roster` 里那一行**原样粘过来**,别手写>
  > panel-review 收尾自己写这个文件(off / FAIL(rc) / 降级 都在里面)。
  > **控制器没活到收尾时它压根不存在** —— 那时跑 `panel-roster <日志前缀>` 从盘上重建,
  > 与控制器自己写的**归一化后一致**(判据 R5b 守着;抬头有渲染时间戳,不是字面逐字节)。**一轮零记录的评审也粘得出这一行**,
  > 所以"那轮被砍了所以没有花名册"不再是理由(2026-08-23,track panel-roster-from-disk)。
  > 08-06 立这条的理由:08-05 我在这里手写了"三条腿一致 PASS",而 Kimi 根本没出结论
  > (同一页第 90 行我自己还写着它没出报告)—— 手抄一份终端上的东西,抄错那次没人会发现。
- findings:
  - <...>
  > 只写发现。腿的身份/降级不在这儿抄第二遍:日志自带身份牌(降级横幅 + 视野边界),
  > 花名册在上一格,查工件不查自述。
- arbitrated verdict (主裁): **PASS**。impact=self ⇒ 外部评审预算 0,没派 panel。

  **本单最值钱的不是同步了文档,是查证时挖出的两件事:**

  1. 🔴 **上层总跑 ⑤ 段是本仓库唯一跑 `tsc -b` 的地方,而它的名字只说「dist 新鲜度」。**
     六段里没有任何独立的类型检查。上一单在 e2e 那段加了道问同一个问题的闸之后,
     **下一个人看到「重复了」很可能顺手删掉 ⑤ 段 —— 连带把类型检查一起删掉,
     而且不会有任何判据变红。** 已在两处注释里钉住,并把「给 tsc 一个独立的段」记进 backlog。
  2. ⑤ 段靠 `git status --porcelain -- web/dist` 判断 ⇒ **依赖 web/dist 入库**;
     哪天它被 gitignore,这道闸**恒绿**(fail-open)。实测现在没被 ignore,判得动。

  另外 README 里那句自相矛盾也修了:它写着「⚠️ 故意不写第几段…按名字指,插多少段都不会漂」
  (2026-08-18 四审换来的教训),**而同一句里就留着「六段」** —— 总数和序号一样会漂。

## Accepted deviations

- **不改任何行为**:两道闸继续并存(六段总跑里会 build 两次,多花约 3 秒)。
  「要不要合并」是独立判断,而且**得先给 `tsc -b` 找个新家**,否则合并就会丢掉类型检查。已记 backlog。
- **搜索是关键词驱动的**,换个说法描述同一件事的地方搜不到 —— 这是本单方法本身的边界。
  > 这里写理由；最终枚举写进 `decision.json.outcome.verdict`。归档时仍为空会被
  > `track-record validate --phase archive` 挡住，`track list` 也会打 ⚠️。

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>
