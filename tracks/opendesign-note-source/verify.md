# Verify: opendesign-note-source

- Date: 2026-08-11
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
runlog -t opendesign-note-source -- <判据命令>
```

```
<粘收据行,逐字节,别改数。**每次提交**都会跟 evidence/ 里的收据逐字节比对(5a);
 **归档时**还要求:最后跑的那一遍必须在这儿、跑红的那几遍一份都不许藏(5b)、
 收据得进 git(5d)。一份收据都没有的话,写一行
 「- 无机器证据:<理由>」认账 —— 沉默不算理由(5c)。>
```

## Review

- lane: full —— **数据一致性面**,不降档:① 档案格式的读侧解析整块换了住址
  (`ds_tools` → `ds_common`),`/changes` 与 `/api/todos` 两个读端点同时吃它,搬错=两个
  页面一起哑;② 写口契约从"动作型"改述成"状态型",并**推翻上一单刚立的一条断言**
  (前端不再判"变没变");③ 待办页的显示真相源整个换掉。任何一条单独拿出来都够 full。
  > **碰了新写口 / 权限 / auth / 钱 / 数据一致性 → full,针孔再薄也不打折**(硬规矩)。
- 派给: `delegate-codex --model gpt-5.5`(PR 级实现档)—— 开工前填。
  理由:方向在 design 里已经钉到函数名一级(搬哪六个符号、`collect` 加哪个键、
  `buildEditRequest` 去掉哪三处比较),剩下的是照着红的 oracle 把实现写绿,不需要 frontier 脑。
  **不升 `gpt-5.6-sol`**:跨了四个后端模块看着像"架构敏感",但架构判断(为什么是 ds_common、
  为什么读侧允许缺席)已经在 design 里做完并写下理由了,派出去的是搬运不是判断。
  **判卷要不要起服务:要** —— `test_ds_web_api` 起真 HTTP、e2e 起 ds_web + chromium,
  codex 沙箱禁网跑不了 ⇒ 按抽屉的默认路走「**主 agent 当测试机**」:它跑纯 python/node
  那部分,起端口的两层由我在闸② 亲跑,失败输出原样退回,**有界 2 轮**,不绿就收回自己修。
  判卷文件全列 `--protect`;`--attack-log` 攻题记录落仓外(进仓 = 把考卷的洞递给考生)。
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
