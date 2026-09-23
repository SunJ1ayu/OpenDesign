# Verify: opendesign-quiet-start-icons

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
runlog -t opendesign-quiet-start-icons -- <判据命令>
```

```
runlog: node rc=1 commit=9532d5d dirty=yes at=2026-09-23T08:44:08Z file=tracks/opendesign-quiet-start-icons/evidence/20260923T084408Z-01-node.txt
```
(上一行 = 判据先行红检:q1~q4 + 改过的 s4 五条红,其余 26 条绿。)

```
runlog: bash rc=1 commit=087bf1c dirty=yes at=2026-09-23T08:46:51Z file=tracks/opendesign-quiet-start-icons/evidence/20260923T084651Z-01-bash.txt
```
(上一行 = 实现后第一遍总跑:只红「dist 新鲜度」一段 —— 入库 dist 还没随改动重建提交;node 506 / python 1436 / e2e 41 全过。)

```
<粘收据行,逐字节,别改数。**每次提交**都会跟 evidence/ 里的收据逐字节比对(5a);
 **归档时**还要求:最后跑的那一遍必须在这儿、跑红的那几遍一份都不许藏(5b)、
 收据得进 git(5d)。一份收据都没有的话,写一行
 「- 无机器证据:<理由>」认账 —— 沉默不算理由(5c)。>
```

## Review

- 规格自查:用户成功条件 = ①冷启动顶上一个字都没有 ②侧栏图标像 ZCode(统一细线)。两条都是业主原话拍板,不是我推导的。
  前提已核:ZCode `RootStartupLoading.tsx` 只有 logo 无文字;侧栏 lucide(`WorkspaceSidebar.tsx` / `NewTaskButtonGroup.tsx` / `WorkspaceSidebarFooter.tsx:382`)。
  未暴露能推翻方向的前提。残余风险(业主已知情):真遇到后台要等很久时只看到转圈 —— 管家崩了仍弹框退出(bs4/bs5 未动)。
- impact = self(纯前端观感,后端/外壳/写口/权限一字未动;preload/main 的后台状态通道原样保留)⇒ 外部评审预算 0,未派腿。
  **判据迁移账**(撤掉的断言必须说清去向,不许无声变少):
  - fb1(横幅有中文字)、fb3(横幅不许说「马上」)—— 对象整个删除,改由 q1 反向钉「web/src 里没有那句话、没有横幅元素/样式、backendState.ts 不存在」。
  - s4 后半 `App 有 backendBanner/backend-connecting` → 反向 `App 没有 backend-connecting`;前半(preload/main 通道)原样。
  - e2-drive E2.connecting「有横幅」→「没有横幅」;E2.noreload 原来借「横幅 30 秒内消失」,改为 launchReady 等到后台就绪后 +2s 查 navs===1 且标记还在(不借横幅,判的仍是「不重新加载」)。
    这两条只在云 Windows 跑,**本单没跑云**,留给下一张发版单的云 run 兑现(见 Accepted deviations)。
- 渲染亲看:本地 ds_web + Chromium 截侧栏(2x),五个 SVG 实测 16×16、颜色跟行文字(新对话行 rgb(44,42,38) 加粗当前态,其余 rgb(92,87,76)),
  线条清楚、与文字基线对齐;截图在 scratchpad `side-after.png` [仓外不承重]。历史对话行本地没网关出不来,只靠 q4 静态判。
- 腿的花名册: 无(self,预算 0,未派 panel)
- arbitrated verdict (主裁): PASS —— 两条业主原话逐条兑现,判据先行红→绿,全量回归见上方收据;云 Windows 两条留发版单。

## Accepted deviations

- 云 Windows e2e(E2.connecting 反向 / E2.noreload 改判)本单未跑:要打安装包才能跑,并入下一张发版单的云 run;红了算本单的账。
- 「新对话」图标原来是赭色强调(`.ico.terra`),换成跟文字同色(照 ZCode);当前态靠加粗白底卡片区分,不靠图标颜色。
- 未 bump 版本:发不发、何时发由业主定,bump 跟发版单走。

## 试行记录(review-convergence 试行,约五单;拿不到的写 unknown,别补 0)

- 总交付历时:<开工 commit 时刻 → 归档 commit 时刻>
- 每轮新增有效阻断:<第 1 轮 n / 第 2 轮 n>
- 基础设施等待:<重试次数;observations 里 panel-review 的 duration_ms 求和>
- 交付后返工:<归档后因本单再改过几次;不知道写 unknown>
