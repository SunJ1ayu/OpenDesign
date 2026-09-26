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

```
runlog: assets-ready rc=0 commit=e3cced8 dirty=yes final=yes at=2026-09-26T08:00:03Z file=tracks/opendesign-release-09814/evidence/20260926T080003Z-01-assets-ready.txt
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

- 第1轮实质发布评审;派前preflight BLOCK=0 / PENDING=1(待评审和仲裁)。
- 同一次两家族: `subdeepseek=PASS(verdict=PASS) subcursor.grok-4.7-high=PASS(verdict=PASS)`。
- 绑定记录在 observations/20260926T075933Z-panel-review-execution_finished-001.json;
  原始日志 /root/aiwork/logs/panel-release14-review-20260926.*.log,摘要如下,日志本身不作口头证明。
- 工具报verify.md反锚定提示:本文件初审前只填机械结果和QA文案处置,发布主裁自审结论在仓外。
  两家工具事件未读取仓外my-review;没有把该结论喂入题面。Grok直接复核产品及证据,
  DeepSeek另外重算三样hash、重跑check-assets及相关单测。

| 发现 | 核实与用户影响 | 处置 |
|---|---|---|
| DeepSeek:升级入口箭头仍像第三级菜单 | 软件更新是常规页区域,说明第17行/清单第1步已明确;用户到常规页即可找到区域 | 接受低风险措辞,不为非阻断再改说明并新增评审轮 |
| DeepSeek:结构闸未列ds_sessions.py | 组包bin/*.py包含它;ds_web顶层import使真实Windows起窗断言可拦缺模块 | 当前验证充分;不扩为任意未来改坏打包的防护单 |
| DeepSeek:识别不了当前模型所属厂商时按钮只显示模型名 | modelPicker.ts:117-122有意避免误标厂商,属composer已归档边界 | 接受;正常已知模型显示厂商和模型,真机回显保留 |
| DeepSeek:离线评审不能再向GitHub查run | 主裁在线亲查两个job成功/head,cloud-check完整141项收据和出货字节已核 | 已满足,不把离线边界当产品缺陷 |

主裁:发布准备通过。版本/产品源码与被测提交一致、出货三样字节相符、Windows141项全过;
两家族同次PASS,没有阻断。发布动作与真实安装后回显仍未完成,
所以decision.outcome.verdict保持null、T4/T5未勾、不得归档为已发布。

## Release

尚未发布。安装包在 /root/opendesign-release14/artifact/,改写后的更新清单 sha512 / size 与安装包一致,三样 sha256 已冻在 evidence/asset-manifest.json。当前产品源码与被测 b37b8dd 逐文件一致(除 tracks)。
正式发布审批与安装后真机回显待完成;不自动开延期项或aiwork腿池单。
