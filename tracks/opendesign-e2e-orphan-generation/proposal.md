# Proposal: e2e 的遗孤是怎么产生的(治生成,不治发现)

- Date: 2026-09-07
- Status: open(**未开工**)

## 由来

`opendesign-stage-timer-e2e-red` 查出:一条 e2e 连红五天,根因是 8 月 30 日留下的
一个 `ds_web` 遗孤占着端口。那一单加了**开跑前的端口预检** —— 那是**治发现**:
下次再有遗孤,开跑前当场喊出来,而不是让它伪装成"产品坏了"。

**生成路径一行没动。** 本单治生成。

## 事实(两条评审腿各自给出,我核过成立)

1. **`spawn` 在 kill 保障之前** —— 35 个 `*.e2e.mjs` 里 **33 个**的 `spawn`
   在第一个 `try` 之前。中间隔着会抛的启动序列(健康轮询 throw、`launchBrowser()`、
   `newPage()`)。任何一处抛 ⇒ node 退出 ⇒ `finally` 从没挂上 ⇒ ds_web 成遗孤。
   (`chat_image` / `chat_reconnect` 是例外 —— 它们把 spawn 包在里面,是安全形状。)
2. **没有任何 e2e 处理信号** —— 全部文件都没有 `process.on('SIGTERM'|'SIGINT')`。
   Node 收到 SIGTERM 时 **`finally` 不会执行**。CI 超时、Ctrl+C、被砍会话都走这条路。
3. **`run-all.sh` 的 trap 不清子进程** —— 它只清 `$E2E_HOME` 和 `$log_dir`。
   run-all 自己被杀时,35 个 node/python 及它们起的 ds_web 全部变遗孤。
4. **`srv.kill()` 默认 SIGTERM** —— 36/37 个文件用默认信号,只有 `llm_key.e2e.mjs`
   用 SIGKILL(说明有人撞过"SIGTERM 不够力")。

## 遗孤为什么会从"旧服务"升级成"产品坏了"

`run-all.sh` 的 `trap 'rm -rf "$E2E_HOME"' EXIT` 会删掉隔离家目录,
而遗孤是从 spawn 继承 `HOME=$E2E_HOME` 的 ⇒ 它的假 key 没了
⇒ 判定"没配大模型 key" ⇒ 前端弹遮罩 ⇒ 点击全被拦。
**生成**和**劣化**是两件事,这一条是劣化。

## 候选做法(未定案)

- `helpers.mjs` 出一个 `registerCleanup(srv)`:挂 `process.on('exit'|'SIGTERM'|'SIGINT')`,
  一处写、35 处用(比让 35 处各自改健康检查便宜)
- 或 `run-all.sh` 用进程组:`set -m` + `trap 'kill 0' EXIT`
  ⚠️ **这条要非常小心** —— 这台机器上 `pkill -f` 自杀过,`kill 0` 同类
- 或让每个场景 spawn 之后立刻进 try(结构改动,35 处)

## Non-goals

- 不重做端口预检(那一单已经做完,是互补的另一半)
- 不在本单顺手修"5 对端口声明碰撞"(串行跑不咬人,并行化才咬;单独记)

## 开工前要先答的

`kill 0` / 进程组那条路,在这台机器上安全吗?**先做探针,别凭推理**。
