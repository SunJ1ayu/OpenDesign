# Verify: opendesign-start-ps1

- Date: 2026-07-12
- Verdict: **PASS**(fast lane:主审 + submimo 双 PASS;UNTESTED on target,真机首跑即验收)

## Mechanical checks

- [x] 全套 oracle 不适用本变更(纯 ps1 + 文档;py/mjs 测试面零接触)——但推前照惯例
      全跑一遍零红(回归护栏)。
- [x] BOM:四个 ps1 全部 UTF-8 BOM(xxd 逐个验)。
- [x] no secrets / unsafe ops:无新监听面、无新写面、key 逻辑零复制(复用 ds-nanobot.ps1)。

## Review

- lane: **fast**(单脚本 + 文档;deploy-class 但目标机不可用,静态审)
- 主审(先于读 submimo 输出):/root/aiwork/tasks/opendesign-start-ps1-my-review.md,
  verdict PASS;PS 5.1 雷区清单逐条(BOM/三元/redirect 双文件/ArgumentList 引号/
  $PID 撞名/else 换行合法性/Write-Warning 与 EAP)。
- submimo(log /root/aiwork/logs/opendesign-start-ps1-review.submimo.log):**PASS**,
  2 findings 均 info 级:
  - F1「浏览器只在全就绪后打开,文档未限定」→ **拒改**:失败路径 Write-Error 可见即够,
    "就绪后自动开浏览器"表述与行为一致。
  - F2「install-windows.md §5 的 127.0.0.1:8765 与自动打开的 8766 不一致」→ **拒**:
    8765=nanobot 聊天 WebUI、8766=工作台,两个并行服务(文档本就分 §5/§5b 两节),
    存量表述非本变更回归。
- arbitrated verdict (主裁): **PASS**

## Accepted deviations

- DV1 并发双跑 start.ps1 有竞态(第二个可能停掉正在启动的 gateway 再重起)——单用户
  手动场景收敛无害,不加锁。
- DV2 隐藏窗口起 powershell 可能闪一下控制台——纯观感,服务化(最终态)时消失。
- DV3 UNTESTED on target(本机无 pwsh,与 install.ps1 同先例)。**真机验收命令**:
  `git pull` 后 `powershell -ExecutionPolicy Bypass -File D:\AI\OpenDesign\bin\start.ps1`,
  预期=浏览器自动开 8766、设置弹层回显 0.5.0;`start.ps1 stop` 应报两腿进程名+PID。
