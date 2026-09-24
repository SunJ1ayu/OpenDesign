# Verify: opendesign-release-09812

- Date: 2026-09-24

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录
> `decision.json`；这里保留检查、理由、发现与主 Agent 仲裁说明，不复制枚举。

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再按 impact-risk 预算跑 panel-review；只有特殊控制面
> 才显式 `--all` 做全池评审。最后仍由主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [x] build passes(云 run 36012748964 出货包)
- [x] tests pass(run-all 六段过、rc=3 仅既有三条 SKIP;云 141 OK / 0 FAIL)
- [x] no secrets / unsafe ops(发布经业主授权:09-24 22:1x 选「现在就发」)

**机器打印的**:

```
runlog: run-all rc=3 commit=8326ccb dirty=no final=yes at=2026-09-24T14:25:23Z file=tracks/opendesign-release-09812/evidence/20260924T142523Z-01-run-all.txt
runlog: cloud-e2e rc=0 commit=8326ccb dirty=yes at=2026-09-24T14:45:21Z file=tracks/opendesign-release-09812/evidence/20260924T144521Z-01-cloud-e2e.txt
runlog: prod-smoke-12 rc=0 commit=ae33c3d dirty=no at=2026-09-24T15:00:18Z file=tracks/opendesign-release-09812/evidence/20260924T150018Z-01-prod-smoke-12.txt
```

- run-all rc=3 = 六段全过(python 1535 / node 514 / e2e 42),3 条既有 SKIP 要起 gateway。
- cloud-e2e = run 36012748964(head `8326ccb`,payload + e2e 两个 job 都 success):**141 OK / 0 FAIL**;E1 安装包名 0.98.12;
  E4 被测版上更新链(0.98.12 → 替身 0.98.13:「重启以更新」→ 向导两下 → 自己重开、三方版本一致)走通。
- prod-smoke-12 = 发布后从 GitHub 正式地址取回:正式版;latest 清单 = 0.98.12;安装包 / blockmap 字节 = artifact;
  旧 blockmap `download/v0.98.11/` 在;tag v0.98.12(`ae33c3d`)与被测 `8326ccb` 非 tracks 源码一致。

## QA(测试员,业主 09-24 定「每单都用」;发版单的 QA = 以业主视角看发版说明与真机清单)

| 次 | 腿 | 日志前缀 [仓外不承重] | 结论 | 抓到的(已照改) |
|---|---|---|---|---|
| 1 | DeepSeek、Grok | explore-release-09812-qa-20260924-222655 | 两家都「改完再发」 | **我初稿写「打开软件会自动更新」是错的**(Electron 版要点「重启以更新」,核 0.98.11 说明与云 E4 属实);厂商 / 模型名不是界面原文;开关位置写错;测试结果是一行字不是弹窗;没说 API Key 格子空着是正常的;没说更新不换当前模型;清单缺「更新」与「原来的没被动」两步、各步没写看到什么算过 |
| 2(复看) | DeepSeek、Grok | explore-release-09812-qa-retest-20260924-224741 | 两家都「改完再发」(主路径能走) | **说明里写了录像的假 key「tp-q…cdef」**;左栏不写「在用」;子菜单会翻到左边;不填上下文就没有 K 标签;第 1 步死等没退路;「半屏宽」比我们量过的 1024 还窄;加模型那步要点「保存」、提示原文 —— 照它们给的句子改,不再第三次复看 |

- 发版说明终稿 = GitHub release v0.98.12 正文(https://github.com/SunJ1ayu/OpenDesign/releases/tag/v0.98.12);真机清单终稿见下「业主真机」。

## Review

- 规格自查:仓外 `/root/aiwork/tasks/opendesign-release-09812-review-my-review.md` [仓外不承重](派发前落盘,暂判 PASS)。
- 腿的花名册:
  - 第 1 次(基础设施失败):`subdeepseek=PASS(verdict=PASS) subkimi=FAIL(rc=1)` —— Kimi 周额度用完(403 weekly usage limit),不是审出问题;按「不许跨 run 拼接」整轮重派。
    派发后才补跑 `track preflight`(rc=3,BLOCK 0)—— 顺序错了,如实记账。
  - 重试:`subdeepseek=PASS(verdict=PASS) subcursor.grok-4.7-high=PASS(verdict=PASS)`(`/root/aiwork/logs/panel-opendesign-release-09812-retry-20260924-225249.roster` [仓外不承重])
- 轮次记录:

  | 轮 | 类型 | 派发前 `track preflight` | 日志前缀 | 新增有效阻断 |
  |---|---|---|---|---|
  | — | 基础设施重试(Kimi 额度) | 派发后补跑 rc=3,BLOCK 0 | panel-opendesign-release-09812-20260924-224633 | — |
  | 1 | 实质 | rc=3,BLOCK 0 | panel-opendesign-release-09812-retry-20260924-225249 | 0 |

- findings(两家都 PASS,照报项):

  | # | 发现 | 核实证据 | 处置 | 理由 |
  |---|---|---|---|---|
  | 1 | (DeepSeek LOW)本单云跑 E4 测的是 0.98.12→替身 0.98.13;真 0.98.11→0.98.12 这一跳用的是 0.98.11 里的更新器 | 0.98.11 发版单云跑已用同一对版本号 + 同一 blockmap 路径走通(那单 evidence cloud-e2e) | 接受 | 生产第一跳的代码在业主机器上、已走通过两次(0.98.9→10、10→11 同一套) |
  | 2 | (DeepSeek LOW)业主真机没有归档前证据 | proposal「不承诺」 | 接受 | 事后补记 |
  | 3 | (DeepSeek)归档前要填 verdict / 收据 | —— | 本单流程内 | 已填 |
  | 4 | (DeepSeek INFO)c4 只钉 package.json == ds_web.VERSION,不钉 lock 根版本 | 当前三处一致 | 延期 | 业主那边:lock 根版本不进安装包名与更新判断,不一致只影响仓里记账 |

- 升级不断聊天:DeepSeek 把 v0.98.11 整棵树取出来,用两份 0.98.11 形态老配置(无 models.json;主槽 MiMo / 主槽 + GLM 额外槽且当前在 GLM)新旧对跑,`current` 与 `modelPreset` 完全相同,新树只多出 v2.6 预设。
- arbitrated verdict (主裁): **PASS**。发布前评审同一次两家族 PASS、0 阻断;QA 两次把发版说明从「会让业主以为没更新」改到能照走;
  云 run 36012748964 141 OK / 0 FAIL、head = 被测 `8326ccb`、版本三处一致;09-24 23:0x 发布正式 release v0.98.12,中文说明已换上,生产源 smoke 10 项全 OK。
  **当天归档**;业主真机回显事后补在下面。
- 业主真机(待补),清单终稿:

  # 0.98.12 真机清单(装好后照着走;1~5 必做,6~8 有条件才做)

  任何一步结果和下面写的不一样:停手,截图发我,别自己猜着改设置。

  1. **更新**:打开软件,等半分钟到一分钟,侧栏最底下「设置」那一行会出现「重启以更新」→ 点它 → 安装向导按两下(下一步、完成)→ 新版自己打开。
     然后点「设置」→「常规」,「软件更新」下面那行字里有「当前版本 v0.98.12」= 过。
     等了一两分钟还没出现「重启以更新」:点「设置」→「常规」,把「软件更新」那一栏截图给我,别干等。
  2. **原来的没被动**(先别改任何东西):点「返回工作区」,输入框右下角的按钮还是更新前那个模型名;打一句话发出去,正常回复 = 过。
  3. **模型设置**:「设置」→「模型设置」。左边五行还是 MiMo(小米)、DeepSeek 官方、Kimi 按量、GLM 套餐(Coding Plan)、GLM 按量,以前填过 key 的几家是绿点;
     点你在用的那家(应该是 MiMo(小米)),右边写着「在用 · 已存 」加你 key 的头尾几位;API Key 格子是空的(正常);
     小米的模型列表里有 mimo-v2.6-pro 和 mimo-v2.6-flash = 过。
  4. **测试**:在 MiMo 页点 mimo-v2.6-pro 那一行的「测试」,等一两秒,模型列表下面出现一行「MiMo(小米) / mimo-v2.6-pro 连接成功」= 过(花一点点额度,正常)。
     写「连接失败」就把那一行截图给我。
  5. **换到 v2.6**:回工作区,点输入框右下角的模型按钮 → 把鼠标停在「MiMo(小米)」上(不用点)→ 旁边弹出的列表里点 mimo-v2.6-pro(输入框贴着窗口右边时列表在左边)
     → 按钮上的字变成 mimo-v2.6-pro;发一句话,正常回复 = 过。
  6. (想试加模型才做)在 MiMo 页点「+ 添加模型」,模型 ID 填 `mimo v2.7`(中间带空格),点「保存」→ 弹窗里出现「模型 ID 不对:只能用字母、数字和 . _ - : / +,不超过 128 个字符」、列表不多出行 = 这一下过。
     改成 `mimo-v2.7-preview`(上下文窗口可以不填),再点「保存」→ 上面出现「已添加 mimo-v2.7-preview」,列表多一行(没填上下文就没有 K 小标签),这行有「删除」= 过。
     回聊天框,模型按钮 → 停在「MiMo(小米)」上,弹出的列表里有 mimo-v2.7-preview = 过。小米没开放这个模型的话发消息会失败,正常,回模型设置把这行删掉即可。
  7. (有别家 key 才做)在那家填 key、点「保存」→ 先是黄点「未就绪」,下面写「已保存 …,后台重启后就能在聊天里选…」,先别退出;
     几秒后变绿点「就绪」,下面可能写着「后台已开始换上这把 key:稍等几秒就能在聊天里选这家的模型」→ 直接回聊天框,菜单里有这一家,选它的模型发一句能回 = 过。
     一直不变绿就点右上「刷新」再等一会儿;还不变就截图给我,别反复点。只有弹窗说「没能自己重启」才退出 OpenDesign 再打开。
  8. (有中转才做)右上「添加供应商」→ 填名称、Base URL、API Key、模型(一行一个)→ 点「添加供应商」→ 等它变绿 →
     点某个模型的「测试」,出现一行「你起的名字 / 模型名 连接成功」→ 聊天框里选它发一句,能回 = 过。

  最后:把窗口拖窄到屏幕宽度的一半多一点(不用更窄),模型设置里左边五家名字、每行的「测试 / 编辑」、右上「刷新 / 添加供应商」都还看得见、点得到 = 过。

## Accepted deviations

- 业主真机结果不在归档前承诺里(见 proposal「不承诺」),事后补记。

## 试行记录(review-convergence 试行,约五单;拿不到的写 unknown,别补 0)

- 总交付历时:09-24 22:2x 立单(`8326ccb`)→ 23:0x 发布并归档,约 45 分钟
- 每轮新增有效阻断:第 1 轮 0(QA 两次改说明不算评审轮)
- 基础设施等待:重试 1(Kimi 周额度);云 Windows 整跑约 20 分钟、评审约 5 分钟、QA 两次各约 5 分钟
- 交付后返工:unknown(刚归档)
