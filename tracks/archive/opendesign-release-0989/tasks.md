# Tasks: opendesign-release-0989

- base-ref: 6e28bf5268db7b8469f39a6483bd002b5456fbcd

> 委托 submimo fix 时:主 agent 先写失败测试(oracle)并 commit,再把窄范围实现
> 交给它;oracle/测试文件对它 off-limits;~2 次红了收回主 agent。


- [x] T1 版本 0.98.9 与 Windows 探针四处默认值(已在 opendesign-per-vendor-keys 内完成,`ce5314c`)。
- [x] T2 本地全量回归(runlog --final;见原功能 track 的 run-all-final)。
- [ ] T3 构建安装包 + 生成更新清单(哈希从产物本身算,不手写)。
- [ ] T4 **问业主** → 推送源码 + 发布 prerelease + 上传安装包与清单。
- [ ] T5 已发布字节取回逐字节核对;从 0.98.8 真查一次更新。
- [ ] T6 归档;业主装机回显 0.98.9 + 走真机清单。
