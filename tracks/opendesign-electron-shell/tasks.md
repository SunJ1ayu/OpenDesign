# Tasks: opendesign-electron-shell

- base-ref: 03f50b70a861f4920316de4225092ddf1e2af8e1

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。

- [x] T0 立单;主 agent 方向派发前落盘;两个家族独立方案挑战(Cursor-Grok / DeepSeek)并逐条核实(design.md 表)
- [x] T1 业主重新拍板:安装包与自动更新换不换(U1)—— 「全换吧」
- [x] T2 探路(U2):E1 构建 / E2 起窗 / E3 过渡 / E4 更新,云 Windows 上量
- [x] T3 定稿 design.md Approach + 写实现判据(判据先单独 commit)—— `94f27ad`:h1~h15 / m1~m22 / r1~r7 / c1~c9 / du1~du12 + electron-e2e;迁移账 `evidence/20260922-t3-oracle-ledger.md`
- [ ] T4 实现(管家瘦身 / Electron 主进程+preload / 前端窗口栏 / 安装包接入)
- [ ] T5 回归 + 两家族评审(impact=high)
- [ ] T6 发版 + 业主真机(A0 界面出来了吗)
