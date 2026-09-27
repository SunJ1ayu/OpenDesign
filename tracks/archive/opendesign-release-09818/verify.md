# Verify: OpenDesign 0.98.18

用户授权合并及正式发布，已完成。
PR #4 合并提交 92b92e8，复核源码 62f7848；被测打包提交 8986c7a。
本 track 只改版本元数据，沿用现有发布流水线。

## Local regression

597 条 Node 通过；1605 条 Python 运行，1 条 Windows 平台项跳过；
47 个浏览器场景通过，0 失败，2 条活网关项跳过。三条既有跳过不计作通过。
MCP、死断言、泄漏闸、TypeScript 和 dist 新鲜度通过。
浏览器 harness 为 workspace_picker.e2e.mjs 收容一次临时残留，已自动清理，泄漏闸通过；保留该提示。
详见 evidence/local-check.json 和 local-regression.log。

## Windows and assets

run 36328729027 精确 head=8986c7a，payload/e2e 两个 job success，141 项断言通过、0 失败。
运行中的后台与 exe 都回显 0.98.18；升级保留配置业务字段。
出货版与被测版只差更新源，正式源指向 GitHub releases/latest/download。
三项资产大小、SHA-256 已冻结；原始和发布用 latest.yml 的 size/SHA-512 均与安装包一致。
详见 evidence/cloud-check.json 和 manifest.json。

## Production

正式 release：https://github.com/SunJ1ayu/OpenDesign/releases/tag/v0.98.18
非 draft / prerelease，tag 指向被测源码 8986c7a，资产恰好三项。
公开 latest.yml 回显 0.98.18，公开下载安装包和 blockmap 的大小、SHA-256 均匹配冻结资产；
线上 feed 的 SHA-512 与公开安装包一致。0.98.16 的旧 blockmap 仍可下载。
production-smoke.json 保存 25 项公开源核对结果。
用户电脑的实际安装操作由用户完成，不将用户机器回显计为已验证。

## Machine receipts

初次版本契约测试 33 条通过；附属 observation 在原独立工作树定位失败，未当作成功覆盖。
收尾转到独立仓库存档，local-result-audit 与 production-smoke 的 observation 已成功保存。
公开校验是正式地址下载与字节验证，本地总跑的退出码 3 代表既有跳过，未隐藏。

```
runlog: version-contract rc=0 commit=92b92e8 dirty=yes at=2026-09-27T15:11:55Z file=tracks/opendesign-release-09818/evidence/20260927T151155Z-01-version-contract.txt
```

```
runlog: local-result-audit rc=0 commit=8986c7a dirty=yes at=2026-09-27T15:30:33Z file=tracks/opendesign-release-09818/evidence/20260927T153033Z-01-local-result-audit.txt
```

```
runlog: production-smoke rc=0 commit=8986c7a dirty=yes final=yes at=2026-09-27T15:44:05Z file=tracks/opendesign-release-09818/evidence/20260927T154405Z-01-production-smoke.txt
```

