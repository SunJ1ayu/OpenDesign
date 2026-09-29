# aiwork-gate(放行关卡)

计划:SunJ1ayu/aiwork 的 `WORKFLOW-MIGRATION-PLAN.md` 阶段 C(规则 G1–G8、M1)。

| 文件 | 做什么 |
|---|---|
| `collect.mjs` | 只读 GitHub API 收集事实;出错、分页没取完、条数对不上一律抛错(G8) |
| `decide.mjs` | 纯判定,不碰网络(G1–G7) |
| `run.mjs` | 流程:校验策略(不合法就只把保险丝拨到 failure)→ 拨保险丝、发占位 → 读 → 判 → 写回;任何一步出错都把占位 / 保险丝改成 failure |
| `main.mjs` | 接线:真实 API、`aiwork-gate` App 令牌、发 / 改检查、用 `GITHUB_TOKEN` 拨保险丝 |
| `../../.aiwork/policy.json` | 策略:判卷面、high 路径、Builder、评审 App、检查名、App ID |

测试:`tests/test_aiwork_gate.mjs`(判定与收集)、`tests/test_aiwork_gate_run.mjs`(流程与失败处理)、
`tests/test_aiwork_gate_main.mjs`(假 GitHub API 上真跑 `main.mjs`)、`tests/test_aiwork_gate_workflow.py`(workflow 形状)。

## 一次性设置

- `aiwork-gate` App(App ID 写在 `policy.json` 的 `gate_app_id`):只有 Checks 读写,只装在本仓库。
- environment `aiwork-gate`:部署分支只许 `main`,**不设审批人**;私钥放在它的 secret `AIWORK_GATE_PRIVATE_KEY`。
  设了审批人,关卡每次都要等人点,等的时候检查和保险丝都停在旧值。

## 两道信号:App 检查 + 保险丝

- **App 检查**(`aiwork-gate-shadow`,转真拦截后叫 `aiwork-gate`):结论本身。只有 `aiwork-gate` App 发得出,PR 冒充不了。
- **保险丝**(commit status `aiwork-gate/fuse`):用 workflow 自带的 `GITHUB_TOKEN` 发,**不靠 App 私钥**。
  每次重算先拨到 pending,App 把结论写回之后才跟着结论走;App 发不出 / 写不回、策略不合法 → failure。
- 为什么要两道:GitHub 上只有 App 自己改得动它发过的检查。App 私钥坏了(被撤、过期、secret 被删)时,
  同一个提交上的旧 success 会一直挂着,之后来的 BLOCK、业主撤回批准都盖不掉它 —— 这时靠保险丝挡。
- 保险丝**只能多挡、不能单独放行**:任何有写权限的 workflow 都拨得动它,所以它必须和 App 检查一起设为必过。
- 仍然挡不住的:关卡 workflow 根本没跑起来(Actions 被关、environment 被加了审批人、检出 main 失败)——
  那时两道都停在旧值。看到 aiwork-gate 的运行失败或一直在等,先别合并。

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
| S8 | 编辑测试 PR 的标题;再改一次目标分支 | 各重算一次;改目标分支后 G1 ❌「目标分支在这次 CI 之后改过」,推一个新提交(或关掉再重开 PR)让 CI 重跑后恢复 | edited 事件会触发重判;旧目标上的 CI 不算数 |
| S9 | 任选上面一次重算,看测试 PR 的检查列表 | `aiwork-gate/fuse` 先变黄(pending),算完与 `aiwork-gate-shadow` 同结论;发出者是 GitHub Actions | 保险丝接通,不靠 App 私钥 |

失败注入(API 出错、限流、App 私钥坏了、PR 中途推进)在线上没法安全制造,由 `test_aiwork_gate_run.mjs`(R5–R5g、R14–R14f)与 `test_aiwork_gate_main.mjs` 覆盖。

## 从 shadow 转为真拦截

S0–S9 全部符合预期,且之后至少 5 个真实 PR 上 shadow 的结论都和业主的判断一致、没见过过时的 success,再:

1. 发一个只改 `policy.json` 的 PR:`check_name` 改为 `aiwork-gate`(判卷面,要业主批准);
2. 业主在 main 的分支规则里把必过检查从 `ci` 换成**两条**:`aiwork-gate`(来源限定 `aiwork-gate` App)和
   `aiwork-gate/fuse`(来源限定 GitHub Actions)。只设第一条,App 私钥坏了时旧 success 仍能合并;
3. 用一个故意缺评审的 PR 确认合并按钮被挡住。
