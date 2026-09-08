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
runlog: judging-r3-selfreview-red rc=1 commit=97d6c2c dirty=yes at=2026-09-07T14:53:59Z file=tracks/opendesign-in-app-update/evidence/20260907T145359Z-01-judging-r3-selfreview-red.txt
runlog: r3-fixes-green rc=0 commit=38b0295 dirty=yes at=2026-09-07T15:01:29Z file=tracks/opendesign-in-app-update/evidence/20260907T150129Z-01-r3-fixes-green.txt
runlog: redcheck-r3-13-and-4 rc=0 commit=38b0295 dirty=yes at=2026-09-07T15:01:38Z file=tracks/opendesign-in-app-update/evidence/20260907T150138Z-01-redcheck-r3-13-and-4.txt
runlog: r3-panel-fixes-green rc=0 commit=71ccf25 dirty=yes at=2026-09-07T15:23:16Z file=tracks/opendesign-in-app-update/evidence/20260907T152316Z-01-r3-panel-fixes-green.txt
runlog: redcheck-r3-panel-24-15-6-5 rc=0 commit=71ccf25 dirty=yes at=2026-09-07T15:23:28Z file=tracks/opendesign-in-app-update/evidence/20260907T152328Z-01-redcheck-r3-panel-24-15-6-5.txt
runlog: final-run-all-with-gateway rc=1 commit=76fa4de dirty=no final=yes at=2026-09-08T00:56:38Z file=tracks/opendesign-in-app-update/evidence/20260908T005638Z-01-final-run-all-with-gateway.txt
runlog: final-run-all-with-gateway-v2 rc=0 commit=7793a95 dirty=no final=yes at=2026-09-08T01:12:08Z file=tracks/opendesign-in-app-update/evidence/20260908T011208Z-01-final-run-all-with-gateway-v2.txt
runlog: build-installer-0984 rc=1 commit=583767f dirty=no at=2026-09-08T02:16:43Z file=tracks/opendesign-in-app-update/evidence/20260908T021643Z-01-build-installer-0984.txt
runlog: build-payload-verify-fixed rc=0 commit=583767f dirty=yes at=2026-09-08T02:19:18Z file=tracks/opendesign-in-app-update/evidence/20260908T021918Z-01-build-payload-verify-fixed.txt
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

🔴 **收据区在断线之后整段没跟上,2026-09-08 接手时补的。** 从
`judging-r3-selfreview-red` 往下那 9 行,当时**全都只躺在 `evidence/` 里,正文一行没粘**
—— 包括**两份最终 `--with-gateway` 总跑**。归档闸取的是收据区的最后一份,这个洞会让它
读到一份 09-07 22:29 的旧收据当"最终"。(本项目栽过的同一种:**过期的绿不只是数字过期,
是收据区整段缺**。)

**新补的这 9 行里有两组必须单独说清:**

- **`final-run-all-with-gateway` rc=1(00:56:38Z)不是回归。** 那一遍红在
  `project-thread.e2e.mjs`,查下来是它的夹具(ds_root 里那两个项目文件)从来没进过仓
  —— `.gitignore:23` 把整个 `projects/` 排掉了。**本单一行都没碰项目/聊天那条链**;
  把夹具摆回去单独重跑那一条 ⇒ 7 步 ALL PASS。红收据原样留证:**它是发现这个洞的唯一
  入口**。机制与正解写进 `tests/e2e/README.md` 第 3b 步 + 后续单 backlog B。
  重跑的是 `-v2`(01:12:08Z):**6 段全绿、e2e 0 SKIP**,跑在 `7793a95` 且
  `source-stable: yes`。

- 🔴 **`build-installer-0984` rc=1(02:16:43Z)是我自己的探针坏了,不是包坏了。**
  我在构建收据里加了一条"前端 dist 打进包了没有"的自检,写成
  `grep -ho update/check …js | wc -l` ⇒ **grep 认定那个 bundle 是二进制文件,匹配走了
  stderr、正文一个字没出 ⇒ 数出 0 ⇒ 判"前端没打进去"**。实际它是命中的。
  **误报和假绿一样坏**,所以这份 rc=1 **不删也不改数字**;修的是探针(`grep -hoa`),
  重跑在 `build-payload-verify-fixed`(02:19:18Z),那份收据里**先把这个误报当场量了
  一遍**(无 `-a` 数出 0 / 带 `-a` 数出 2)再往下走。

**打包结论(机器写的,见 `build-payload-verify-fixed`)**:
`OpenDesign-Setup-0.98.4.exe`,45,852,528 字节,
sha256 `0a5f914acef07d8dcb76c9eb5c1a70b4c611468c26970cf82ee1b512ecd0ae05`。
包结构闸 0 条不合格 / 静态闸 23 条 / 成品闸 7 条,全过。
另外问了四件**闸问不出**的(闸只比"exe == payload",不问 payload 里该有什么):
① `ds_update.py` 在包里 ② 包里 `VERSION = "0.98.4"` ③ 前端 bundle 里有 `update/check`
与「检查更新」 ④ 包里的 dist 与仓里的 dist 逐文件一致。

⚠️ **同一份源码两次构建的 sha256 不一样**(第一次 `afc8061d…`,runlog 那次 `0a5f914a…`)
—— NSIS 把构建时刻编进了产物,**这个安装器不是逐字节可复现的**。所以"要发出去的"只能指
**盘上现在这一个**;发布之后要照 0.98.3 的做法跑一次 `release-asset-roundtrip`
(把资产下回来和本地这份逐字节比)才算闭环。

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

- 腿的花名册(第三、四轮,**原样粘的,没手写**):

  第三轮 `panel-inappupdate-r3-20260907T150454Z`(审第一、二轮的修法,冻结在 `71ccf25`):
  ```
  # impact-risk=high requested-budget=2 selected-count=1
  # snapshot=head:71ccf25
  submimo=SKIP(health:cooldown:INCOMPLETE) subdeepseek=PASS(verdict=PASS) subglm=SKIP(health:cooldown:FAIL) subkimi=SKIP(health:cooldown:FAIL) subgemini=SKIP(health:dead:FAIL:6)
  ```
  第四轮 `panel-inappupdate-r4-20260907T152737Z`(审第三轮那三条修法,冻结在 `2302e8f`):
  ```
  # impact-risk=high requested-budget=3 selected-count=3
  # snapshot=head:2302e8f
  submimo=PASS(verdict=PASS) subdeepseek=PASS(verdict=PASS) subglm=SKIP(health:cooldown:FAIL) subkimi=PASS(verdict=PASS) subgemini=SKIP(health:dead:FAIL:6)
  ```

- **第三轮 findings(subdeepseek,当轮唯一派得出的腿,PASS,给了 6 条)** —— 逐条复现,
  3 修 3 核过不改。修法与理由在 `2302e8f` 的 commit 消息里写全了,这里落工件的账
  (第四轮 subdeepseek 的 [Info] 就是指这一格当时是空的):
  - 🔴 **F1 `notesSummary` 只认 ATX 标题**:setext 写法(下一行整行 `===`)的标题被当正文
    印给业主;正文以 `---` 开头时界面直接印一串横杠,还把"去发布页 ›"那句兜底顶掉。
    两条我都用它给的 probe 原样复现。⇒ 修,判据 u21/u22 + 变异 v15/v16。
  - **F6 `?force=false` 会强制刷新**(原判据是"非空且非 0")。无危害,但一个反着读的参数
    迟早骗到下一个人。⇒ 改成只认明确的开(`1/true/yes/on`),判据 t9e + 变异 w5。
  - 🔴 **F4 那条 catch 修法此前没有任何判据守着**(第二轮 F-A 的修法本身):改回 idle,
    54 条判据 + 17 条变异全绿,而业主点了「检查更新」看见的和没点一模一样。
    ⇒ 新增 e2e 第 E 格(`route.abort()` ⇒ fetch reject ⇒ 真走 catch)+ 变异 e5。
  - 它还指出我那条新 e2e 的等待是假的(等"检查中"消失,而设置弹层默认收起、那三个字
    压根不在 DOM ⇒ 该等待立即通过、断言抢在 fetch 前面)。⇒ 改成等 Node 侧的事实 + 轮询。
  - F2(强查失败抹掉旧蓝点)/ F3(自动检查只在挂载跑一次)/ F5:核过不改,见偏差栏。

## 第四轮:三个家族第一次同时到齐(这一轮把预算真正补上了)

第三轮只派得出 subdeepseek 一条(其余四条腿全在冷却/dead),**"两轮各 1 条"仍然不等于 2**,
所以第三轮结束后立刻又派了第四轮。它是本单第一次、也是唯一一次**同一个 run、同一个
subject digest 下三个不同模型家族全部完整交卷**:

```
run_id=20260907-232737-3111896-panel-review   subject digest=sha256:f727b7bb12a1270…
submimo(xiaomi) PASS / subdeepseek(deepseek) PASS / subkimi(moonshot) PASS
三条都 degraded=false、failure_kind=none、evidence completeness=complete
```
(以上逐字段来自机器写的 `observations/20260907T154534Z-panel-review-execution_finished-001.json`,
不是我的转述。)⇒ `impact.level=high` 要求的「同一次成功 panel、2 个 coverage-eligible
的不同家族」在这一轮**是 3 条,超额满足**;而它冻结的 `2302e8f` 就是此刻树上的 HEAD ——
**这一次不存在 D13 那个"放行依据是一棵早就不存在的树"的形状**(merge-base 不用算:
subject 的 `worktree_tree_oid` 与 `index_tree_oid` 相同,且等于当前 HEAD 的树)。

### 三腿一致 PASS,给了 4 条 LOW —— 我全部亲手复现过

前三条是**同一个根**:`notesSummary` 是逐行判断,**跳过 setext 标题时没有把它下面那行
下划线一起吃掉**,也没区分"这一行能不能合法地当 setext 的正文"。我的探针输出(现跑现贴):

```
L1 短下划线(==)          => "=="   ← 本单要治的"印一串记号"的迷你版
L1 短下划线(--)          => "--"
L1 长下划线(====)        => "正文内容"   ← ≥3 个字符时 HORIZONTAL_RULE 兜住了,只漏 1~2 个字符的
L2 多行 setext         => "很长很长的"   ← 多行标题只跳最后一行,前半截照印
L3 列表项+hr            => "- 另一个改动"   ← 第一条要点被当成标题吃掉(GitHub 会渲染成正文)
L3 引用+hr             => "正文"
对照 正文\n\n---         => "一段正文"   ← 真空行隔开的分隔线,正文保留(没有回归)
对照 ATX               => "- 修复白屏"
```
(subdeepseek 与 subkimi **各自独立**命中 L1 与 L3,submimo 把 L1 判成"不会发生"。
两腿独立命中同一处,通常是真的 —— 我的探针证实了这一点。)

第 4 条是记账:**资产名漂移仍然只有注释级契约**(`bin/ds_update.py:35` 的 `ASSET_RE`
与 `installer/build-installer.sh:146` 的产物名之间没有机械绑定)。

### 我自己去核的两件(腿提了问题,答案得我给)

1. **submimo 问:那条红字警告守的是不是真门?** —— "如果打包可以绕过 `build-installer.sh`
   (比如 CI 直接调 NSIS),那这个防御就是纸糊的。"这正是 `guards-must-watch-the-right-door`
   那条记忆的形状,**所以我去查了而不是回答"应该没问题"**:
   `grep -ln 'makensis\|build-installer' .github/workflows/*.yml` **一个都没有** ——
   三个 workflow(gui-probe / nonempty-probe / package-probe)全是**消费**已发布资产的探针,
   仓里没有任何 CI 打包路径。⇒ `installer/build-installer.sh` 是唯一的产物出口,
   警告贴在定义名字的那个文件顶上,门是对的。**(它挡不住的是"在 GitHub 网页上手改资产名",
   那一幕没有任何机械防线 —— 如实记在偏差栏。)**
2. **subkimi 的一条更尖锐的观察,我核了属实**:通知路径其实**不需要**硬依赖资产名 ——
   界面下载行只用 `release_url`(`web/src/workspace/Sidebar.tsx:377`),`asset` 字段在本单
   范围内**没有任何消费方**(只在 `update.ts:13` 的类型里,给第二刀"装"预留)。
   ⇒ 放宽 `pick_latest` 能让这一整类"安静地错"消失。**但我不改**:t1c 那条
   "没有安装包的 release 不是可更新到的版本"是有理由的(选中它 = 把业主指向一个下不动的
   东西),放宽等于用一种坏结局换另一种。⇒ 记进后续单,连同"给 `EXE=` 那行加一条机械断言"。

### 这 4 条我为什么**不在本单改**(这是个判断,不是省事)

- 都是 LOW,且**在真实语料上一次都不发生**:仓里录着 20 条真实 release 正文
  (`tests/fixtures/update/github-releases-20260907.json`),subdeepseek 拿新旧两版实现
  逐条对过输出**完全一致**;更关键的是,这些正文是**我自己在发版时写的**,
  不是外部输入 —— 触发它要我自己去写 `标题\n==` 或"列表项紧贴 `---`"。
- 失败形态是**难看**(界面上多印两个字符 / 摘要挑了下一行),不是**安静地错**。
  本单真正在治的那一类("说了但业主看不见/看错版本")没有一条落在这里。
- 🔴 **代价那一侧是实的**:此刻树上这棵正是三个家族刚刚全部审过的那一棵。为了一条
  1~2 个字符的下划线去动 `notesSummary`,**发出去的就是一棵没有任何外部腿看过的树** ——
  而 09-02 那一单的账刚记完:"改正"这个动作本身在生产新的审查面,那一单为此白跑四轮。
  停止条件是**代码有问题才重审**;这四条够不上。
- ⇒ 原样搬进后续单 `opendesign-in-app-update-install` 的 backlog(第二刀本来就要动这块)。

- arbitrated verdict (主裁): **PASS**(代码面;**欠业主真机一趟**,清单见
  `真机清单-0.98.4.md`)

  裁决是 2026-09-08 断线之后**重新接手时现做的**,不是把断线前那半句补完 ——
  所以下面写的是**这一遍我自己看到了什么**,不是转述前面四轮的结论。

  **① 我自己把交付面从头读了一遍**(不是只信腿的 PASS,panel 永远不能替代第一遍):
  `bin/ds_update.py` 全文、`ds_web.py` 的 `_update_check`、`web/src/update.ts` 全文、
  `App.tsx` / `Sidebar.tsx` 的 diff。方向上最要紧的那两条我逐行确认成立 ——
  **查不动绝不说「已是最新」**(`updateLabel` 先问 error 再问 update_available,
  次序是对的)、**失败不许甩栈给业主**(端点一律 200+error,`check_for_update`
  三处兜底)。读的过程里我独立起疑的一条是「`target="_blank"` 在 pywebview 外壳里
  到底开不开浏览器」—— 翻工件才看到 S6 早就把它记下了,而且记的是"这条我不猜"。
  **独立起疑撞上已记在案的疑虑,是这份工件可信的正面证据**,我把它记在这儿。

  **② 我找到并补上了一个真缺口**:verify.md 第 102 行写着「⇒ 真机清单一条」,
  而**这个 track 从头到尾没有真机清单文件**(别的 track 都有)。
  写在散文里的承诺没有工件兜着,下一个人(包括几天后的我)就找不到它。
  ⇒ 已补 `真机清单-0.98.4.md`,并在里面写清了 C 节那条**这一趟根本验不了**的路。

  **③ 最终收据是有效的,我查的是时间戳不是红绿**:
  `20260908T011208Z-…-v2.txt` 跑在 `7793a95`(当时的 HEAD),
  `source-view-before == source-view-after`、`source-stable: yes`
  ⇒ 既不是"跑在最后一次编辑之前"的过期绿,也没有人在那 11 分钟里写过仓库。
  6 段全绿,e2e **0 SKIP**(那两条要活网关的第一次真跑了)。

  **④ 预算是真的满足了,而且冻结的那棵树到现在没走形**(D13 那个形状):
  第四轮 `panel-inappupdate-r4` 一次 run、同一 subject digest 下
  submimo(xiaomi)/ subdeepseek(deepseek)/ subkimi(moonshot) 三个家族全部
  完整交卷、全 PASS,`impact.level=high` 要的是 2,这里是 3。
  它冻结在 `2302e8f`;此刻 HEAD 与它相比,**生产代码一行没动** ——
  `git diff 2302e8f..HEAD -- . ':(exclude)tracks/'` 只有
  `tests/e2e/README.md` 的 +21 行注释(讲那条 e2e 缺夹具的机制)。
  ⇒ 腿审过的那棵树,就是要发出去的这棵。

  **⑤ 我判 PASS 的边界(说清楚它不覆盖什么)**:
  - 覆盖的是**代码面**:挑版本、比版本、失败措辞、缓存方向、端点契约、界面接线。
  - **不覆盖**"业主看不看得见/看不看得懂"这一类 —— 本项目栽过一模一样的
    (0.91:12 条判据全绿,窗口栏整块没画出来)。这类只有真机和他本人能答。
  - **不覆盖**"有新版"那整条路(S6 + 蓝点 + 下载链接):
    装上 0.98.4 时线上最新就是 0.98.4,软件只会说"已是最新",
    **那条路要等下一版发出去才第一次走得到**。这不是我偷懒不验,是结构上此刻验不了；
    已写死进真机清单 C 节和后续单,不靠我记得。
  - 第四轮那 4 条 LOW 接受不改,理由在上一格,不重复。

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
- **第四轮那 4 条 LOW,接受不改、原样搬进后续单**(理由写在上面「这 4 条我为什么不在本单改」
  一格:真实语料上零发生、失败形态是难看不是安静地错、而改它就等于发一棵没有外部腿看过的树)。
- **资产名如果是在 GitHub 网页上手改的,没有任何机械防线拦得住**(`installer/build-installer.sh`
  是仓里唯一的产物出口,这一点我查过;但它管不到"包已经传上去之后有人改了名字")。
  后果是那一版在业主的检查更新里被静默跳过。⇒ 记进后续单,本单接受。
- **`now=time.time` 是 def 时刻早绑定**,与 `fetch` 的延迟绑定风格不一致(submimo 补充②)。
  核过:`now` 只在判据里注入,生产路径恒为 `time.time`,不构成错误。不改。
