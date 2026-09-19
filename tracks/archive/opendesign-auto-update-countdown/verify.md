# 接续验收：启动直接更新（2026-09-19）

## 需求和现场

- 09-18 用户已确认继续取消倒计时方案；从 9e7f95d 接续。原有 5 个测试文件修改及两条变异修复收据保留。
- 旧方案 Windows run 35222749618 只证明旧交互；新方案不能沿用其通过结论。
- 判据先行：旧源码跑新前端单测 48/50（shouldAutoUpdate 尚不存在）；旧 dist 跑新浏览器流程 15 条失败。

## 实现与自审

- 移除倒计时常量、计时器、取消按钮及相关状态；启动 checking/updating/ready 三阶段控制工作区挂载。
- 检查回包先同步 updateInfoRef，再立即安装，避免拿到 render 前的旧数据；effect 重放不重复请求。
- 安装成功交棒后继续等待重启；失败进入旧版，保留失败文案、服务端防循环和手动出口。
- 只读检查 35 秒超时并取消，迟到回包不能自动安装；安装本身不套该超时。
- 逐项保留后端原有协议；本次没有修改后端产品或安装器。
- 原外审阻断：mutation harness 的 M8/M13/M26 锚点修复与 ds-web n1/n3/n4 锚点修复已在接续现场，09-17 收据均通过；错误的函数名自证声明现已撤回。
- 新增前端逻辑由本次主 agent 自审，未把旧方案的外审 PASS 当作新方案外审结论。

## 机械验证

- 前端单测 50/50；后端及 Windows harness 209/209；TypeScript/Vite 构建通过。
- 新浏览器流程单跑通过；全仓 browser 41 PASS / 0 FAIL / 2 SKIP（两个依赖活 gateway 的既有场景）。
- 全仓 node 451 通过；MCP 三闸通过；泄漏闸 14 通过。
- 全仓 Python 1727 条中 1 失败、1 跳过：失败是构建后 CSS 改动导致 dist 不同步，非产品断言失败；零死断言。重新构建后复核 dist 判据 8/8 通过，见 evidence/20260919-startup-dist-tests.txt。
- 全仓 dist 段要求产物已提交；ad06d2d 后单独复核产物 3 文件逐字节一致，见 evidence/20260919-startup-dist-fresh.txt。
- Windows 新方案九场景通过，本机用当前判定器对原始 facts-e1..e9 再判全部通过。run 35415559169 的 head 是 ad06d2d，原始事实存 evidence/ci-35415559169/。e9 清单到下载 0.938731 秒，总下载 1 次，回滚后 health_final=0.98.6、relay_again=false、why_not=attempted/recent_failure=true。
- 前端 M1~M5 全部命中预期行为失败，见 evidence/20260919-startup-mutation.txt。本轮没有重跑已经通过且未改动的后端变异测试。
- 第 2 轮复审已完成并由主 agent 仲裁；结论及覆盖见文末。未正式发布。

## 外审处置与轮次（接续记录）

- 第 1 轮（2026-09-17）实质评审，主提交 9e7f95d；旧倒计时方案。日志前缀 `/root/aiwork/logs/panel-opendesign-auto-update-countdown-review-r1-20260917-2111`。旧控制器无本轮 preflight 收据，记 unknown；不补造。
- 原样花名册：`submimo=PASS(verdict=PASS) subdeepseek=PASS(verdict=BLOCK) subglm=off subkimi=off subgemini=off subgrok=off`。
- 第 2 轮派发前预检第一次 BLOCK=1 为新增收据尚未暂存，暂存后复核；此前没有已完成的第二轮，不把修改/构建/Windows 流水线算外审。实质预算共 2 轮；第 2 轮核对修复与用户变更后的启动行为。无真实阻断且机械门满足即结束。

| 发现及影响 | 核实证据 | 处置 | 理由 |
|---|---|---|---|
| 第一轮 DeepSeek：mutation harness M8/M13/M26 锚点失效，测试未实际变异 | tests/mutation-update-e2e-harness.py；09-17 r1fix-mutation-harness 收据 | 本单必须修，已修 | 恢复本次承诺依赖的校验；29/29 变异命中原收据 |
| 第一轮 DeepSeek：verify 声称删除不存在的两个函数能红 | 当前源码无该函数，旧验收文字现明确撤回 | 本单必须修，已修 | 无法复现的结论不能当证据 |
| 自审接续：ds-web mutation n1/n3/n4 锚点随资格逻辑移动而失效 | tests/mutation-ds-web-update.sh；09-17 r1fix-mutation-ds-web 收据 | 本单必须修，已修 | 既有校验恢复，无额外产品变化 |
| 第一轮 DeepSeek：shell port 字符串带空白时 no_shell | bin/ds_web.py 对环境变量 fullmatch；外壳产生纯数字 | 延期 | 手工篡改环境为带空白时会少一次自动更新；正常外壳不产生该值 |
| 第一轮 DeepSeek：另一窗口在安装进行中可能显示“上次没成功” | recent_failure 根据预写时间，非完成状态 | 延期 | 两窗口并存且一次自动安装尚未结束时，另一窗口的短暂文案不精确；安装锁和防循环未失效 |
| 第一轮 MiMo：未知版本时显示“新版本” | 后端有更新时必给 latest，且 canApply 守卫版本 | 驳回 | 实际更新来源不产生该状态 |

### 历史失败收据认账

- impl-e2e / impl-e2e-ac-c-red：手动按钮的 React 事件被误当 auto=true，已由显式手动回调与严格布尔判定修复，fix1-e2e 随后通过。
- mutation-frontend 首次 rc=1：变异锚点/红检匹配错误；后续修正的 mutation-frontend-2 与当前 M1~M5 均能命中具体失败行。
- 09-17 run-all rc=3：仅两个依赖 gateway 的既有场景跳过，不是全部执行通过；当前全仓也保留这两个 SKIP。

```text
runlog: oracle-red-python rc=1 commit=bdad422 dirty=yes at=2026-09-17T11:36:17Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T113617Z-01-oracle-red-python.txt
runlog: oracle-red-node rc=1 commit=bdad422 dirty=yes at=2026-09-17T11:36:42Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T113642Z-01-oracle-red-node.txt
runlog: oracle-red-e2e rc=1 commit=bdad422 dirty=yes at=2026-09-17T11:36:49Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T113649Z-01-oracle-red-e2e.txt
runlog: baseline-run-all rc=143 commit=a057f6b dirty=no at=2026-09-17T11:50:56Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T115056Z-01-baseline-run-all.txt
runlog: oracle-v2-red-python rc=1 commit=a057f6b dirty=yes at=2026-09-17T12:04:55Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T120455Z-01-oracle-v2-red-python.txt
runlog: oracle-v2-red-node rc=1 commit=a057f6b dirty=yes at=2026-09-17T12:05:24Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T120524Z-01-oracle-v2-red-node.txt
runlog: oracle-v2-red-e2e rc=1 commit=a057f6b dirty=yes at=2026-09-17T12:05:25Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T120525Z-01-oracle-v2-red-e2e.txt
runlog: oracle-v3-red-python rc=1 commit=ea81c72 dirty=yes at=2026-09-17T12:23:19Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T122319Z-01-oracle-v3-red-python.txt
runlog: oracle-v3-red-node rc=1 commit=ea81c72 dirty=yes at=2026-09-17T12:23:49Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T122349Z-01-oracle-v3-red-node.txt
runlog: oracle-v3-red-e2e rc=1 commit=ea81c72 dirty=yes at=2026-09-17T12:23:49Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T122349Z-02-oracle-v3-red-e2e.txt
runlog: impl-e2e rc=1 commit=eeb59c1 dirty=yes at=2026-09-17T12:35:19Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T123519Z-01-impl-e2e.txt
runlog: impl-e2e-ac-c-red rc=1 commit=d6a42bb dirty=yes at=2026-09-17T12:37:03Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T123703Z-01-impl-e2e-ac-c-red.txt
runlog: mutation-frontend rc=1 commit=a532761 dirty=no at=2026-09-17T12:43:15Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T124315Z-01-mutation-frontend.txt
runlog: run-all rc=3 commit=77798b5 dirty=no at=2026-09-17T12:57:31Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T125731Z-01-run-all.txt
runlog: r1fix-mutation-harness rc=0 commit=9e7f95d dirty=yes at=2026-09-17T13:34:44Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T133444Z-01-r1fix-mutation-harness.txt
runlog: r1fix-mutation-ds-web rc=0 commit=9e7f95d dirty=yes at=2026-09-17T13:34:59Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T133459Z-01-r1fix-mutation-ds-web.txt
```

## 历史验收（倒计时版本）

# Verify: opendesign-auto-update-countdown

- Date: 2026-09-17

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录
> `decision.json`；这里保留检查、理由、发现与主 Agent 仲裁说明，不复制枚举。

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再按 impact-risk 预算跑 panel-review；只有特殊控制面
> 才显式 `--all` 做全池评审。最后仍由主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

旧模板勾选位不作为当前验收；构建、测试与安全边界详见文首机械验证和最终仲裁。

**机器打印的**(不是我的转述)。

### 判据先行:实现之前的红(基线 bdad422 + 判据改动,未提交时跑)

- python:au1~au5、au7~au10、au12 + t9a 红,**缺 auto_update / 没记账 / 没二次把关**,红的原因都对。
  au6 / au11 在基线就绿 —— 它们是**防修过头**的反面判据(手动那条路不许被自动那条路连累),基线手动那条路本来就对,结构上红不了。
- node:ac1~ac8 全红(函数不存在)。
- e2e:AC-A / AC-B / AC-D 红(没有横幅)、AC-C 红一半(设置里没有解释)。AC-E / AC-F 与 AC-C 的"不出横幅"是**什么都不该发生**的守卫,基线本来就什么都不发生,结构上红不了;它们的咬合要等实现落地后用变异证(把「只在打开后第一次自动查」那道闸去掉)。
- Windows 判定器:aw1~aw4 在本机随判定器一起写。旧记录声称删掉 `_auto_update_eligible` / `_auto_not_retried` 后分别红 9 / 11 条，但当前代码没有这些函数，缺可复现证据，撤回该声明（09-17 外审指出）。实际 Windows 旧方案收据见后续记录；不能用于证明新方案。

```
runlog: oracle-red-python rc=1 commit=bdad422 dirty=yes at=2026-09-17T11:36:17Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T113617Z-01-oracle-red-python.txt
runlog: oracle-red-node rc=1 commit=bdad422 dirty=yes at=2026-09-17T11:36:42Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T113642Z-01-oracle-red-node.txt
runlog: oracle-red-e2e rc=1 commit=bdad422 dirty=yes at=2026-09-17T11:36:49Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T113649Z-01-oracle-red-e2e.txt
```

### 判据第二版:攻题之后(派活之前)

- 第三方攻题(GPT-5.6-sol,只读)报 19 条;逐条核对后改规格 5 处、改考卷 12 处、驳回 3 条、接受 1 条。
  攻题记录在仓外(进仓 = 把考卷的洞递给考生),**收货之后**再把处置表并进本文件。
- 最重的三条都是结构性的:Windows 真机场景会被产品自己的倒计时抢跑(且外壳 child_env 剥掉 `DS_*`,开关名必须避开)、
  接力脚本回滚后业主眼前没有任何说明、「10 秒」没有被真正量过。
- 第二版红:python au1~au5、au7~au10、au9b/au9c、au12a~e、au13~au15 + t9a 红(au6 / au11 仍是基线结构上红不了的反面判据);
  node ac1~ac9 红;e2e AC-A / AC-B / AC-C(设置解释)/ AC-C2 / AC-D / AC-H 红,AC-E / AC-F 是"什么都不该发生"的守卫。
  Windows 判定器 aw1 / e9 / H8 本机全绿(判定器与脚本静态检查,不依赖产品)。

```
runlog: oracle-v2-red-python rc=1 commit=a057f6b dirty=yes at=2026-09-17T12:04:55Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T120455Z-01-oracle-v2-red-python.txt
runlog: oracle-v2-red-node rc=1 commit=a057f6b dirty=yes at=2026-09-17T12:05:24Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T120524Z-01-oracle-v2-red-node.txt
runlog: oracle-v2-red-e2e rc=1 commit=a057f6b dirty=yes at=2026-09-17T12:05:25Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T120525Z-01-oracle-v2-red-e2e.txt
```

### 判据第三版:第二轮攻题之后(派活之前)

- 第二轮只攻 v2 增量,报 11 条:1 条是我的错(au8 仍按两字段断言,合规实现必红),8 条成立已改,1 条驳回为规格
  (查更新不许等更新锁),1 条接受为规格(`os.fsync` / `os.replace` 模块属性调用)。v3 是这 11 条处置的直接落实,未再攻第三轮。
- 第三版红:python 26 条红(au1~au5、au7~au10、au9b/c、au12a~e、au13~au15、au15b + t9a),au6 / au11 绿;node ac1~ac9 红;e2e 7 条没过。

```
runlog: oracle-v3-red-python rc=1 commit=ea81c72 dirty=yes at=2026-09-17T12:23:19Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T122319Z-01-oracle-v3-red-python.txt
runlog: oracle-v3-red-node rc=1 commit=ea81c72 dirty=yes at=2026-09-17T12:23:49Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T122349Z-01-oracle-v3-red-node.txt
runlog: oracle-v3-red-e2e rc=1 commit=ea81c72 dirty=yes at=2026-09-17T12:23:49Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T122349Z-02-oracle-v3-red-e2e.txt
```

### 基线总跑被我中途停掉(内存)

本机 2G 内存,攻题(codex)与基线总跑并跑时系统杀了两个等待进程;为保攻题,我停掉了总跑(rc=143,半截)。实现落地后重跑。

```
runlog: baseline-run-all rc=143 commit=a057f6b dirty=no at=2026-09-17T11:50:56Z file=tracks/opendesign-auto-update-countdown/evidence/20260917T115056Z-01-baseline-run-all.txt
```

历史模板中的空白 Review/Accepted deviations/试行记录已移除；正式处置、轮次及当前结论以文首接续验收为准。

接续环境 node --test 只回报文件级 1 项，不能作为 50 条断言收据；改用 node tests/test_update_ui.mjs 直接执行，50/50 通过，不修改测试。最终收据采用直接执行。

## 14:10 接续收尾

- 第 2 轮派发前预检：BLOCK=0 PENDING=2 ERROR=0 OK=5，rc=3；待定为外审/仲裁及最新收据引用，非实现失败。
- Windows 原始 JSON/TSV 保留 CRLF 字节；普通 diff --check 的报错均为这些原始收据的 CR，不改写验收事实。用 cr-at-eol 检查其余空白问题。

```text
runlog: startup-final-direct rc=0 commit=ad06d2d dirty=yes final=yes at=2026-09-19T03:52:05Z file=tracks/opendesign-auto-update-countdown/evidence/20260919T035205Z-01-startup-final-direct.txt
```

- 第 2 轮基础设施重试：首次派发前 oracle rc=0，但沙箱拒绝 unshare，只读挂载未能建立；MiMo/Grok rc=78，DeepSeek 回落也失败，无合格外审结论。日志前缀 `/root/aiwork/logs/panel-opendesign-immediate-startup-r2-20260919-1420`。
- 获准后原题在宿主环境重试，产品及判据未改，日志前缀 `/root/aiwork/logs/panel-opendesign-immediate-startup-r2-host-20260919-1413`；oracle 再次 rc=0。这是第 2 轮实质复审的基础设施重试，不能把控制器第 3 次派发误报成第 3 轮实质评审。

- 第 2 轮宿主重试结果：MiMo PASS，GLM 代理及聊天回落均余额不足（401），Kimi 周额度耗尽（403）。未获得同轮两个家族的覆盖，不能归档。
- 再试目的仅为完成缺失覆盖；有限预算：再派一次 MiMo + Cursor（Grok），禁用已失败的额度通道。无产品/判据变更，不新增实质审查范围。
- MiMo 发现处置：它把旧总跑的 dist 不同步称为低风险，驳回此风险分类；若产物仍旧应阻断。实际已由 ad06d2d 中产物、20260919-startup-dist-tests.txt 的 8 项复核和 20260919-startup-dist-fresh.txt 的逐字节一致证明修复，不留作延期缺陷。MiMo 在仓库根目录运行 npm build 的 ENOENT 是其命令目录错误，真实构建目录是 web，已有成功构建收据。

## 最终仲裁（2026-09-19）

当前承诺成立：检查/自动安装期间不挂载工作区；合格新版立即请求；交棒后等重启；检查超时及明确安装失败放行旧版；自动尝试预写、防重入和回滚不重试保留，手动出口可用。主 agent 亲读前后端及判据、核对原始 Windows facts，并亲看 e9-end.png 的失败说明。没有未解决的阻断项。

- 最终复审：MiMo（xiaomi/mimo-v2.5-pro）与 Cursor/Grok 两个不同家族同轮、同一交付内容，均给出 PASS；没有代码返工，不再续轮。
- Cursor/Grok 明确只读核验，没有执行测试；其报告的证据边界属实：Windows e9 覆盖真实页面自动触发、注入失败及回滚，e1/e6/e8 覆盖成功安装和重启；浏览器 AC-A 覆盖更新后重新加载进入工作区。不能称为 Windows 单个自动更新成功的完整场景。
- MiMo 重试报告将 451 node/41 browser 的数量挂到单项收据文件，引用不精确；以本文件机械验证为准：单项 node 50、单项后端 209；全仓 node 451、browser 41/0/2 在 startup-all 和 startup-all-e2e。数字未据外审自述改写。
- 两条旧低风险观察仍留在发现表，不另开单。安装请求服务端完全无响应时页面仍等待，因为取消前端等待不能证明安装停止；没有加入新的取消或超时协议。
- 正式发布、版本号变更及用户电脑加载新版不在本单范围。当前为已实现、已验收的可发布代码。

### 实际派发记录

第 2 轮首次派发（沙箱失败）：
```text
submimo=FAIL(rc=78) subdeepseek=FAIL(rc=1,降级:回落聊天腿也没成) subglm=SKIP(rotation) subkimi=SKIP(rotation) subgemini=SKIP(health:dead:FAIL:6) subgrok=FAIL(rc=78) subcursor=SKIP(rotation)
```

第 2 轮基础设施重试 1（缺额度）：
```text
submimo=PASS(verdict=PASS) subdeepseek=SKIP(health:cooldown:FAIL) subglm=FAIL(rc=1,降级:回落聊天腿也没成) subkimi=FAIL(rc=1) subgemini=SKIP(health:dead:FAIL:6) subgrok=SKIP(rotation) subcursor=SKIP(rotation)
```

第 2 轮基础设施重试 2（最终覆盖）：
```text
submimo=PASS(verdict=PASS) subdeepseek=off subglm=off subkimi=off subgemini=off subgrok=off subcursor=PASS(verdict=PASS)
```

本单共 2 轮实质评审；第 2 轮有 2 次基础设施重试。4 次 panel 控制器累计记录 1472518 ms（约 24.54 分钟），含失败和缺额度等待，不含人工授权等待；不是 4 轮产品返工。第 1 轮新增有效阻断 2 项（变异锚点失效、不可复现的验收声明），第 2 轮新增有效阻断 0 项。交付后返工 unknown，尚未正式发布。
