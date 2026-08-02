# Verify: opendesign-structure-debt

- Date: 2026-08-02
- Verdict: <PASS | BLOCK | NEEDS_MORE_INFO>

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [ ] build passes(`web/` tsc + build,dist 入库)
- [ ] tests pass(py 827 例 + `tests/e2e/run-all.sh` 31 例)
- [ ] no secrets / unsafe ops
- [ ] **O1 搬运保真闸绿**(函数体 + 模块层常量逐字节不变)
- [ ] **O2 无环**(且 `ds_workspace` 的延迟 import 辩解注释已删)
- [ ] **闸③ 亲读 diff**,盯 `create mode 120000`(worktree 符号链接事故史)

## Review

- lane: **full**
  > 硬触发器(新写口/权限/auth/钱/数据一致性)**严格说没命中** —— 本单零行为改动、
  > 零新参数、不碰写口语义。仍然打 full,理由是**这单的 diff 形态本身**:
  > 几百行纯位移里夹一行真改动,正是闸③「亲读 diff」最挡不住的形态。
  > O1 机械闸挡"函数体被改",但挡不住"边界画错了"(design 记的第三个洞)——
  > 那只有人能看。**这是主动加严,不是硬规矩要求的,不构成先例。**
- 派给: **codex / gpt-5.5**(分层还账第 4 单)
  > 轴 = 判卷要不要起服务:本单判卷是纯 python 单测(O1/O2/O3),**不起服务** ⇒ 可外包。
  > 且形态最适合执行腿:纯机械搬运,oracle 是"逐字节不变"这种零解释空间的题。
  > 三件套的 `--protect` **必须列全** `tests/test_structure_moves.py`、
  > `tests/test_no_import_cycles.py`、`tests/test_no_stale_refs.py` 以及基线存档文件 ——
  > 守卫强度只等于这份清单,漏列一个就是那个洞。
  > ⚠️ **派活前先开 `delegate` skill 抽屉**,不许凭记忆调参数(08-01 栽过:
  > 记忆里抄的换腿规矩当天就被抽屉软化了,拿过期抄件路由了四单)。
- 规格自查(读任何 panel 输出之前先答):
  > **规格错了会错成什么样?** 本单的规格 = "这两块东西放错位置了,该挪走"。
  > 它可能错在:① 边界画错 —— 比如 `Handler._open_folder` 该不该一起搬走。
  > 我判断它是 HTTP 层(解析/鉴权/拼响应)该留下,但这是**判断不是事实**,
  > 若判错,结果是 `ds_web` 里留了个只会转发的空壳、而"开文件夹"这件事被劈成两半,
  > 比不拆更难读。② taxonomy 独立成模块可能过度设计 —— 也许它本就该在 `ds_intake`,
  > 是 `ds_workspace` 不该用它。**这两条 panel 全票 PASS 也不能证伪** ——
  > panel 只验"实现合不合规格",验不了"规格对不对"(记忆 [[panel-review-trust-calibration]])。
  > 我怎么发现?③ 刀那单开工时若发现边界又要重画,就是本单画错了的证据。
- findings(**主 agent 独立审,读任何 panel 输出之前落盘**):
  - **F1 我自己的规格错(不是执行腿的错)** —— 任务书让它「删掉
    `ds_workspace._load_taxonomy_for_skip`」,它照办了,于是同样 4 行的
    `try/except → load_taxonomy` 被**原地复制了两遍**(`excluded_structural`
    与 `project_folders`)。但删那个函数的**理由**是里面那行延迟 import,
    不是这个薄封装本身 —— 正确的题应该是「去掉延迟 import,保留封装」。
    影响:8 行重复,零行为差异。**记忆里已有同类史料:真漏的根因反复是我自己的
    规格/夹具错。** 处置见下。
  - **F2 `bin/ds_taxonomy.py` 的模块 docstring 是英文**
    (`"""Taxonomy loading and category suggestions for OpenDesign."""`),
    全仓其余模块 docstring 均为中文。执行腿看不到本机说明书,这类风格约定
    不写进任务书就等于不存在 —— **又一次是任务书的洞,不是它的错**。
  - **F3 两个新模块都加了 `from __future__ import annotations`**,原文件没有。
    Python 3.12 上这两个模块用的 `str | None` 原生就支持,该行多余。
    零行为影响,但它是"搬运单里出现了原文件没有的行" —— 形态上属于夹带,
    虽然无害,仍应记账。
  - **零 BLOCK 级发现**:闸① 判卷文件逐字节未动;闸③ 无符号链接、
    四份被改的判据文件经机械核验(把模块名换回去后与原版逐字节相同)
    **全是纯改调用点,无一条断言/期望值被动**;两个新模块内容 = 搬来的定义
    + 必要 import + 跟随的两个常量(内容逐字节原样),无夹带。
- arbitrated verdict (主裁): <...>

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>

## 真机待验(用户 Windows,主 agent 无法代跑)

- [ ] **G3 「打开文件夹」真的弹窗并切前台**(见 tasks.md G3)。
      **在他验之前本单不许宣布完成。**
