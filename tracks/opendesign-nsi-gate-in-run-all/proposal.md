# Proposal: `.nsi` 的静态闸接进总跑(现在改坏它可以带绿通过)

## 事实

`tests/run-all.sh` 六段里**没有一段**碰安装器:既不编 `.nsi`,
也不跑 `installer/check-installer.py`(全仓 grep:唯一调用点在
`installer/build-installer.sh`,**发版打包时才跑**)。

⇒ **改坏 `installer/OpenDesign.nsi` 可以带着一片绿通过 `run-all`,直到发版才炸。**

## 已经被这个洞咬过一次

2026-08-25,track `opendesign-fresh-install-fix`:我把 `/SD` 写在了正文前面,
`s2`/`s3` 全绿,而 `makensis` 当场 abort(`OpenDesign.nsi` line 191)。
事后补的 `s4` 只覆盖"`/SD` 写在正文前"这**一种**错法。

## 两条腿独立命中

panel 的 subglm 和 submimo 各自把这条列为 MEDIUM/第 5 点,措辞不同、结论一致:
**至少把 `check-installer.py static` 接进总跑**(它是纯 Python、不需要 makensis,
17 条静态闸,只是从来没有人在总跑里叫它)。

## 打算怎么做(待 design 定案)

1. `run-all.sh` 加一段跑 `installer/check-installer.py static installer/OpenDesign.nsi
   --launcher installer/launcher.nsi`,rc 用 `if !` 直接接(不许 `;`/管道吞掉)。
2. 想清楚要不要连 `makensis` 一起(它要 apt 下载锁版本的 deb —— 总跑里做这件事
   会把"离线也能跑"这条性质弄没,可能该留在打包步)。
3. 顺手把邻居那笔账收了:`tests/test_installer_slim.py:216` 那条死断言
   (track `opendesign-installer-slim` 留下的,**那一单至今没有任何 run-all 收据**)
   —— 要么搬到问得出的地方,要么带理由写进 `tests/dead_assertions.allow`。

## 注意

**这是判卷防线的改动** ⇒ 要红检(改坏 `.nsi` 之后闸必须真的红),
并且改了判卷工具就得跑它自己的判据。
