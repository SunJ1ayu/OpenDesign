# 放行关卡首次部署验收记录

对照 `.github/aiwork-gate/README.md`「首次部署验收」逐条验,每条附检查或运行的链接。验收时关卡是 shadow(检查名 `aiwork-gate-shadow`,只报不拦)。
时间 2026-09-30(UTC)。测试 PR 是 #13;有几条在 PR #10 ~ #12 上已经顺带验过。
S5 后半和合并标签(S10–S13,PR #15 加的)在 2026-10-01 用 PR #16、#17 验;这两个 PR 的改动本身是正常的小修,验完都已由关卡合并。

| # | 结果 | 在哪验的 | 看到了什么 | 凭据 |
|---|---|---|---|---|
| S0 | ✅ | main @ `43b4cd9`(PR #10 合并) | main 上 CI 跑完后的关卡运行成功;main 的提交上没有 `aiwork-gate-shadow`,也没有保险丝 | main 上 CI 跑完后触发的 [运行 36692667451](https://github.com/SunJ1ayu/OpenDesign/actions/runs/36692667451) |
| S1 | ✅ | #13 @ `b5f3299` | 开 PR 10 秒后出现 `aiwork-gate-shadow`(进行中,「等 CI」),由关卡的 App 发出,不是 Actions 任务;保险丝同时变黄「重算中」 | [检查 109895879577](https://github.com/SunJ1ayu/OpenDesign/runs/109895879577);[运行 36718049294](https://github.com/SunJ1ayu/OpenDesign/actions/runs/36718049294) |
| S2 | ✅ | #13 @ `b5f3299`;#11、#12 | CI 通过后「不放行:缺合格评审」:G1 ✅,G4 ✅ 作者 `SunJ1ayuBoT(anthropic)`;只改 `docs/` 时不出现 G2 / G6 | [检查 109902467276](https://github.com/SunJ1ayu/OpenDesign/runs/109902467276) |
| S3 | ✅ | #13 @ `d49313e`;#12 | 评审发出后约 20 秒自动重算;有 PASS、CI 通过、不需要业主批准的 PR 直接「放行」 | [检查 109912120362](https://github.com/SunJ1ayu/OpenDesign/runs/109912120362);#12 [评审 5366237384](https://github.com/SunJ1ayu/OpenDesign/pull/12#pullrequestreview-5366237384) → [运行 36715848297](https://github.com/SunJ1ayu/OpenDesign/actions/runs/36715848297) |
| S4 | ✅ | #13 @ `d49313e` | 同一提交上先 PASS 后 BLOCK:从「放行」变为「等业主批准:有 BLOCK」(G5、G7);业主在 BLOCK 之后批准 → 「放行」 | [评审 5366980550](https://github.com/SunJ1ayu/OpenDesign/pull/13#pullrequestreview-5366980550) → [检查 109913852941](https://github.com/SunJ1ayu/OpenDesign/runs/109913852941);业主 [评审 5367004875](https://github.com/SunJ1ayu/OpenDesign/pull/13#pullrequestreview-5367004875) → [运行 36723573121](https://github.com/SunJ1ayu/OpenDesign/actions/runs/36723573121) |
| S5 | ✅(后半见注 1) | 前半 #13 @ `e279c8d`;后半 #17 @ `e24c4b3` | 业主在网页上提交后:G4「作者 UNKNOWN:有非 Builder 账号推送过:SunJ1ayu」,G7 要业主在当前提交上批准;旧提交上的批准和评审都不算。后半:业主点 Update branch 推出 `e24c4b3` → 同上;新提交上有 PASS 后「等业主批准:作者 UNKNOWN」;业主批准后「放行」 | 前半 [检查 109915947779](https://github.com/SunJ1ayu/OpenDesign/runs/109915947779)、[检查 109923336016](https://github.com/SunJ1ayu/OpenDesign/runs/109923336016);后半 [检查 110200933638](https://github.com/SunJ1ayu/OpenDesign/runs/110200933638) → [评审 5374560832](https://github.com/SunJ1ayu/OpenDesign/pull/17#pullrequestreview-5374560832) → [检查 110203189158](https://github.com/SunJ1ayu/OpenDesign/runs/110203189158) → 业主 [评审 5374626565](https://github.com/SunJ1ayu/OpenDesign/pull/17#pullrequestreview-5374626565) → [检查 110205060502](https://github.com/SunJ1ayu/OpenDesign/runs/110205060502) |
| S6 | ✅ | #11、#12 | 改判卷面要业主批准(G2);high 路径只有 1 家 PASS 时拦下,2 家(openai、deepseek)都 PASS 时 G6 通过 | #11 [检查 109825010381](https://github.com/SunJ1ayu/OpenDesign/runs/109825010381);#12 [检查 109888506197](https://github.com/SunJ1ayu/OpenDesign/runs/109888506197)(1 家)、[检查 109891360301](https://github.com/SunJ1ayu/OpenDesign/runs/109891360301)(2 家) |
| S7 | ✅ | #13 @ `b5f3299` | 加标签 → 关卡重算一次 | [运行 36720544315](https://github.com/SunJ1ayu/OpenDesign/actions/runs/36720544315)、[运行 36720583501](https://github.com/SunJ1ayu/OpenDesign/actions/runs/36720583501) |
| S8 | ✅ | #13 @ `b5f3299` → `d49313e` | 改标题 → 重算,结论不变;改目标分支 → G1「目标分支在这次 CI 之后改过」;改回 main、推新提交让 CI 重跑后恢复 | 改标题 [检查 109904975829](https://github.com/SunJ1ayu/OpenDesign/runs/109904975829);改目标分支 [检查 109905165792](https://github.com/SunJ1ayu/OpenDesign/runs/109905165792);改回 [检查 109905494806](https://github.com/SunJ1ayu/OpenDesign/runs/109905494806);恢复 [检查 109912120362](https://github.com/SunJ1ayu/OpenDesign/runs/109912120362) |
| S9 | ✅ | #13 | 重算时保险丝先变黄「重算中,算完之前不放行」,压住上一次的「放行」,算完与检查同结论,由 GitHub Actions 发出;连着两次重算,后一次的任务在前一次跑完后才开始 | [运行 36723334048](https://github.com/SunJ1ayu/OpenDesign/actions/runs/36723334048)(保险丝先 pending 后 failure);[运行 36720544315](https://github.com/SunJ1ayu/OpenDesign/actions/runs/36720544315) → [运行 36720583501](https://github.com/SunJ1ayu/OpenDesign/actions/runs/36720583501)(排队) |
| S10 | ✅ | #16 @ `5af2ab8` | 业主贴的 `aiwork:merge`;PASS 后那次运行放行并当场合并:合并者 `aiwork-gate[bot]`,合并提交 `f78c7d0` 的第二个父提交就是判过的 `5af2ab8`;日志「PR #16:按 SunJ1ayu 的请求合并了 5af2ab8」 | [评审 5374361278](https://github.com/SunJ1ayu/OpenDesign/pull/16#pullrequestreview-5374361278) → [运行 36807432622](https://github.com/SunJ1ayu/OpenDesign/actions/runs/36807432622)、[检查 110194829262](https://github.com/SunJ1ayu/OpenDesign/runs/110194829262) |
| S11 | ✅ | #17 @ `c0f16fc` | 机器账号 `SunJ1ayuBoT` 贴的 `aiwork:merge`;有 PASS、放行,但不合并;日志「PR #17:贴着合并标签,但合并请求是 SunJ1ayuBoT 提的,不算数」 | [评审 5374361528](https://github.com/SunJ1ayu/OpenDesign/pull/17#pullrequestreview-5374361528) → [运行 36807432622](https://github.com/SunJ1ayu/OpenDesign/actions/runs/36807432622) |
| S12 | ✅ | #16 @ `5af2ab8` | 业主在评审之前贴标签:那次运行「不放行:缺合格评审」,不合并;PASS 之后那次运行合并(同 S10) | [运行 36804811986](https://github.com/SunJ1ayu/OpenDesign/actions/runs/36804811986)、[检查 110186723765](https://github.com/SunJ1ayu/OpenDesign/runs/110186723765) |
| S13 | ⚠️ 部分通过(见注 4) | #17 @ `c0f16fc` | 验到的:#16 合并后 #17 落后于 main;业主撤掉机器账号的标签、自己重贴 → 关卡放行并去合并,GitHub 拒绝(HTTP 405「Required status check "ci" is expected」),原因写进日志,请求留着;之后业主点 Update branch、重新评审批准后合并(见 S5)。**没验到**:两个都由业主贴了标签、都已放行的 PR,在同一次运行里连着合并 | [运行 36807902897](https://github.com/SunJ1ayu/OpenDesign/actions/runs/36807902897)、[检查 110196295702](https://github.com/SunJ1ayu/OpenDesign/runs/110196295702) |

注:

1. S5 后半(新提交上有 PASS + 业主批准 → 放行)第一次没做成:#13 在「等业主批准:作者 UNKNOWN」时被误点合并。
   2026-10-01 在 #17 上补验:业主在网页上点 Update branch(业主推送),之后的结论与前半一致,有 PASS、业主批准后放行,
   并由关卡按业主的合并标签当场合并。
2. 这次误合并本身说明了 shadow 的边界:只报不拦时,没放行的 PR 照样能合。转真拦截之后,合并按钮会被挡住。
3. S4 的 BLOCK 是为验收手工发的评审(正文注明「验收用」),不是评审模型的结论。
4. S13 按 README 的场景是两个 PR 都由业主贴上标签、都已放行,关卡在**同一次运行**里合进第一个后再去合第二个。
   这次 #16 合并时 #17 的标签还是机器账号贴的,业主重贴已是另一次运行,只验到了"落后于 main 的 PR 合并会被拒"。
   同一次运行里第二次合并紧跟第一次(相隔一两秒),GitHub 是否同样拒绝要实测,所以 **S13 在转真拦截之前要补验**:
   两个 PR 都有 PASS 后,业主几秒内先后给两个贴标签(第一次运行开始读数据前两个标签都在),看日志里第二个是否被拒。
