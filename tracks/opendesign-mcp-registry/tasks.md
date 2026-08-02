# Tasks: opendesign-mcp-registry

> ## 👉 明天从这里接(2026-08-03 凌晨存档,用户说困了要睡)
>
> **代码已写完并全绿,停在分支 `mcp-registry`(commit `00abdcd`),故意未合并主线** ——
> lane 是 full,评审没做完不合,这是 full 的意思。worktree 在
> `/root/aiwork/worktrees/mcp-registry`。
>
> **剩三步:**
> 1. **panel-review(lane full)** ← 明天第一件事。自审 findings 见 verify.md,
>    **必须在读任何 panel 输出之前落盘**(现在已落)。
>    brief 写好放 `/root/aiwork/tasks/`,记得 `PANEL_INCLUDE` 把判据喂进去
>    (chat 腿只看得到增量 diff),自审文件放**仓库外**。
> 2. 逐条对账 → 主裁 → 合并 → **合后亲跑**(上一单就是在这步逮到一条红)→ push
> 3. **用户那边(这条卡着"完成")**:两台 Windows 各跑一次装机脚本更新 config,
>    然后**让助手真干一次活**(记条变更 / 查待办),确认 29 个工具还能用。
>    ⚠️ 这条我这边验不了:仓库全绿 ≠ 他机器上那份 `%USERPROFILE%\.nanobot\config.json`
>    已更新。**盘上和运行时对不上 = BLOCK。**
>
> **已完成(证据在 commit `00abdcd`)**:三闸过了两道半 ——
> 闸①逐字节空 / 闸②py 850 例 0 红 + e2e 31 绿(主 agent 亲跑)/ 闸③亲读 diff 无夹带;
> 29 个包装函数完整源码逐字节相同;环 `KNOWN_REMAINING` 已清零;
> 承重墙实测(拦截 mcp 后 8/8 业务模块仍可 import)。
> 执行腿(codex gpt-5.6-sol)**自身错误 0 处**;主 agent 补了 1 处(我任务书的洞)。


- base-ref: c1f666fd3502dc87aec358125613b5e6fecd0847

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

- [ ] <task 1>
- [ ] <task 2>
