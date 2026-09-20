# Proposal: OpenDesign 0.98.8 发布

- Date: 2026-09-20
- 业主原话：「现在就发 0.98.8」(2026-09-20 17:5x,在我汇报"修复还没到你那儿"之后拍的板)。

把已归档 PASS 的 `opendesign-startup-not-blocked-by-update`(打开软件不再被更新检查挡住)
发布为可被现有客户端发现并安装的 0.98.8。范围只有版本字符串、Windows 探针默认值、发布工件;
不动业务行为、安装器与判据。沿用现有 prerelease 渠道。
原功能验收与四轮外审见 `../archive/opendesign-startup-not-blocked-by-update/verify.md`。

## 验收

本地回归无新增失败;安装包结构/静态/成品闸通过;已发布安装包与本地构建、与清单哈希逐字节一致;
产品真实更新检查从 **0.98.7** 识别 0.98.8;Windows 云机探针回显 0.98.8。
业主自己那台装没装由他现场确认,**本单不宣称远程完成他的设备部署**。

## 风险定级

impact-risk **self** —— 纯发版单,外审预算 0(业务逻辑的双家族外审已在原功能 track 完成)。
design-uncertainty **low** —— 流程与 0.98.7 那单逐步同形,无新未知。
