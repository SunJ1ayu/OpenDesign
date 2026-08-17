# Verify: opendesign-key-startup-crash

- Date: 2026-08-16 / 2026-08-17(断线跨了一天,见下面「这一单断过一次」)
- Verdict: PASS(代码面)—— **最终判决等业主真机**(`真机清单-0.89.0.md`)

## 这一单断过一次,先把断口说清楚

08-16 23:51 提交完 track 工件之后会话断线。断线砍在**四审收尾**那一步,
而 tasks.md 上「full 四审」和「编好安装器」两个勾**是提前打的**:

- 打「四审」那个勾时,panel 才刚开跑 3 分钟;三腿里 **subkimi 被砍成半截**
  (日志停在句子中间 "Hmm — but wait: is there"),**没有结论**;智谱欠费 off。
- 打「安装器」那个勾时,exe 确实造出来了,但它在**上一个会话的临时目录**里,
  **GitHub 上最新仍是 0.88.0** ⇒ 业主装不到 0.89.0。
- 两个评审给的 13 条发现,当时**一条都没落地**(最后一个 commit 比结论还早)。

⇒ 08-17 的做法:**半截收据作废**(规矩:断线砍断的收据必须重跑),
发现逐条对账落地,四审在**最终代码**上整轮重跑。

## Mechanical checks

- [x] build passes(`npm run build`;dist 新鲜度闸在总跑里,与源码同步)
- [x] tests pass(见下,**2 条 e2e 如实 SKIP,不算通过**)
- [x] no secrets / unsafe ops(本轮不碰凭据面;业主当天另问了一次全仓密钥审计,
      结论:仓里没有任何真实密钥、没有数据库、没有"我们的服务器",
      `sk-*` 全是判据夹具)

**机器打印的**(不是我的转述):

```
runlog: redcheck-nameerror rc=1 commit=08de4ac dirty=yes at=2026-08-16T15:03:26Z file=tracks/opendesign-key-startup-crash/evidence/20260816T150326Z-01-redcheck-nameerror.txt
runlog: greencheck-nameerror rc=0 commit=67db02c dirty=yes at=2026-08-16T15:04:38Z file=tracks/opendesign-key-startup-crash/evidence/20260816T150438Z-01-greencheck-nameerror.txt
runlog: redcheck-supervisor3 rc=1 commit=25133bf dirty=yes at=2026-08-16T15:07:58Z file=tracks/opendesign-key-startup-crash/evidence/20260816T150758Z-01-redcheck-supervisor3.txt
runlog: redcheck-supervisor3 rc=1 commit=25133bf dirty=yes at=2026-08-16T15:09:01Z file=tracks/opendesign-key-startup-crash/evidence/20260816T150901Z-01-redcheck-supervisor3.txt
runlog: greencheck-supervisor3 rc=0 commit=c4adb42 dirty=yes at=2026-08-16T15:11:22Z file=tracks/opendesign-key-startup-crash/evidence/20260816T151122Z-01-greencheck-supervisor3.txt
runlog: runall-0.89.0 rc=1 commit=1c37b66 dirty=yes at=2026-08-16T15:18:20Z file=tracks/opendesign-key-startup-crash/evidence/20260816T151820Z-01-runall-0.89.0.txt
runlog: runall-0.89.0-final rc=3 commit=684574d dirty=no at=2026-08-16T15:35:38Z file=tracks/opendesign-key-startup-crash/evidence/20260816T153538Z-01-runall-0.89.0-final.txt
runlog: redcheck-panel-findings rc=1 commit=23387d8 dirty=yes at=2026-08-17T01:31:37Z file=tracks/opendesign-key-startup-crash/evidence/20260817T013137Z-01-redcheck-panel-findings.txt
runlog: redcheck-panel-findings rc=1 commit=23387d8 dirty=yes at=2026-08-17T01:31:52Z file=tracks/opendesign-key-startup-crash/evidence/20260817T013152Z-01-redcheck-panel-findings.txt
runlog: redcheck-panel-findings-r2 rc=1 commit=23387d8 dirty=yes at=2026-08-17T01:32:46Z file=tracks/opendesign-key-startup-crash/evidence/20260817T013246Z-01-redcheck-panel-findings-r2.txt
runlog: redcheck-c21 rc=1 commit=23387d8 dirty=yes at=2026-08-17T01:32:54Z file=tracks/opendesign-key-startup-crash/evidence/20260817T013254Z-01-redcheck-c21.txt
runlog: redcheck-c21 rc=1 commit=23387d8 dirty=yes at=2026-08-17T01:33:00Z file=tracks/opendesign-key-startup-crash/evidence/20260817T013300Z-01-redcheck-c21.txt
runlog: greencheck-panel-findings rc=1 commit=165870a dirty=yes at=2026-08-17T01:39:33Z file=tracks/opendesign-key-startup-crash/evidence/20260817T013933Z-01-greencheck-panel-findings.txt
runlog: greencheck-panel-findings-r2 rc=0 commit=165870a dirty=yes at=2026-08-17T01:40:00Z file=tracks/opendesign-key-startup-crash/evidence/20260817T014000Z-01-greencheck-panel-findings-r2.txt
runlog: mutation-panel-findings rc=0 commit=165870a dirty=yes at=2026-08-17T01:40:44Z file=tracks/opendesign-key-startup-crash/evidence/20260817T014044Z-01-mutation-panel-findings.txt
runlog: runall-after-panel-fixes rc=1 commit=165870a dirty=yes at=2026-08-17T01:41:11Z file=tracks/opendesign-key-startup-crash/evidence/20260817T014111Z-01-runall-after-panel-fixes.txt
runlog: runall-final-0.89.0 rc=3 commit=cba802d dirty=no at=2026-08-17T01:51:36Z file=tracks/opendesign-key-startup-crash/evidence/20260817T015136Z-01-runall-final-0.89.0.txt
runlog: dsweb-finds-config rc=1 commit=cba802d dirty=yes at=2026-08-17T02:08:15Z file=tracks/opendesign-key-startup-crash/evidence/20260817T020815Z-01-dsweb-finds-config.txt
runlog: dsweb-finds-config-r2 rc=0 commit=cba802d dirty=yes at=2026-08-17T02:08:50Z file=tracks/opendesign-key-startup-crash/evidence/20260817T020850Z-01-dsweb-finds-config-r2.txt
runlog: redcheck-kimi-block rc=2 commit=c5e83e5 dirty=yes at=2026-08-17T02:17:58Z file=tracks/opendesign-key-startup-crash/evidence/20260817T021758Z-01-redcheck-kimi-block.txt
runlog: greencheck-kimi-block rc=0 commit=5615be2 dirty=yes at=2026-08-17T02:20:11Z file=tracks/opendesign-key-startup-crash/evidence/20260817T022011Z-01-greencheck-kimi-block.txt
runlog: greencheck-kimi-block-r2 rc=1 commit=5615be2 dirty=yes at=2026-08-17T02:20:49Z file=tracks/opendesign-key-startup-crash/evidence/20260817T022049Z-01-greencheck-kimi-block-r2.txt
runlog: greencheck-kimi-block-r3 rc=0 commit=5615be2 dirty=yes at=2026-08-17T02:21:32Z file=tracks/opendesign-key-startup-crash/evidence/20260817T022132Z-01-greencheck-kimi-block-r3.txt
runlog: mutation-window-chrome rc=0 commit=5615be2 dirty=yes at=2026-08-17T02:22:48Z file=tracks/opendesign-key-startup-crash/evidence/20260817T022248Z-01-mutation-window-chrome.txt
runlog: mutation-ds-shell-core rc=1 commit=5615be2 dirty=yes at=2026-08-17T02:23:07Z file=tracks/opendesign-key-startup-crash/evidence/20260817T022307Z-01-mutation-ds-shell-core.txt
runlog: mutation-ds-shell-core-r2 rc=0 commit=5615be2 dirty=yes at=2026-08-17T02:32:28Z file=tracks/opendesign-key-startup-crash/evidence/20260817T023228Z-01-mutation-ds-shell-core-r2.txt
runlog: runall-0.89.0-final2 rc=3 commit=36aefe8 dirty=yes at=2026-08-17T03:45:15Z file=tracks/opendesign-key-startup-crash/evidence/20260817T034515Z-01-runall-0.89.0-final2.txt
```

> ⚠️ `evidence/20260817T024323Z-01-runall-0.89.0-r2.txt` 是**断线砍出来的半截收据**:
> 只跑到 python 那一段,**没有结论行**。留着不删(藏红比红本身坏),
> 它由下面那份 `runall-0.89.0-final2` 取代。

**跑红的那几遍一份都没藏**,逐条认账:

| 收据 | rc | 它红在哪 |
|---|---|---|
| redcheck-nameerror / supervisor3 ×2 | 1 | **判据先行**,红是它该有的样子 |
| redcheck-panel-findings(第一份) | 1 | **我用错解释器**(venv 没装 pytest)—— 假红,不是判据结果 |
| redcheck-panel-findings / -r2、redcheck-c21 ×2 | 1 | 判据先行 |
| greencheck-panel-findings(第一份) | 1 | **x6 判据自己有 bug**(`(e) =>` 里的 `>` 把属性区截断)已修 |
| runall-0.89.0 / runall-after-panel-fixes | 1 | dist 尚未随改动重建 —— 重建入库后转绿 |
| runall-final-0.89.0 | **3** | 五段 0 红,但 **2 条 e2e SKIP**(见下)⇒ 工具如实不判通过 |
| dsweb-finds-config(第一份) | 1 | **判据自己写错**:口令用了中文,而实现有意拒收非 latin-1 ——
  实现是对的,顺手把那条防线也补成判据(g4) |
| redcheck-kimi-block | **2** | 判据先行(1+1:x8 和 c22 各红一条),红是它该有的样子 |
| greencheck-kimi-block(第一份) | **0 而正文 FAILED** | **管道又吃了一次退出码**(`\| tail -5; rc=$?` 拿到的是 tail 的)。
  **这是一份假绿收据**,只因为我随手又跑了一遍 r2 才没混过去。今年第四次踩同一个坑 |
| greencheck-kimi-block-r2 | 1 | **判据自己是假红**:x8 用正则找窗口栏标签的收尾,又被 `(e) =>` 里的箭头截断
  (x6 第一版栽过、x8 第二版再栽)⇒ 红在**已经改对**的代码上。改成扫括号深度后转绿 |
| mutation-ds-shell-core(第一份) | 1 | **变异脚本自己坏了(第四次)**:M4 锚点过期两个版本 ⇒ 那条契约一直没有红检覆盖。
  换成不易改的锚点后 15 咬 0 漏 |

**最后一遍总跑**(`runall-0.89.0-final2`,commit `36aefe8` = 四审第二轮全部落地之后):
node **374** 通过 0 跳过 / python **1268** 跑过 **0 跳过** / MCP 三闸全绿 /
dist 与源码同步 / e2e **35 PASS 0 FAIL 2 SKIP**。rc=3 —— **五段 0 红,但那 2 条没跑,
工具如实不判通过**(为什么不跑见「Accepted deviations 1」)。

> python 从上一轮的 1262 涨到 1268:新判据 c22(新腿收尸)、x9(把手几何)、
> g1~g4(ds-web 找不找得到网关配置)都进了汇总 —— **这正是重跑的理由**:
> 上一份 `runall-final-0.89.0` 的收据里没有它们,拿它交差就是「我给的绿是过期的」
> (08-10 那次事故的形状,孤腿 subdeepseek 抓到过一模一样的)。

## Review

- lane: **full**(碰 auth 面的读取路径 + 装机形态,硬规矩不打折)
- 派给: 主 agent 直接干 —— 输入是**两份只在业主机器上存在的日志**加上我现读的
  pywebview 5.4 源码,任务书要把这些复述给执行腿的成本高于自己写;改动面又小又散
  (外壳一行 + core 三处 + 前端窗口条 + CSS 层号)。判卷不起服务(替身 Supervisor)。
  ⚠️ 这条理由**只对这一单成立**,别当默认值抄下去(07-31 教训:自述型字段挡不住惯性)。

- 规格自查(读任何 panel 输出之前先答):

  **如果规格本身错了,会错成什么样?** 这一单的规格是业主两句真机反馈:
  「每次开机崩」和「聊天连不上」。前者有确定的技术形态(NameError,已修且有判据)。
  **后者我到现在也没有确认的根因** —— 我修的是"下次查得动"(退出码 + 日志尾巴),
  不是"它为什么死"。**如果那个真因不在我碰过的任何一处,业主装完 0.89.0 会
  再撞一次一模一样的墙,而我这一单全绿。** 这是本单最大的规格风险,
  已在 tasks.md 顶部写死给下一次接手的人。

  今天顺着这条又排除了一个候选(ds-web 找不到网关配置 ⇒ 不代签 ⇒ 连不上):
  判据 g1 绿,那条路是通的,并且从此有防线。**排除一个不等于找到那个。**

  另一条:无边框窗口是**我按业主一句话("能不能不要外面那个框")做的形状判断**,
  panel 只能验"实现合不合这个形状",验不了"这个形状是不是他要的"。
  真机 D 组一红就要能一行退回带边框 —— 已写进清单 H 段。

- 腿的花名册(原样粘,没手写):

  ```
  # panel-review 花名册(2026-08-17 10:14:32)task=opendesign-089-r2
  # PASS = 进程 rc=0,**不等于给了裁决**;off = 这条腿压根没派(不许读成通过)。
  # 日志:/root/aiwork/logs/panel-089r2-20260817-100323.*.log
  submimo=PASS subdeepseek=PASS subglm=FAIL(rc=1,降级:回落聊天腿也没成) subkimi=PASS
  # ⚠️ 评审期间 HEAD 从 cba802d 移到 c5e83e5 —— 各腿未必评的同一棵树。
  ```

  实到 **2 条有效腿**,不是 4 条:
  - **submimo** rc=0,但产出的只是一份"我打算怎么评"的计划,**没有任何结论** ⇒ 无裁决。
    (roster 头一行那句"PASS 不等于给了裁决"就是防这个的。)
  - **subglm** 智谱**欠费**(`1113 余额不足`),agent 腿和回落的聊天腿都没起来 ⇒ off。
    这已经是连续第几轮少这条腿了,记在 backlog,别每轮重新查一遍。

- findings(两条有效腿共 13 条,逐条对账;**"不落地"的都写了理由,没有一条是"没看见"**):

  | # | 腿 | 级别 | 发现 | 落地? |
  |---|---|---|---|---|
  | F-1 | subkimi | **HIGH** | `.win-bar` 是 `fixed`+`z-index` ⇒ 自己就是 stacking context,装在里面的 `.win-btns:220` 在根上下文里**不算数**,把手照样吃掉按钮上沿。**F7 上一轮等于没修,而 x8 给的是假绿** | ✅ 按钮区抬成栏的兄弟 + 根级 `fixed`;x8/x6 改问结构 |
  | F-2 | subkimi | MEDIUM | `restart()` 收**新**腿只 `_terminate_tree`,没 `_kill_tree`/`_close_job`/关句柄 —— 同一函数收旧腿走的是全套(c18) | ✅ 两条路合并;判据 c22 + 变异 M15 |
  | F-3 | subkimi | LOW | 那 7 条变异跑在会话临时目录下的一个脚本里,**仓库里没有、谁也复现不了** | ✅ `tests/mutation-window-chrome.sh` 入库 |
  | F-4 | subkimi + subdeepseek | LOW | `restart()` 不持 `_shutdown_lock` 这个取舍,代码里**一个字没写** | ✅ docstring 写清取舍、前提、以及"下一个想加锁的人先做什么" |
  | F-5 | subkimi + subdeepseek | NIT | Aero 贴边最大化不走 `toggle_maximize` ⇒ 按钮图标画反 | ❌ 外观级,记 backlog + 真机清单 G1 |
  | F-6 | subkimi + subdeepseek | NIT | `_on_ui` 兜底在**工作线程**上重跑 fn —— 而 `Bounds` 写入正是"安静地不生效" | ✅ 删掉回退,改成留一句日志 |
  | D-1 | subdeepseek | MEDIUM | `.win-grip-right` 压住最右列滚动条的滑块 ⇒ 拖滚动条可能变成改窗口大小 | ❌ 要动布局,单独一单;已进真机清单 **D12** 让业主先判断碍不碍事 |
  | D-2 | subdeepseek | LOW | `inDesktopShell` 只求值一次;若 pywebview 注入晚于首渲,窗口栏永不出现 = 无边框下没有出口 | ❌ 前提在 EdgeChromium 上成立(两腿同判),记 backlog |
  | D-3 | subdeepseek | LOW | `body.has-window-chrome` 挂在 `useEffect` ⇒ 首帧压着内容、再跳 30px | ✅ 改 `useLayoutEffect` |
  | D-4 | subdeepseek | INFO | `ds_web.py` 里 0.88.0 的版本注释和 0.87.0 的抬头串成了一行 | ✅ 拆开 |
  | D-5 | subdeepseek | 覆盖缺口 | x7 只问把手**名字**、x8 只问**层序**:把某条把手挪到屏幕中间或厚度改 0,两条都照绿 | ✅ 新判据 x9 问**几何**(贴边+有厚度)+ 变异 W5/W6 |
  | — | subdeepseek | 复核 | 高度链不引入滚动条(`border-box` + `padding-top:30px`)、删那 5 条死代码判据**不算放水**、`take_dead` 读日志的开销可接受 | 与我自判一致 |
  | — | subkimi | 复核 | 同上三条 + F1/F2/F5/NameError 四条修复逐条核过代码与判据 | 与我自判一致 |

- arbitrated verdict (主裁): **PASS(代码面)** —— F-1/F-2/F-3/F-4/F-6/D-3/D-4/D-5 全部落地并重跑
  (变异 8 咬 0 漏 + 15 咬 0 漏、总跑见上),不落地的 3 条(F-5/D-1/D-2)各自写了理由与去处。
  **最终判决仍等业主真机。**

  **这一轮最该记的一条:孤腿 BLOCK 又一次是对的,而且这次全票会错得很难看。**
  subkimi 一条腿 BLOCK,subdeepseek 不但 PASS,还在**同一处**白纸黑字写下
  "**F7 (grips eating buttons) — properly fixed.** z-order 220 > 210 > 200; x8 bites"。
  它验的是两个**声明数字**的大小,没问这两个数字在不在同一个 stacking context 里 ——
  和我的 x8 犯的是同一个错,所以它复核我的判据时当然复核不出来。
  **两个独立主体用同一个错误模型看同一处,得到的一致不是证据。**
  真正把它捅破的是 subkimi 去问了"浏览器实际会怎么画"。
  ⇒ 再次坐实:**全票不能降标准,孤腿 BLOCK 要当信号**;而且我自己第一版也认为修好了 ——
  这条 HIGH 是**我的判据在替我的错误背书**,不是"腿之间吵架我来断"。

## Accepted deviations

1. **2 条 e2e 一直 SKIP**(`new_chat.e2e.mjs` / `project-thread.e2e.mjs`)。
   它们要一个**活的 gateway**,而活 gateway 就是外网出口 —— 与「判据不许有外网出口」
   那条机械不变量正面冲突(08-10 烧光额度那次立的)。**这是设计使然的跳过,不是遗漏**;
   两条测的是"新建对话"和"项目会话线程",与本轮改动(窗口层号 / 看门狗 / ctypes 声明)
   无交集。
   > 08-16 那版 tasks.md 写着"认账见 verify.md",而 verify.md 当时是**空模板** ——
   > 那个洞本身就是这次要修的东西之一。
2. **F3 / F4 / F6 三条四审发现不落地**,理由逐条写在实现 commit 里
   (真机覆盖 / 没有证据推翻现有断言 / 既有竞态且加锁有死锁先例)。已记 backlog。
3. **`poll_dead()` 的语义变了**:它现在走 `take_dead()`,对**已死**的腿会读日志文件尾巴。
   正常路径零额外开销(没死就 continue)。真读文件的那一刻程序马上要弹窗退出。
   **我判这是可接受的取舍,不是遗漏。**
4. **32 位 Windows 上 `windll`(cdecl)调 stdcall 仍不对**(上一轮 DeepSeek 提过)。
   目标平台是 64 位,不为它引入 `WinDLL` 分支。**取舍,不是遗漏。**
5. **层号改动没有真机截图** —— Linux 上开不出那个弹窗的运行形态。
   已加进真机清单 E 组(三条)。
6. **右把手压着最右列滚动条的滑块**(第二轮 subdeepseek MEDIUM)。要修得动布局(最右列内收),
   **不在这一单的针孔里**。已进真机清单 **D12**:让业主自己拖一次滚动条,
   碍事就单开一单。**这是"先问业主碍不碍事",不是"我判它不重要"。**
7. **`inDesktopShell` 只求值一次**(D-2)。若 pywebview 注入晚于 React 首渲,
   无边框窗口就没有出口了。两条腿独立判定"EdgeChromium 上注入在页面脚本之前",
   前提成立;**但这是本单第二大的规格风险**(第一是那个没根因的网关死亡),
   已记 backlog,真机 A 组第一条就会撞上它。
8. **`maximized` 会过时**(F-5):Aero 贴边 / Win+Up 不走 `toggle_maximize`,图标画反。
   外观级,行为仍对。真机清单 G1 已声明"贴边这条路不归这一单管"。
