# Verify: opendesign-shell-chrome

- Date: 2026-08-17
- Verdict: <PASS | BLOCK | NEEDS_MORE_INFO>

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [ ] build passes
- [ ] tests pass
- [ ] no secrets / unsafe ops

**机器打印的**(不是我的转述)—— 判据用 `runlog` 跑,把它打印的收据行原样粘进来:

```
runlog -t opendesign-shell-chrome -- <判据命令>
```

```
<粘收据行,逐字节,别改数。**每次提交**都会跟 evidence/ 里的收据逐字节比对(5a);
 **归档时**还要求:最后跑的那一遍必须在这儿、跑红的那几遍一份都不许藏(5b)、
 收据得进 git(5d)。一份收据都没有的话,写一行
 「- 无机器证据:<理由>」认账 —— 沉默不算理由(5c)。>
```

## Review

- lane: **fast**(主 + 1 腿)
  > 硬规矩那五样一样没碰:零新写口、零权限/auth、不花钱、不动档案格式。
  > 但也够不上 self —— self 限"纯前端/纯观感、后端一字未动",而这一单动了
  > `bin/ds_shell.py`(外壳那层)。且无边框之后这三个按钮是**业主唯一能关掉窗口的出口**,
  > 坏了他只能上任务管理器 ⇒ 不在这儿降档。
- 派给: **主 agent 直接干** —— 针孔只有三处(一个常量、一个地址、一个判断),
  而**判据是本单的大头**(要新造一份真 chromium e2e 把"栏会不会被画出来"从
  "只有真机答得了"变成 Linux 答得了)。根因要现场读 pywebview 5.4 源码定语义,
  派出去等于把"根因对不对"一起外包;判卷要起 ds_web + chromium,我这边现成。
- 规格自查(读任何 panel 输出之前先答):**最可能的错法是"我修的不是他撞的那个病"。**
  分三种:
  ① 地址标记这条路本身不成立(query 被路由/服务吞掉)—— 已被真 chromium e2e 当场问掉,
     它是"业主症状在 Linux 上的复现",不是代理量;
  ② 根因在别处(比如他机器上跑的根本不是新 dist、或 WebView2 缓存了旧页面)——
     判据一条都答不了,所以真机清单第一条改成**先自报版本**(`/api/health` 里的号
     + 窗口栏在不在),分辨"没装上"和"装上了还坏";
  ③ pywebview 在 Windows 上对 URL 做了我不知道的处理(它不会,但 Linux 上证不了)——
     真机清单 A 组一眼可见:有按钮 = ③ 不成立。
  另外**这一单改了两条现存判据的问法**(s-w1/s-w2),证据方向写在判据注释里:
  不是"红了所以改",是 pywebview 源码证明旧问法在真运行时里问不出东西。
- 腿的花名册: <把 `<日志前缀>.roster` 里那一行**原样粘过来**,别手写>
  > panel-review 收尾自己写这个文件(off / FAIL(rc) / 降级 都在里面)。
  > 08-06 立这条的理由:08-05 我在这里手写了"三条腿一致 PASS",而 Kimi 根本没出结论
  > (同一页第 90 行我自己还写着它没出报告)—— 手抄一份终端上的东西,抄错那次没人会发现。
- findings:
  - <...>
  > 只写发现。腿的身份/降级不在这儿抄第二遍:日志自带身份牌(降级横幅 + 视野边界),
  > 花名册在上一格,查工件不查自述。
- arbitrated verdict (主裁): <...>
  > **归档时这一条和顶部的 `Verdict:` 都不许还是占位符**,`track-guard` 规矩3 会挡;
  > 没归档但已经合并上线的,`track list` 会打 ⚠️(stage-timer 就这么漏了两个月)。

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>
