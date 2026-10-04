# aiwork-gate(放行关卡)

计划:SunJ1ayu/aiwork 的 `WORKFLOW-MIGRATION-PLAN.md` 阶段 C(规则 G1–G8、M1)。

| 文件 | 做什么 |
|---|---|
| `collect.mjs` | 只读 GitHub API 收集事实;出错、分页没取完、条数对不上一律抛错(G8) |
| `decide.mjs` | 纯判定,不碰网络(G1–G7) |
| `run.mjs` | 流程:每次运行把所有开着的 PR 全重算一遍(事件只是门铃)。列出开着的 PR、按 head 分组 → 先在每个 head 上占位 → 每个 head 把以它为 head 的 PR 全判一遍、合成一个结论写一次;读不全就不放行;写上的是放行,就合并有合并请求的 PR(见下「合并」) |
| `main.mjs` | 接线:真实 API、`aiwork-gate` App 令牌、发 / 改检查、合并、用 `GITHUB_TOKEN` 拨保险丝 |
| `../../.aiwork/policy.json` | 策略:判卷面、high 路径、Builder、评审 App、检查名、App ID、合并标签和谁贴的算数 |

测试:`tests/test_aiwork_gate.mjs`(判定与收集)、`tests/test_aiwork_gate_run.mjs`(流程与失败处理)、
`tests/test_aiwork_gate_main.mjs`(假 GitHub API 上真跑 `main.mjs`)、`tests/test_aiwork_gate_workflow.py`(workflow 形状)。

## 一次性设置

- `aiwork-gate` App(App ID 写在 `policy.json` 的 `gate_app_id`):只装在本仓库。权限 Checks 读写(发检查),
  Contents、Pull requests、Workflows 读写(合并:合并接口要前两个;PR 改了 `.github/workflows/` 的,GitHub 还要
  Workflows 才让 App 合)。改了 App 的权限,要在仓库的安装处接受新权限才生效。
  私钥能合并 PR 之后,它和 main 本身一样要紧。
- 标签 `aiwork:merge`(`policy.json` 的 `merge_label`)。
- main 的规则集保留「合并前分支必须和 main 同步」(Require branches to be up to date,现在已开;不能关,见「合并」)。
- environment `aiwork-gate`:部署分支只许 `main`,**不设审批人**;私钥放在它的 secret `AIWORK_GATE_PRIVATE_KEY`。
  设了审批人,关卡每次都要等人点,等的时候检查和保险丝都停在旧值。

## 两道信号:App 检查 + 保险丝

- **App 检查**(`aiwork-gate`;shadow 阶段叫 `aiwork-gate-shadow`):结论本身。只有 `aiwork-gate` App 发得出,PR 冒充不了。
- **保险丝**(commit status `aiwork-gate/fuse`):用 workflow 自带的 `GITHUB_TOKEN` 发,**不靠 App 私钥**。
  每次重算先拨到 pending,App 把结论写回之后才跟着结论走;App 发不出 / 写不回、策略不合法 → failure。
- 为什么要两道:GitHub 上只有 App 自己改得动它发过的检查。App 私钥坏了(被撤、过期、secret 被删)时,
  同一个提交上的旧 success 会一直挂着,之后来的 BLOCK、业主撤回批准都盖不掉它 —— 这时靠保险丝挡。
- 保险丝**只能多挡、不能单独放行**:任何有写权限的 workflow 都拨得动它,所以它必须和 App 检查一起设为必过。
- 仍然挡不住的:关卡 workflow 根本没跑起来(Actions 被关、environment 被加了审批人、检出 main 失败)——
  那时两道都停在旧值。看到 aiwork-gate 的运行失败或一直在等,先别合并。

## 事件只是门铃;同一时间只有一次运行

- **每次运行把所有开着的 PR 全重算一遍**,结论只取决于 GitHub 上的现状,与是哪个事件叫醒的无关。
  以前从事件推"该算哪个 PR、写到哪个提交",漏过好几次(没带 PR 的 workflow_run、旧提交、合并提交、指向默认分支的)。
- **同一时间只有一次运行**:workflow 的并发组是固定名字 `aiwork-gate`,不取消正在跑的;排队的只留最新一个
  (GitHub 自己会把更早排队的取消),它开始时读到的一定不比被它顶掉的旧,而它又会重算全部 PR,所以顶掉的不会漏算。
  于是同一提交上后写的结论一定出自后读的数据 —— 不会有慢一步的旧运行盖掉新结论,也不会有较新的运行 App 出错
  拨了 failure、较早的运行又拨回 success。同名检查后发的一定后写完,GitHub 按创建还是按完成时间取"最新",取到的都是
  最后一次运行的;运行半路死掉时它的占位停在 in_progress、保险丝停在 pending,照样挡着,下一次运行全部重算。
- job 上**不许**按事件过滤(比如只认某个标签):排队时被顶掉的运行,要靠顶掉它的那次来算。
- 代价:每次运行读每个开着的 PR 约 6–8 次 API。`GITHUB_TOKEN` 每小时 1000 次;开着的 PR 多、事件又密时会先撞上它,
  撞上就是 G8 不放行(不会误放行)。到时再按实际用量优化。
- 一次运行里先把所有 head 的保险丝拨到 pending(快、不靠 App),再发 App 占位,之后才读 PR 的数据;单个请求最多等
  30 秒(`AIWORK_GATE_TIMEOUT_MS`),卡住的请求拖不垮整次运行。开着的 PR 的列表连读两遍一致才算数(翻页期间有 PR 关掉,
  后面的会往前挪、漏掉一个)。

## 每样输入的门铃

关卡的结论是它读到的输入的函数;哪样输入变了没有门铃,旧结论就一直挂着。

| 关卡读的输入 | 变了靠什么叫醒 |
|---|---|
| PR 的 head、改动文件、推送记录 | `pull_request_target`:`opened` / `synchronize` / `reopened` |
| 目标分支(G1 要 CI 晚于最后一次改目标分支) | `pull_request_target`:`edited` |
| 开着的 PR 有哪些(同一提交上几个 PR 合在一起判) | `pull_request_target`:`opened` / `reopened` / `closed` |
| CI(以最后开始的那次执行为准) | `workflow_run`(ci):`requested` / `in_progress` / `completed`(重跑不一定发 `requested`,开始跑时会发 `in_progress`) |
| 评审(读当前正文;机器人评审发出后被改写过一律按 BLOCK、时刻按改写那一刻;人的评审被撤销按撤销那一刻) | `aiwork-review-ping`:`submitted` / `edited` / `dismissed` → `workflow_run` |
| 策略 `.aiwork/policy.json`(只认 main 上的) | 改 main 之后 CI 跑完的 `workflow_run` |
| 合并请求(PR 上有没有 `aiwork:merge`、最后是谁贴的) | `pull_request_target`:`labeled`(撤掉标签不用叫醒:只会少合并,下一次运行自然读到) |
| 手动重算 | 给 PR 加任何标签(如 `aiwork:recheck`) |

## 已知限制:状态检查只能"最终一致"

关卡靠"输入变了 → 叫醒 → 重算 → 写回",写在提交上的结论总是某一刻的。这种做法本身有补不死的上限,
业主已接受,列在 `.aiwork/accepted-risks.md`。经合并标签合并的 PR 不靠提交上的旧结论,见下「合并」。

## 合并:贴 `aiwork:merge`

- **谁贴的算数**:业主(`policy.json` 的 `owner`)和 `merge_requesters` 里的账号(以后放 OpenClaw 的身份)。
  Builder 贴的不算,也写不进名单(策略校验会拒)—— 不然 Builder 能把自己的 PR 合进去。
  认的是 PR 事件里最后一次贴这个标签的人:撤掉再贴,按最后一次算。
- **不另起一套判定**:关卡每次运行照常把所有开着的 PR 判一遍;某个 head 的结论(App 检查和保险丝)都写上了、
  而且是放行,就当场合并这个 head 上有合并请求的 PR。合并用的就是这次刚读到的数据,调合并接口时带上判过的
  head(`sha`):判完之后又推了新提交,接口会拒,不会把没判过的提交合进去。
- **没放行的请求留着**:之后哪次运行判为放行,就在那次合。不想合了就撤掉标签(关卡正在合的那几秒里撤可能来不及,
  见 `.aiwork/accepted-risks.md` 第 5 条)。
- **"在最新的 main 上测过"不归关卡判**:关卡读的输入(head、改动、评审、head 上的 CI、推送、标签)没有一样随 main
  前进而变,main 动了重判一遍结论也一样。这一点靠 main 规则集的「合并前分支必须和 main 同步」,它对 App 的合并同样生效:
  同一次运行里合了一个 PR,指向 main 的其他 PR 就落后了,GitHub 拒绝合并,请求留着;更新分支 → CI、评审重来 → 放行时再合。
  关了这条规则,关卡会把没和最新 main 一起测过的 PR 合进去。
- **合并没成**(分支落后于 main、有冲突、评审讨论没解决完、刚推了新提交):原因写在那次运行的摘要里,请求留着。
  处理完之后,推送、评审都会叫醒下一次运行再合;没有门铃的(比如把讨论标为已解决),加个 `aiwork:recheck`。
- 合并用 App 另换的一张令牌(Contents / Pull requests / Workflows 写权限),只在真要合并时才换;发检查的那张始终只有 Checks。
- 业主仍可以在网页上直接合并;那条路看的是提交上某一刻的结论(见 `.aiwork/accepted-risks.md`)。

## 同一提交上有几个 PR

检查和保险丝都挂在**提交**上,不是 PR 上。同一提交可以同时是几个开着的 PR 的 head(目标分支不同,改动和要求就不同)。
所以写 success 之前,关卡把这个提交上其他开着的 PR 也判一遍:**全都放行才放行**,有一个不放行就不放行,
查不到就按 G8 失败。

## 模型按任务切换角色

作者识别继续用 `collect.mjs` 的实际推送活动和 `decide.mjs` 的 `authorOf`，策略来源仍是 main。
已知作者时，登记过的其他 Builder 家族可以审这次 PR；审核排除只针对本次作者家族。
作者 UNKNOWN 时保留原有保守处理，不从共享 build 账号猜测实际模型。
本改动不新增可信执行来源，也不改变 App 权限、模型账号配置或云平台接入。

## 首次部署验收(shadow:检查名 `aiwork-gate-shadow`,只报不拦)

合并后,用一个无害的测试 PR(云端 Claude 以机器账号开)逐条看。每条写下 PR 号、提交号和检查的链接。

| # | 做什么 | 预期 | 证明了什么 |
|---|---|---|---|
| S0 | 合并本 PR 后看 main 上 CI 跑完触发的那次 aiwork-gate | 运行成功,只重算开着的 PR;main 的提交上**没有** `aiwork-gate-shadow` | 事件只是门铃,不往非 head 的提交上写 |
| S1 | 开测试 PR | 立刻出现 `aiwork-gate-shadow`(重算中 / 等 CI);检查的 app 是 `aiwork-gate`(id 5121026),不是 GitHub Actions | 占位先行;结果由 App 发出 |
| S2 | 等 CI 跑完 | failure「不放行:缺合格评审」;摘要里 G1 ✅、G4 ✅ 作者 `SunJ1ayuBoT(anthropic)` | CI 按本 PR 认;活动记录接口在 `GITHUB_TOKEN` 下读得到 |
| S3 | 本机 `review-pr` 在当前 head 发 PASS(openai) | 一两分钟内自动重算为 success「放行」 | 评审 → `aiwork-review-ping` → 关卡重算这条链通 |
| S4 | 同一 head 再发一条 BLOCK | failure(G5);业主**在 BLOCK 之后**批准 → success | BLOCK 与批准的先后被认 |
| S5 | 业主在网页上改测试 PR 的一个文件(非机器账号推送) | failure,作者 UNKNOWN(G4);业主在新 head 批准 + 有 PASS → success | 混合作者要业主批准 |
| S6 | 测试 PR 改 `.github/` 下一个文件 / 改 `desktop/` 下一个文件 | 分别要业主批准(G2)/ 两家 PASS + 业主批准(G6) | 判卷面与 high 路径 |
| S7 | 给 PR 加标签 `aiwork:recheck` | 重算一次;算的时候合并框里这条检查显示"重算中",保险丝变黄 | 手动重算可用;占位压得住上一次的结论 |
| S8 | 编辑测试 PR 的标题;再改一次目标分支 | 各重算一次;改目标分支后 G1 ❌「目标分支在这次 CI 之后改过」,推一个新提交(或关掉再重开 PR)让 CI 重跑后恢复 | edited 事件会触发重判;旧目标上的 CI 不算数 |
| S9 | 任选上面一次重算,看测试 PR 的检查列表;再连着触发两次(比如先后加两个标签),看 Actions 里 aiwork-gate 的运行 | `aiwork-gate/fuse` 先变黄(pending),算完与 `aiwork-gate-shadow` 同结论,发出者是 GitHub Actions;两次运行一个跑完另一个才开始 | 保险丝接通,不靠 App 私钥;同一时间只有一次运行 |

合并(本节在「合并」上线后补做,同样用无害的测试 PR):

| # | 做什么 | 预期 | 证明了什么 |
|---|---|---|---|
| S10 | 业主给一个会放行的测试 PR 贴 `aiwork:merge` | 那次运行放行后当场合并:合并者是 `aiwork-gate` App,合进去的是判过的 head | 合并用的是刚判过的数据和 head |
| S11 | 机器账号(Builder)给另一个会放行的测试 PR 贴 `aiwork:merge` | 不合并;运行摘要里写"是 SunJ1ayuBoT 提的,不算数" | Builder 合不了自己的 PR |
| S12 | 业主给一个还缺评审的测试 PR 贴 `aiwork:merge`,之后补上 PASS | 贴的时候不合;PASS 之后那次运行合并 | 请求留着,放行时才合 |
| S13 | 两个都会放行、都指向 main 的测试 PR,业主都贴上 `aiwork:merge` | 合进去一个;另一个被 GitHub 拒(分支落后于 main),摘要里写明,请求留着 | 连着合并时,后一个必须先和新的 main 一起测过 |

失败注入(API 出错、限流、App 私钥坏了、PR 中途推进、合并接口拒绝)在线上没法安全制造,由 `test_aiwork_gate_run.mjs`(R4–R5e、R14b–R14f、R20、R25–R27、M1–M10)与 `test_aiwork_gate_main.mjs`(含请求卡住)覆盖;几次运行不会交错由 workflow 的并发组保证(`test_aiwork_gate_workflow.py`)。

## 从 shadow 转为真拦截

S0–S13 全部符合预期,且之后至少 5 个真实 PR 上 shadow 的结论都和业主的判断一致、没见过过时的 success,再:

1. 发一个 PR 把 `policy.json` 的 `check_name` 改为 `aiwork-gate`(连同钉住它的那条测试;判卷面,要业主批准);
2. 业主在 main 的规则集里:
   - 必过检查从 `ci` 换成**两条**:`aiwork-gate`(来源限定 `aiwork-gate` App)和
     `aiwork-gate/fuse`(来源限定 GitHub Actions)。只设第一条,App 私钥坏了时旧 success 仍能合并。
     「合并前分支必须和 main 同步」留着(见「合并」);
   - **另建**一个规则集,目标 main,只勾 Restrict updates;绕过名单:Repository admin(业主自己还能合)和
     `aiwork-gate` App(选 For pull requests only:只能合 PR,不能直接推)。这样别人只能贴标签请关卡合。
     必须另建:绕过名单绕过的是整个规则集,和必过检查放在一起,App 合并时连必过检查也绕过了;
3. 确认:故意缺评审的 PR 合并按钮被挡住;机器账号在网页上合并被拒;贴了标签、放行的 PR 由 App 合进去。
