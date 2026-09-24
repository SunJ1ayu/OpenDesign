# Verify: opendesign-kimi-glm-vendors

- Date: 2026-09-23

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
runlog -t opendesign-kimi-glm-vendors -- <判据命令>
```

```
runlog: bash rc=1 commit=53560cc dirty=yes at=2026-09-23T09:37:17Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T093717Z-01-bash.txt
```
(上一行 = 判据先行红检:k1/k2/k4/k5/k5b/k6 + ku1/ku3 红,红因都是「不认识的厂商 / 缺 keyUrl / 卡片无链接」;k3、ku2 是守卫型、现状即绿。)

```
runlog: bash rc=3 commit=64442c0 dirty=no at=2026-09-23T09:39:46Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T093946Z-01-bash.txt
```
(上一行 = 第一版实现后总跑:六段全 PASS(rc=3 = 活网关 e2e 2 条 + python 1 条跳过)。**之后自审抓到两条真 bug,见下。**)

```
runlog: python rc=1 commit=64442c0 dirty=yes at=2026-09-23T09:51:37Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T095137Z-01-python.txt
```
(上一行 = 自审补判据 k4b/k7/k7b 的红检:① 重启后 GLM 同名预设被 prepare_gateway 按「最后一家」重指,三种槽位组合全红;
② Kimi 每个模型真发出去的 temperature=0.1(nanobot 的 moonshot 覆盖只对它自己的 moonshot 规格生效)。)

```
runlog: python rc=1 commit=a913a4f dirty=yes at=2026-09-23T09:53:18Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T095318Z-01-python.txt
```
(上一行 = 修 k4b 时想到的反面 k4c 红检(工作树里已有 k4b/k7 的修法):存第二家 GLM 的 key 后「想换过去」,
同名预设被保留给原来那家 ⇒ 重启后仍在原来那家,两个方向都红;k4b/k7/k7b 此时已绿。)

```
runlog: bash rc=3 commit=700ace1 dirty=no at=2026-09-23T09:54:36Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T095436Z-01-bash.txt
```
(上一行 = 修完后总跑,干净树:六段全 PASS;rc=3 = 活网关 e2e 2 条 + python 1 条跳过。)

```
runlog: bash rc=0 commit=700ace1 dirty=yes at=2026-09-23T10:06:26Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T100626Z-01-bash.txt
```
(上一行 = 本单判据 11 条 + 前端 ku/老 llm_key/per_vendor_ui 全绿;dirty 只是 verify/收据未提交,源码 = 700ace1。)

```
runlog: python rc=1 commit=264aad4 dirty=yes at=2026-09-23T10:22:57Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T102257Z-01-python.txt
```
(上一行 = 第 1 轮修复清单的判据:k8 红(正用按量、只带模型名被换到套餐);k7b 加强为走 `_build_kwargs` 出口,现实现即绿。)

```
runlog: bash rc=3 commit=4311fd2 dirty=no at=2026-09-23T10:24:15Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T102415Z-01-bash.txt
```
(上一行 = 修完 #1 后总跑,干净树:六段全 PASS;rc=3 = 活网关 e2e 2 条 + python 1 条跳过。)

```
runlog: bash rc=0 commit=4311fd2 dirty=yes at=2026-09-23T10:36:03Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T103603Z-01-bash.txt
```
(上一行 = 本单判据 12 条 + ku 全绿。)

```
runlog: python rc=1 commit=9d0c2c2 dirty=yes at=2026-09-23T10:54:40Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T105440Z-01-python.txt
```
(上一行 = 第 2 轮修复清单判据:k8b(不带厂商要同名家族另一模型被换家)、k9(丢一家 GLM key 后改扣另一家)均红。)

```
runlog: bash rc=3 commit=47ca5d9 dirty=no at=2026-09-23T10:56:15Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T105615Z-01-bash.txt
```
(上一行 = 修完 #7/#8 后总跑,干净树:六段全 PASS;rc=3 同前。)

```
runlog: bash rc=0 commit=47ca5d9 dirty=yes at=2026-09-23T11:08:01Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T110801Z-01-bash.txt
```
(上一行 = 本单判据 14 条 + ku 全绿。)

```
runlog: python rc=1 commit=fb97e4d dirty=yes at=2026-09-23T11:24:51Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T112451Z-01-python.txt
```
(上一行 = 改设计的判据:k10(同名模型两家各一份预设)红;k9b 两格对位在旧补丁上已绿。)

```
runlog: bash rc=3 commit=218e13a dirty=no at=2026-09-23T11:27:11Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T112711Z-01-bash.txt
```
(上一行 = 改设计后总跑,干净树:六段全 PASS;rc=3 同前。)

```
runlog: bash rc=0 commit=218e13a dirty=yes at=2026-09-23T11:39:08Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T113908Z-01-bash.txt
```
(上一行 = 本单判据 16 条 + ku 全绿。)

```
<粘收据行,逐字节,别改数。**每次提交**都会跟 evidence/ 里的收据逐字节比对(5a);
 **归档时**还要求:最后跑的那一遍必须在这儿、跑红的那几遍一份都不许藏(5b)、
 收据得进 git(5d)。一份收据都没有的话,写一行
 「- 无机器证据:<理由>」认账 —— 沉默不算理由(5c)。>
```

## Review

- 规格自查(派发前,正本在仓外 /root/aiwork/tasks/opendesign-kimi-glm-vendors-my-review.md [仓外不承重]):用户成功条件 = 下拉多三家、各带获取 key 链接、
  选哪家就走哪家(扣对钱)。自审中推翻了 design 前提 3 的一半,抓到并修了三条(k4b 重启串家、k4c 想换过去不兑现、k7 Kimi temperature),见上方收据。
  4c:沿用 per-vendor-keys 已验证契约、不改用户必经步骤 ⇒ 未做实施前独立挑战(premise not_required);impact=high(money/sensitive_data)⇒ 两家族实现评审。
- 反锚定如实记账:第 1 轮派发时 verify.md 已含收据注释(里面写了我自审抓到的三条 bug),两条腿都读得到;
  **它们对这三条的确认不算独立发现**,独立价值在它们另报的条目(下表 1~3)。
- 腿的花名册: submimo=PASS(verdict=PASS) subcursor.grok-4.7-high=PASS(verdict=PASS)
- 轮次记录(预算 2 轮实质评审):

  | 轮 | 类型 | 派发前 `track preflight` | 日志前缀 | 新增有效阻断 |
  |---|---|---|---|---|
  | 1 | 实质 | rc=3,BLOCK 0(PENDING=待评审) | /root/aiwork/logs/panel-kimi-glm-20260923-1806 [仓外不承重] | 0(1 条钱路径缺口按必须修处理) |
  | 2 | 实质 | rc=3,BLOCK 0 | /root/aiwork/logs/panel-kimi-glm-r2-20260923-1836 [仓外不承重] | 2(Grok BLOCK,下表 7、8) |
  | 3 | 实质(追加,预算 1) | rc=3,BLOCK 0 | /root/aiwork/logs/panel-kimi-glm-r3-20260923-1908 [仓外不承重] | 1(MiMo BLOCK,下表 12;按预案回头改设计) |
  | 4 | 实质(改设计后,预算 1) | rc=3,BLOCK 0(PENDING=待评审) | /root/aiwork/logs/panel-kimi-glm-r4-20260923-1939 [仓外不承重] | 1(两家都 BLOCK,同一个洞,下表 15)|

- findings(第 1 轮):

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | 1 | (MiMo,Grok 也点到)`POST /api/llm/model` 不带 provider 且两家 GLM 都活时,`hits[0]` 静默改成 glm_plan,改走套餐端点+套餐 key | `bin/ds_credential.py:303-310` 读码属实;调用方:现界面 `modelSelectBody` 总带 provider,外壳前后端同包发 ⇒ 装好的软件里走不到 | **本单必须修** | 同名模型是本单引入的新暴露面,落在「扣错钱」轴上;修法小:缺 provider 时优先保留预设现在的归属,多家都能用且无归属 ⇒ 拒绝并要求指明厂商(判据 k8) |
  | 2 | (MiMo)k7b 只看 generation.temperature,不走 `_build_kwargs` 真出口 | 读 `tests/test_kimi_glm_vendors.py` 属实 | **本单必须修**(随清单一起) | 考卷证明「主槽 Kimi 真发出的值」这条当前承诺时隔了一层;改成与 k7 同一出口,成本一行 |
  | 3 | (两家)ku3 是源码字符串匹配,可被「假链接 + 真 UI 另画」骗过 | 属实 | 延期 | 当前实现经截图核过(卡片外链文字/href 随下拉变);这是「挡不住任意未来错误实现」类,不扩大本单承诺。在业主那边:将来有人改卡片时可能漏掉链接而考卷仍绿 —— 发版单云 e2e 截图兜一次 |
  | 4 | (MiMo)k7 只钉 temperature,不钉全部出参;kimi-k3 可能另有拒收参数 | 属实,但无真 key 问不出 | 延期 | 已知未知(design 前提 2);业主那边的样子:选 Kimi 聊天报参数错误,改表一行即修 |
  | 5 | (MiMo)`rel` 可写 `noopener noreferrer` | noreferrer 在 Chromium 已含 noopener 语义 | 驳回 | 行为等价 |
  | 6 | (Grok)k7 `>= 1.0` 放过 1.5 | 1.5 同样被 Kimi 接受(拒的是 <1.0) | 驳回 | 断言与真实约束同形 |

- 第 2 轮花名册: submimo=PASS(verdict=PASS) subcursor.grok-4.7-high=PASS(verdict=BLOCK)(两家冲突:MiMo PASS、Grok BLOCK;冲突不靠投票,逐条核实如下)
- findings(第 2 轮):

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | 7 | (Grok BLOCK)正用按量 glm-5.3,不带厂商要 glm-5.3-flash(其预设仍归套餐)⇒ 被换到套餐,换端点/key/账单 | 判据 k8b 复现红;修 #1 的「优先预设归属」漏了「优先当前这家」 | **本单必须修** | 第 1 轮 #1 的修法没修全,同一条钱路径;老菜单只列当前这家的目录 ⇒ 不带厂商 = 当前这家 |
  | 8 | (Grok BLOCK)正用套餐 glm-5.3,套餐 key 文件没了再起网关 ⇒ 预设删了又被按量重建,当前模型改扣按量 | 判据 k9 复现红;界面无删 key 入口,只能手删文件 | **本单必须修** | 与 DeepSeek 丢 key 回落主槽的既有语义不一致,且落在扣钱轴;修法小:当前预设在①被删 ⇒ 回落主槽默认 |
  | 9 | (MiMo)预设归属那家没 key 时 `owner in hits` 仍会留在归属 | `_live_vendors` 主槽不验 key | 延期 | fail-closed(报错/发不出去),不扣错钱;业主那边:删了主槽 key 后选模型会报错,需重填 key |
  | 10 | (MiMo)`bin/set_model.py` 不读 presetParams;零迁移路径不补写 | 读码属实(set_model.py:65-67;prepare_gateway 零迁移分支) | 延期 | 界面不走 set_model.py;没有任何已发版本写过 Kimi 预设 ⇒ 零迁移路径上不存在缺温度的 Kimi 预设;脚本换到 Kimi 会报参数错(fail-closed) |
  | 11 | (MiMo)k8 缺 owner∉hits 对位 | 属实 | 本单必须修(随 7 一起) | k8b 即补这一位 |

- **追加第 3 轮的理由(派发前写)**:预算 2 轮已用完;7、8 是真实阻断,且都在扣钱轴。追加目的:只核验 7、8 的修法与 k8b/k9 考卷;
  新预算 = 1 轮(两家族,同成员)。第 3 轮再有阻断 ⇒ 本单保持未完成、回头重看同名模型的设计(改成按厂商区分预设名),不再续轮。

- 第 3 轮花名册: submimo=PASS(verdict=BLOCK) subcursor.grok-4.7-high=PASS(verdict=PASS)(冲突:MiMo BLOCK、Grok PASS)
- findings(第 3 轮):

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | 12 | (MiMo BLOCK)主槽=GLM 按量、人在额外槽套餐 glm-5.3,套餐 key 丢了 ⇒ 回落主槽默认 = 按量 glm-5.3,模型名不变、账单换家 | Grok 同一格读码:落到主槽 custom,端点/key 一致;k9b ① 实测落主槽按量 | 驳回「作为 bug」,但**按预案回头改设计** | 行为本身是「丢 key 回主槽默认」的既定规矩(DeepSeek→MiMo 同一条),不是串到非主槽的第三方;但同名模型已第五次打补丁(k4b/k4c/k8/k8b/k9),4c「同一类问题第二次打补丁要回头看根因」早已触发 ⇒ 改成同名模型按厂商各存一份预设(k10),未发版无迁移成本 |
  | 13 | (MiMo)k9 夹具只有 MiMo 主槽;缺「主槽=另一家 GLM」与「人在第三家丢一家 GLM 不许被踢」对位 | 属实 | 本单必须修(随设计改) | 补 k9b 两格 |
  | 14 | (MiMo)k8b 只考一个方向,缺「预设归属」那一支 | 属实 | 随设计改消失 | 改设计后预设不再共享,「归属」分支删除,不需要考 |

- **追加第 4 轮的理由(派发前写)**:第 3 轮按预案不再补丁,改设计(同名模型按厂商分预设名、删 keeps_owner/removed 补丁)。
  这是方向改变 ⇒ 必须再审一轮;预算 = 1 轮(两家族)。再有阻断 ⇒ 本单记 NEEDS_MORE_INFO 交业主定是否先只发 Kimi + 一家 GLM。

- 第 4 轮花名册: submimo=PASS(verdict=BLOCK) subcursor.grok-4.7-high=PASS(verdict=BLOCK)(两家族一致 BLOCK;09-23 断线后接手核实)
- findings(第 4 轮):

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | 15 | (两家)只有一把 GLM 套餐 key 在主槽,业主**替换**成 GLM 按量(不是再加一家)⇒ 没有额外槽,`prepare_gateway` 在 650 行提前返回,③b 不跑;残留的 `glm-5.3@glm_plan` 仍是 `custom` ⇒ 经 `/model` 或 agent 的 model_preset 工具选中它时,名字写套餐、实际发到按量端点、用按量 key | 接手后亲跑复现:nanobot 自己加载 `glm-5.3@glm_plan` 得到 key=按量、apiBase=`open.bigmodel.cn/api/paas/v4` | **本单阻断**;按预案停,交业主 | 改设计只把「同名」拆开了,没拆掉真正共享的东西:**`custom` 这个槽的厂商会变,而指向它的预设不带厂商**。第 3 轮之前那五个补丁、以及这个洞,都是它的症状 |
  | 16 | (MiMo)不重名的旧主槽预设(如 MiMo 换成 DeepSeek 后 `mimo-v2.5`)仍指 `custom` ⇒ 发到新主槽 | 在 base `53560cc`(=已发 0.98.10 的代码)上亲跑同样复现:`mimo-v2.5` → DeepSeek 端点+key | 不属本单引入;记进下一单 | 已发版本就有;模型名在新端点不存在 ⇒ 报错,不扣错钱。但与 15 是同一根因,修 15 时应一并修 |
  | 17 | (MiMo)`bin/set_model.py` 一律写裸模型名,会和 `@厂商` 名并存 | 读码属实(set_model.py:67-68) | 随 15 一起处理 | 界面不走它,但文档点名它是换模型入口 |
  | 18 | (两家)k10 只数 provider 字段、不咬预设名、不走 nanobot 加载;k8 的 `pop("glm-5.3-flash")` 改设计后成了空操作 | 读 tests/test_kimi_glm_vendors.py 属实 | 随 15 一起加强 | 考卷没挡住 15,本身就是判据太弱的实证 |

- **状态:NEEDS_MORE_INFO(待业主拍板)**。按第 4 轮前写下的预案,不再自己续轮。给业主的两条路:
  A. 先只发 Kimi + 一家 GLM(同名问题直接消失;16 仍是已发版本的旧毛病,另开单);
  B. 两家 GLM 都要 ⇒ 按根因改:「主槽换厂商的那一刻,所有指向 custom 且不属于新主槽那家的预设,有额外 key 就改指 od_<厂商>、没有就删」,一条规矩同时收 15/16,再审一轮。
- **业主 09-23 晚拍板:「从第一性原理修就好了」⇒ 走 B。** 根因判据(先红):
  k11 = 不变量「存完 key / 起完网关后,每一份认得出主人的预设按名字交给 nanobot 加载都发到主人那家;主人没 key ⇒ 预设不在」,
  五种主槽换人序列(含无外壳存完即问、#16 MiMo→DeepSeek、额外槽变主槽);k12 = set_model.py 写带厂商的名字(#17);
  k10 加咬名字 + 按名字加载、k8 的 pop 改成真实预设名(#18)。
runlog: python rc=1 commit=627c28b dirty=yes at=2026-09-23T12:14:13Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T121413Z-01-python.txt
  (上一行 = 根因判据红:k11 五格全红,且逐份列出 —— 第一格里 `glm-5.3@glm_plan` 单独点名(=#15),另有模板自带的 MiMo 预设在首把 key 是 GLM 时就残留(同根);k12 红。)
- 变异自检(修法写好后,逐个拆掉修法的一部分看判据红不红):save 不对齐 / 主人没 key 不删 / 指 custom 一律当主槽 ⇒ k11 红;
  **老家快路径不对齐、起网关主路径不对齐两个变异存活** ⇒ 补 k11b(盘上已有的错指配置起网关就对齐:0.98.10 换过 DeepSeek 的老家 + 有额外槽的家)。
  v9 夹具原先靠「save 换主槽后 mimo-* 残留」造老形状,修后 save 不再造它 ⇒ 夹具改为照老样子直接写出(断言不变;新旧实现上都绿)。
runlog: python rc=1 commit=04e78b4 dirty=yes at=2026-09-23T12:18:21Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T121821Z-01-python.txt
  (上一行 = 补的 k11b 在修前代码上红;两个存活变异各被 k11b 的一格杀死。)
runlog: bash rc=3 commit=bc67483 dirty=no at=2026-09-23T12:18:45Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T121845Z-01-bash.txt
runlog: bash rc=0 commit=bc67483 dirty=yes at=2026-09-23T12:30:38Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T123038Z-01-bash.txt
  (上两行 = 按根因修后:总跑六段全过(python 1455,rc=3 只因既有 SKIP);判据三件套 + set_model 老判据 rc=0。)
- **追加第 5 轮的理由(派发前写)**:业主拍板走 B(按根因修),方向又变了一次(从「改名字」到「不变量:预设只发到主人那家」)⇒ 必须再审一轮;
  预算 = 1 轮(两家族,同成员 MiMo + Grok)。再有阻断:若与本根因同类 ⇒ 说明根因判定错了,停下交业主;若是新的不同类问题 ⇒ 逐条核实后按常规处置。

- 第 5 轮花名册: submimo=PASS(verdict=BLOCK) subcursor.grok-4.7-high=PASS(verdict=BLOCK)(两家族一致 BLOCK,主发现相同)
- findings(第 5 轮):

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | 19 | (两家)正用 Kimi 时 `set_model.py glm-5.3` ⇒ 写出裸名 `glm-5.3` 且抄走 od_kimi ⇒ glm-5.3 发到 Kimi 端点带 Kimi key;对齐认不出「两家都有」的裸名,起网关也不修 | 亲跑复现(active=glm-5.3,provider=od_kimi,nanobot 加载得 Kimi key + moonshot 端点) | **本单必须修** | 实际后果是 Kimi 报「没这个模型」(不会扣错钱),但违反不变量。**根子是两个写「当前模型」的入口**:界面走 select_model(认厂商、按厂商命名、分不清就拒绝),set_model.py 不认厂商。修法 = 我们管的配置里 set_model.py 改走 select_model(同一个入口),不给路由规则再加一格 |
  | 20 | (MiMo)业主手写预设名字以 `@kimi` 等结尾会被当成我们的删掉 | 属实(`_qualified_vendor` 只看后缀) | 本单必须修 | 「认不出主人不碰」的承诺被后缀撞名打破。修法:只认**我们自己会起的名字**(模型在那家目录里且名字正是 preset_name 的结果) |
  | 21 | (Grok)没写 provider 的手写预设被当成指 custom | 属实(nanobot 默认 auto) | 本单必须修(随 20) | 只动显式指 custom / od_* 的 |
  | 22 | (MiMo)set_model 不清「想换过去」标记,手选被下次起网关顶掉 | 属实 | 随 19 消失 | 同一入口 select_model(home=…) 本来就清(v18) |
  | 23 | (两家)k12 用 gateway_env() 问 ⇒ 先对齐再看,错的写法被纠正后才被看见;k11 只查留下的都对、不查活着那家的预设没被删;owner_of 与实现同构 | 属实 | 本单必须修 | k12/k13 改用网关此刻手里的 env;k11 加「活着的厂商默认预设必须在」;owner_of 改为按规格写(名字=那家会起的名字),与实现各写各的 |
  | 24 | (MiMo)手改配置后、**没外壳**的启动器起网关不跑对齐 | 读码属实(只有 ds_shell 调 prepare_gateway) | 驳回(不扩大) | 手写错指不是我们的写入口造的;没外壳 = git-pull/Linux 开发机,不是业主的装法;#16 那种老残留在没外壳的机器上是「报错不扣钱」 |
  | 25 | (MiMo)存第二家 key(额外槽)时 save 不对齐 | 属实 | 驳回 | v1 既定契约:存额外 key 时配置一个字节不动,对齐只在起网关时做 |

- **第 5 轮停不停的判断(按派发前写的预案)**:预案是「与本根因同类 ⇒ 根因判错了,停下交业主」。MiMo 认为是同类;我判不是:
  #19 不是「custom 槽换厂商」造成的,而是**第二个写入口绕开了命名**;修法是删掉第二个写入口(不是给路由加分支)。
  且业主已明示「从第一性原理修就好了」⇒ 继续修,把这一判断原样写进给业主的汇报。第 6 轮是最后一轮:再有阻断一律停下交业主。
- 第 5 轮判据(先红):k13/k13b/k13c(set_model 走同一入口:没 key 的厂商拒绝、两家 GLM 分不清拒绝、带 --provider 按厂商命名、手选盖过标记)、
  k14(手写预设不碰:`@kimi` 撞名、名模不一致、没写 provider)、k11 加「活着的厂商默认预设必须在」、k12 改用网关此刻的 env。
runlog: python rc=1 commit=cd0ab0f dirty=yes at=2026-09-23T12:47:52Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T124752Z-01-python.txt
  (上一行 = 第 5 轮判据红:k13 四处、k13b、k13c、k14。)
- 变异自检(第 5 轮修法):set_model 不走入口 / 不传 home / 额外槽也删 ⇒ 红;**「没写 provider 当 custom」存活**(k14 那份没写 provider 的名字本来就不是我们起的,问不到这一支)
  ⇒ k14 补一份「名字是我们会起的、但没写 provider」的预设;把上一版认主人的函数原样放回 ⇒ k14 红。
runlog: python rc=1 commit=3afb648 dirty=yes at=2026-09-23T12:50:59Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T125059Z-01-python.txt
  (上一行 = 补过的 k14 在修前代码上红。)
runlog: bash rc=3 commit=b033875 dirty=no at=2026-09-23T12:51:12Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T125112Z-01-bash.txt
runlog: bash rc=0 commit=b033875 dirty=yes at=2026-09-23T13:03:15Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T130315Z-01-bash.txt
  (上两行 = 第 5 轮修后:总跑六段全过(python 1465,rc=3 只因既有 SKIP);判据三件套 + set_model 老判据 rc=0。)
- **追加第 6 轮的理由(派发前写)**:第 5 轮两处实质修改(set_model 改走同一入口、所有权规则收窄)⇒ 必须再审;预算 1 轮、同成员。
  **这是最后一轮**:再有任何阻断 ⇒ 停下,原样交业主定(不再自己续轮)。
- 第 6 轮第一次派发(/root/aiwork/logs/panel-kimi-glm-r6-20260923-2103 [仓外不承重]):两腿都在 900s 被砍(rc=124),**无结论 = 基础设施失败,不算实质轮**。
  MiMo 残稿里的探针(E/F/G)全部要先手改配置(手写预设占用我们起的名字却填别的模型)或是旧版 set_model 留下的裸名,我们任何写入口都走不到;
  题面第 1 问本来就限定「我们的写入口」⇒ 重派时加长时限(MIMO_CLI_TIMEOUT=2100、CURSOR_TIMEOUT=1800,已知大单要这么久),题面加一句范围说明,问题不减。
  重派被健康闸拦(两腿因刚才的超时进入冷却)⇒ 用 PANEL_HEALTH_OVERRIDE 放回:超时原因已知(时限短,MiMo 残稿显示它在正常干活),时限已加长;不是腿坏了。

- 第 6 轮花名册: submimo=PASS(verdict=BLOCK) subcursor.grok-4.7-high=PASS(verdict=PASS)(冲突:MiMo BLOCK、Grok PASS;日志 /root/aiwork/logs/panel-kimi-glm-r6c-20260923-2120.* [仓外不承重])
- findings(第 6 轮):

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | 26 | (MiMo BLOCK)主槽是**自配端点**(install.ps1 `--api-base`,不用手改)+ 界面加了两家 GLM ⇒ set_model.py 走老分支:`--provider glm` 被无视,裸名 `glm-5.3` 抄走 od_glm_plan ⇒ 要按量、实际留在套餐(扣错钱) | 亲跑复现:rc=0,active=glm-5.3,provider=od_glm_plan,nanobot 加载得套餐 key + 套餐端点 | **阻断成立**;按预案停,交业主 | 第 5 轮「一个写入口」的闸设在「主槽认得出」,应设在「配置里有我们管的厂商槽」(`_live_vendors` 非空)。Grok 判 PASS 是因为它认定老分支只有手改才走到 —— install.ps1 的 `--api-base` 证明不需要手改 |
  | 27 | (两家)手写预设占用我们起的名字却填别的模型,那家有 key 时起网关 ②/③ 按名字改指 | 读码属实 | 延期(范围外) | 需手改配置;已发版本同样如此 |

- **状态:NEEDS_MORE_INFO(第 6 轮 = 预案里的最后一轮,再有阻断即停)**。给业主的选择:
  A. 修 #26(闸改成「有我们管的厂商槽就走统一入口」+ 一条判据),再审一轮;
  B. 本单先停在这里不发,等业主有空再定。
- **业主 09-23 晚选 A(「修掉这个」)。** 判据 k13d(自配端点 + 两家 GLM:set_model `--provider glm` 真发按量、不出裸名、没 key 的厂商拒绝;红)、
  k13e(反面:只有自配端点、没有我们的厂商槽 ⇒ 照老办法写;修前修后都得绿)。
runlog: python rc=1 commit=d179286 dirty=yes at=2026-09-23T14:24:41Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T142441Z-01-python.txt
  (上一行 = k13d 红,k13e 绿。)
- 变异自检:闸退回「主槽认得出」⇒ k13d 红;闸放开到任何配置 ⇒ k13e 红。
runlog: bash rc=3 commit=cb861bf dirty=no at=2026-09-23T14:25:38Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T142538Z-01-bash.txt
runlog: bash rc=0 commit=cb861bf dirty=yes at=2026-09-23T14:37:39Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T143739Z-01-bash.txt
  (上两行 = 修 #26 后:总跑六段全过(python 1473,rc=3 只因既有 SKIP);判据三件套 + set_model 老判据 rc=0。)
- **追加第 7 轮的理由(派发前写)**:业主选 A,改动只一处(set_model 的闸)⇒ 审这一处;预算 1 轮、同成员,时限一开始就给足(MiMo 2100s / Grok 1800s)。
  再有阻断 ⇒ 停下交业主。

- 第 7 轮花名册: submimo=PASS(verdict=BLOCK) subcursor.grok-4.7-high=PASS(verdict=PASS)(冲突:MiMo BLOCK、Grok PASS;日志 /root/aiwork/logs/panel-kimi-glm-r7-20260923-2237.* [仓外不承重])
- findings(第 7 轮):

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | 28 | (MiMo BLOCK)代码与规格一致(它自己认 Q1/Q2 过),但称闸的两种写残 M3「只看额外槽」/ M4「活厂商≥2」**穿过整个套件**,会在「只有主槽」的装法上复活 #19 | 亲跑变异(脚本 tracks/opendesign-kimi-glm-vendors/mut_gate_r7.sh):两个都被 **k13c** 杀死(它就是「主槽认得出、额外 key 还没进配置」的形状)。MiMo 只跑了 k13d/k13e 与自己的探针。Grok 同一格读码也点名 k13c 会杀「只看额外槽」 | **驳回「穿过整个套件」**;**采纳建议**:补一格直接问「只有主槽」的 k13f | 事实主张被收据证伪;但「靠 k13c 顺带杀」不如直接钉死 —— 补 k13f(只有 MiMo 主槽:要 glm-5.3 拒绝且不写、要本家模型走统一入口),M3/M4 在它上面各红一次 |
  | 29 | (MiMo)新分支 `.bak` 在 select_model 落盘后才写 | 属实 | 延期 | 内容仍是改前原文;失败路径不写 .bak;只有「.bak 那一下 I/O 失败」才缺备份 |

runlog: bash rc=0 commit=893cdc7 dirty=yes at=2026-09-23T14:55:14Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T145514Z-01-bash.txt
  (上一行 = #28 变异收据:两个闸变异都被 k13c 杀死,rc=0 = 没有存活。)
- **停不停**:预案「再有阻断 ⇒ 停」。这条阻断的事实前提被收据证伪、代码零改动;归档闸要求同一次评审里两家族一致 ⇒
  补 k13f 后请同两家复核(第 8 轮 = 仲裁复核,不是修复轮);仍冲突 ⇒ 停下交业主。
runlog: bash rc=0 commit=922bb7f dirty=no at=2026-09-23T14:56:54Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T145654Z-01-bash.txt
runlog: bash rc=0 commit=922bb7f dirty=yes at=2026-09-23T14:57:07Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T145707Z-01-bash.txt
  (上两行 = 补 k13f 后:闸变异收据(两个都被杀,k13f 也在杀手里);判据三件套 + set_model 老判据 rc=0。产品代码自 cb861bf 起零改动。)

- 第 8 轮花名册: submimo=PASS(verdict=BLOCK) subcursor.grok-4.7-high=PASS(verdict=PASS)(冲突:MiMo BLOCK、Grok PASS;日志 /root/aiwork/logs/panel-kimi-glm-r8-20260923-2257.* [仓外不承重])
  - Grok:#28 驳回成立(k13c/k13f 杀 M3/M4);另指出一种闸写残(主槽认得出 或 额外槽≥2)能穿过全部判据,留「自配端点 + 恰好一家额外槽」的洞 —— 非现行代码,测试网缺一格。
  - MiMo:新发现 #30 —— 老 PowerShell 安装脚本 `bin/install.ps1` 让机主手填 apiBase + model(→ `ds_merge_config --model`)写**共享模型裸名**
    (如 `glm-5.3 → custom`);之后界面存别家 key 进主槽 ⇒ `_route_presets` 认不出主人不碰 ⇒ glm-5.3 发到别家。亲核:install.ps1:127-134 确有这两问。
- **状态:NEEDS_MORE_INFO,按预案停**(第 8 轮后不修、不续轮)。交业主:A 修 #30(+ Grok 那一格判据)再审一轮 / B #30 记延期另开单、本单照常收尾。
- **业主 09-23 晚:修 #30,评审加上 DeepSeek 和 GPT**(同时把 codex 腿换成 gpt-6-sol,aiwork track codex-leg-gpt6-sol 已归档)。
  判据:k15(安装合并按厂商命名共享模型;装 GLM 套餐后换 Kimi 每份预设仍发到主人那家)、k15b(已装 MiMo 重装换 DeepSeek,合并后对齐)—— 红;
  k13g(Grok:自配端点 + 恰好一家额外槽,set_model 走统一入口)—— 现代码绿,套上 Grok 那种闸写残即红(亲跑)。
runlog: python rc=1 commit=3c88167 dirty=yes at=2026-09-23T15:39:30Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T153930Z-01-python.txt
  (上一行 = k15、k15b 红。)
- 夹具修正(判据面,单独 commit):修 #30 时合并器改为 import 同目录的 ds_credential,test_ds_provision 15 条红 ——
  原因是它的假安装目录只拷了合并器一个文件;出货包 `tracks/opendesign-windows-installer/spike/build-package.sh:258` 是 `cp bin/*.py`。
  夹具改成同形拷 bin/*.py(不拷整仓,原注释的用意保留);旧合并器 + 新夹具、新合并器 + 新夹具都绿。
- 变异自检(#30 修法):合并后不对齐 ⇒ k15/k15b 红;不按厂商命名 ⇒ k15 红。
runlog: bash rc=3 commit=f4f510a dirty=no at=2026-09-23T15:43:31Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T154331Z-01-bash.txt
runlog: bash rc=0 commit=f4f510a dirty=yes at=2026-09-23T15:55:50Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260923T155550Z-01-bash.txt
  (上两行 = 修 #30 后:总跑六段全过(python 1489,rc=3 只因既有 SKIP);判据 + 合并/出货安装/set_model 老判据 rc=0。)
- **第 9 轮派发(派发前写)**:业主要求评审加上 DeepSeek 和 GPT。正式评审 = MiMo + Grok + DeepSeek(三家族,计入归档);
  GPT(subcodex,gpt-6-sol)是角色腿、不进普通池(工具设计:GPT 也是执行腿)⇒ 同题单独派,结论入账、逐条核实,但不计入归档覆盖。
  本单代码全由主 agent 写,不存在「GPT 审自家代码」。有阻断 ⇒ 停下交业主。

- 第 9 轮花名册: submimo=PASS(verdict=BLOCK) subcursor.grok-4.7-high=PASS(verdict=BLOCK) subdeepseek=PASS(verdict=BLOCK)(日志 /root/aiwork/logs/panel-kimi-glm-r9-20260923-2356.* [仓外不承重]);GPT(subcodex gpt-6-sol,不计覆盖):BLOCK(/root/aiwork/logs/codex-kimi-glm-r9-20260923-2356.log [仓外不承重])
- findings(第 9 轮,四家全 BLOCK;未修,按预案停):

  | # | 发现 | 谁 | 处置 |
  |---|---|---|---|
  | 31 | 老安装脚本填**认得出的端点 + 别家的共享模型名**(如 Kimi 端点 + glm-5.3)⇒ 合并写裸名 glm-5.3、指 custom ⇒ 发到 Kimi;对齐认不出裸共享名,之后也修不掉。#30 只修了「模型在这家目录里」那一半 | MiMo/Grok/DeepSeek 三家独立同一条 | 待业主定 |
  | 32 | 判据缺口:k11 的 owner_of 对裸共享名瞎(结构上看不见 #30/#31 形状);k15 只钉 glm-5.3 一个名字、只测套餐端点;合并路径的悬空回落与 presetParams(Kimi temperature)无判据 | MiMo/DeepSeek | 待业主定 |
  | 33 | 重跑老安装脚本:已有 key.txt 就跳过录 key,但仍允许换成别家端点 ⇒ 新端点配旧 key(报认证错,不扣错钱;已发版本就有) | GPT(HIGH) | 待业主定 |
  | 34 | 普通更新合并现在也对齐:名字像我们起的、主人没槽的手写预设会被删,当前模型可能回落 | DeepSeek(INFO) | 与 k14「我们的名字」口径一致,记录 |
  | 35 | check-package.sh 的必需文件清单没有 ds_credential.py / ds_model.py | DeepSeek(LOW) | 待业主定 |

- **主裁判断**:#31/#33 的共同根子是**老 PowerShell 安装脚本让机主手填任意「端点 + 模型」**,这是第六个写入口,且和界面里「选厂商 → 填 key」重复;
  出货的一键安装包(ds_provision)不走这两问。第一性原理的修法是把手填端点/模型这两问从老安装脚本撤掉(换厂商一律走界面),或合并器拒绝「认得出但不成对」的端点/模型并要求重录 key。
- **状态:NEEDS_MORE_INFO,停**。交业主。

## 第 9 轮后改设计(业主 09-24「不如直接抄 zcode」→「可以 那你开始吧」)

- 同类缝第九次出现 ⇒ 不再补缝,回头改设计(见 design.md「第 9 轮四家全 BLOCK 后改设计」)。
- 4c 方案挑战:一条读仓的不同家族腿(Grok 4.7,xai),主裁方向先落盘仓外、未喂给它;原文与题面存 evidence/20260924-design-challenge-*.md。
  改变了两处决定:稳态清扫(不等端点变)、认不出主人的名字只删不改指。
- 处置第 9 轮发现:#31/#33 = 写口删除(d1/d2),盘上存量由 d7/d8 管;#32 = d3 穷举五家两两换 × 有无外壳 × 每家每个模型的裸名/限定名/手写名;
  #34 与新规矩一致(记录);#35 = d6。
- 判据(单独 commit):tests/test_vendor_one_door.py d1~d8 新增;k14「名模不一致」一格、k15/k15b、test_ds_merge_config 两条显式参数判据退场,
  test_existing_brain_survives_a_plain_remerge 的「模板预设要合进来」改判(那些 MiMo 预设会发到机主自配的端点)。
runlog: redesign-red rc=1 commit=02a2b02 dirty=yes at=2026-09-24T00:36:50Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260924T003650Z-01-redesign-red.txt
  (上一行 = 新判据红:d4 护栏绿,其余 50 格全红。)
- 本次评审预算(派发前写):改设计后 **2 轮实质评审**,high = 每轮两个不同家族;有真实阻断就停下交业主,不续轮。
- 实现(`4836d9e`):判据全绿;变异自检六个(去掉稳态清扫 / 裸名留在主槽 / 忽略端点变化 / 永远当端点变了 / 合并照合模板 / 合并收参数)全被杀。
runlog: redesign-mutants rc=0 commit=edc6608 dirty=yes at=2026-09-24T00:39:07Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260924T003907Z-01-redesign-mutants.txt
runlog: run-all rc=3 commit=edc6608 dirty=yes at=2026-09-24T00:39:24Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260924T003924Z-01-run-all.txt
  (上两行 = 实现在工作树上时:总跑六段全过(python 1494、node 509、e2e 41),rc=3 只因既有 3 条 SKIP(两条要活网关的 e2e + 一条 python)。
   之后只改了 install.ps1 两句提示文字,d1 复跑绿。)

- 第 10 轮花名册(改设计后第 1 轮实质评审): submimo=PASS(verdict=BLOCK) subdeepseek=PASS(verdict=BLOCK)(日志 /root/aiwork/logs/panel-kimi-glm-r10-20260924-0901.* [仓外不承重])
  反锚定:复审轮,verify.md 已含第 9 轮处置与本轮改设计说明,腿读到属预期(4b ②);主审自审在仓外 /root/aiwork/tasks/opendesign-kimi-glm-vendors-r10-my-review.md。
  DeepSeek 另跑 60 轮 × 100 步随机序列(五个入口混跑,每步交 nanobot 加载器问端点+key):0 违规 —— 新设计的主张成立,阻断都在边上。

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | 36 | (MiMo A)合并:主槽是认不出的自配端点、机主**没有**自己的预设(纯 onboard)⇒ 模板 MiMo 预设照合、modelPreset 被设成 mimo-v2.5,压过机主的 agents.defaults.model ⇒ MiMo 模型名发到他的端点,聊天连不上 | 读 ds_merge_config.py:125 的 `own_presets` 条件属实;本单前就有,但合并是本单「写口」名单里的一扇 | 本单必须修 | 正是「名字属于 A、发到 B」;自配端点一律不合模板预设,modelPreset 只留机主自己有的,没有就不设(悬空的删掉) |
  | 37 | (MiMo B)稳态清扫把「目录模型 + 非正式名」一律删:主槽 GLM 套餐 + 老安装写的裸名 glm-5.3-flash(路由本来正确、正在用)⇒ 删掉并回落 glm-5.3,**业主选的模型被换** | 读 _route_presets 新分支属实;是本轮引入的回归;d7/d8 只种了默认模型,问不到 | 本单必须修 | 模型在它所在那格厂商的目录里 ⇒ **原地改成正式名**(不换格、不换模型),当前模型跟着改名;只有那格厂商没有这个模型才删(Grok 担心的跨格改指仍不做) |
  | 38 | (MiMo C)同一家再存一次 key(换 key)⇒ save 把当前模型重置成那家默认 | 读 save 末段属实;历史行为 | 本单修 | 小改动;「当前模型被无故换掉」是本单写明要挡的;端点没变就不动当前模型 |
  | 39 | (DeepSeek 1)合并路径的对齐没有判据:删掉合并末尾两行全绿 | 属实(k15b 退场带走了这条性质) | 本单必须修(判据) | 老 git-pull 形态上合并是唯一一次清扫;补 d9 |
  | 40 | (DeepSeek 2)install.ps1 强制填 MiMo 的 key ⇒ 没有 MiMo key 的人要么装不完、要么把别家 key 塞进 MiMo 槽(401,界面还显示已配置) | 读 install.ps1 Step 6 属实 | 本单修 | 回车可跳过,提示装完在界面里选厂商填 key |
  | 41 | (DeepSeek 3)手写的 od_kimi 预设被删后回落到主槽默认、跨厂商 | 只能手改配置造出;#37 的「原地改名」后,模型在该格目录里的不再删 | 延期 | 剩下的只有「手写预设的模型那格厂商根本没有」—— 本来就发不通;业主那边长成:手改过配置的人换回了主槽默认模型 |
  | 42 | (DeepSeek 4/5、MiMo 4)install-windows.md 手动合并一节仍教改端点、测试/合并器注释过时 | 属实 | 本单修 | 文字 |
  | 43 | (MiMo 3)d3 只查指 custom 的、裸共享名留在新主槽不判违规、没有额外槽在场的组合;d4 不问当前模型 | 属实 | 本单修(判据) | d3 改查「每份指我们槽位的目录模型都是那格厂商的正式名」,加额外槽在场的组合;d4 加当前模型不变 |
  | 44 | (MiMo 残留)select_model 对已存在的正式名预设只纠 provider 不纠 model | 只能手改造出 | 本单修 | 一行;与不变量对齐 |
  | 45 | (MiMo 5)d1 是文本闸 | 属实 | 延期 | 对「不再问端点/模型」够用;install.ps1 是老装法,业主那边长不出东西 |

- 本轮修复清单 = #36~#40、#42~#44,判据先 commit(红),再一次修完,派第 2 轮(预算最后一轮)。
runlog: r10-criteria-red rc=1 commit=a99efaa dirty=yes at=2026-09-24T01:19:15Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260924T011915Z-01-r10-criteria-red.txt
  (上一行 = 第 10 轮判据红:d4b×2、d5b×2、d7b×4、d9(glm-5.3-flash 一格)、d10、d11;d3 改成问整条不变量 + 额外槽在场后现实现仍绿。)
runlog: r10-mutants-fixed rc=0 commit=403b634 dirty=yes at=2026-09-24T01:22:17Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260924T012217Z-01-r10-mutants-fixed.txt
runlog: r10-mutants rc=2 commit=403b634 dirty=yes at=2026-09-24T01:21:43Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260924T012143Z-01-r10-mutants.txt
  (上两行按时间倒序:先跑的 rc=2 里 M1/M2「存活」是假的 —— 代码改了,它们要替换的原文已不存在,脚本没打上变异就跑了测试;
   脚本加了 BROKEN 分支(替换失败大声报),M1/M2 按新代码重写后全杀。)
runlog: run-all-r10 rc=3 commit=403b634 dirty=yes at=2026-09-24T01:22:41Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260924T012241Z-01-run-all-r10.txt
  (上一行 = 修完第 10 轮清单后总跑:六段全过(python 1500、e2e 41),rc=3 仅既有 3 条 SKIP。)
- 业主插话「遵循第一性原理别忘了 不要留下屎山」⇒ 派最后一轮前回头审整条逻辑:起网关 ②③ 与 _route_presets 三处都在改指,收成一处(见 design.md)。
  自查补出一条没人盯的规矩(指向已删额外格的预设):先补判据 d12,再加变异 M13。
runlog: r10-mutants-after-cleanup rc=0 commit=403b634 dirty=yes at=2026-09-24T01:44:29Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260924T014429Z-01-r10-mutants-after-cleanup.txt
runlog: d12-red-on-403b634 rc=1 commit=403b634 dirty=yes at=2026-09-24T01:45:23Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260924T014523Z-01-d12-red-on-403b634.txt
runlog: r10-mutants-final rc=0 commit=403b634 dirty=yes at=2026-09-24T01:45:33Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260924T014533Z-01-r10-mutants-final.txt
  (上三行 = 收层后 12 个变异全杀;d12 在修复前代码上是绿的(老 ① 本就会删),rc=1 来自其余未修判据 —— d12 的红检靠变异 M13:删掉那条规矩 ⇒ d12 红;最终 13 个变异全杀。)

runlog: run-all-final rc=3 commit=fab85c8 dirty=no final=yes at=2026-09-24T01:47:07Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260924T014707Z-01-run-all-final.txt
  (上一行 = 派第 11 轮前,干净树 final:六段全过(python 1501、node 509、e2e 41),rc=3 仅既有 3 条 SKIP。)
- 第 11 轮 = 改设计后第 2 轮(预算最后一轮):MiMo + DeepSeek,同成员复核 #36~#44 与收层;有真实阻断 ⇒ 停下交业主,不续轮。

- 第 11 轮花名册(改设计后第 2 轮 = 预算最后一轮): submimo=PASS(verdict=BLOCK) subdeepseek=PASS(verdict=BLOCK)(日志 /root/aiwork/logs/panel-kimi-glm-r11-20260924-1000.* [仓外不承重])
  两家都确认:#36~#44 在正常入口上成立;DeepSeek 270 条随机序列(含老安装脏数据注入)0 次发错家;MiMo 也没找到新的跨家扣钱路径。阻断全在边缘形状与判据缺口:

  | # | 发现 | 核实 | 可达性 | 处置 |
  |---|---|---|---|---|
  | 46 | (MiMo F1)合并:自配端点 + 机主有预设 + 从没设过 modelPreset ⇒ 替他设成第一份,压过 agents.defaults.model | 读 ds_merge_config.py:137 `elif own_presets` 不区分「悬空」与「没设」属实;本单前就有 | 要手改配置才有这形状 | 待业主定 |
  | 47 | (MiMo F2)界面 save 同一家,当前模型写在 agents.defaults.model(没有 modelPreset)⇒ 被换成默认 | 读 save 末段属实 | 我们的安装总会写 modelPreset,要手改 | 待业主定 |
  | 48 | (MiMo F3)主槽自配端点 + 额外格 key 文件没了 ⇒ modelPreset 悬空、网关起不来 | 读 _fallback_if_dangling 属实;0.98.9 起就有 | 界面没有删 key 的入口,要手删文件 | 待业主定 |
  | 49 | (MiMo F4)老合并已经污染过的自配端点配置,新合并不修 | 属实;主槽认不出时不碰是设计 | 老 git-pull 自配端点的机器 | 建议延期:认不出的端点上替人猜归属就是又一个写口 |
  | 50 | (DeepSeek 1)改名补 presetParams 那一行删掉,全部判据仍绿 | 属实(判据缺口) | Kimi 的非正式名只能手改出 | 待业主定 |
  | 51 | (DeepSeek 2)悬空回落主槽默认只被夹具字典序顺带钉住 | 属实(判据缺口,钱轴) | — | 待业主定 |
  | 52 | (DeepSeek 3/5)同家换 key 的择一条件没被考;手删 key.txt 后同家从额外格挪进主槽当前型号回默认 | 属实,低 | 手删文件 | 待业主定 |
  | 53 | (DeepSeek 4)`_qualified_vendor` 死代码 | 全仓无调用方,属实 | — | 待业主定(一行删除) |

- **状态:NEEDS_MORE_INFO,按预案停**(预算 2 轮已用完,有阻断不自行续轮)。交业主:A 一次小修(#46~#48、#50~#53,多为判据与边缘)+ 追加 1 轮 / B 记延期、本单按现状收尾(需业主接受这些边缘形状)。
- **业主 09-24 选 A,不加界面提示**(先问了「zcode 是怎么做的」:ZCode 选择 = 厂商+模型一对,用不了就报「不可用」让人重选,
  不改原选择、不自动清库;老配置只迁能确认的用户意图)。本轮照它的原则修:**能不动用户的选择就不动**;
  非动不可(nanobot 要求当前模型有效才肯启动)才回落,且只回主槽那家、不随便挑。#49 延期(认不出的端点上不替人猜)。
- **追加 1 轮的理由(派发前写)**:具体阻断 = #46~#48(三处替用户改了当前模型 / 悬空)、#50/#51(钱轴判据缺口);
  目的 = 核验这批修法;新预算 = 1 轮(MiMo + DeepSeek)。这一轮若只剩「要手改配置才碰得到」的边缘形状 ⇒ 记延期收尾,不再续轮。
- 判据:d4c(#52)、d4d(#47)、d5c(#46)、d12b(#48)红;d7b 加 Kimi 改名带 temperature(#50)、d13 回落不落到排在最前的别家(#51)—— 现实现即绿,
  靠变异 M14/M15 证明它们咬得住。
runlog: r11-criteria-red rc=1 commit=10d0bbe dirty=yes at=2026-09-24T02:44:12Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260924T024412Z-01-r11-criteria-red.txt
runlog: r11-mutants-before-fix rc=0 commit=10d0bbe dirty=yes at=2026-09-24T02:44:14Z file=tracks/opendesign-kimi-glm-vendors/evidence/20260924T024414Z-01-r11-mutants-before-fix.txt
  (上一行**不算证据**:跑的时候判据里还有 4 条红,任何变异都会「被杀」。修完在全绿基础上重跑。)

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>

## 试行记录(review-convergence 试行,约五单;拿不到的写 unknown,别补 0)

- 总交付历时:<开工 commit 时刻 → 归档 commit 时刻>
- 每轮新增有效阻断:<第 1 轮 n / 第 2 轮 n>
- 基础设施等待:<重试次数;observations 里 panel-review 的 duration_ms 求和>
- 交付后返工:<归档后因本单再改过几次;不知道写 unknown>
