# Design: opendesign-release-09814

## Goal-to-design check

用户目标是用上三项已定改动。发布契约沿用 installer/RELEASE.md 与 0.98.13 的已验证路径;
本单仅换版本、包和说明,不引入升级迁移或新写入口,方案检查保持轻量。
出货先经同一 CI 的产品包 / 被测包逐文件比对,再取包,不把提前上传的 artifact 当整跑成功。
未经最终发布授权不创建正式 release;准备完说明、验收结果和命令后收口。

## Approach

1. bump ds_web.VERSION / desktop package / lock 根版本到 0.98.14。
2. 只推 ci-electron/rel-09814 接受云验证;主分支与正式 release 留到发布动作。
3. 取成功 run 的 release 三样,verify / rewrite / verify feed。
4. QA 黑盒看说明和真机清单;发布评审只查升级契约与实际交付。

## Oracle

本地最终总跑(既有 3 条 SKIP 明列)、云 Windows E1–E7 所有断言 FAIL 0;
版本三处相等,出货安装包名、size、sha512、blockmap 和 latest.yml 可核对。
若授权发布,正式源 smoke 核 latest/tag/三样字节与 CI 一致,再归档。

## Known limits

模型真实超时与 Windows 中文输入法需真机回显。反复改名 / 重名后少数旧对话项目归属仍可能不准,
按时间仍可找到;不声称任何重名都正确。升级器沿用旧版,真实 0.98.13→14 的最后一跳由业主安装确认。

## Independent checks

先查当前池,发布评审选 DeepSeek + Cursor Grok(健康、不同家族)。
QA 每个可用家族一条:MiMo、DeepSeek、Cursor Grok / Gemini / Composer / Kimi / GLM。
OpenAI 为本单主裁家族、Claude 为三项功能原作者家族,避免作者复核自己的说明。
