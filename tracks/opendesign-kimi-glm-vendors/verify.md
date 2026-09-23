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

- findings(第 1 轮):

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | 1 | (MiMo,Grok 也点到)`POST /api/llm/model` 不带 provider 且两家 GLM 都活时,`hits[0]` 静默改成 glm_plan,改走套餐端点+套餐 key | `bin/ds_credential.py:303-310` 读码属实;调用方:现界面 `modelSelectBody` 总带 provider,外壳前后端同包发 ⇒ 装好的软件里走不到 | **本单必须修** | 同名模型是本单引入的新暴露面,落在「扣错钱」轴上;修法小:缺 provider 时优先保留预设现在的归属,多家都能用且无归属 ⇒ 拒绝并要求指明厂商(判据 k8) |
  | 2 | (MiMo)k7b 只看 generation.temperature,不走 `_build_kwargs` 真出口 | 读 `tests/test_kimi_glm_vendors.py` 属实 | **本单必须修**(随清单一起) | 考卷证明「主槽 Kimi 真发出的值」这条当前承诺时隔了一层;改成与 k7 同一出口,成本一行 |
  | 3 | (两家)ku3 是源码字符串匹配,可被「假链接 + 真 UI 另画」骗过 | 属实 | 延期 | 当前实现经截图核过(卡片外链文字/href 随下拉变);这是「挡不住任意未来错误实现」类,不扩大本单承诺。在业主那边:将来有人改卡片时可能漏掉链接而考卷仍绿 —— 发版单云 e2e 截图兜一次 |
  | 4 | (MiMo)k7 只钉 temperature,不钉全部出参;kimi-k3 可能另有拒收参数 | 属实,但无真 key 问不出 | 延期 | 已知未知(design 前提 2);业主那边的样子:选 Kimi 聊天报参数错误,改表一行即修 |
  | 5 | (MiMo)`rel` 可写 `noopener noreferrer` | noreferrer 在 Chromium 已含 noopener 语义 | 驳回 | 行为等价 |
  | 6 | (Grok)k7 `>= 1.0` 放过 1.5 | 1.5 同样被 Kimi 接受(拒的是 <1.0) | 驳回 | 断言与真实约束同形 |

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>

## 试行记录(review-convergence 试行,约五单;拿不到的写 unknown,别补 0)

- 总交付历时:<开工 commit 时刻 → 归档 commit 时刻>
- 每轮新增有效阻断:<第 1 轮 n / 第 2 轮 n>
- 基础设施等待:<重试次数;observations 里 panel-review 的 duration_ms 求和>
- 交付后返工:<归档后因本单再改过几次;不知道写 unknown>
