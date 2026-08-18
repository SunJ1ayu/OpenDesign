# Verify: e2e-gateway-dependency

- Date: 2026-08-18
- Verdict: <待主裁>

## Mechanical checks

- [x] build passes(无 build:只改 `tests/e2e/`;变异用的是 dist,已 `git checkout` 还原并核对)
- [ ] tests pass(权威那一遍见下)
- [x] no secrets / unsafe ops(改动=一段 `page.route` + 注释,产品代码零改动)

**机器打印的**(不是我的转述)——四种条件的收据,逐字节:

```
runlog: redcheck-A-before-nogateway rc=1 commit=aafd008 dirty=yes at=2026-08-18T06:40:36Z file=tracks/e2e-gateway-dependency/evidence/20260818T064036Z-01-redcheck-A-before-nogateway.txt
runlog: green-nogateway rc=0 commit=aafd008 dirty=yes at=2026-08-18T06:42:26Z file=tracks/e2e-gateway-dependency/evidence/20260818T064226Z-01-green-nogateway.txt
runlog: redcheck-B-mutant-connectcard rc=1 commit=aafd008 dirty=yes at=2026-08-18T06:43:14Z file=tracks/e2e-gateway-dependency/evidence/20260818T064314Z-01-redcheck-B-mutant-connectcard.txt
runlog: green-after-mutation-restore rc=0 commit=aafd008 dirty=yes at=2026-08-18T06:43:52Z file=tracks/e2e-gateway-dependency/evidence/20260818T064352Z-01-green-after-mutation-restore.txt
runlog: green-with-gateway rc=0 commit=aafd008 dirty=yes at=2026-08-18T06:44:19Z file=tracks/e2e-gateway-dependency/evidence/20260818T064419Z-01-green-with-gateway.txt
```

| 收据 | rc | 它证明什么 |
|---|---|---|
| `redcheck-A-before-nogateway` | 1 | **改之前**、无 gateway ⇒ 2 FAIL。病是真的 |
| `green-nogateway` | 0 | 改之后、无 gateway ⇒ 2 PASS。**病好了** |
| `redcheck-B-mutant-connectcard` | 1 | 把 dist 里 `data-ui="connect-card"` 改名 ⇒ 2 FAIL。**判据仍咬得动,不是永远绿** |
| `green-after-mutation-restore` | 0 | 变异还原后回绿(`git checkout` + grep 双查:原标记 1、变异残留 0) |
| `green-with-gateway` | 0 | 改之后、**有** gateway ⇒ 2 PASS。**不再受环境摆布** |

**权威的那一遍(默认口径 e2e 总跑,不带 `--with-gateway`)**:

```
<AUTHORITATIVE>
```

## Review

- lane: **fast**
  > 判据:full 的硬触发器(新写口 / 权限 / auth / 钱 / 数据一致性)一条没碰 ——
  > **产品代码零改动**,只在两条 e2e 里加了一段 `page.route`。
  > **不判 self**:模板里 self 限"纯前端/纯观感、后端一字未动、只新增已过审针孔的调用方",
  > 而本单改的是**判卷防线本身**,风险不在那一档 —— 改判据最该怕的是"改成永远绿",
  > 那是要有人复核的事,不该我自己说了算。(变异红检已经堵了这一条,但那是我自己的证据。)
- 派给: **主 agent 直接干** —— 改的是判据,硬规矩「oracle 永远由主 agent 亲自写,绝不外包」。
  改动一段 route + 注释,写任务书的成本远高于自己动手。
- 规格自查(读任何 panel 输出之前先答,原文保留):
  这单的"规格"= **「让 e2e 进入登录态的正确做法是拦 bootstrap 回 401」**。
  它最可能错在:**401 这条路是否真的等价于"业主机器上的未连接态"**。
  如果不等价,后果是这两条 e2e 从"依赖环境"变成"测了一个现实中不存在的状态" ——
  那比原来的假红更坏(假红至少吵,假绿不吵)。
  我的依据是因果链三段都读了源码(`ChatPage:753` / `reconnect:88` / `connection:93`),
  且**探针实测**了无 gateway 时的真实界面(8s 后「连接不上」提示,连接卡不出现)。
  **但我必须记账:今天我在同一件事上已经判错过两次** ——
  先把"依赖活网关"当成既成事实写进归档工件(其实从没验证过),
  又把它判成"产品 bug"并向业主提了产品方案(其实产品是对的)。
  两次都是**读得不够就下结论**。所以这一格我给自己的信心打折,请腿重点看这条。
- 腿的花名册: <收尾时原样粘 roster>
- findings:
  - <待填>
- arbitrated verdict (主裁): <待填>

## Accepted deviations

- **`redcheck-B` 变异的是 `web/dist` 而不是源码**:e2e 加载的就是 dist,变异它更贴近
  真实加载路径,也省掉一次 build。风险是 dist 被改脏 ⇒ 已用 `git checkout` 还原,
  并用 grep 双查(原标记 1 / 变异残留 0),`git status` 干净。
