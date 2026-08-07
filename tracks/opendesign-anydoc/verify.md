# Verify: opendesign-anydoc

- Date: 2026-08-07
- Verdict: <PASS | BLOCK | NEEDS_MORE_INFO>

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [ ] build passes
- [ ] tests pass
- [ ] no secrets / unsafe ops

## Review

- lane: **full**
  > **碰了权限面**:在 `disable_builtin_file_tools` 特意砌起来的墙上开一条读的缝。
  > 硬规矩说得很死 —— 新写口 / 权限 / auth / 钱 / 数据一致性 → full,针孔再薄也不打折。
  > 这条缝虽然只读,但它决定"助手能看到业主的哪些文件",按权限面判,不降档。
- 派给: **codex `-m gpt-5.5`(实现);规划双出用 `gpt-5.6-sol`** —— 理由:
  ① **判卷不需要起服务**(纯 python 单测 + 转换库用替身),不撞"考卷要开端口"那条,
  GPT 腿可以自己验完再交;② 方向和安全边界已经由我在 design 里定死,
  剩下的是照着红的判据把实现写绿 —— 正是执行档该干的活;
  ③ 权限面属架构敏感 ⇒ **规划那一步**升 `gpt-5.6-sol` 独立出一版对差异,
  实现仍走默认档 `gpt-5.5`。
  返工轮数 / 自身错误数收货时补在这里(唯一账本,不写"第 N 单")。
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
