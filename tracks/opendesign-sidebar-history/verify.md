# Verify: opendesign-sidebar-history

- Date: 2026-09-25

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录
> `decision.json`；这里保留检查、理由、发现与主 Agent 仲裁说明，不复制枚举。

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再按 impact-risk 预算跑 panel-review；只有特殊控制面
> 才显式 `--all` 做全池评审。最后仍由主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [ ] build passes
- [ ] tests pass
- [ ] no secrets / unsafe ops

**机器打印的**(不是我的转述)—— 判据用 `runlog` 跑,把它打印的收据行原样粘进来:

```
runlog -t opendesign-sidebar-history -- <判据命令>
```

```
<粘收据行,逐字节,别改数。**每次提交**都会跟 evidence/ 里的收据逐字节比对(5a);
 **归档时**还要求:最后跑的那一遍必须在这儿、跑红的那几遍一份都不许藏(5b)、
 收据得进 git(5d)。一份收据都没有的话,写一行
 「- 无机器证据:<理由>」认账 —— 沉默不算理由(5c)。>
```

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
  | 3 | 实质(业主 09-26 00:1x 同意加这一轮:只核第 2 轮两条的修复) | 见下 | 见下 | 见下 |

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
- arbitrated verdict (主裁):(第 3 轮后填)

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>

## 试行记录(review-convergence 试行,约五单;拿不到的写 unknown,别补 0)

- 总交付历时:<开工 commit 时刻 → 归档 commit 时刻>
- 每轮新增有效阻断:<第 1 轮 n / 第 2 轮 n>
- 基础设施等待:<重试次数;observations 里 panel-review 的 duration_ms 求和>
- 交付后返工:<归档后因本单再改过几次;不知道写 unknown>
