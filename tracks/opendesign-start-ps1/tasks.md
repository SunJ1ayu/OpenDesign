# Tasks: opendesign-start-ps1

- base-ref: 31fc7a915e9de9c28dca44f4a118803b87a82980
- design.md 已删:无开放分叉(方案 07-12 谈定,proposal 即设计),不设 panel-explore 挂点。

- [x] T1 `bin/start.ps1`(start/stop 两模式,幂等,UTF-8 BOM,PS 5.1 兼容)
- [x] T2 docs/install-windows.md 启动段收敛为一条命令(旧命令降排查)
- [x] T3 verify:静态走查(BOM/语法雷区清单逐条)+ fast lane review;真机验收=用户下次开机
