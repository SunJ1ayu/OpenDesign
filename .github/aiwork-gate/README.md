# aiwork-gate(放行关卡)

计划:SunJ1ayu/aiwork 的 `WORKFLOW-MIGRATION-PLAN.md` 阶段 C(规则 G1–G8、M1)。

| 文件 | 做什么 |
|---|---|
| `collect.mjs` | 只读 GitHub API 收集事实;出错、分页没取完、条数对不上一律抛错(G8) |
| `decide.mjs` | 纯判定,不碰网络(G1–G7) |
| `run.mjs` | 流程:校验策略 → 先占位 → 读 → 判 → 写回;任何一步出错都把占位改成 failure |
| `main.mjs` | 接线:真实 API、`aiwork-gate` App 令牌、发 / 改检查 |
| `../../.aiwork/policy.json` | 策略:判卷面、high 路径、Builder、评审 App、检查名、App ID |

测试:`tests/test_aiwork_gate.mjs`(判定与收集)、`tests/test_aiwork_gate_run.mjs`(流程与失败处理)、
`tests/test_aiwork_gate_main.mjs`(假 GitHub API 上真跑 `main.mjs`)、`tests/test_aiwork_gate_workflow.py`(workflow 形状)。

## 一次性设置

- `aiwork-gate` App(App ID 写在 `policy.json` 的 `gate_app_id`):只有 Checks 读写,只装在本仓库。
- environment `aiwork-gate`:部署分支只许 `main`,**不设审批人**;私钥放在它的 secret `AIWORK_GATE_PRIVATE_KEY`。

## 首次部署验收(shadow:检查名 `aiwork-gate-shadow`,只报不拦)

合并后,用一个无害的测试 PR(云端 Claude 以机器账号开)逐条看。每条写下 PR 号、提交号和检查的链接。

| # | 做什么 | 预期 | 证明了什么 |
|---|---|---|---|
| S0 | 合并本 PR 后看 main 上 CI 跑完触发的那次 aiwork-gate | 运行成功,日志写"与 PR 无关",main 的提交上**没有** `aiwork-gate-shadow` | push 到 main 不误判 |
| S1 | 开测试 PR | 立刻出现 `aiwork-gate-shadow`(重算中 / 等 CI);检查的 app 是 `aiwork-gate`(id 5121026),不是 GitHub Actions | 占位先行;结果由 App 发出 |
| S2 | 等 CI 跑完 | failure「不放行:缺合格评审」;摘要里 G1 ✅、G4 ✅ 作者 `SunJ1ayuBoT(anthropic)` | CI 按本 PR 认;活动记录接口在 `GITHUB_TOKEN` 下读得到 |
| S3 | 本机 `review-pr` 在当前 head 发 PASS(openai) | 一两分钟内自动重算为 success「放行」 | 评审 → `aiwork-review-ping` → 关卡重算这条链通 |
| S4 | 同一 head 再发一条 BLOCK | failure(G5);业主**在 BLOCK 之后**批准 → success | BLOCK 与批准的先后被认 |
| S5 | 业主在网页上改测试 PR 的一个文件(非机器账号推送) | failure,作者 UNKNOWN(G4);业主在新 head 批准 + 有 PASS → success | 混合作者要业主批准 |
| S6 | 测试 PR 改 `.github/` 下一个文件 / 改 `desktop/` 下一个文件 | 分别要业主批准(G2)/ 两家 PASS + 业主批准(G6) | 判卷面与 high 路径 |
| S7 | 给 PR 加标签 `aiwork:recheck` | 重算一次 | 手动重算可用 |
| S8 | 编辑测试 PR 的标题或目标分支 | 重算一次 | edited 事件会触发重判 |

失败注入(API 出错、限流、令牌坏、PR 中途推进)在线上没法安全制造,由 `test_aiwork_gate_run.mjs` 与 `test_aiwork_gate_main.mjs` 覆盖。

## 从 shadow 转为真拦截

S0–S8 全部符合预期,且之后至少 5 个真实 PR 上 shadow 的结论都和业主的判断一致、没见过过时的 success,再:

1. 发一个只改 `policy.json` 的 PR:`check_name` 改为 `aiwork-gate`(判卷面,要业主批准);
2. 业主在 main 的分支规则里把必过检查从 `ci` 换成 `aiwork-gate`,并限定来源为 `aiwork-gate` App;
3. 用一个故意缺评审的 PR 确认合并按钮被挡住。
