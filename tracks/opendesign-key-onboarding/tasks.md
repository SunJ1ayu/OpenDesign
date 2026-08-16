# Tasks: opendesign-key-onboarding

- base-ref: 9a641d24d48c8e598a363c61b46c0166ccb1b24f

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

## 已完成(判据先行 → 实现 → 红检,每步单独 commit)

- [x] **T1 凭据模块 + 外壳启动计划** —— `bin/ds_credential.py`(只收不读/只落一处/
      变量名从配置读/报错不带入参)+ `ds_shell_core` 起停计划改成
      「ds-web 无条件起、网关有 key 才起」(design 对差异 #2)。
      判据 `f5e37eb` 先行 → 实现 `1860c38` 14/14 → 红检 `df426ba` 9 变异 9 咬住 0 漏网。
- [x] **T2 两个接口 + 来源检查 + 口令代签** —— `GET/POST /api/llm/credential`、
      `_same_site_ok`(双向验,不带 Origin 的 curl 照常放行)、`_proxy` 在前端没带
      Authorization 时用 `_gateway_password()` 替它签(前端从此不必持有口令)。
      判据 `dd6fb09` 先行(11 条 10 红) → 实现 `5acf226` 12/12 →
      题面加强 `89ca1e7`(代理不再是「纯管道」,断言改强 + 给这份判据加隔离)。
- [x] **T2.5 全量回归** —— `89ca1e7` 上 node 350 / python 1197 / MCP 契约 / dist 新鲜度
      全绿,e2e 34 PASS 0 FAIL;收据在 `evidence/20260815T152602Z-01-regression-http-v2.txt`。
      ⚠️ **rc=3 不是通过**:2 条 e2e 因为没带 `--with-gateway` 是 SKIP,收口前要补跑。

## 待办

- [x] **T3 外壳重启通道**(主 agent 自己写)。判据先行 `d09ee2f`/`88af99a`/`47bc1a6`/`e99adc6`
      → 实现 `a044263` → 判据跟随 `0adc038`;红检 15 条 **15 咬住 / 0 漏网**。
      锁通道加动词 `RESTART-BACKEND`(不新开端口)、`Supervisor.restart()` 只换点名的腿、
      `child_env` 的 key 变量名改成从配置读、缺 key 不再 die 改问 `startup_plan`。
      **顺带发现三件断线时没记的**:锁协议的第二行**从来没被读过**;
      `child_env` 里变量名是写死的(design 对差异 #1 第二次露头);
      `ds_shell.py` 压根没接 `startup_plan` ⇒ 引导页原本永远出不来。
      > 🔴 **仍未验**:「真的重启完还能聊天」判据答不了(design 骗法三)⇒ 已进真机清单。
      > `ds_shell.py` 那层只有静态接线闸(`test_ds_shell_wiring.py`),
      > 它证明"写了"、证明不了"跑起来对"。
- [x] **T4 前端模态框**(派 codex `gpt-5.5`;oracle 主 agent 写并先单独 commit)。
      判据先行 `cc53cc3` → 三轮攻题加固 `2127979`/`4af74dc`/`9b098ed`/`5021b22`
      → 实现 `1b07d61`(腿)→ 合入 `7afe4e5`。**返工 0 轮,自身错误 0 处。**
      **收货三闸**:① `--receive` 判卷逐字节没动、无多余未跟踪文件;② 主树重新
      build(tsc 过)+ e2e **26/26 全绿**;③ 亲读 diff,无符号链接、无需退回项。
      > 🔴 **判据被攻了三轮才敢派活**(记录在仓外 `attack-t4-final.md`):
      > 我自己两轮 9 条 + 两条攻题腿 15 条(驳回 4 条)。最值钱的三条:
      > **b2 那条"防前端硬编码后端值"的闸,自己把后端的值硬编码了**;
      > **我上一轮的修改自己造出一个必然误报**(C2 跑在 C10 前,ariaSnapshot 看得见
      > 刚填的 key ⇒ 正确实现被判红,而人会因此调钝报警器);
      > **e2e 跑 dist、静态判据扫 src,两者可以不是同一份代码**(GPT 抓到,我没想到)。
      > 腿有两处做得比我要求的稳:key 走 `useRef` 非受控(不进 React state)、
      > 逻辑层多加一道"上游万一回显 key 就地抹掉"。
      > 我读代码另找到 3 条判据答不了的(F1 effect 依赖靠调用方记得用 useCallback /
      > F2 catch 把两种病说成一句话 / F3 已配置时设置里那行看不出能点),全不阻断。

- [ ] **T5 收口** —— 红检(`tests/mutation-llm-key.sh`,13 条定点变异)→
      全量回归**带 `--with-gateway`**(把 T2.5 那 2 条 SKIP 变成真跑)→
      **lane=full 四审** → verify.md 落主裁判决 → bump 版本 + 真机清单 → push → 归档。
      > 真机清单必须写的**三**条:**key.txt 权限在 Windows 上是 ACL 语义,本单不声称
      > 文件级隔离**;**重启后真能聊天**只有真机能答;
      > 🔴 **新增第三条:「不手输口令、界面真能连上聊天」这条代签主路,今天没有任何
      > 一条自动判据走通过**(e2e 里没有 gateway,python 那条 j1 是拿假上游验的)。
