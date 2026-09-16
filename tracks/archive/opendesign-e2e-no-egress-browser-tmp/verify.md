# Verify: opendesign-e2e-no-egress-browser-tmp

- Date: 2026-09-15

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录
> `decision.json`；这里保留检查、理由、发现与主 Agent 仲裁说明，不复制枚举。

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再按 impact-risk 预算跑 panel-review；只有特殊控制面
> 才显式 `--all` 做全池评审。最后仍由主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [x] build passes(`node --check` / `bash -n` / python ast 均通过)
- [x] tests pass
- [x] no secrets / unsafe ops(产品代码零改动;新增的只有判据侧守卫与临时目录管理)

**机器打印的**(不是我的转述):

判据先行(09-15,实现之前)—— **7 红 5 绿**,两份红的是同一组(ne1 ne2 ne5 ne6 ne7 ne8 bt1)。
v2 是 bt1 的场景从「被硬杀」扩成「开着就退出 / 主进程被硬杀」两种之后重跑的,红集合不变:

```
runlog: red-ne-bt-oracle rc=1 commit=c98f406 dirty=yes at=2026-09-15T13:51:49Z file=tracks/opendesign-e2e-no-egress-browser-tmp/evidence/20260915T135149Z-01-red-ne-bt-oracle.txt
runlog: red-ne-bt-oracle-v2 rc=1 commit=c98f406 dirty=yes at=2026-09-15T13:54:00Z file=tracks/opendesign-e2e-no-egress-browser-tmp/evidence/20260915T135400Z-01-red-ne-bt-oracle-v2.txt
```

实现之后:

```
runlog: e2e-all-after-noegress rc=0 commit=c7b2510 dirty=yes at=2026-09-16T07:53:09Z file=tracks/opendesign-e2e-no-egress-browser-tmp/evidence/20260916T075309Z-01-e2e-all-after-noegress.txt
runlog: redcheck-noegress rc=0 commit=aee16e2 dirty=yes at=2026-09-16T07:58:17Z file=tracks/opendesign-e2e-no-egress-browser-tmp/evidence/20260916T075817Z-01-redcheck-noegress.txt
runlog: full-suite-after-noegress rc=0 commit=aee16e2 dirty=yes at=2026-09-16T07:58:27Z file=tracks/opendesign-e2e-no-egress-browser-tmp/evidence/20260916T075827Z-01-full-suite-after-noegress.txt
runlog: e2e-with-gateway-exempt-two rc=0 commit=aee16e2 dirty=yes at=2026-09-16T08:07:17Z file=tracks/opendesign-e2e-no-egress-browser-tmp/evidence/20260916T080717Z-01-e2e-with-gateway-exempt-two.txt
runlog: redcheck-round1-fixes rc=0 commit=590d86f dirty=yes at=2026-09-16T08:22:10Z file=tracks/opendesign-e2e-no-egress-browser-tmp/evidence/20260916T082210Z-01-redcheck-round1-fixes.txt
runlog: e2e-all-after-round1-fixes rc=0 commit=590d86f dirty=yes at=2026-09-16T08:22:18Z file=tracks/opendesign-e2e-no-egress-browser-tmp/evidence/20260916T082218Z-01-e2e-all-after-round1-fixes.txt
runlog: full-suite-final rc=0 commit=590d86f dirty=yes at=2026-09-16T08:25:15Z file=tracks/opendesign-e2e-no-egress-browser-tmp/evidence/20260916T082515Z-01-full-suite-final.txt
runlog: arbitrate-r2-deepseek-block rc=0 commit=590d86f dirty=yes at=2026-09-16T09:11:35Z file=tracks/opendesign-e2e-no-egress-browser-tmp/evidence/20260916T091135Z-01-arbitrate-r2-deepseek-block.txt
```

- 判据 `tests/test_e2e_harness_guard.mjs`:第 1 轮前 **12/12 绿**(实现前 7 红,见判据先行那一笔 `b13a71d`);
  第 1 轮修完 **15/15 绿**(补的 ne9/ne10/bt4 在旧实现上精准红 3 条,`redcheck-round1-fixes`)。
  ⚠️ **15/15 里的 bt4 是假绿**,见下面仲裁 F2 —— 绿的条数不等于问住的条数。
- 第 1 轮修完:e2e 总跑仍 **40 PASS / 0 FAIL / 2 SKIP**;全仓 python 总跑 1695 OK(`full-suite-final`)。
  ⚠️ **外层 `tests/run-all.sh` 这一单一次都没真跑过**(见 F2 附带的证据缺口)。
- **红检是"真退回实现"**:退回 `b13a71d` 的 6 个实现文件 ⇒ 正好 **7 红**,红在目标断言上(`fail 7`)。
- e2e 总跑 **40 PASS / 0 FAIL / 2 SKIP**(与改动前逐项一致 —— 隔离没打坏任何一条);
  `--with-gateway` **42 PASS / 0 FAIL / 0 SKIP**(豁免那两条真连活网关、真发消息,现实中成立)。
- 全仓 python 总跑 **1695 OK(skipped=1)**;死断言闸 69 文件 / 4058 断言 / **0 条从没跑过**。

**不止"判据绿"——闸给了我想要的答案,所以我去查了它**:
- 直接看内核:真 e2e 的场景进程 `ns=net:[4026532293]`,1 号进程 `net:[4026531840]` ⇒ **真隔离**;
- 给**真 e2e**(不是合成场景)预设 `DS_E2E_NOEGRESS_TRIED` ⇒ 当场拒跑 rc=78
  ⇒ 守卫活在真文件的导入链上,不只活在判据的夹具里。

## Review

- 规格自查(读任何 panel 输出之前先答):**这份规格最可能错在"把问题定义窄了"。**
  我治的是"e2e 会去问 GitHub",做法是掐掉整个进程的外网。若规格错了,会错成这样:
  **某条 e2e 本来就需要某个外部服务,而它一直靠真网跑通** —— 隔离之后它红了,
  我会把它读成"我改坏了"并去加豁免,豁免名单一条条长大,最后这道闸名存实亡。
  目前的证据不支持这种情况(40 条隔离后逐项与改前一致),但**判断它的时机是在未来加第三条豁免时**:
  那一刻要问的是"这条 e2e 为什么需要外网",不是"怎么让它过"。
- 腿的花名册(机器写的,原样):

  第 1 轮 @ `aee16e2`:
  ```
  # impact-risk=high requested-budget=2 selected-count=2
  # selected=submimo(xiaomi/submimo),subdeepseek(deepseek/subdeepseek-agent)
  # escalation=none
  # snapshot=head:aee16e2
  submimo=PASS(verdict=PASS) subdeepseek=PASS(verdict=PASS) subglm=SKIP(rotation) subkimi=SKIP(health:cooldown:rate_limit) subgemini=SKIP(health:dead:FAIL:6) subgrok=SKIP(health:cooldown:rate_limit)
  ```
  第 2 轮 @ `590d86f`(本单上限 2 轮的最后一轮):
  ```
  # impact-risk=high requested-budget=2 selected-count=3
  # selected=submimo(xiaomi/submimo),subdeepseek(deepseek/subdeepseek-agent),subglm(zhipu/subglm-agent)
  # escalation=conflict
  # snapshot=head:590d86f
  submimo=PASS(verdict=PASS) subdeepseek=PASS(verdict=BLOCK) subglm=FAIL(rc=1,降级:回落聊天腿也没成) subkimi=SKIP(health:cooldown:rate_limit) subgemini=SKIP(health:dead:FAIL:6) subgrok=SKIP(health:cooldown:rate_limit)
  ```
  第三腿 GLM 是冲突触发的追加腿,死于 `GoUsageLimitError`(月额度用光,服务端原话)—— 不是腿坏了。
  ⇒ **冲突没有第三意见可借,由我造探针量**(不投票)。

- findings —— 第 1 轮(DeepSeek 虽判 PASS,另提 8 条;处置在第 2 轮任务书里逐条写过):
  - 已修:#1 点名到不了人眼 / #2 回环起不来是静默的 / #5 探得过、跑不动时裸退(→ bt4 / ne9 / ne10)。
  - 记账:#3 ne0 看外网脸色(有意,已知代价)/ #4 豁免按仓内路径匹配 / #6 python re-exec 丢解释器 flag /
    #7 重复 import(nit)/ #8 README 没写守卫前提。

- findings —— 第 2 轮(MiMo PASS、0 条;DeepSeek BLOCK、7 条)。**逐条对代码核过**,复现收据
  `arbitrate-r2-deepseek-block`(脚本 `arbitrate-r2.sh` 在本目录,只读,可重跑):
  - **F2 成立 · 考卷假绿**:bt4 按原样判法,把 `tests/run-all.sh` 里两行计数代码删掉**照样绿** ——
    它找的那句话在上面的注释里也有,位置同样在 `note_last` 之前。红检当时红,是因为退回旧实现时注释一起没了。
    附带证据缺口:本单证据里外层 `tests/run-all.sh` 打印的 `════ 总跑汇总 ════` 出现 **0 次**
    (同一匹配在别的 track 的外层真跑收据里命中 91 次,正对照成立)⇒ 新加的两行 shell **从没执行过**。
  - **F3 成立**:用两处真实代码块喂 1 条点名,汇总行报「浏览器收容 **2** 次」。内层表头那行也含这句话,`grep -c` 数的是行。
    这就是 F2 放过的东西。
  - **F1 成立**:汇总行叫人「看 e2e 段日志点名」,而绿路径(全绿 / 只跳过)上 `tests/run-all.sh` 先 `rm -rf "$log_dir"`
    ⇒ 名字仍然到不了人眼,还多了一句指向已删日志的话。第 1 轮 #1 只修到「有没有」,没修到「是谁」。
  - **F4 成立**:ne9 的 node 版注释写「errno 不同」,实现是拿 bash 报错**文本**匹配 `unreachable|不可达`。
    bash 二进制里没有 unreachable 这个词、libc 里有 ⇒ 文本来自 strerror,吃 locale;换语言环境时静默放行(fail-open)。
    **MiMo 的「bash /dev/tcp 不走 strerror」是错的。** 本机 en_US 且无 libc.mo,本机踩不到。
  - **F6 成立**:python 版的回环检查没有任何判据跑到它(ne9 只跑 node 场景;ne7 用真 ip,lo 总是起的)。
  - **F5 成立但轻**:python 版没有 ne10 的等价物 —— 内层 bash exec 失败时只有 bash 自己的一行报错,没有守卫横幅。
  - **F7 部分成立**:泄漏闸 `find -mindepth 1 -maxdepth 1` **不分文件目录**(复现数到 1)⇒ 父进程被 SIGKILL 留下的
    `.started` 文件会被报成泄漏、归因不准;**MiMo 的「闸只数目录」是错的**。PID 复用读到陈旧标记、标记写不进去时误诊 —— 成立,可达性很低。

- 规矩②自检(**每条「不在本单修」先写它在业主那边会长成什么样**):
  - F1/F2/F3:业主看不到汇总行,**业主侧零影响**。但 F2 是考卷假绿 ⇒ 按②**值得返工**;
    长成的样子是「以后有人弄坏计数,没有判据会红 ⇒ 浏览器残留又变回没人听见 ⇒ 慢慢攒进 /tmp」,
    而这台机器 08-17 真被判据的残留撑满过一次盘(业主报「磁盘满了」)。F1/F3 是同一处、同一次修。
  - F4/F6:业主侧零影响;本机 locale 下踩不到。F4 是「注释说 errno、实现看文本」,F6 是新代码零判据 —— 都是「设计说了、判据没问到」,改动各几行 ⇒ 并进下一单。
  - F5/F7、第 1 轮 #3/#4/#6/#7:业主侧零影响;说不出会硌到他的样子 ⇒ **记账,不占一轮**。
  - 第 1 轮 #8 README:业主侧零影响;对我是「下一个跑 e2e 的人不知道要 root+unshare」,横幅会自己说明 ⇒ 顺手并进下一单(纯文档)。

- arbitrated verdict (主裁):**BLOCK**(机器字段在 `decision.json`)。
  - 核心不变量**是交付了的**:e2e 判据进程真没有外网出口(看内核 netns、真 e2e 预设标记当场拒跑、40 条逐项与改前一致、
    豁免两条连活网关 42 PASS)。它不是「没做成」,是**这单宣称的三件事里有一件的判据是假绿**,那就不许盖 PASS。
  - **为什么不开第 3 轮**:proposal 开工时写死「本单外部评审上限 2 轮,超出的发现记进 verify.md 并排入下一单」(规矩③)。
    F2 符合②的返工条件,返工的地方是**下一单**,不是本单的第 3 轮。
  - 两条腿冲突时 MiMo 的 PASS 带着两句**事实性错误**(F4 的 strerror、F7 的只数目录),它的「无新问题」不能用来抵消 DeepSeek 的复现。
    这是 MiMo 在本机又一次「全票 PASS 里的那一票不可靠」的数据点。

- 下一单(`opendesign-e2e-guard-followup`):F1+F2+F3(名字真到人眼 + bt4 改成行为级 + 计数改对 + 外层真跑一次)、
  F4(node 版改读 errno)、F6(python 回环补判据)、#8(README)。记账不做:F5、F7、#3、#4、#6、#7。

## Accepted deviations

- 不接受任何偏差按 PASS 收 —— 本单裁决 BLOCK,上面的修复转下一单。
- 本单 3 个实现 commit(`aee16e2` / `9d13623` / `590d86f`)**不回退**:守卫的核心隔离是对的、判据 ne0~ne10/bt1~bt3 真能红,
  坏的只是汇总行的计数/点名那一截,回退反而把真在起作用的无出口闸一起拆掉。
