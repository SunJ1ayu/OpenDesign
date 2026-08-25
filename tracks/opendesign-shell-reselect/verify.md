# Verify: opendesign-shell-reselect

- Date: 2026-08-25

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录 `decision.json`。

## Mechanical checks

**本单零代码改动**（只新增 `tracks/opendesign-shell-reselect/**` 下的工件）。

- 无机器证据:**这一单没有实现，也没有 oracle 可跑** —— 产出是一份决定 + 四份外部证据。
  唯一可机械核对的是"确实零代码改动"：`git show --stat` 里除本 track 目录外不含任何路径。

## Review

- **规格自查**（在读任何腿的输出之前答的，正本见
  `evidence/20260825-explore-00-我的方向-派发前落盘.md`）：我自己写下的四条"我可能错在哪"，
  其中第 3 条（*"我可能整个问错了——真正该投的也许是让我能在 Windows 上跑一遍"*）
  **被四条腿一致命中**，且我去核之后发现它比腿说的更严重（仓库是 public、
  Windows runner 免费、而 `.github/workflows` 一个文件都没有）。
- **腿的花名册**:`panel-explore` 不写 `.plan`/`.state`（那是 `panel-review` 的机制），
  `panel-roster` 对这一轮会印「连派发都没走到」——**假话，已记进工艺账**。
  这一轮的机器事实以控制器自己的收尾行为准，逐字：
  ```
  panel-explore: done. submimo rc=0  subdeepseek rc=0  subglm rc=0
  ```
  第四条腿 `gpt-5.6-sol` 由我单独派（`codex exec -s read-only`），`rc=0`，tokens used 91,292。
- **findings**:四份位置论文 + 我的逐条对账（接受 3 条、仍成立 2 条、驳回 3 条，
  每条都附了证据或反证）全文在 `explore-synthesis.md`，不在这里抄第二遍。
  其中最重的一条反证：DeepSeek 与 GLM 独立提出的「无边框需求找不到需求方」被
  `git show 684574d` 里业主 08-16 的原话**当场证伪**。
- **arbitrated verdict(主裁)**:见 `explore-synthesis.md`「主 agent 的裁决」三条
  （不换壳 / 先建 Windows 验证通道 / 三条触发条件）。
  **本单不归档** —— T4（要业主答的产品问题）还没答，`decision.json.outcome.verdict` 留 null。

## Accepted deviations

- **执行顺序与业主同意的相反**：他同意的是"先补工件、再发散"，我改成"先发散、再补工件"，
  并在动手前当场说明了原因（底座腿自己读仓库 ⇒ 先落工件 = 把我的答案递给考生）。
  代价是那段时间重估只在仓外（`/root/aiwork/tasks/`）躺着；收益是这一轮的独立性是真的。
