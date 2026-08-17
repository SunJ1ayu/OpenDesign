# Verify: opendesign-shell-chrome

- Date: 2026-08-17
- Verdict: **PASS(代码面)—— 欠业主真机一趟**(`真机清单-0.91.0.md`,含 0.89/0.90 欠的两趟)

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [x] build passes(dist 新鲜度那一段:重新 build 后 git 无差异)
- [x] tests pass(五段全跑,见下面最后一行收据)
- [x] no secrets / unsafe ops(只动了一个 query 参数、一个前端判断、一句日志;
      不碰凭据/网络/写口/档案格式)

**机器打印的**(不是我的转述)—— 判据用 `runlog` 跑,把它打印的收据行原样粘进来:

```
runlog -t opendesign-shell-chrome -- <判据命令>
```

```
runlog: e2e-------HEAD rc=1 commit=58d7cb6 dirty=yes at=2026-08-17T13:54:54Z file=tracks/opendesign-shell-chrome/evidence/20260817T135454Z-01-e2e-------HEAD.txt
runlog: redcheck-e2e-unfixed-head rc=1 commit=58d7cb6 dirty=yes at=2026-08-17T13:55:09Z file=tracks/opendesign-shell-chrome/evidence/20260817T135509Z-01-redcheck-e2e-unfixed-head.txt
runlog: redcheck-e2e-unfixed-head rc=1 commit=58d7cb6 dirty=yes at=2026-08-17T13:55:31Z file=tracks/opendesign-shell-chrome/evidence/20260817T135531Z-01-redcheck-e2e-unfixed-head.txt
runlog: runall-0.91.0 rc=1 commit=4f4f5c0 dirty=no at=2026-08-17T13:59:49Z file=tracks/opendesign-shell-chrome/evidence/20260817T135949Z-01-runall-0.91.0.txt
```

**上面这四遍都不是最终收据,一份不藏,逐条说清楚**(规矩 5b):

- 第 1 行 **量具坏了,不算判据结果**:我给了一个空的家目录,`chromium` 缓存接不上
  ⇒ 红在 `ENOENT ms-playwright`,不是红在被测的东西上。
  (这正是 `tests/e2e/run-all.sh` 里写着的那场"31 条秒挂假红"的形状,我又踩了一次。)
- 第 2 行 **红检,但只有汇总**:走 `tests/e2e/run-all.sh` 代跑,收据里只有
  `FAIL shell_chrome.e2e.mjs`,断言细节留在它自己的临时日志里 ⇒ 汇总级收据没用。
- 第 3 行 **这才是那份红检**:未修的 HEAD 上 11 条红(A/C/D 段),
  **B 段(浏览器无标记 ⇒ 零按钮)是绿的** —— 对照组在同一份收据里。
- 第 4 行 **dist 新鲜度那一段红是我自己造的**:那一遍在跑的时候我又改了源码
  (`window_url()` 收口 + `pywebviewready` 等待),于是"入库的 dist 是旧的"。
  其余四段全绿(node 376 / python 1276 / MCP 三闸 / e2e 36 PASS 0 FAIL 2 SKIP)。
- 还有一遍 `runall-0.91.0-withgw`(`evidence/20260817T141213Z-…`)**是我中途掐掉的**,
  所以那份收据没有末行:掐掉的原因是评审 F1/F3 要改判据,让它跑完也是过期收据。
  **不删,留在 evidence 里认账。**

**最终代码(`c82dcbc`)上跑了两遍,红的那遍也留着:**

```
runlog: runall-0.91.0-final rc=1 commit=c82dcbc dirty=no at=2026-08-17T14:25:12Z file=tracks/opendesign-shell-chrome/evidence/20260817T142512Z-01-runall-0.91.0-final.txt
runlog: runall-0.91.0-final-r2 rc=0 commit=c82dcbc dirty=yes at=2026-08-17T14:46:38Z file=tracks/opendesign-shell-chrome/evidence/20260817T144638Z-01-runall-0.91.0-final-r2.txt
```

**第一遍(rc=1)红了两段,查清楚了再往下走**(不许先喊"抖动"):

- `test_ds_shell_core` 的 **g2 两腿真联跑**:`port_listening(ws_port)` 为假。
  那条判据自己 `free_port()` 挑三个空端口再让子进程去 bind —— 中间那一瞬有人抢走就红
  (经典 TOCTOU)。**单独跑 2/2 绿、各 1.5~3 秒**。
  连带那 3 条"死断言"是它红了之后**没走到**的后续行,不是独立问题。
- `settings_fvis.e2e.mjs`:工作区文件夹列表回了空(`0 个勾选框`)。
  **单独跑 2/2 全绿**。
- 两条都在**我这一单一行都没碰过**的代码里(我的 diff = 一个 query 参数、一个前端判断、
  一句日志、判据),而这两处都是"自己起服务/自己扫目录"的形状 ⇒ 判为并发/负载。
  ⇒ **不改代码、不放宽判据、不加重试**,清干净机器重跑一遍(第二遍 rc=0,
  五段 0 跳过:node 376 / python 1277 / MCP 三闸 / dist 与源码同步 /
  **e2e 38 PASS 0 FAIL 0 SKIP**,38 里含本单新增那份)。
  按 [[behavior-evals-are-sampling]]:再红一次就当真 bug 查,别再记一次"负载"。

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
- 腿的花名册: **没有 roster** —— fast lane 我没走 `panel-review` 驱动,直接单腿:
  `subdeepseek-agent review`(底座腿,自己读仓库),日志
  `/root/aiwork/logs/panel-shellchrome-0817.subdeepseek.log`(138 turns / 上限 200,
  正常收尾并给出结论),原始 stream 同前缀 `.stream.jsonl`。
  自审文件 `/root/aiwork/tasks/opendesign-shell-chrome-my-review.md`(仓外,派发前写完)。
  ⚠️ **反锚定有个缺口要认**:diff base 是 `df75738`,所以这份 verify.md 的
  lane/派给/规格自查(pre-commit 守卫要求开工前就填)也在它看得见的 diff 里。
  findings 与裁决是它交卷之后才写的。
- findings:
  - **F1(采纳,已改)按钮的行为面零覆盖**:我那份 e2e 全程没有一次 `click` ——
    "按钮画出来了"和"按钮点得动"之间是空的。它给的失败场景可执行:把
    `onClick={() => api()?.close_window()}` 换成空函数 ⇒ A/B/C/D 段 + 契约 x2/x3
    **全绿**,而业主看着三个按钮关不掉窗口(无边框之后那是唯一出口)。
    ⇒ 新增 E 段(`addInitScript` 塞假 `pywebview.api`,真点/真按,断言每一下都叫到
    对应方法、方向名一字不差)。**这一段第一次跑就挖出一条真的边界**,见下面 D1。
  - **F3(采纳,已改)x5 只认 `inset:0` 一种写法** ⇒ 换成四个 offset 或 `100vw/vh`
    的遮罩会被静默漏掉,而漏掉的后果正是这道闸存在的全部理由(盖住窗口栏 = 只能
    上任务管理器)。三种写法都认了;**对照组**:同样两个变异遮罩,旧闸 OK(0 咬 2 漏)、
    新闸红两条。
  - **F2(认账不改)首帧到 pywebview 注入之间,按钮可见但点不动**(`api()` 为 null,
    静默 no-op)。毫秒级,且另一条路(等注入再画)的代价是**每次开窗口界面往下跳 30px**。
    ⇒ 记进 Accepted deviations;真机清单 B2 就是"抓栏拖一下"。
  - **F4(认账不改)e2e 的 `?shell=1` 是手工拼的**,"外壳真会发这个标记"由 x10 咬着 ——
    而 x10 现在是**直接调 `ds_shell.window_url(8766)`**,不是 grep 源码字面量。
  - **我自己闸③ 抓的两条(评审腿没提,仍然成立)**:
    ① 日志里印的地址少了标记 —— 而 `外壳.log` 是业主报"没按钮"时我唯一的现场 ⇒
       地址收进唯一来源 `window_url()`,开窗口和写日志都叫它;
    ② 挂载时那句 `window_state()` 是**装饰**(`api()` 那时必然是 null)⇒ 改成等
       `pywebviewready`,并加 x12 钉住这个等待。
  - **D1 顺带挖出来的真边界(不是本单弄坏的)**:`.win-grip-topright` 那 6×6
    **完全落在三个按钮的 132×30 里**,而"按钮压过把手"是 0.89 四审定的
    (否则点关闭按钮上沿变成改大小)⇒ **右上角这个斜角改不了大小**。
    已钉进判据(按下去命中关闭按钮)+ `app.css` 注释 + 真机清单 B7/F4,
    并把"要不要把按钮往里收几像素"的取舍**摆给业主**(代价:最大化时甩到右上角
    点关闭会落空)。**我不替他定。**
- arbitrated verdict (主裁): **PASS(代码面)**。根因是源码级确认的(pywebview 5.4
  在 `on_navigation_completed` 之后才注入),修法与注入时机解耦,红检 + 变异对照组都
  在这个病上咬住了,而且这一层第一次有了 Linux 能跑的行为判据(A~E 五段)。
  评审腿单腿 PASS + 4 条 finding:**两条采纳(F1 最值钱,它逼出的 E 段当场挖到 D1)**、
  两条认账不改。**代码面到此为止 —— Windows 那半边(按下去动不动、拖得跟不跟手)
  只有业主真机答得了**,清单已写成一趟走完 0.89/0.90/0.91 三版。

## Accepted deviations

- **开窗后极短一段时间(毫秒级)三个按钮可见但点不动**:窗口栏靠地址首帧就画,
  而 `pywebview.api` 要等注入。取舍写在 design.md 的三方案表里 ——
  另一条路是每次开窗口界面往下跳 30px,那个业主一定看得见。影响面:第一下点击可能落空。
- **右上角斜角改不了大小**(上面 D1)。影响面:七个方向能拖,右上角那 6px 归按钮。
  改法与代价已摆给业主,等他说。
- **`e2e` 里的 `?shell=1` 是手工拼的**(F4)。"外壳真会发它"由 x10 直接调
  `window_url()` 咬住;"Windows 上 WebView2 收得到带 query 的地址"只有真机答得了
  (真机清单 A 组 + G 组的两问就是为这个准备的)。
- **`~/.nanobot/config.json` 仍是 Windows 形状**(08-15 那笔账,backlog 里记着)。
  这一单没动它:最终收据里那两条要活 gateway 的 e2e 连的是本机**已经在跑**的那份
  gateway(用真配置起的),所以跑到了 0 跳过 —— 但那笔账还欠着,不是本单还的。
