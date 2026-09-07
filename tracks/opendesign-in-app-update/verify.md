# Verify: opendesign-in-app-update

- Date: 2026-09-07

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录
> `decision.json`；这里保留检查、理由、发现与主 Agent 仲裁说明，不复制枚举。

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再按 impact-risk 预算跑 panel-review；只有特殊控制面
> 才显式 `--all` 做全池评审。最后仍由主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [x] build passes —— 总跑「dist 新鲜度 + 类型检查」段绿(现场 build 出来的产物与
      `web/dist` 逐字节一致,顺带 `tsc`)
- [x] tests pass —— **0 红,但 3 条没跑**(总跑 rc=3)。**这不叫"全绿"**,那 3 条的身份见下。
- [x] no secrets / unsafe ops —— 本单新增的唯一外呼是**匿名 GET api.github.com**:
      不带凭证、不写盘、失败只影响界面上那一行提示;新写口 `GET /api/update/check` 只读。

**机器打印的**(不是我的转述)—— 判据一律用 `runlog` 跑,下面每一行都是它写的:

```
runlog: judging-first-red rc=1 commit=6933060 dirty=yes at=2026-09-07T13:05:14Z file=tracks/opendesign-in-app-update/evidence/20260907T130514Z-01-judging-first-red.txt
runlog: t1t7-green rc=0 commit=c1bdf4e dirty=yes at=2026-09-07T13:08:51Z file=tracks/opendesign-in-app-update/evidence/20260907T130851Z-01-t1t7-green.txt
runlog: redcheck-12bites rc=0 commit=c1bdf4e dirty=yes at=2026-09-07T13:08:52Z file=tracks/opendesign-in-app-update/evidence/20260907T130852Z-01-redcheck-12bites.txt
runlog: judging-cache-5red rc=1 commit=8c74486 dirty=yes at=2026-09-07T13:10:35Z file=tracks/opendesign-in-app-update/evidence/20260907T131035Z-01-judging-cache-5red.txt
runlog: t1t8-green rc=0 commit=1e69d2e dirty=yes at=2026-09-07T13:12:03Z file=tracks/opendesign-in-app-update/evidence/20260907T131203Z-01-t1t8-green.txt
runlog: redcheck-17bites rc=0 commit=1e69d2e dirty=yes at=2026-09-07T13:12:03Z file=tracks/opendesign-in-app-update/evidence/20260907T131203Z-02-redcheck-17bites.txt
runlog: judging-endpoint-4red rc=1 commit=afaf346 dirty=yes at=2026-09-07T13:13:35Z file=tracks/opendesign-in-app-update/evidence/20260907T131335Z-01-judging-endpoint-4red.txt
runlog: endpoint-green rc=0 commit=b8597f3 dirty=yes at=2026-09-07T13:15:18Z file=tracks/opendesign-in-app-update/evidence/20260907T131518Z-01-endpoint-green.txt
runlog: redcheck-endpoint-5bites rc=0 commit=b8597f3 dirty=yes at=2026-09-07T13:15:21Z file=tracks/opendesign-in-app-update/evidence/20260907T131521Z-01-redcheck-endpoint-5bites.txt
runlog: judging-ui-red rc=1 commit=02a5098 dirty=yes at=2026-09-07T13:16:58Z file=tracks/opendesign-in-app-update/evidence/20260907T131658Z-01-judging-ui-red.txt
runlog: node-all-green rc=0 commit=df6b3f3 dirty=yes at=2026-09-07T13:19:17Z file=tracks/opendesign-in-app-update/evidence/20260907T131917Z-01-node-all-green.txt
runlog: final-run-all rc=1 commit=efe8dbb dirty=no final=yes at=2026-09-07T13:21:14Z file=tracks/opendesign-in-app-update/evidence/20260907T132114Z-01-final-run-all.txt
runlog: judging-selfreview-red rc=1 commit=efe8dbb dirty=yes at=2026-09-07T13:34:18Z file=tracks/opendesign-in-app-update/evidence/20260907T133418Z-01-judging-selfreview-red.txt
runlog: selfreview-fixes-green rc=0 commit=b006676 dirty=yes at=2026-09-07T13:38:34Z file=tracks/opendesign-in-app-update/evidence/20260907T133834Z-01-selfreview-fixes-green.txt
runlog: redcheck-20-and-7 rc=0 commit=b006676 dirty=yes at=2026-09-07T13:38:37Z file=tracks/opendesign-in-app-update/evidence/20260907T133837Z-01-redcheck-20-and-7.txt
runlog: judging-panel-f1f2f3f5-red rc=1 commit=55e5dba dirty=yes at=2026-09-07T13:53:31Z file=tracks/opendesign-in-app-update/evidence/20260907T135331Z-01-judging-panel-f1f2f3f5-red.txt
runlog: panel-fixes-green rc=0 commit=752ac1d dirty=yes at=2026-09-07T13:56:14Z file=tracks/opendesign-in-app-update/evidence/20260907T135614Z-01-panel-fixes-green.txt
runlog: judging-r2-findings-red rc=1 commit=1431900 dirty=yes at=2026-09-07T14:07:24Z file=tracks/opendesign-in-app-update/evidence/20260907T140724Z-01-judging-r2-findings-red.txt
runlog: r2-fixes-green rc=0 commit=8f91e57 dirty=yes at=2026-09-07T14:09:44Z file=tracks/opendesign-in-app-update/evidence/20260907T140944Z-01-r2-fixes-green.txt
runlog: final-run-all rc=143 commit=14f1791 dirty=no final=yes at=2026-09-07T14:11:59Z file=tracks/opendesign-in-app-update/evidence/20260907T141159Z-01-final-run-all.txt
runlog: final-run-all rc=3 commit=14f1791 dirty=yes final=yes at=2026-09-07T14:29:03Z file=tracks/opendesign-in-app-update/evidence/20260907T142903Z-01-final-run-all.txt
```

上面这堆数字不会自己解释自己,三件事说清楚:

- 🔴 **`rc=143` 那一份是断线砍出来的半截,作废。** 22:11:59 起跑的最终总跑在第 83 秒
  被会话的 SIGTERM 打死 —— 收据的输出区一片空白,一段都没跑完。文件已改名成
  `20260907T141159Z-01-final-run-all-VOID-断线砍半.txt`:**不删**(半截收据是线索不是
  垃圾,08-19 就是从这种半截里查出两个真 bug),但它不能给任何结论当依据。
  重跑的是 `14:29:03Z` 那一份。
- **中途那份 `rc=1`(13:21:14Z)红在哪:不是产品代码,是死断言闸咬到我自己新写的判据。**
  `tests/test_ds_update.py` 有 2 条断言和它的守卫写在同一行,行粒度问不出"它跑过没有"
  ⇒ 那道闸对这 2 条是瞎的。已拆成两行,现在这一段绿。
- **最后那份 `rc=3` 是什么意思**:总跑自己的口径是「0 = 全跑且全绿 / 1 = 有红 /
  **3 = 没红,但有没跑的,不算通过**」。这一遍 **0 红**;没跑的 3 条**全是同一个原因 ——
  要一台活着的 gateway**:`new_chat.e2e.mjs`、`project-thread.e2e.mjs`,以及
  `tests/test_ws_protocol_smoke.py`(整类 SKIP,连带 16 条断言没被问到)。
  三条都长在聊天 / WebSocket 通道上,**本单一行都没碰那条通道**。
  ⇒ 收口那一遍会照 `tests/e2e/README.md` 起 gateway,跑 `--with-gateway` 把这 3 条也
  真跑一次,再宣布做完。

## Review

## 规格自查(读任何 panel 输出之前落盘)

**如果规格本身就是错的,会错成什么样?**
本单的规格是"让软件自己发现新版并说一句"。它最可能错在**说得不对**而不是**查得不对**:
查错了(挑错版本)判据咬得住;而"说了但业主没看懂/没看见"那一类,
18+4+7 条判据一条都问不出来 —— 那要靠真机截图和他本人。

### 我自己审出来的(共 6 条)

S1 🔴 **两段式版本号会被静默跳过。** `parse_version` 的正则要求**三段**
   (`(\d+)\.(\d+)\.(\d+)`)。业主哪天宣布 1.0,若 tag 打成 `win-installer-1.0`
   (两段),`release_version` 返回 None ⇒ 那一版**在更新检查里根本不存在**,
   而且一声不吭。这正是本单开头那个 404 坑的同一种病,出现在我自己写的代码里。
   更难看的是 `releasePageUrl` 的正则是 `^\d+(\.\d+)*$` —— **它收两段,而解析器不收**,
   两处对同一件事口径不一致。⇒ 要修,并加判据。

S2 **资产名字必须严格等于 `OpenDesign-Setup-<版本>.exe`。** 哪天打包脚本改了命名
   (加个后缀、换个大小写),更新检查会安静地看不见新版。
   ⇒ 本单不改(严格是对的),但要在 `installer/build-installer.sh` 旁边留一句话,
   说明这个名字现在**被更新检查依赖**。

S3 **每次打开软件都会往 api.github.com 发一次请求,而且关不掉。**
   在这一单之前,这个软件唯一往外连的地方是业主自己配了 key 的大模型接口。
   现在多了一个**无条件的**外部目的地。功能上没问题(缓存 6 小时),
   但"业主的机器,业主做主" ⇒ 应该给一个开关(仓里已有 `boolPrefs.ts` 这套东西)。
   ⇒ 我判:这一单补上,不留到以后。

S4 `notes`(更新说明)后端取了、类型里带了、**界面上没显示**。
   proposal 里写的是"发现有新版就说一句:有新版 X,更新说明:…"。
   ⇒ 要么显示,要么把 proposal 那句改掉。**不许留着"取了不用"的字段假装做了。**

S5 `force=1` 完全绕开缓存,业主连点十下就是十次真请求(未登录 GitHub 每小时 60 次)。
   ⇒ 轻微。加一个"最短间隔"就够,但要小心别把 u4 那条"点了要有反应"弄没了。

S6 发布页链接用 `<a target="_blank">`,**在 pywebview 外壳里点了会不会真开浏览器,本机验不了**。
   ⇒ 真机清单一条。这条我不猜,也不写成"应该没问题"。

### 这份判据接不住什么(写在前面,不等腿来说)

- 界面上那一行**长什么样、看不看得见**:判据只问措辞文本,不问它有没有被画出来、
  会不会被别的元素挡住。本项目栽过一模一样的(0.91 窗口栏整块没画出来,12 条判据全绿)。
- pywebview 外壳里的行为(外链、弹窗)。
- 业主点了之后**心里怎么想**:"有新版 0.99.0 ›" 这句话对他是不是够用,只有他能说。

- 腿的花名册(两轮,**原样粘的,没手写**):

  第一轮 `panel-inappupdate-20260907T134023Z`(审第一刀全部):
  ```
  submimo=SKIP(health:cooldown:INCOMPLETE) subdeepseek=PASS(verdict=PASS) subglm=FAIL(rc=1,降级:回落聊天腿也没成) subkimi=SKIP(health:cooldown:FAIL) subgemini=SKIP(health:dead:FAIL:6)
  ```
  第二轮 `panel-inappupdate-r2-20260907T135734Z`(审第一轮发现的改法):
  ```
  submimo=PASS(verdict=UNKNOWN) subdeepseek=PASS(verdict=PASS) subglm=SKIP(health:cooldown:FAIL) subkimi=SKIP(health:cooldown:FAIL) subgemini=SKIP(health:dead:FAIL:6)
  ```
  > panel-review 收尾自己写这个文件(off / FAIL(rc) / 降级 都在里面)。
  > **控制器没活到收尾时它压根不存在** —— 那时跑 `panel-roster <日志前缀>` 从盘上重建,
  > 与控制器自己写的**归一化后一致**(判据 R5b 守着;抬头有渲染时间戳,不是字面逐字节)。**一轮零记录的评审也粘得出这一行**,
  > 所以"那轮被砍了所以没有花名册"不再是理由(2026-08-23,track panel-roster-from-disk)。
  > 08-06 立这条的理由:08-05 我在这里手写了"三条腿一致 PASS",而 Kimi 根本没出结论
  > (同一页第 90 行我自己还写着它没出报告)—— 手抄一份终端上的东西,抄错那次没人会发现。
- findings:
  **第一轮(subdeepseek,PASS,5 条)** —— 我逐条核过,4 修 1 接受:
  - 🔴 **F1 我自己造的**:修 S1 时给版本号补零(`1.0`→`1.0.0`),界面拿它拼
    `…/tag/win-installer-1.0.0`,而真 tag 是 `win-installer-1.0` ⇒ **404**。
    我写探针复现确认(后端 `latest='1.0.0'`)。⇒ 地址改由 GitHub 的 `html_url` 给,前端只验。
    **而且我的 u8 测的是 `releasePageUrl("1.0")` —— 运行时永远不会传两段进去,判据在测一条走不到的路。**
  - 🔴 **F2 规格没兑现**:那句"有新版"只活在**默认收起**的设置弹层里 ⇒ 记号挂到收起来的那一行上。
  - F3 `done`+空结果长得像"还没查过" ⇒ 改说"查不到更新"。
  - F5 t1b 那道 AST 闸只咬"一整条字符串含 releases/latest" ⇒ 抽 `releases_url()` 逐字节断言。
  - F4 冷缓存并发 N 请求→N 次真取 ⇒ **接受不改**(见下面偏差栏)。

  **第二轮(subdeepseek PASS 6 条 / submimo 裁决行没匹配=UNKNOWN 但给了实质复核 3 条)**
  —— 全部核过并修掉:
  - 🔴 **F-B**:`fetch_releases` 是全仓唯一真打网处,而所有判据都注入替身
    ⇒ 在那儿内联拼 `"/releases" + "/latest"` 能绕过全部三道防线,**F5 的洞在下一层还开着**。
    ⇒ t12(不打网,只看它把什么地址交给 urlopen)+ m22 原样重现那条绕闸路。
    ⚠️ **t12 写出来就是绿的** —— 它是回归绊线不是红检,值不值钱靠 m22 证明。
  - F-A 手动点击而 ds_web 不可达时回到 idle ⇒ 点了和没点一样。
  - F-C 仓库改名 ⇒ 前缀闸拦下 html_url ⇒ 下载行静默消失而蓝点还亮 ⇒ 退回发布页常量。
  - F-D `update_available=true` + `latest=null` ⇒ 渲染成"已是最新"(和蓝点同屏矛盾)。
  - 🔴 **F-E 我自审 S2 说过要在打包脚本旁留一句话,话我没留** ⇒ 现在留了。
  - F-F accepted deviation 只在 commit 消息里、verify 偏差栏还是空模板 ⇒ 本次补上。
  - submimo 补充①:"跳过标题"按开头几个词判会误杀正文 ⇒ 改成按 markdown 标题记号判。
    (submimo 另两条 —— `now=time.time` 早绑定风格不一致、force 无节流 —— 核过,不构成错误,不改。)

  **红检漏网照出我自己一个真 bug**:v6 漏网 ⇒ 查出"剥掉 `#`"那行在加了 isHeading 之后
  成了半死代码,而它还把 `#123`(issue 编号)剥成 `123`。已删并加 u18。
  ⇒ **变异漏网不总是判据的错,有时是被测对象里那一行本来就不该在。**

## 第三轮:原来写的是"不跑",断线之后我改了主意

上一版这里的标题是「停止条件(为什么不跑第三轮)」,理由是发现的边际收益已经很低:

- 两轮共 14 条发现,我全部复现过:11 修 / 2 核过不改 / 1 是流程账(F-F,本次补)。
- 第二轮之后的每一处改动**各自有一条变异钉着**(m22 / v11 / v12 / v13 / v6 重定靶 / u18)。
- 剩下的都是"开后续单"类,不是本单代码的问题。
- **"改正"这个动作本身在生产新审查面**(09-02 那一单为此白跑四轮)。

**这些理由现在仍然成立,但它们答的不是全部的题。** 断线之后我去核机器写的记录
(`observations/*-panel-review-*.json`,不是我的回忆),翻出两件上面四条管不着的事:

1. **家族覆盖不够,归档闸会拦。** 本单 `impact.level=high` ⇒ 归档要求
   **同一次成功 panel、同一 subject digest 下,有 2 个 coverage-eligible 的不同模型家族腿**。
   实际是:第一轮只有 subdeepseek 一条(subglm 起来 1.5 秒就 rc=1 挂了),
   第二轮**还是**只有 subdeepseek 一条(submimo 认真复核并给了 3 条实质意见,
   但结论行没匹配上 ⇒ 机器记 `UNKNOWN`,而按规矩 **UNKNOWN 不补预算、跨轮也不许拼**)。
   **两轮各 1,不等于 2。**
2. **第二轮之后的那棵树,没有任何外部腿看过。** r2 的 subject 冻结在 `1431900`,
   而那之后我又改了 6 处(`8f91e57` + `70ebb75`)—— 正是上面第 4 条说的
   "改正动作自己生产的新审查面",而这一次它落在**没人复核过的**位置上。

所以第三轮不是"再挑一轮毛病",是补这两件;它要攻的是**修法**,不是重审原始功能。

- ⚠️ **反锚定这一轮是打折的,如实记账。** 两轮的发现在断线前已经写进这份 verify.md
  并提交(`14f1791`),而底座腿自己读仓库 —— **文件在树上就够得着**,`git log -p` 里
  也躺着。panel skill 讲得很清楚:真干净只有一条路,让 verify.md 在派发那一刻还没被写;
  这一单已经做不到了(我也不打算为了好看去回退一份已经提交的工件)。
  ⇒ **第三轮腿给的 PASS,分量比前两轮轻;它给的 BLOCK 分量不变** ——
  锚定只会让它更容易附和我,不会让它更容易反对我。

  > 只写发现。腿的身份/降级不在这儿抄第二遍:日志自带身份牌(降级横幅 + 视野边界),
  > 花名册在上一格,查工件不查自述。

- arbitrated verdict (主裁): <...>
  > 这里写理由；最终枚举写进 `decision.json.outcome.verdict`。归档时仍为空会被
  > `track-record validate --phase archive` 挡住，`track list` 也会打 ⚠️。

## Accepted deviations

- **F4 冷缓存并发:N 个同时进来的请求 → N 次真取**(无 single-flight)。
  接受不改。理由:改的代价是把 10 秒的网络调用挪进锁里(ThreadingHTTPServer 下会卡住
  整个线程池),或引入单飞锁/超时的复杂度;不改的代价是冷启动时多打 2~3 次
  GitHub API(未登录限额 60 次/小时),且失败形态是**诚实的**(403 ⇒ error 字段 ⇒
  界面显示"查不到更新"),不是安静地错。业主是单窗口使用。
  **影响范围**:仅限缓存冷的那一瞬;两条评审腿独立认为这个取舍站得住。
  (F-F 指出这条原来只写在 commit 消息里、工件里是空模板 —— 现在补在这儿。)
- **force 无节流**(S5):业主连点十下就是十次真请求。同上,限额够用,
  且触发限流的后果可见(不是安静的)。不改。
- **`now=time.time` 是 def 时刻早绑定**,与 `fetch` 的延迟绑定风格不一致(submimo 补充②)。
  核过:`now` 只在判据里注入,生产路径恒为 `time.time`,不构成错误。不改。
