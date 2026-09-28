# 方案

沿用现有 `electron-e2e` 工作流。仅同步 `bin/ds_web.py`、`desktop/package.json` 和 lock 文件的版本号；由精确源码 SHA 在 GitHub Actions 的 Linux payload 与 Windows e2e 两个 job 生成和验证出货包。安装包、blockmap 和 latest.yml 从同一次全绿 run 下载。

发布前核对源码 SHA、Windows 断言、出货更新源、安装包与 latest.yml 的字节摘要。使用 `desktop/scripts/release-feed.mjs` 将 latest.yml 改写为带版本的正式下载地址，再创建非预发布 release。发布后从公开地址回读清单和安装包，确认版本及摘要。

风险：错误版本或错误资产会让自动更新失败；任何 job 失败、版本不一致或公开资产摘要不一致都停止发布。此流程沿用 0.98.18 已验证的契约。
