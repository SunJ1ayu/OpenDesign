# Proposal: opendesign-start-ps1

- Date: 2026-07-12
- Status: accepted(07-12 与用户谈定的近期队列②)

## Why

现状启动 = 两个窗口两条命令(`ds-nanobot.ps1 gateway` + `ds-web.ps1`),对日用太糙。
谈定方案:**一条命令拉起全套**;"注册 Windows 服务、窗口彻底消失"是最终态,本轮不做。

## What

`bin/start.ps1`:
- `start.ps1` —— 幂等拉起:gateway(8765/18790)没起就起、ds-web(8766)没起就起,
  各自隐藏窗口 + 日志落 `%USERPROFILE%\.openDesign\logs\`,就绪后自动开浏览器。
- `start.ps1 stop` —— 按端口找 OwningProcess 停掉两者。
- 复用 `ds-nanobot.ps1`/`ds-web.ps1` 起进程(key 注入/venv 推导单一来源,不复制逻辑)。
- docs/install-windows.md 启动段改为一条命令,旧两条降级为排查用。

## Non-goals

- 注册 Windows 服务 / 开机自启(最终态,另轮)。
- Linux 侧等价物(开发机用不上)。
- 改 ds-nanobot.ps1 / ds-web.ps1 本体。

## Risks

- 本机无 pwsh,UNTESTED(与 install.ps1 同先例):静态走查 + fast lane 审,
  真机首跑即验收。PS 5.1 雷区:UTF-8 BOM、无三元运算符、Start-Process
  redirect stdout/stderr 必须两个不同文件、隐藏窗口下杀 wrapper 不杀孙进程
  (故 stop 按端口杀真身)。
