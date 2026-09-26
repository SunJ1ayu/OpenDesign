# Verify: opendesign-release-09814

- Date: 2026-09-26

## Mechanical checks

本地最终总跑:Node 575 通过;Python 1578 跑过 / 1 SKIP;浏览器 45 PASS / 0 FAIL / 2 SKIP。
三条既有跳过不计通过;MCP契约、3979条死断言扫描、泄漏闸、构建与dist新鲜度通过。
云 Windows run 36226326190 两个job success,head=b37b8ddd4c3be2f35fccf6c8a853caab3036bd0f;
141项断言通过 / 0失败,E7运行中的后台/exe回显0.98.14,资料与配置字段保留。

```
runlog: release-local-final rc=3 commit=b37b8dd dirty=no final=yes at=2026-09-26T07:24:43Z file=tracks/opendesign-release-09814/evidence/20260926T072443Z-01-release-local-final.txt
```

```
runlog: assets-verify rc=0 commit=b37b8dd dirty=yes at=2026-09-26T07:48:14Z file=tracks/opendesign-release-09814/evidence/20260926T074814Z-01-assets-verify.txt
runlog: cloud-windows-e2e rc=0 commit=b37b8dd dirty=yes final=yes at=2026-09-26T07:51:59Z file=tracks/opendesign-release-09814/evidence/20260926T075159Z-01-cloud-windows-e2e.txt
```

## QA

黑盒题面:发布说明与真机清单,仓库参数为没有产品代码的 qa-blackbox-repo。
七家族派发,合格输出五家(DeepSeek/Grok/Gemini/Composer/Kimi),见 evidence/qa-*.txt 和 qa.roster。
MiMo rc=1 EROFS,没有报告;GLM high/max各rc=1(分别缺 How it works / Direction标签),其文字只采建议、不冒充成功或评审覆盖。
不再为基础设施格式问题重复派整份 QA。五家合格输出共识已核对源代码并照改:

| 发现 | 核实 | 处置 |
|---|---|---|
| 停止被理解成撤销已写入项目、不会再收在途文字 | 已归档 composer 的迟到输出延期;停止不回滚工具写入 | 说明和清单改成请求停止、可重新发送、不会撤回已完成操作、少量在途文字可能晚到 |
| 置顶后项目下找不到、全置顶没有数字 | sidebarModel.projectView 抽走 pinned;Sidebar只显示未置顶数 | 两处说明规则;真机第5步用未置顶对话 |
| 版本路径像软件更新子页,两处表述不同 | settings/SettingsPage.tsx:92-101 软件更新是常规页中的区域 | 两处统一为常规页的软件更新区域、当前状态 |
| 仅口头提到项目就算操作、中文输入法验收模糊 | 项目归属只认项目工具/首句前缀;composing期间回车不发送 | 真机看项目中新记录;拼音候选窗回车不直接发送 |
| 关窗口与完全退出混淆;打码可能理解为乱码 | Windows关窗进托盘;modelError.maskKeys隐藏敏感串 | 说明写托盘完全退出;敏感内容隐藏;模型按钮厂商和模型名统一 |

源文修改后主裁逐条复核,不整份复判;没有产品代码修改,后续发布评审检查最终说明。

## Review

独立自审在 /root/aiwork/tasks/opendesign-release-09814-review-my-review.md,发布评审待派。

## Release

尚未发布。安装包在 /root/opendesign-release14/artifact/,改写后的更新清单 sha512 / size 与安装包一致,三样 sha256 已冻在 evidence/asset-manifest.json。当前产品源码与被测 b37b8dd 逐文件一致(除 tracks)。
正式发布审批与安装后真机回显待完成;不自动开延期项或aiwork腿池单。
