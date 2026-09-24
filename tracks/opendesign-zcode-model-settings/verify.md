# Verify: opendesign-zcode-model-settings

- Date: 2026-09-24

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
runlog -t opendesign-zcode-model-settings -- <判据命令>
```

```
<粘收据行,逐字节,别改数。**每次提交**都会跟 evidence/ 里的收据逐字节比对(5a);
 **归档时**还要求:最后跑的那一遍必须在这儿、跑红的那几遍一份都不许藏(5b)、
 收据得进 git(5d)。一份收据都没有的话,写一行
 「- 无机器证据:<理由>」认账 —— 沉默不算理由(5c)。>
```

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

- 规格自查(读任何 panel 输出之前先答):<回看 design 的用户成功条件、前提证据和未解决项。
  实现符合规格不证明规格合理;实现评审也可质疑规格,但不能替代实施前 panel 4c 的方案检查。
  本轮若暴露能推翻方向的前提,先回到设计;全池一致 PASS 也不等于题是对的。>
- 腿的花名册: <把 `<日志前缀>.roster` 里那一行**原样粘过来**,别手写>
  > panel-review 收尾自己写这个文件(off / FAIL(rc) / 降级 都在里面)。
  > **控制器没活到收尾时它压根不存在** —— 那时跑 `panel-roster <日志前缀>` 从盘上重建,
  > 与控制器自己写的**归一化后一致**(判据 R5b 守着;抬头有渲染时间戳,不是字面逐字节)。**一轮零记录的评审也粘得出这一行**,
  > 所以"那轮被砍了所以没有花名册"不再是理由(2026-08-23,track panel-roster-from-disk)。
  > 08-06 立这条的理由:08-05 我在这里手写了"三条腿一致 PASS",而 Kimi 根本没出结论
  > (同一页第 90 行我自己还写着它没出报告)—— 手抄一份终端上的东西,抄错那次没人会发现。
- 轮次记录(每次派发一行;实质评审与基础设施重试分开,重试不算轮但次数与耗时照记):

  | 轮 | 类型(实质 / 重试) | 派发前 `track preflight` | 日志前缀 | 新增有效阻断 |
  |---|---|---|---|---|
  | 1 | 实质 | <rc,BLOCK 数> | <…> | <n> |

- findings(**先处置、后动手**;一轮一份修复清单,一次修完再复审 —— panel 抽屉 4b):

  | # | 发现:触发条件与影响 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | 1 | <…> | <file:line / 复现收据> | 必须修 / 延期 / 驳回 / 尚未核实 | <延期必写:它在业主或下一个使用者那边会长成什么样> |

  > 只写发现。腿的身份/降级不在这儿抄第二遍:日志自带身份牌(降级横幅 + 视野边界),
  > 花名册在上一格,查工件不查自述。延期 = 留在这里,不自动开新单。
- arbitrated verdict (主裁): <...>
  > 这里写理由；最终枚举写进 `decision.json.outcome.verdict`。归档时仍为空会被
  > `track-record validate --phase archive` 挡住，`track list` 也会打 ⚠️。

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>

## 试行记录(review-convergence 试行,约五单;拿不到的写 unknown,别补 0)

- 总交付历时:<开工 commit 时刻 → 归档 commit 时刻>
- 每轮新增有效阻断:<第 1 轮 n / 第 2 轮 n>
- 基础设施等待:<重试次数;observations 里 panel-review 的 duration_ms 求和>
- 交付后返工:<归档后因本单再改过几次;不知道写 unknown>
