# Windows 端到端第六趟(全绿)的原始事实

- run: https://github.com/SunJ1ayu/OpenDesign/actions/runs/34865587921 (分支 ci-update/e2e-6,commit 32b4f47)
- 这里是从那一趟构件 `update-e2e-out` 里复制出来的:`verdicts.tsv`(runner 上写的收据)、五份 `facts-eN.json`
  (判定器吃的事实)、接力脚本日志(GBK 转 UTF-8)、e1 更新后 20 秒的截图。
- 为什么复制进仓:构件 1 天后过期;verify.md 引用的证据不能住在仓外(证据寿命闸)。
- 本机复判:`python .github/scripts/update_e2e_verdict.py eN facts-eN.json`,收据见 verify.md §3。
