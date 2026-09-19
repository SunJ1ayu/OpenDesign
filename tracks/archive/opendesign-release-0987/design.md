# Design: OpenDesign 0.98.7 发布

采用现有 installer/build-installer.sh 与 make-update-manifest.py。
版本唯一来源 bin/ds_web.py；同步 windows-package-probe 的四处默认值。
使用独立构建目录，复用旧版下载缓存，不复用旧版 payload。
先验证，再上传安装包和清单；通过后发布 prerelease，取回产物核对并用产品代码检查更新。
不新增写口、不改变权限/安装/更新协议；本单风险沿用纯发版单 self、方向确定。
既有业务变更及 Windows 更新九场景证据属于原功能 track，不重复伪造成本轮测试。
