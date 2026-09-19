# Verify: OpenDesign 0.98.7 发布

## 范围

代码面只有版本字符串 + CI 探针四处默认值 + 一段版本说明注释。
业务行为(启动立即更新)的验收与外审属于原功能 track,见
`../archive/opendesign-auto-update-countdown/verify.md`,本单不重复计入。

## 收据(机器写的,逐字节粘;别手改)

runlog: release-regression rc=3 commit=167e60d dirty=no final=yes at=2026-09-19T12:58:21Z file=tracks/opendesign-release-0987/evidence/20260919T125821Z-01-release-regression.txt
runlog: build-installer-0987-release rc=0 commit=c78851e dirty=no final=yes at=2026-09-19T13:28:08Z file=tracks/opendesign-release-0987/evidence/20260919T132808Z-01-build-installer-0987-release.txt
runlog: published-bytes-match-0987 rc=0 commit=c78851e dirty=yes final=yes at=2026-09-19T13:33:12Z file=tracks/opendesign-release-0987/evidence/20260919T133312Z-01-published-bytes-match-0987.txt
runlog: real-update-check-from-0986 rc=0 commit=c78851e dirty=yes final=yes at=2026-09-19T13:33:45Z file=tracks/opendesign-release-0987/evidence/20260919T133345Z-01-real-update-check-from-0986.txt

Windows 真机探针:run 35446165320(headSha c78851e,conclusion success)
  PHASE 1  下载安装包   OK —— OpenDesign-Setup-0.98.7.exe,44.6 MB
  PHASE 5  服务活了吗   OK —— /api/health 通(端口 8766,**version=0.98.7**)
  PHASE 10 带系统代理启动 OK —— 45s,颜色 76 种 / 近白 27.5%
  裁决收据独立复核:no FAIL verdict in the receipt
  (探针自己写着:**白屏读数不在闸内**,仍要看图。76 色 / 27.5% 近白不是白屏形态。)

## 判读(三条,别让收据被误读)

**1. 回归 rc=3 不是失败。** 六段全 PASS、0 FAIL:泄漏闸 14 条、node 451 通过/0 跳过、
python 1727 跑过/1 跳过、MCP 三闸全绿、dist 与源码同步、e2e 41 PASS/0 FAIL/2 SKIP。
rc=3 = 那 3 条没跑(gateway 相关),与历史 `9e7f95d` 记的同形。
run-all.sh 自己的话是「没有红的,但有 3 条没跑 —— 不算通过」;要真绿须起 gateway 跑 `--with-gateway`。
这一版没碰 gateway 那条路,本单不因此挡发布,但**也不许把它说成全绿**。

🔴 **2. `real-update-check-from-0986` 里「0.98.5 也查得到」是假绿,不许引用。**
那一段跑的是**本仓当前代码**(= 0.98.7 的查更新实现),不是 0.98.5 里那份只问 GitHub API 的旧实现。
装着 0.98.5 的机器查不查得到,这条收据**证明不了**——09-16 正是栽在这:
修复在 main 上、而业主手上那版早于修复,他点了没反应。
真正成立的只有第一段:**当前版本 0.98.6 → 查到 0.98.7**,digest 与清单一致。
发布说明里因此写明 0.98.5 及更早请手动装。

**3. 已发布字节 == 本地构建 == 清单描述**,并逐字节 `cmp` 通过;
清单 sha256 从构建产物本身算(`make-update-manifest.py`,不许手写)。

## 还欠

**业主真机一趟**(只有他能做):在他自己的机器上装一次 0.98.7,并回显版本。
云 Windows 回显 0.98.7 只证明安装包在干净机器上装得上、起得来,
**不等于他那两台(公司 F: / 家里 D:)也一样** —— 那两台有他的真实档案和参考图库。
