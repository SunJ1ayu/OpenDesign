# Proposal: OpenDesign 0.98.12 发布(正式 release `v0.98.12`)

- Date: 2026-09-24
- 业主原话:09-24 22:1x 问「0.98.12 什么时候发?发布后你两台机器下次打开会自动更新」,业主选「**现在就发**」⇒ 授权推送 main + 创建正式 release。
  同一问答里业主定:测试员(QA)角色以后每单都用 ⇒ 本单的 QA = 让两家测试员以业主视角看发版说明与真机清单。
- 发的内容(已归档 PASS):`opendesign-zcode-model-settings`(`49c6986`)—— 照 ZCode 重做设置页与模型设置、聊天框两级换模型。

## 本单做什么

1. 版本号 0.98.11 → 0.98.12(`bin/ds_web.py VERSION`、`desktop/package.json`、lock 根版本;只加第三位)。
2. 本地总跑;云 Windows `electron-e2e` 整跑 FAIL 0,从同一次运行取出货三样。
3. QA:两家测试员看中文发版说明 + 业主真机清单(说没说人话、有没有漏告诉他的变化);两家族发布评审。
4. 推送 main;照 `installer/RELEASE.md` 发布正式 release + 中文说明;发布后生产源 smoke(latest 指向 0.98.12、字节 = artifact、旧 blockmap `download/v0.98.11/` 在)。
5. **发布 + smoke 当天归档**;业主真机回显事后补进已归档 verify.md。

## 验收边界与轮次预算

- 承诺:发出去的安装包来自云上测过的同一次运行、与被测版只差更新源;正式版三样资产;生产源 latest 指向 0.98.12 且字节一致;
  已装 0.98.11 的机器能从生产源看到 0.98.12。
- 发版说明(中文)要写:设置整页 + 模型设置照 ZCode;小米 v2.6-pro / v2.6-flash;自己加模型 / 自定义供应商 / 禁用 / 测试;
  限制 —— 自定义供应商要先有一家内置厂商的 key、只支持 Chat Completions 格式;「测试」会花一点点额度。
- 不承诺:业主真机结果(事后补记)。
- 实质评审上限:2 轮(impact=high:公开发布 = production_side_effect)。题面只问发布会不会弄坏东西;「锤子砸墙」类照报不算阻断。
