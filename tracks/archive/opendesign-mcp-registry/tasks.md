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

- 派给:**codex gpt-5.6-sol(worktree)**,主 agent 收货三闸 + 仲裁。
  lane: **full**,不打折。

> ⚠️ **这份清单是 2026-08-04 补的**,原来从头到尾是模板占位符 `<task 1> <task 2>`。
> 活干完了、验收单也写了,唯独没人填过它。补的内容**全部照 git 史料还原**
> (下面每条都挂着 commit),不是回忆。
> 教训:开工前不填清单,事后只能靠考古 —— 而考古补出来的东西**证明不了当时想过什么**,
> 只能证明当时干了什么。

## 实施顺序(照 commit 还原)

- [x] **T1 方向选定** ✅ `panel-explore` 先跑(proposal 开头写着"方向未定")。
      选定**方向 R**:登记层单独成文件 `bin/ds_*_server.py` + 统一入口 `ds_mcp.py`。
- [x] **T2 判据先行** ✅ `adea45d`:三条闸 + 改造前的 29 工具表基线
      (**基线先存,才有得对**)。
- [x] **T3 实现(执行腿)** ✅ `00abdcd`,codex gpt-5.6-sol 在 worktree。
      **自身错误 0 处**;主 agent 补了 1 处 —— 根因是我任务书的洞,不是它的。
- [x] **T4 收货三闸** ✅ 闸①逐字节空 / 闸② pytest 850 + e2e 31 主 agent 亲跑 /
      闸③亲读 diff 无夹带;29 个包装函数源码逐字节相同;循环依赖清零;
      承重墙实测(拦掉 mcp 后 8 个业务模块仍可 import)。
- [x] **T5 panel-review(full)** ✅ `59ec15b` 判据补录(panel 三腿 + 主 agent 命中的
      四个洞,**补完是红的**)→ `3da58f7` 五条闸转绿:旧入口改成响亮报错、
      **三处撒谎文档**、两份 eval 跟着搬家(它们从 AST 抽工具表,搬家后抽到空表,
      而 eval 不进 pytest ⇒ 典型静默退化)。
- [x] **T6 合并 + bump** ✅ `8ff9805`(0.72.0)+ `48e4ecb` merge,已 push。
- [x] **T7 verify 落盘** ✅ `661bb4a`:PASS(代码面),欠装机验收。

## 唯一还卡着的

- [ ] **两台 Windows 各跑一次装机脚本**,然后**让助手真干一次活**(记条变更 / 查待办),
      确认工具还能用。⚠️ **我这边验不了**:仓库全绿 ≠ 他机器上那份
      `%USERPROFILE%\.nanobot\config.json` 已更新。**盘上和运行时对不上 = BLOCK。**
      验完这条才能归档。
