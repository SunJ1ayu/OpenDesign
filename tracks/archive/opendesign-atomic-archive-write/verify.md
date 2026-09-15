# Verify: opendesign-atomic-archive-write

- Date: 2026-09-15

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录
> `decision.json`；这里保留检查、理由、发现与主 Agent 仲裁说明，不复制枚举。

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再按 impact-risk 预算跑 panel-review；只有特殊控制面
> 才显式 `--all` 做全池评审。最后仍由主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [x] build passes —— 最终总跑「dist 新鲜度 + 类型检查」段(收据 `final-run-all-with-gateway-rerun`)
- [x] tests pass —— **0 红,但 1 条没跑**(最终总跑 `--with-gateway` rc=3,`source-stable: yes`)。**这不叫"全绿"**:
      六段全 PASS(python 1637 跑过 / 1 跳过、node 422、e2e 42 PASS / 0 SKIP)。跳过的那 1 条是
      `test_aw12b_a_long_reader_fails_the_write_but_keeps_the_archive`(`skipped '只有 Windows 上"开着的文件换不掉"'`,
      本机 `-v` 逐条核过,三个模块里唯一一条)⇒ 由 windows-atomic-probe 在 Windows 上真跑:probe-4 @ 8a4e327 `aw12b ... ok`(收据 `…-probe4`)。
      总跑末尾「要跑那两条 e2e:先起 gateway」是 run-all.sh 第 189 行无条件打印的提示,这遍 e2e 0 SKIP,与本次跳过无关(文案账,不在本单改)。
- [x] no secrets / unsafe ops —— 本单只改档案写入方式,无新外呼、无新写口;新增 `.locks/` 目录只放空锁文件

**机器打印的**(不是我的转述)—— 判据一律用 `runlog` 跑,下面每一行都是它写的:

```
runlog: red-aw-oracle rc=1 commit=9bdd3af dirty=yes at=2026-09-15T03:49:13Z file=tracks/opendesign-atomic-archive-write/evidence/20260915T034913Z-01-red-aw-oracle.txt
runlog: judge-no-nested-still-bites rc=0 commit=5d68dcd dirty=yes at=2026-09-15T03:53:37Z file=tracks/opendesign-atomic-archive-write/evidence/20260915T035337Z-01-judge-no-nested-still-bites.txt
runlog: green-aw-impl-python-full rc=1 commit=e5eb0c1 dirty=yes at=2026-09-15T03:54:19Z file=tracks/opendesign-atomic-archive-write/evidence/20260915T035419Z-01-green-aw-impl-python-full.txt
runlog: green-aw-impl-python-full-v2 rc=0 commit=84db520 dirty=yes at=2026-09-15T04:25:31Z file=tracks/opendesign-atomic-archive-write/evidence/20260915T042531Z-01-green-aw-impl-python-full-v2.txt
runlog: redcheck-atomic-write rc=1 commit=46c929d dirty=yes at=2026-09-15T07:01:06Z file=tracks/opendesign-atomic-archive-write/evidence/20260915T070106Z-01-redcheck-atomic-write.txt
runlog: red-aw10b-on-pre-fix-impl rc=0 commit=46c929d dirty=yes at=2026-09-15T07:03:22Z file=tracks/opendesign-atomic-archive-write/evidence/20260915T070322Z-01-red-aw10b-on-pre-fix-impl.txt
runlog: redcheck-atomic-write-v2 rc=0 commit=d813814 dirty=yes at=2026-09-15T07:03:56Z file=tracks/opendesign-atomic-archive-write/evidence/20260915T070356Z-01-redcheck-atomic-write-v2.txt
runlog: windows-atomic-probe-run-34930064530 rc=0 commit=d813814 dirty=yes at=2026-09-15T07:04:36Z file=tracks/opendesign-atomic-archive-write/evidence/20260915T070436Z-01-windows-atomic-probe-run-34930064530.txt
runlog: red-aw12c-aw15-aw16-oracle rc=0 commit=9e716a9 dirty=yes at=2026-09-15T07:41:52Z file=tracks/opendesign-atomic-archive-write/evidence/20260915T074152Z-01-red-aw12c-aw15-aw16-oracle.txt
runlog: green-aw12c-aw15-aw16-impl rc=0 commit=448d598 dirty=yes at=2026-09-15T07:42:37Z file=tracks/opendesign-atomic-archive-write/evidence/20260915T074237Z-01-green-aw12c-aw15-aw16-impl.txt
runlog: redcheck-atomic-write-v3 rc=0 commit=8ff7875 dirty=yes at=2026-09-15T07:43:07Z file=tracks/opendesign-atomic-archive-write/evidence/20260915T074307Z-01-redcheck-atomic-write-v3.txt
runlog: red-aw17-oracle rc=0 commit=6ca1d24 dirty=yes at=2026-09-15T07:52:16Z file=tracks/opendesign-atomic-archive-write/evidence/20260915T075216Z-01-red-aw17-oracle.txt
runlog: windows-atomic-probe-run-34943232207-after-fix rc=0 commit=6ca1d24 dirty=yes at=2026-09-15T07:52:31Z file=tracks/opendesign-atomic-archive-write/evidence/20260915T075231Z-01-windows-atomic-probe-run-34943232207-after-fix.txt
runlog: windows-atomic-probe-run-34943425108-prefix-448d598 rc=0 commit=6ca1d24 dirty=yes at=2026-09-15T07:52:34Z file=tracks/opendesign-atomic-archive-write/evidence/20260915T075234Z-01-windows-atomic-probe-run-34943425108-prefix-448d598.txt
runlog: green-aw17-impl rc=0 commit=ff93e92 dirty=yes at=2026-09-15T07:53:25Z file=tracks/opendesign-atomic-archive-write/evidence/20260915T075325Z-01-green-aw17-impl.txt
runlog: redcheck-atomic-write-v4 rc=0 commit=bd00f7a dirty=yes at=2026-09-15T07:53:47Z file=tracks/opendesign-atomic-archive-write/evidence/20260915T075347Z-01-redcheck-atomic-write-v4.txt
runlog: red-aw17b-oracle rc=0 commit=9fb4868 dirty=yes at=2026-09-15T08:30:13Z file=tracks/opendesign-atomic-archive-write/evidence/20260915T083013Z-01-red-aw17b-oracle.txt
runlog: windows-atomic-probe-run-34944147765-probe3 rc=0 commit=9fb4868 dirty=yes at=2026-09-15T08:30:42Z file=tracks/opendesign-atomic-archive-write/evidence/20260915T083042Z-01-windows-atomic-probe-run-34944147765-probe3.txt
runlog: green-aw17b-impl rc=0 commit=feaaf04 dirty=yes at=2026-09-15T08:31:36Z file=tracks/opendesign-atomic-archive-write/evidence/20260915T083136Z-01-green-aw17b-impl.txt
runlog: redcheck-atomic-write-v5 rc=0 commit=e754c09 dirty=yes at=2026-09-15T08:32:11Z file=tracks/opendesign-atomic-archive-write/evidence/20260915T083211Z-01-redcheck-atomic-write-v5.txt
runlog: final-run-all-with-gateway-rerun rc=3 commit=8a4e327 dirty=yes final=yes at=2026-09-15T09:31:08Z file=tracks/opendesign-atomic-archive-write/evidence/20260915T093108Z-01-final-run-all-with-gateway-rerun.txt
runlog: windows-atomic-probe-run-34947593560-probe4 rc=0 commit=8a4e327 dirty=yes at=2026-09-15T09:43:56Z file=tracks/opendesign-atomic-archive-write/evidence/20260915T094356Z-01-windows-atomic-probe-run-34947593560-probe4.txt
```

- **红的那几份各自红在哪(一份不藏)**:
  - `red-aw-oracle` rc=1:判据先行,修前 7 红(0 字节档案真复现过)—— 该红。
  - `green-aw-impl-python-full` rc=1:1622 OK,但**死断言闸**报 aw12b 三条断言本机一次没执行(Windows 专属)⇒
    `84db520` 放进 `tests/dead_assertions.allow` 并让 windows-atomic-probe 单独要求 aw12b「真跑且 ok」;v2 rc=0。
  - `redcheck-atomic-write` rc=1:m8 漏网 —— **判据真有洞**:aw10 夹具首行不是 `# 旧名`、故障先落在①,问不到"改档案标题"那个写口。
    补 aw10b 并对修复前实现 2063c9a 跑红(`red-aw10b-on-pre-fix-impl`,档案被截成 37324/38348 字节),v2 起全咬住。
  - `red-aw12c-aw15-aw16-oracle` / `red-aw17-oracle` / `red-aw17b-oracle` 的 rc=0 是外层 grep 的;内容分别是 FAILED(2) / errors=1 / failures=4 —— 判据先行的红。
- **Windows 真机半**:四次探针。`probe-2-prefix @ 448d598`(判据在、修复前)**3 红**:aw15 空转 2.047 秒、aw12c「being used by another process」、aw16
  ⇒ 证明 aw12c / aw15 在 Windows 上真问得到;修复后 probe-2 / probe-3 / probe-4 全绿(probe-4 @ 8a4e327 = 评审 r4 的 subject,aw17b 在 Windows 上真跑 ok)。
- **最终总跑跑了两遍,第一遍没有结果**:16:54 起跑的 `final-run-all-with-gateway` 被会话断线砍掉(runlog 由会话里的后台任务拉起,
  断线把整组进程杀了),收据只写出表头、没有输出也没有 `runlog:` 结果行 ⇒ 它不是红也不是绿,是"没跑完"。
  **没进 git**:交付绑定只把带 `runlog:` 结果行的收据当作收尾记录排除,这份无结果行的会被当普通内容计入仓库 digest,
  提交它会让 r4 绑定的交付内容对不上。17:31 用 `setsid -f` 脱离会话重跑(`-rerun`,父进程 1),上面贴的是这一遍。

## Review

- 规格自查(读任何 panel 输出之前先答):**规格若错,最可能错在"原子写就等于不会半截"**—— 它只管单个文件;
  多文件的操作(rename_project 五处)照样能半截。我原来的判据表把 aw10 写成"三类都问",实际只问到一类(红检 m8 才照出来),
  后面三轮评审抓到的全是这一条线上的东西(只读档案、兄弟文件只读)。发现方式:红检 + 让评审专门问"多文件中途失败"。
- 腿的花名册(五次派发,**原样粘的**;r3 第一次派发因 GLM 在冷却没选上、我撤掉重派,花名册用 panel-roster 从盘上重建):

```
r1  panel-opendesign-atomic-archive-write-review-20260915-150932(subject 9e716a9)
submimo=PASS(verdict=PASS) subdeepseek=SKIP(rotation) subglm=SKIP(rotation) subkimi=PASS(verdict=PASS) subgemini=SKIP(health:dead:FAIL:6) subgrok=PASS(verdict=BLOCK)
r2  panel-opendesign-atomic-archive-write-review-r2-20260915-154528(subject 6ca1d24)
submimo=off subdeepseek=PASS(verdict=BLOCK) subglm=FAIL(rc=1,降级:回落聊天腿也没成) subkimi=off subgemini=off subgrok=off
r3a panel-opendesign-atomic-archive-write-review-r3-20260915-155558(撤销)
submimo=未收尾(无 state:被砍或仍在跑) subdeepseek=off subglm=SKIP(health:cooldown:FAIL) subkimi=off subgemini=off subgrok=未收尾(无 state:被砍或仍在跑)
r3  panel-opendesign-atomic-archive-write-review-r3-20260915-155652(subject 9fb4868)
submimo=PASS(verdict=BLOCK) subdeepseek=off subglm=FAIL(rc=1,降级:回落聊天腿也没成) subkimi=off subgemini=off subgrok=PASS(verdict=PASS)
r4  panel-opendesign-atomic-archive-write-review-r4-20260915-163425(subject 8a4e327)
submimo=off subdeepseek=off subglm=PASS(verdict=PASS) subkimi=PASS(verdict=PASS) subgemini=off subgrok=PASS(verdict=PASS)
```

- GLM 两次失败的死因(查 opencode DB,不看腿日志尾巴):r2 第 8 步 **流在传了 219 秒、52,589 字推理之后被切断**(finish=unknown、tokens 0,
  同 08-25 / 09-09 两次;本机到 opencode 边缘 3 毫秒、首包 0.39 秒,不是本机网络);r3 跑满 `ZHIPU_TIMEOUT` 900 秒(glm-5.3 慢),
  r4 放宽到 1800 秒后 815 秒交卷。回落聊天腿两次都没有 diff 基线(r4 起配 `PANEL_DIFF_BASE`)。
- findings(逐条对代码 / 复现核过):
  - r1 Kimi【低】Windows 只读档案:替换和删除都失败 ⇒ 空转 2 秒 + 删不掉的只读 `.tmp`(旧 open(r+) 立刻报错)—— **修**(aw15)。
    MiMo 以"档案从不只读"否掉 —— 推测,驳回。
  - r1 Kimi【低】④ 裸 `os.replace` —— **修**(aw12c 行为 + aw16 结构)。
  - r1 Kimi【低】aw10 docstring / design 表写"三类都问"—— **改正表述**。
  - r1 Kimi【低】`.locks/x.lock/` 目录能藏档案 —— 驳回:产品无入口在 `.locks` 里建目录,项目名带 `/` 被 H1 闸拒。
  - r1 Grok【中】重试用尽不删 tmp —— 驳回:finally 在 tmp 非 None 时 unlink,aw12b 在 Windows 上验过。
  - r1 Grok【中】重试中途进程被杀留 tmp —— 成立,**降为低、记账**:档案完好,残骸是隐藏 `.x.md.xxxx.tmp`,列表只认 `.md`。
  - r1 MiMo【低】改名后等旧锁的写者拿到 FileNotFoundError —— 成立、低,比修前(写进已被 unlink 的 inode、改动静默蒸发)好。
  - r2 DeepSeek【中】只读档案改名留半成品 —— **修**(aw17):临时目录复现,aw15 拦截落在①提交之后。
  - r2 DeepSeek【低】永久 PermissionError 也空转 2 秒 / workspace.json 写口同样的只读残骸机制(07-27 起就在)/ 只读判法只看权限位 /
    aw16 可被别名绕过 / aw12c 夹具不走改标题分支 —— 接受不修(理由见 r3 自审,仓外 `/root/aiwork/tasks/…-r3-my-review.md`)。
  - r3 GLM(被砍前实验证实)【中】客户备忘 / 索引 / 参考图索引只读同样改到一半 —— **修**(aw17b + `_rename_rewrites` 闸前清单)。
  - r3 MiMo【中】`projects/` 目录只读 —— **驳回**:修前 `os.replace` 同样要求目录可写;Windows 目录"只读"属性不挡写入,按权限位拦会误拒;
    `os.access` 在 root 下恒真写不红。r4 GLM 与 Kimi 各自逐条核对三条理由,均判成立。
  - r4 GLM F1 / Kimi #2【低】红检缺②(参考图索引)那一类的变异 —— 接受不补(见 Accepted deviations)。
  - r4 GLM F2【低】错误路径 `os.path.relpath` 跨盘(Windows 跨盘 junction)抛 ValueError —— 接受,记账(崩在 return 构造处,一份文件都没动)。
  - r4 GLM F3 / Kimi #1【中,**修前就在**】坏编码(GBK)`refs-index.md` 改名在②崩、①已提交 —— 两条腿都在基线 9fb4868 上复现同形,
    非本单引入;记账,建议另开单(预扫把"读不出的参考图索引"也当成拒绝理由)。
  - r4 Kimi #3【低】aw17b 不钉②条件边界(弱化成整行子串仍绿)—— 后果是多拒不是漏拦,接受。
- arbitrated verdict (主裁): **PASS**。
  r4 三个家族(zhipu / moonshot / xai)在同一 subject 8a4e327 上一致 PASS、无冲突;我的 r4 自审(派发前落盘)同为 PASS。
  r1~r3 的每条 BLOCK 都已逐条修掉或给出可复核的驳回理由。

## Accepted deviations

- **红检没有②(参考图索引)那一类的变异**:aw17b 的 `refs` subTest 咬得住,由 r4 GLM 与 Kimi **各自手工删掉预扫②分支实测红**
  (日志 `/root/aiwork/logs/panel-opendesign-atomic-archive-write-review-r4-20260915-163425.subglm.log` / `.subkimi.log`)。
  不在本单补:改 `tests/` 会让 r4 的交付绑定作废,再审一轮换的只是一张红检收据。
- **目录只读(r3 MiMo #1)**、**坏编码参考图索引(修前就在)**、**relpath 跨盘**、**重试中途被杀留隐藏 .tmp**、**workspace.json 写口的只读残骸**:
  记账不修,理由见上。
- **Windows 上 ACL 拒写但属性不只读**:只读判法判不出,会走到替换那步失败(临时文件可写、能删,只多空转约 2 秒)。
- **Windows 上"读者长期开着档案 > 2 秒"写入失败**(aw12b):设计风险 1,拿"偶尔保存失败、可重试"换"永不半截";
  真机清单要问业主档案有没有放在同步盘里。
