# Verify: opendesign-zcode-model-settings

- Date: 2026-09-24

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录
> `decision.json`；这里保留检查、理由、发现与主 Agent 仲裁说明，不复制枚举。

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再按 impact-risk 预算跑 panel-review；只有特殊控制面
> 才显式 `--all` 做全池评审。最后仍由主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [x] build passes(dist 新鲜度 + 类型检查闸在 run-all 里,与源码同步)
- [x] tests pass(run-all rc=3 = **没有红**,只跳既有三条:两条要活网关的 e2e new_chat / project-thread + 1 条 python;全仓一直如此,与本单无关)
- [x] no secrets / unsafe ops(录像脚本自查 key 不进 tour.md;判据 C 组泄漏扫描、z10/z14 不回显 key)

**机器打印的**(按时间序,逐字节;红的几遍是判据先行的红检,最后一遍 run-all 在 600bbe7):

```
runlog: backend-criteria-red rc=1 commit=a2222b5 dirty=yes at=2026-09-24T07:57:51Z file=tracks/opendesign-zcode-model-settings/evidence/20260924T075751Z-01-backend-criteria-red.txt
runlog: web-criteria-red rc=1 commit=1575924 dirty=yes at=2026-09-24T08:05:36Z file=tracks/opendesign-zcode-model-settings/evidence/20260924T080536Z-01-web-criteria-red.txt
runlog: t4-node-criteria-red rc=1 commit=89c21ab dirty=yes at=2026-09-24T08:59:18Z file=tracks/opendesign-zcode-model-settings/evidence/20260924T085918Z-01-t4-node-criteria-red.txt
runlog: t4-w8-red rc=1 commit=89c21ab dirty=yes at=2026-09-24T08:59:18Z file=tracks/opendesign-zcode-model-settings/evidence/20260924T085918Z-02-t4-w8-red.txt
runlog: t4-configured-red rc=1 commit=980c73f dirty=yes at=2026-09-24T10:37:13Z file=tracks/opendesign-zcode-model-settings/evidence/20260924T103713Z-01-t4-configured-red.txt
runlog: qa-exec-fixes-red rc=1 commit=cd4c734 dirty=yes at=2026-09-24T11:16:56Z file=tracks/opendesign-zcode-model-settings/evidence/20260924T111656Z-01-qa-exec-fixes-red.txt
runlog: run-all-after-qa-fixes rc=3 commit=33e6108 dirty=no final=yes at=2026-09-24T11:20:50Z file=tracks/opendesign-zcode-model-settings/evidence/20260924T112050Z-01-run-all-after-qa-fixes.txt
runlog: mutation-model-picker-after-qa-fixes rc=0 commit=cfd1e72 dirty=no at=2026-09-24T11:35:34Z file=tracks/opendesign-zcode-model-settings/evidence/20260924T113534Z-01-mutation-model-picker-after-qa-fixes.txt
runlog: mutation-llm-key-after-qa-fixes rc=0 commit=cfd1e72 dirty=yes at=2026-09-24T11:38:07Z file=tracks/opendesign-zcode-model-settings/evidence/20260924T113807Z-01-mutation-llm-key-after-qa-fixes.txt
runlog: run-all-final rc=3 commit=23b008f dirty=no final=yes at=2026-09-24T11:45:59Z file=tracks/opendesign-zcode-model-settings/evidence/20260924T114559Z-01-run-all-final.txt
runlog: review-r1-fixes-red rc=1 commit=0dc309b dirty=yes at=2026-09-24T12:24:01Z file=tracks/opendesign-zcode-model-settings/evidence/20260924T122401Z-01-review-r1-fixes-red.txt
runlog: run-all-after-review-r1 rc=3 commit=600bbe7 dirty=no final=yes at=2026-09-24T12:28:55Z file=tracks/opendesign-zcode-model-settings/evidence/20260924T122855Z-01-run-all-after-review-r1.txt
runlog: mutation-model-picker-after-review-r1 rc=0 commit=0752917 dirty=no at=2026-09-24T12:42:05Z file=tracks/opendesign-zcode-model-settings/evidence/20260924T124205Z-01-mutation-model-picker-after-review-r1.txt
runlog: mutation-llm-key-after-review-r1 rc=0 commit=0752917 dirty=yes at=2026-09-24T12:44:36Z file=tracks/opendesign-zcode-model-settings/evidence/20260924T124436Z-01-mutation-llm-key-after-review-r1.txt
```

- 红收据各自对应:backend/web = T2/T3 判据先行;t4-* = T4 移植批与 w9/ms9;qa-exec-fixes-red = QA 缺陷 K1~K5;review-r1-fixes-red = 第 1 轮代码评审 #1~#5。
  K6(上下文标签)的红是在 9fd4dfb 提交前手跑 node 看到的(ms6 1 fail),没有单独 runlog 收据 —— 如实记账。
- 红检(判据的判据):mutation-model-picker 23/23、mutation-llm-key 18/18,QA 修复后与第 1 轮评审修复后各跑一次,全咬住、还原核对一致。

## 判据先行的红收据

- 后台 z1~z12 / 接口 w1~w7 / 界面纯逻辑 ms1~ms7:见 evidence/20260924T075751Z-01-backend-criteria-red.txt、20260924T080536Z-01-web-criteria-red.txt(当时没粘行,文件在)
- T4 移植批(模块未写 ⇒ 红在 ERR_MODULE_NOT_FOUND;b2 本来就该绿)与 w8(红在 KeyError 'writable'):

```
runlog: t4-node-criteria-red rc=1 commit=89c21ab dirty=yes at=2026-09-24T08:59:18Z file=tracks/opendesign-zcode-model-settings/evidence/20260924T085918Z-01-t4-node-criteria-red.txt
runlog: t4-w8-red rc=1 commit=89c21ab dirty=yes at=2026-09-24T08:59:18Z file=tracks/opendesign-zcode-model-settings/evidence/20260924T085918Z-02-t4-w8-red.txt
```

- 实现中补的判据 w9 / ms9(首启口径与旧卡片同一个:有 key 就算有;红在 KeyError 'configured' / ms9 首条断言):

```
runlog: t4-configured-red rc=1 commit=980c73f dirty=yes at=2026-09-24T10:37:13Z file=tracks/opendesign-zcode-model-settings/evidence/20260924T103713Z-01-t4-configured-red.txt
```

## T4 判据移植对照(旧界面 → 照 ZCode 的新界面;09-24,判据单独 commit)

旧 key 卡片(`LlmKeyCard.tsx` / `llmKey.ts`)与一维换模型菜单被删;钉着它们的判据**逐条搬到新界面,编号尽量不变**,性质一条不丢。
钩子表见 design.md「界面钩子」。

| 旧 | 新 | 说明 |
|---|---|---|
| test_model_picker mp1~mp4(modelMenuItems) | 同号,问 `modelMenuTree`(两级树) | 「换厂商 / 换 key…」⇒ 底行「管理模型」(落到当前那家);mp5/mp6 原样 |
| test_per_vendor_ui pv1~pv4 | 同号,问 `modelMenuTree` | pv3 加问厂商行的勾;pv1 加问没模型的那家不列;pv5 原样 |
| test_per_vendor_ui pv6 / pv7(卡片每行状态与说法) | test_model_settings_ui ms1 / ms4 | 四种说法 + ZCode 的「已禁用」= 五种 |
| test_kimi_glm_ui ku1 / ku2(keyUrl 透出、只收 https) | ms1 / ms2 | 文件删除 |
| test_kimi_glm_ui ku3(源码扫:链接跟着选中那家、新窗口、不带来源、没链接不画) | e2e model_settings A28 ×2 | 从扫源码改成问真页面(更强) |
| test_llm_key a1~a7 / b1 / c1 / c2 / d1~d3(llmKey.ts) | 同号,问 `settings/modelSettings.ts` | 新增 a8(添加供应商带 key 同一纪律);c2 加问 key 塞进某家末四位提示 |
| test_llm_key_surface b2 / c3 / c4 | 同号;c3/c4 扫 `web/src/settings/` 全部源码 | 原来只扫逻辑层一份,现在连组件一起扫 |
| e2e llm_key A1~A7 | 同号 | 自动弹卡 ⇒ 自动进 `#/settings/models`;关卡片 ⇒「返回工作区」;遮罩吃点击 ⇒ 离开后点得动侧栏 |
| e2e llm_key B1~B3 / C1~C10 / D1 / E1 / E2 / G1 / C5 | 同号 | 选择器换新钩子;E1 等 `/api/llm/providers` 回包;E2 新旧两个接口都问;C5 保存路径 `/api/llm/providers/key` |
| e2e llm_key F0~F3 | 同号 + F4 | 设置弹层 ⇒ 设置页「常规」;F1 问「模型设置」入口唯一且常规页没有第二个密码框;F4 常规页原弹层各项都在 |
| e2e llm_key H1(卡片只读) | 同号(stub `/api/llm/providers` 的 writable=false) | 后台一半新增 w8(test_ds_web_providers,真环境变量) |
| — | e2e llm_key N1 | 老装法说明 + 无「添加供应商」(QA Q6 / A25) |
| e2e per_vendor_keys A1~E | 同号 | 卡片行 ⇒ 设置页左栏 + 详情 `ms-state`;**C2 按 D4 改语义**:存别家 key 不换当前模型(原「存完就换过去」);D 组改成先点 DeepSeek-pro 再点 MiMo-pro(当前本来就是 mimo-v2.5,先点它问不出"变了") |
| e2e model_picker ①~⑮ | 同号 + ⑦a/⑦b/⑦c | ⑦ 问厂商行 ✓ + 管理模型;⑦b 子菜单在右边;⑦c 斜着移进子菜单不闪退(A23);⑫ ⇒ 管理模型进设置页当前那家 |
| e2e settings_fvis B(`.settings-pop`) | 同段,等 `settings-general` | 其余原样 |
| — | e2e model_settings(新) | 验收清单 A1/A2/A3/A5/A6/A7/A8/A9/A10/A12/A15/A16/A18/A19/A20/A21/A22/A27/A28 + Q8;**无外网出口**(只测本机假厂商) |
| desktop_update / 云 E4 | **不改** | `settings-toggle` / `update-*` 钩子沿用(常规页放更新各项,侧栏设置行留 `update-restart` / `update-badge`) |

仍由别处管、这里不重复:A13 升级(py z11 + 业主 UAT)、A14(desktop_update + 云 E4)、A26 两处聊天框同步(`MODEL_CHANGED_EVENT` 未改)、A29 像不像 ZCode(T5 截图亲看 + QA-执行)。
`tests/mutation-llm-key.sh` 的锚点指着旧文件,实现落地后改锚点重跑(红检,不是判据本身)。

## T4 实现中的判据改动与事故(09-24 下午)

- `ae7d599` 判据修:llm_key E1/H1 只改 # 的 goto 在 Chromium 是同文档跳转、不重载 ⇒ 补 reload(实现前自查)。
- `980c73f` 判据修:model_picker ⑦c ① 多元素 locator 取 innerText 必抛(恒红)② 原轨迹一行不擦、问不到擦边闪退;
  改瞄最后一行 + 断言真擦过底行 + 等过宽限期。红检:删子菜单 `onMouseEnter={cancel}` ⇒ ⑦c FAIL,还原 ALL PASS。
  🔴 **这个 commit 误带了 `web/src/LlmKeyCard.tsx` / `web/src/llmKey.ts` 的删除**(早先 `git rm` 留在暂存区,
  提交判据时没看 `git diff --cached`)。判据内容不受影响,但单独检出 980c73f 前端 build 不过(App.tsx 仍引用它们);
  本地未 push,不改写历史,在此认账。之后每次判据提交前先看 `git diff --cached --stat`。
- `5d214d4` 判据 w9 / ms9(红):首启「没 key 进模型设置」口径必须与旧卡片同一个(status().configured)。
  来历:desktop_update / settings_fvis 的 ds_web 没有 nanobot 配置,每家那一行认不出 key.txt 归谁,只看行 ⇒ 有 key 的机器被甩进设置页。
  这是我实现里引入的**真行为改动**(不是判据问题),修在 `6a8d320`。
- `ea99d37` 判据移植:settings_fvis B「保存当场看左侧列表」—— 设置整页时侧栏不在屏上,观察点结构性不存在;
  改成关体检卡 → 返回工作区 → 看列表(不 reload,性质不变:没刷新 dataEpoch 就看不到)。
- `6a8d320` 实现;`ca53484` 两个红检脚本改锚点(另:mutation-model-picker 段 A 的后端锚点早在 kimi-glm 改版时就失效了,
  c2 锚点也早已过时 —— 红检脚本会悄悄烂掉,只有真跑才知道)。

## Review

- 规格自查(读任何 panel 输出之前先答;第 1 轮派发前的主裁自审正本在仓外 `/root/aiwork/tasks/opendesign-zcode-model-settings-r1-my-review.md` [仓外不承重]):
  用户成功条件 = 照 ZCode 的设置页 + 两级换模型,钱跟着选中那家走、升级不断聊天、选好的模型不被换、key 不回显。
  自审判 PASS,点名最不放心「漏包 _scoped 的写入口」与「两处写中途失败」。**第 1 轮证明我对第二条的担心是对的、而对设计的检查漏了一条整路径**(只配中转的新用户,见 #1)。
- 切片 / 整份:**整份**。理由:本轮的实验是 QA 腿(测试员角色),再叠切片会搅乱「谁抓到的」归因;切片对比数据 09-15 已有一份(in-app-update 那单)。
- 反锚定记账:第 1 轮派发时 verify.md 评审一节是空模板(工具照例报 anchor leak,指的是这份文件);腿能读到的是 evidence/qa-exec-triage.md(QA 缺陷的主裁分级),与代码评审题面不重叠。
- 腿的花名册:
  - 第 1 轮:`submimo=PASS(verdict=BLOCK) subkimi=PASS(verdict=PASS)`(`/root/aiwork/logs/panel-zcode-r1-20260924-195939.roster` [仓外不承重])
  - 第 2 轮:`submimo=PASS(verdict=BLOCK) subkimi=PASS(verdict=PASS)`(`/root/aiwork/logs/panel-zcode-r2-20260924-205018.roster` [仓外不承重])
- 轮次记录(每次派发一行;实质评审与基础设施重试分开,重试不算轮但次数与耗时照记):

  | 轮 | 类型(实质 / 重试) | 派发前 `track preflight` | 日志前缀 | 新增有效阻断 |
  |---|---|---|---|---|
  | QA-设计 | 测试员(非评审,不计轮) | — | explore-zcode-qa-design-* | —(产出验收清单 A1~A29、需求空白 Q1~Q9) |
  | QA-执行 | 测试员(非评审,不计轮) | — | explore-zcode-qa-exec-20260924-190341 | 5 条用户层真问题 K1~K5(见 evidence/qa-exec-triage.md) |
  | QA-复测 | 测试员(非评审,不计轮) | — | explore-zcode-qa-retest-20260924-193518 | 0(K1~K5/T1~T3 全关;顺藤查出 K6) |
  | 1 | 实质 | rc=3,BLOCK 0(PENDING 2) | panel-zcode-r1-20260924-195939(MiMo 18 分、Kimi 19 分) | 3(#1 #2 #3) |
  | 2 | 实质(预算最后一轮) | rc=3,BLOCK 0(PENDING 2) | panel-zcode-r2-20260924-205018(MiMo、Kimi) | 1(#8,本单引入的假话) |
  | 3 | **追加**(见下「追加一轮」) | 待填 | 待填 | 待填 |

- findings(**先处置、后动手**;一轮一份修复清单,一次修完再复审 —— panel 抽屉 4b):

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | 1 | (MiMo BLOCK-1)只配自定义供应商、一家内置 key 都没有:外壳重启网关只认 key.txt ⇒「不动」;起程序时 startup_plan(has_key=False) 不起网关 ⇒ 聊天永远用不了,界面却说「正在自动重启」 | 亲读 bin/ds_shell.py `restart_gateway`(`if not k: log…; return`)、bin/ds_shell_core.py `startup_plan`;design.md G4/D2 只考虑过「主槽被禁/被挪」,没考虑只有中转的新用户 | **本单必须修** | 承诺「能加自定义供应商」在这条路上不成立且界面撒谎。修法:没有内置 key 时拒绝添加自定义供应商 / 拒存自定义 key,说清要先填一家内置厂商;**让只配中转也能聊是设计改动**(主槽槽位规矩 13 轮),不在本单做,写进 Accepted deviations 并告诉业主 |
  | 2 | (MiMo BLOCK-2)删自定义供应商:先写登记、再写配置、最后删 key 且吞掉 OSError;新供应商按登记里的空号复用 id ⇒ 继承旧 key,显示成「已保存」,起网关时把旧 key 发到新端点 | 亲读 remove_custom_provider / add_custom_provider(`used` 只看登记) | **本单必须修** | key 外泄到第三方端点 = 安全面。修法:先删 key(删不掉就报错、什么都不动),分配 id 跳过盘上还有 key 文件的号 |
  | 3 | (MiMo BLOCK-3 + MIN-2;Kimi MEDIUM)四个新写口(删模型 / 改上下文窗口 / 改名改地址 / 添加供应商带 key)先写登记后写配置或 key:第二处失败时报「写不进去」而登记已变 —— 改地址那支界面与测试是新地址、聊天仍走旧地址;添加供应商留下僵尸,重试撞「这个地址已经是…」 | 亲读四个函数写序;Kimi 用 monkeypatch `_atomic_write` 实测 D/E/F/G 四支 | **本单必须修**(整类一次修) | 数据一致性 + 「两处写中途失败看不出来」正是题面第 2 问。修法统一:配置 / key 先写、登记最后写;登记写不进去 ⇒ 把配置 / key 还原。**同一类不逐个打补丁** |
  | 4 | (MiMo MIN-1;Kimi LOW)等重启那一句写死「正在重启后台…」:重启其实不会发生(没外壳应答 manual、prepare_gateway 失败)时是永久假话 | modelSettings.ts providerStateText pending 分支 | 本单修(一行措辞) | 说成「后台重启后就能选;一直没好就重开 OpenDesign」,两种情况都是真话 |
  | 5 | (MiMo MIN-3)「显示」按钮悬停字写「已保存的永远只显示末四位」,实际是首四 + 末四 | _hint 与 ModelSettings.tsx 眼睛按钮 title | 本单修(措辞) | 界面文字说真话 |
  | 6 | (Kimi LOW)主槽换 key 后绿条一直说「正在自动重启」 | K1 的有意选择(主槽没有可观察的等待) | 延期 | 业主那边:存完 MiMo key 绿条停在「稍等片刻」,回聊天能用就是好了;要改口得有网关侧信号(同主裁自审 F2) |
  | 7 | (Kimi 自己排除)save() 主槽「先写配置、后写 key.txt」 | 095ec4c 已存在 | 驳回(不属本单) | 老版本就有 |
  | 8 | (MiMo 第 2 轮 发现 1)等重启那家一出现在配置里,绿条就改口「**后台已重启,这把 key 已生效**」;而外壳是**先** prepare_gateway 写配置、**再** sup.restart —— 重启进行中(冷启动)或重启失败(外壳自己弹「没能自己重启」)时这句都是假话 | 亲读 bin/ds_shell.py build_env / restart_gateway 顺序;ModelSettings.tsx awaiting 那段;这句是**我 cb0c57b 加的** | **本单必须修** | 本单引入的回归,且正面违反仓里明写的「不许撒谎的重启」(ds_web.py 重启应答那段注释)。修法:改口只说确定知道的 ——「后台已开始换上这把 key」+ 稍等几秒 + 弹窗说没重启成就重开 |
  | 9 | (同上,MiMo 的推论)此时去聊天框选这家 ⇒ 旧网关沿用旧厂商「发错家」 | 亲读 ds_shell_core.py `Supervisor.restart`:**先杀旧腿再起新腿**,重启失败时没有网关(连不上 + 外壳弹窗),不会一直发错家;剩下「外壳写完配置到旧网关被杀」那一瞬,是 0.98.9 per-vendor-keys design.md:109 当年评审过、判可接受的窄窗 | 驳回(持续发错家不成立;窄窗老版本就有) | — |
  | 10 | (MiMo 第 2 轮 发现 2)删自定义供应商:key 先删、后面两处写失败 ⇒ 界面到刷新前仍显示「已保存」 | 亲读 remove_custom_provider + 前端失败分支不刷新 | 延期 | 业主那边:要磁盘写失败才碰到;key 没外泄(#2 的目标);报错照出,刷新后显示「还没填 API Key」,重填即可 |
  | 11 | (MiMo 第 2 轮 发现 3)`_commit_both` 还原配置那一步也写失败(连续两次写盘失败)⇒ 配置新地址、登记旧地址 | 我自审 R2-F1 已列 | 延期 | 业主那边:要盘彻底坏了才碰到;钱去的是他刚填的新地址(同一家),不是别家 |
  | 12 | (MiMo)env 供 key 且变量名非 DS_、key.txt 空时 #1 的闸放行;(Kimi)删供应商不清「想换过去」标记、编号复用后可能指向新供应商 | 前者:标准 Windows 装法 child_env 剥掉 DS_*,Kimi 核为够不着;后者:新界面已不调 /api/llm/credential(web/src 无引用),标记只能手搓请求写出 | 驳回(锤子类 / 走不到) | — |

- **追加一轮**(4b ④:预算 2 轮已用完,派发前在这里写明):
  - 具体阻断:#8 一处 —— 我自己加的「后台已重启,这把 key 已生效」在重启完成前 / 重启失败时就说,违反「不许撒谎的重启」。
  - 为什么不能「延期 + 分裂裁决」收场:它是**本单引入的回归**、落在业主明确要的「提示说真话」上,按 4b 属「本单必须修」;而改了它,第 2 轮的评审绑定就不覆盖最终交付,归档闸不认。
  - 追加目的:只核验这一句改口(及对应判据)是否说真话、有没有别处还在宣称重启完成;**不重开整单**。
  - 新的有限预算:**1 轮,两家(同 MiMo、Kimi)**;这一轮的新发现只要不是「本单必须修」一律延期,**不再续轮**。


- arbitrated verdict (主裁): <...>
  > 这里写理由；最终枚举写进 `decision.json.outcome.verdict`。归档时仍为空会被
  > `track-record validate --phase archive` 挡住，`track list` 也会打 ⚠️。

## Accepted deviations

- **只配自定义供应商(一家内置 key 都没有)用不了**(第 1 轮评审 #1):ZCode 可以只用中转,我们现在当场拒并说清「先填一家内置厂商」。
  原因:外壳只靠主槽(内置厂商)的 key 起网关;要让只配中转也能聊,得改主槽 + 额外槽的槽位设计(kimi-glm 那单 13 轮磨出来的规矩)、
  改外壳起网关的条件,属于设计改动,本单不做。影响:业主两台机器都有 MiMo key,不受影响;新机器 / 只有中转 key 的人会被挡在添加那一步(说真话,不是死路)。已告诉业主,要做另开单。
- 上下文标签:ZCode 缺值时画「0」,我们不画(不编数字、也不画误导人的 0)。

## 试行记录(review-convergence 试行,约五单;拿不到的写 unknown,别补 0)

- 总交付历时:<开工 commit 时刻 → 归档 commit 时刻>
- 每轮新增有效阻断:<第 1 轮 n / 第 2 轮 n>
- 基础设施等待:<重试次数;observations 里 panel-review 的 duration_ms 求和>
- 交付后返工:<归档后因本单再改过几次;不知道写 unknown>
