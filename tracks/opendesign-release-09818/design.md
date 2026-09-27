# Design

使用既有 electron-e2e 工作流，从精确源码提交生成安装包、blockmap 和 latest.yml。
版本只改 ds_web.VERSION、desktop/package.json 与 lock 的对应元数据；不改发布协议。
产品 PR 已由主 agent 独立审阅并复现修复。本 track 的版本准备是沿用现有已验证流程的局部修改。

先做版本契约检查，推送被测提交并启动 Windows 构建；本地总回归同时运行。
Windows 两个 job 全部成功、运行时回显版本正确、出货源为正式 GitHub 地址后才发布。
冻结三项资产的大小、SHA-256、安装包 SHA-512，再用现有 release-feed 工具改写绝对安装包地址。
发布 tag 指向被测源码 SHA；公开的 releases/latest/download/latest.yml 必须回显 0.98.18，
公开下载安装包必须与冻结 hash 一致，旧 0.98.16 blockmap 仍可获取。

本地总跑三条既有跳过单独记录：Windows 平台项及两条活网关浏览器场景，不计通过。
用户机器无法远程控制，运行中的本机更新源和 Windows 云安装升级回显是可亲测边界。
若云构建或验收失败，不发布；修复后重新绑定源码 SHA 和资产。
