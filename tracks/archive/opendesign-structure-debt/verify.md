# Verify: opendesign-structure-debt

- Date: 2026-08-02
- Verdict: **PASS** —— 代码三闸全过 + 三腿 PASS + **G3 真机 08-02 已验过**,可归档

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [x] build passes —— ⚠️ 本单**零前端改动**,web/ 一个文件没动,不需要 build/dist(闸③已核)
- [x] tests pass —— py **838 例 0 红** + `run-all.sh` **31 PASS / 0 FAIL / 2 SKIP**(主 agent 亲跑,合后又跑一遍)
- [x] no secrets / unsafe ops —— 闸③亲读 diff,无凭证、无新写口、无符号链接
- [x] **O1 搬运保真闸绿** —— 15 项逐字节(含 panel 补进的 2 个跟随常量)
- [x] **O2** 目标环已死 + 未引入新环 + 辩解注释已删
- [x] **闸③ 亲读 diff**,盯 `create mode 120000`(worktree 符号链接事故史)

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
- panel 结果:四腿跑了三腿,**submimo / subdeepseek / subkimi 全 PASS**;
  **subglm 失败**(`rc=1`,日志显示 MiMo 端点 429「余额不足」+ agent 腿 claude 退出 1)
  —— 是后端问题不是评审意见,**不计入合议,也不当作 PASS**。
  失败腿日志已读(规矩:失败腿的日志也要读),里面没有评审内容。
- **逐条对账(每条都给依据,禁止"看报告都说没问题")**:
  - **他们标了、我漏了 →(往死里查,全部核实成立并已修)**
    - `_FOLDER_WIN_CLASSES` / `_WIN_FOCUS` 不在 MOVES ⇒ 逐字节闸与"不留副本"闸
      对这两行是空的。**subdeepseek 与 subkimi 两腿独立命中。**
      我亲核:`grep -c` 于 `tests/structure_moves.py` = **0**,属实。
      已补进 MOVES,**基线取自 `git show 39e7f4c:bin/ds_web.py`**(搬运前),13 → 15 项。
      ⇒ **这是本轮 panel 最大的价值:它补的是我自己判据的洞,不是实现的洞。**
    - O3 只查限定引用、漏 `from X import Y`(subdeepseek)。实测零命中,但缺口属实,已补。
    - 死代码:`ds_intake.REPO_ROOT`(subkimi)、`ds_adopt` 的 `import ds_intake`
      (subdeepseek)。我亲核两处均零使用零引用,属实,已删(硬切就该切干净)。
  - **我标了、他们没标 → 依然成立**(沉默不是放行):
    F1/F2/F3 三条无一腿提及。F1(我的规格错导致 4 行重复)在派 panel 之前已修,
    diff 里看不到,合理;F3(多余的 `__future__` import)我在任务书里写了"已知不用报"。
  - **他们标了但我驳回**:无。
  - **连带发现(修 ③ 时炸出)**:环的 DFS 枚举起点依赖遍历顺序,白名单按字面比对
    会把"同一个环换个写法"误判成新环。已加 `_canon()` 归一化。
    方向由 subkimi 的 `[信息]` 条点出(它说 DFS 带全局 seen 不保证枚举所有基本环)。
  - **边界判断(我在自审里明确标为"机械挡不住,只有人能看")**:
    subdeepseek 与 subkimi **各自独立**核了 `Handler._open_folder` 的 104 行内容
    (CT/body 尺寸闸、key 白名单映射、rel/sub 分流的安全判读、inbox 分支服务端解析、
    `self._json` 编排),结论一致:**它不是转发空壳,搬走反而把安全决策劈到模块外**。
    ⇒ 我的边界判断成立,且他们给出了我没写出来的具体理由。
- arbitrated verdict (主裁): **PASS**(代码层面),**但本单不归档** —— 见下方真机待验。
  > 依据:三闸全过(闸①逐字节空 / 闸②我亲跑 838 例 0 红 + e2e 31 绿 / 闸③亲读无夹带);
  > 三腿 PASS 且我逐条对账后**接受了 3 条并主动加严判据**;边界判断经两腿独立复核成立。
  > **全票 PASS 没有让我降低标准** —— 本轮所有改动都是把判据改严,零处放松。
  > ⚠️ 但 PASS 只覆盖"代码合乎规格"。**规格对不对、以及 Windows 真机行为,
  > 判据和 panel 都证明不了**(自审第 1 条洞:mock 绿只证明我搬对了调用)。

## Accepted deviations

- **F3** 两个新模块多了 `from __future__ import annotations`(原文件没有)。
  3.12 上这两个模块用的 `str | None` 原生支持,该行多余。零行为影响,
  形态上属于"搬运单里出现了原文件没有的行",记账但不为它再动一轮。
- **残留 3 个循环依赖**(`ds_adopt⇄ds_organize` / `ds_intake⇄ds_organize` /
  `ds_lint⇄ds_tools`),反向边全在 MCP 工具登记处 —— **有意划出 Scope**,
  是第 ③ 刀的事,已写进 `KNOWN_REMAINING` 白名单(只许缩短不许加长)。

## 合后处置(merge → push 之间发生的事)

- **合后亲跑逮到一条红**:`inbox_open_button.e2e.mjs`(分支上是绿的)。
  查证 **不是本单引入**:改动前 0.70.0 **3 红/12 次**、改动后 0.71.0 **4 红/12 次**
  (差异在 n=12 上是噪声)⇒ 既有竞态。
  **当场修而不是记债**:总跑开关刚上线,一条三成概率无故变红的判据会让整套开关的
  "绿"不值钱。加等待后 **0 红/12 次**。commit `33f89d7`。
- ⚠️ **过程中我自伤一次**:为做前后对照建了"改动前"的临时 worktree,shell 工作目录
  停在那儿,同一个修复的两半落进两个目录 ⇒ 对照树 `waitFolders is not defined`、
  12/12 全红。那组数据当场作废重跑;临时树已删,主仓未污染。
  形态是老毛病换了个马甲:**同一件事复制到两个地方、只更新其中一个**
  (这次复制的不是事实,是工作目录)。
- 最终状态:merge `--no-ff`(两个新文件均 `create mode 100644`,**无 `120000` 符号链接**);
  合后全量 **py 838 例 0 红 + e2e 31 PASS / 0 FAIL / 2 SKIP**;
  已 push(`5e13c9b..33f89d7`);worktree 与 `structure-debt` 分支已清理。

## 真机待验(用户 Windows,主 agent 无法代跑)

- [x] **G3 「打开文件夹」真的弹窗并切前台** —— **2026-08-02 用户家里机(D:\AI\OpenDesign)
      验过,原话「没什么问题 挺好的」。** 0.71.0 装机 + 点击均正常。
      ⇒ 本单唯一"判据和 panel 都证明不了"的那一条已由真机接住,可归档。
