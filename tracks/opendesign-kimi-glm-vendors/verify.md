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

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>

## 试行记录(review-convergence 试行,约五单;拿不到的写 unknown,别补 0)

- 总交付历时:<开工 commit 时刻 → 归档 commit 时刻>
- 每轮新增有效阻断:<第 1 轮 n / 第 2 轮 n>
- 基础设施等待:<重试次数;observations 里 panel-review 的 duration_ms 求和>
- 交付后返工:<归档后因本单再改过几次;不知道写 unknown>
