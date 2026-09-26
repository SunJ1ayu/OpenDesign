# Verify: opendesign-sidebar-history

- Date: 2026-09-25

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录
> `decision.json`；这里保留检查、理由、发现与主 Agent 仲裁说明，不复制枚举。

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再按 impact-risk 预算跑 panel-review；只有特殊控制面
> 才显式 `--all` 做全池评审。最后仍由主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- 09-26 Codex 接手核验:最终本地总跑 575 条 Node 通过、Python 1578 跑过 / 1 跳过、e2e 45 PASS / 0 FAIL / 2 SKIP;MCP、泄漏闸、类型检查与 dist 新鲜度通过。三条既有跳过保持单列,不计作通过。
- 沙箱内第一次尝试被 `unshare: Operation not permitted` 挡住,已中止(退出 130),未完成、无有效收据;清掉该次仅含头部的占位文件。下列 host 收据是在获准环境保留断网守卫重跑的最终结果,`source-stable: yes`。

```
runlog: takeover-final-host rc=3 commit=68540f0 dirty=yes final=yes at=2026-09-26T06:58:12Z file=tracks/opendesign-sidebar-history/evidence/20260926T065812Z-01-takeover-final-host.txt
```

- [x] build passes(`npm run build`,总跑「dist 新鲜度 + 类型检查」一段)
- [x] tests pass(最终总跑见下面最后一行;rc=3 = 只跳既有三条:两条要真网关的 e2e + python 1 条,同前几单)
- [x] no secrets / unsafe ops(新写口只写 `<数据根>/config/sidebar.json` 两个字段;新读口只读网关对话文件与回放记录)

**机器打印的**(按时间顺序,红的全在;判据先行的红检 / 两个推翻前提的探针 / 变异 / 总跑):

```
runlog: oracle-unit-red-on-old rc=1 commit=4a235db dirty=yes at=2026-09-25T10:48:40Z file=tracks/opendesign-sidebar-history/evidence/20260925T104840Z-01-oracle-unit-red-on-old.txt
runlog: oracle-api-red-on-old rc=1 commit=4a235db dirty=yes at=2026-09-25T10:48:40Z file=tracks/opendesign-sidebar-history/evidence/20260925T104840Z-02-oracle-api-red-on-old.txt
runlog: oracle-e2e-red-on-old rc=1 commit=4a235db dirty=yes at=2026-09-25T10:48:40Z file=tracks/opendesign-sidebar-history/evidence/20260925T104840Z-03-oracle-e2e-red-on-old.txt
runlog: probe-gateway-longline rc=0 commit=aff50ad dirty=yes at=2026-09-25T13:25:10Z file=tracks/opendesign-sidebar-history/evidence/20260925T132510Z-01-probe-gateway-longline.txt
runlog: oracle-api-v2-red-on-old rc=1 commit=aff50ad dirty=yes at=2026-09-25T13:25:47Z file=tracks/opendesign-sidebar-history/evidence/20260925T132547Z-01-oracle-api-v2-red-on-old.txt
runlog: oracle-api-v3-red-on-old rc=1 commit=3046f84 dirty=yes at=2026-09-25T13:28:31Z file=tracks/opendesign-sidebar-history/evidence/20260925T132831Z-01-oracle-api-v3-red-on-old.txt
runlog: oracle-e2e-v2-red-on-old rc=1 commit=febc747 dirty=yes at=2026-09-25T13:36:22Z file=tracks/opendesign-sidebar-history/evidence/20260925T133622Z-01-oracle-e2e-v2-red-on-old.txt
runlog: oracle-unit-v2-red-on-old rc=1 commit=9861f4b dirty=yes at=2026-09-25T13:40:34Z file=tracks/opendesign-sidebar-history/evidence/20260925T134034Z-01-oracle-unit-v2-red-on-old.txt
runlog: mutation-sidebar-history rc=1 commit=a99a012 dirty=yes at=2026-09-25T13:44:07Z file=tracks/opendesign-sidebar-history/evidence/20260925T134407Z-01-mutation-sidebar-history.txt
runlog: mutation-sidebar-history-e13-e14 rc=0 commit=a99a012 dirty=yes at=2026-09-25T13:52:25Z file=tracks/opendesign-sidebar-history/evidence/20260925T135225Z-01-mutation-sidebar-history-e13-e14.txt
runlog: oracle-e6b-blocked-delete-red rc=1 commit=a99a012 dirty=yes at=2026-09-25T13:53:22Z file=tracks/opendesign-sidebar-history/evidence/20260925T135322Z-01-oracle-e6b-blocked-delete-red.txt
runlog: mutation-sidebar-history-b7-after-fix rc=0 commit=b3e6762 dirty=yes at=2026-09-25T13:54:06Z file=tracks/opendesign-sidebar-history/evidence/20260925T135406Z-01-mutation-sidebar-history-b7-after-fix.txt
runlog: run-all-impl rc=1 commit=25b715d dirty=no at=2026-09-25T13:55:09Z file=tracks/opendesign-sidebar-history/evidence/20260925T135509Z-01-run-all-impl.txt
runlog: probe-real-sessions-time rc=0 commit=2654b1f dirty=yes at=2026-09-25T14:26:01Z file=tracks/opendesign-sidebar-history/evidence/20260925T142601Z-01-probe-real-sessions-time.txt
runlog: probe-idle-compact rc=0 commit=2654b1f dirty=yes at=2026-09-25T14:26:01Z file=tracks/opendesign-sidebar-history/evidence/20260925T142601Z-02-probe-idle-compact.txt
runlog: oracle-p1p6-api-red rc=5 commit=2654b1f dirty=yes at=2026-09-25T14:27:26Z file=tracks/opendesign-sidebar-history/evidence/20260925T142726Z-01-oracle-p1p6-api-red.txt
runlog: oracle-p6-unit-red rc=1 commit=2654b1f dirty=yes at=2026-09-25T14:27:27Z file=tracks/opendesign-sidebar-history/evidence/20260925T142727Z-01-oracle-p6-unit-red.txt
runlog: oracle-p1p6-api-red-2 rc=1 commit=2654b1f dirty=yes at=2026-09-25T14:27:39Z file=tracks/opendesign-sidebar-history/evidence/20260925T142739Z-01-oracle-p1p6-api-red-2.txt
runlog: oracle-p6-e2e-red rc=1 commit=2654b1f dirty=yes at=2026-09-25T14:27:55Z file=tracks/opendesign-sidebar-history/evidence/20260925T142755Z-01-oracle-p6-e2e-red.txt
runlog: mutation-p1p6 rc=0 commit=cfe0897 dirty=yes at=2026-09-25T14:30:43Z file=tracks/opendesign-sidebar-history/evidence/20260925T143043Z-01-mutation-p1p6.txt
runlog: oracle-r1fix-api-red rc=1 commit=315ea10 dirty=yes at=2026-09-25T15:12:09Z file=tracks/opendesign-sidebar-history/evidence/20260925T151209Z-01-oracle-r1fix-api-red.txt
runlog: oracle-r1fix-unit-red rc=1 commit=315ea10 dirty=yes at=2026-09-25T15:12:18Z file=tracks/opendesign-sidebar-history/evidence/20260925T151218Z-01-oracle-r1fix-unit-red.txt
runlog: oracle-r1fix-e2e-red rc=1 commit=315ea10 dirty=yes at=2026-09-25T15:12:27Z file=tracks/opendesign-sidebar-history/evidence/20260925T151227Z-01-oracle-r1fix-e2e-red.txt
runlog: mutation-r1fix rc=0 commit=1b3f2fb dirty=yes at=2026-09-25T15:14:19Z file=tracks/opendesign-sidebar-history/evidence/20260925T151419Z-01-mutation-r1fix.txt
runlog: run-all-r1fix rc=3 commit=bc84d28 dirty=no at=2026-09-25T15:29:12Z file=tracks/opendesign-sidebar-history/evidence/20260925T152912Z-01-run-all-r1fix.txt
runlog: oracle-r2fix-api-red rc=1 commit=bc84d28 dirty=yes at=2026-09-25T16:00:08Z file=tracks/opendesign-sidebar-history/evidence/20260925T160008Z-01-oracle-r2fix-api-red.txt
runlog: oracle-r2fix-unit-red rc=1 commit=bc84d28 dirty=yes at=2026-09-25T16:00:16Z file=tracks/opendesign-sidebar-history/evidence/20260925T160016Z-01-oracle-r2fix-unit-red.txt
runlog: mutation-r2fix rc=0 commit=c37ee08 dirty=yes at=2026-09-25T16:02:18Z file=tracks/opendesign-sidebar-history/evidence/20260925T160218Z-01-mutation-r2fix.txt
runlog: mutation-sidebar-history-final rc=0 commit=e417b03 dirty=yes at=2026-09-25T16:03:39Z file=tracks/opendesign-sidebar-history/evidence/20260925T160338Z-01-mutation-sidebar-history-final.txt
```

读法:
- `oracle-*-red*` = 判据先行,在改之前的代码上红;每组后面紧跟对应的实现提交(见 git log)。
- `probe-gateway-longline` 推翻 P3(网关状态口 8KB);`probe-real-sessions-time` + `probe-idle-compact` 推翻 P4(空闲压缩)。
- `mutation-sidebar-history`(rc=1)第 1 遍 E13 / E14 两处变异没编译过(删掉了回调唯一的调用,tsc 拒),改写后 `…-e13-e14` 咬住;
  `mutation-sidebar-history-final` 是改完所有修复后的全量:**56 / 56 咬住**。
- `run-all-impl`(rc=1)红的两条 = 老 e2e 替身只认带 `?` 的会话列表地址(本单前端不再拼无用的 `?limit=10`),已改替身(`2654b1f`,断言不动)。

## Review

- 规格自查(读任何 panel 输出之前先答):见仓外 `/root/aiwork/tasks/opendesign-sidebar-history-r1-my-review.md`(派发前落盘)。要点:
  实现中推翻两条前提 —— **P3**(网关侧栏状态口把整份状态塞进网址,8KB 就断 ⇒ 改存 ds_web 自己的 sidebar.json)与
  **P4**(QA 录像时发现网关每 15 分钟空闲压缩闲置对话:对话文件只留最近约 8 条、updated_at 每次刷成当时 ⇒ 碰过的项目并读界面回放记录 P1′、
  最后聊天时间取最后一条带时间的消息 P6)。两次都是判据先行、红检后再改实现。方向(业主定的方案一 + 二)没变。
  规格上我定的取舍:聊天服务连不上时历史整组隐藏(同现在);置顶只在置顶区出现一次(4c C10)。
- 腿的花名册:
  - 第 1 轮代码评审:`subcursor.gpt-5.6-sol-high=PASS(verdict=BLOCK) subcursor.kimi-k3-high=PASS(verdict=PASS)`
  - QA 判卷(第 1 遍录像):`subdeepseek=EXPLORE(rc=0,coverage=none) subcursor.grok-4.7-high=EXPLORE(rc=0,coverage=none) subcursor.gpt-5.6-terra-high=EXPLORE(rc=0,coverage=none) subcursor.gemini-3.8-flash-high=EXPLORE(rc=0,coverage=none) subcursor.kimi-k3-high=EXPLORE(rc=0,coverage=none) subcursor.glm-5.2-high=FAIL(rc=1) subcursor.composer-2.5=EXPLORE(rc=0,coverage=none)`
    (GLM 的 rc=1 是输出少了工具要求的「Direction」小节,报告正文完整,我照读;不补派)
- 轮次记录:

  | 轮 | 类型(实质 / 重试) | 派发前 `track preflight` | 日志前缀 | 新增有效阻断 |
  |---|---|---|---|---|
  | 1 | 实质 | rc=3(BLOCK 0,PENDING 2:归档才要的收据引用) | `/root/aiwork/logs/panel-sidebar-r1-20260925-225828` | 1(GPT H1) |
  | 2 | 实质 | rc=3(BLOCK 0,PENDING 2) | `/root/aiwork/logs/panel-sidebar-r2-20260925-235401` | 2(GPT 第 2 轮 M-a / M-b,中) |
  | — | (23:28 那次没派出去:缺第 2 轮自审文件,工具拒派,不算轮;我没看派发输出白等 20 多分钟) | — | `/root/aiwork/logs/panel-sidebar-r2-20260925-232832` | — |
  | 3 | 实质(业主 09-26 00:1x 同意加这一轮:只核第 2 轮两条的修复) | rc=3(BLOCK 0,PENDING 2) | `/root/aiwork/logs/panel-sidebar-r3-20260926-002630` | 0(GPT 新提 1 条中危,主裁延期) |

- findings(第 1 轮代码评审 + QA 判卷,一份修复清单,一次修完):

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | R1 | (GPT H1)助手改项目名**失败**(新名被占 name_taken)时,扫描照记别名 ⇒ 旧名项目的对话被挂到别的项目下 | `bin/ds_tools.py:1132-1147` 失败回 error;旧 `_Touched.tool` 无条件记别名;判据先行 `1b3f2fb` 红 6 条(4 条老断言因错挂一起红) | **已修** `96d14a0`:对话文件看后面 tool 行、回放记录看 result,回 ok 才记 | 真 bug,业主会看到对话挂错项目 |
  | R2 | (GPT M2)快速连点两次置顶,回话乱序到达,后到的旧状态把界面盖回去 | `App.tsx` 直接整份覆盖;后端锁保证盘上对 | **已修** `96d14a0`:前端排队依次发(`makeSerial`,判据 s9) | 我自审原列延期,改起来便宜 |
  | R3 | (Kimi F1)最后聊天时间只看文件最后一行,碰巧没带时间就退回被刷过的 updated_at | `_scan_file` 只解析最后一行 | **已修** `96d14a0`:逐行取最后一条带时间的(判据 p8) | 低危但一行能修 |
  | R4 | (Kimi F2)分段文件按名排序当时间序 | nanobot `webui/transcript.py` `_TRANSCRIPT_SEGMENT_RE = ^\d{6}\.jsonl$`,六位补零 | **驳回** | 按名排序即时间序 |
  | R5 | (Kimi F3)`valid_key` 死代码 | 针孔用 `_KEY_RE` | **已修** `96d14a0` 删掉 | — |
  | R6 | (GPT 前提核验)回放记录并非物理只追加(超 8MB 重写当前份挪进分段;fork 重写) | nanobot `webui/transcript.py:345-377,564-568` | **已修措辞**:design P1′ 写准;扫描本来就读分段 ∪ 当前份 | 不漏;fork 无入口 |
  | Q1 | (QA Grok / DeepSeek / Gemini,P1)重开后视图没记住:第 17 步是「按时间」,第 18 步重开是「按项目」 | **录像漏截一步**:tour.mjs 第 17 步截图后执行了 `await view("project")` 才关软件,没截图;重开后是「按项目」= 记住了。e2e ④「切换记住」绿 | **驳回**(录像台子的错,不是缺陷);第 2 遍录像补上这一步 | 「录像每个动作都截一步」的老教训又犯了一次 |
  | Q2 | (QA Gemini,P1)按项目视图项目行上待办数与对话数两个裸数字挨着(「2 2 ▾」),分不清 | 第 1 遍录像 06/07/13 | **已修** `96d14a0`:对话数前加对话图标 + 读屏名「展开这个项目的 N 段对话」(e2e ③) | 看得见的误导 |
  | Q3 | (QA DeepSeek / GLM,P2)按时间小标「翡翠湾-1801 +1」看不出另一个是哪个 | 第 1 遍录像 08 | **已修** `96d14a0`:小标悬停列出全部项目(e2e ①) | 便宜 |
  | Q4 | (QA GLM,P1)置顶的对话在按项目展开列表里看不到 | design C10 | **驳回** | 定好的规则(置顶只出现一次),其余六家认可 |
  | Q5 | (QA Kimi / DeepSeek)录像事实栏「今天这段」其实是列表前几行、混进了「昨天」的 | tour.mjs 标签写错 | **已修**录像台子标签 | 台子的错 |
  | D1 | (我,自审)改名别名全局、不分先后:项目「改名又改回去」或新项目用了旧名 ⇒ 老对话可能挂错 | `_scan_all` alias 表 | **延期** | 很少见、不丢数据;业主会看到个别旧对话挂在别的项目下,点「按时间」照样找得到 |
  | D2 | (我,自审)sidebar.json 条数无上限 | — | **延期** | 只有本机同站网页能写 |
  | D3 | (我,录像发现,老问题)前端写死连 ws 8765;管家试绑端口不带 SO_REUSEADDR,Linux 上 8765 刚断开的连接(TIME_WAIT)未过就顺延到 8766 ⇒ 页面连不上 | 第 1 遍录像 18.jpg「连接不上」;台子等 62 秒才可绑(第 2 遍录像事实) | **延期、另开单**(不在本单) | 业主「关掉马上再开」可能撞上;Windows 上是否同样未核实 |
  | D4 | (我)回放记录是 nanobot 内部格式(schema v3),钉版本才靠得住 | — | **延期** | 升级 nanobot 时要回看 |

- 第 2 轮花名册:`subcursor.gpt-5.6-sol-high=PASS(verdict=BLOCK) subcursor.kimi-k3-high=PASS(verdict=PASS)`
- 第 2 轮 findings:

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | R7 | (GPT 第 2 轮 M-a)改名失败时,这段对话自己仍把目标名算碰过 ⇒ 出现在已存在的目标项目下 | 旧 `_Touched.tool` 无条件 add(new) | **已修** `e417b03`(判据先行 `9ba42b5` 红):改名只算碰过旧名 | 真问题,一行修 |
  | R8 | (GPT 第 2 轮 M-b)我对 D1(改错又改回去 A→B→A、新项目用旧名)的延期理由站不住:按项目是核心承诺 | 旧 `_resolve` 全局别名、成环停在错的名字 | **已修** `e417b03`:后台回原始名字 + 成功改名记录,前端「现在还有的项目优先、再顺着改名找第一个还在的」(判据 s10) | 我同意这个反驳;D1 从延期改为已修(剩「新项目恰好用了被改掉的旧名」时,老对话归到新项目 —— 更少见,记 D1′ 延期) |
  | R9 | (Kimi 第 2 轮,低)一轮回合收尾时刷新侧栏状态的那一下不经排队,和正在进行的置顶回话赛跑 | `App.tsx` sessionsEpoch effect 里 fetchSidebarState | **延期** | 本机毫秒级窗口;盘上数据对,下次刷新自愈 |
  | Q6 | (QA 复测 DeepSeek)待办数仍是没名字的裸数字;「+1」全名只有悬停看得到 | 第 2 遍录像 06 / 08 | **延期** | 待办数是老样子不在本单;桌面版业主用鼠标 |
  | D1′ | (我)项目 A 改名成 B 之后,又新建了一个也叫 A 的项目 ⇒ 改名前碰过老 A 的对话归到新 A 下 | 前端规则「现在还有的优先」 | **延期** | 很少见;对话仍在按时间里 |

- QA 复测(只复测报过又被修的 Q2 / Q3;人选 = 报过的人,GLM 冷却中未派):`subcursor.gemini-3.8-flash-high=EXPLORE(rc=0,coverage=none) subdeepseek=EXPLORE(rc=0,coverage=none)` —— 两家都判 Q2、Q3「已修好」,没引出新问题。
- 第 3 轮花名册:`subcursor.gpt-5.6-sol-high=PASS(verdict=BLOCK) subcursor.kimi-k3-high=PASS(verdict=PASS)`
- 第 3 轮 findings:

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | R10 | (GPT 第 3 轮,中)不同对话里对同一项目连续改名且来回重名(A→B、B→A、A→C),改名记录按文件名顺序合并、不是真实先后 ⇒ 个别旧对话落「其他对话」,或挂到后来新建的同名项目 | `bin/ds_sessions.py:251-280` 按路径收、`{old: new}` 覆盖;回放记录不带时间;`bin/ds_tools.py` rename_project 不在档案记曾用名 | **延期、另开单**(decision.json split_resolutions 记着 GPT 原话) | 罕见(同一项目三次以上改名且重名);不丢数据(按时间照样找得到);根治 = rename_project 在档案里记曾用名(ds_tools 写入改动,不在本单)。同一类(改名归属)第三个变体 ⇒ 不再逐个打补丁,换数据来源 |
  | R11 | (Kimi 第 3 轮,低)两个同名分组项目 + 别处有过「该名 → X」的成功改名 ⇒ 对话挂到 X | `sidebarModel.ts` resolve 对不上唯一名字后继续顺改名找 | **延期**(并入 R10 那单) | 极罕见,同一类 |
  | R12 | (Kimi 第 3 轮,低,非本轮引入)改名记录是从对话里读出来的,删掉「发生改名的那段对话」后别名消失 ⇒ 改名前碰过旧名的对话掉回「其他对话」 | — | **延期**(并入 R10 那单:档案记曾用名后不再依赖对话) | 不挂错,只是不挂 |

- arbitrated verdict (主裁):**PASS**。三轮代码评审(GPT 三轮均 BLOCK、Kimi 三轮均 PASS)+ QA 七家判卷 + 复测:
  第 1、2 轮 GPT 挡的 4 条全部认了、判据先行修掉(R1 R2 R7 R8);第 3 轮 GPT 新提的 R10 是「改名归属」这一类的第三个变体,
  属实但罕见、不丢数据,根治要改另一个模块的写入(档案记曾用名)⇒ 延期另开单,split_resolutions 记在 decision.json。
  QA 报的 Q2 Q3 修好且报的人复测通过;Q1(视图没记住)是我录像漏截一步,第 2 遍录像补上后证实软件是对的。
  判据:后台 25 条、纯逻辑 10 条、e2e 1 份(27 项断言)全绿;变异全量 56 / 56 咬住;最终总跑见 Mechanical checks 最后一行。
  **实现中推翻了两条设计前提(P3 网关状态口 8KB、P4 网关空闲压缩)**,两次都判据先行、红检后改。

## Accepted deviations

- 聊天服务连不上时「历史对话」整组隐藏(同现在;会话列表来自聊天服务)—— QA 设计里 GPT TC-23 / Grok TC-12 期望不清空,我定的取舍。
- 延期项(不自动开单,业主定):R9 R10 R11 R12 Q6 D1′ D2 D3 D4(见 findings)。其中 **D3「关掉马上再开聊天连不上」是老问题**、R10 需要「改名记曾用名」—— 建议开单。
- 录像台子限制:种的旧对话没有完整界面回放,点开首页正文为空;「关掉再开」前台子等了 62 秒端口释放(D3)。

## 业主真机清单(录像够不着的,5 步)

1. 左边侧栏右上角点「按项目」,点某个项目右边带对话图标的数字,看它下面的对话对不对;点一条回首页能接着聊。
2. 对一段对话「⋯ → 置顶」「⋯ → 改名」,把软件完全关掉再打开,置顶和名字都还在,「按时间 / 按项目」停在上次选的那种。
3. 点项目栏的「+」真建一个新项目,看它落在对的阶段堆里。
4. 打开一段正在看的对话,从侧栏「⋯ → 删除」确认,看首页是不是换成一条新对话、侧栏里它没了。
5. 让助手在项目页右边「记一次沟通」,看这段对话出现在那个项目下面。

## 试行记录(review-convergence 试行,约五单;拿不到的写 unknown,别补 0)

- 总交付历时:开工 `4a235db`(09-25 18:3x)→ 归档(09-26 00:4x 左右),约 6 小时(含 21:1x 前额度用尽的停顿)
- 每轮新增有效阻断:第 1 轮 1(GPT H1)/ 第 2 轮 2(GPT M-a / M-b)/ 第 3 轮 0(R10 延期)
- 基础设施等待:panel 三轮 duration_ms ≈ 470s + 256s + 约 290s;23:28 那次没派出去(缺自审文件)我没看输出干等约 20 分钟;GLM QA 腿格式失败 1 次(冷却)
- 交付后返工:unknown
