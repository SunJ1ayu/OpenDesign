# Proposal: OpenDesign 0.98.9 发布(Electron 外壳首版,正式 release `v0.98.9`)

- Date: 2026-09-23
- 业主原话(09-23 00:0x):「ok 你测完直接发布吧」—— 授权推送源码与发布;问「直接更新还是卸载再下载」。
- 把已归档 PASS 的 `opendesign-electron-shell`(含已归档的 `opendesign-per-vendor-keys`,0.98.9 从没发出去)发成正式 release `v0.98.9`。
  取代 `opendesign-release-0989`(旧壳 prerelease 方案,ARCHIVED-SUPERSEDED)。换壳单移交过来的承诺 ⑤:业主真机 A0。

## 本单做什么

1. **出货包流水线**(发版前发现的洞):`electron-e2e` 测的包更新源指本机替身,RELEASE.md 说「从 workflow artifact 取回三样资产」但 workflow 根本不传出货包。
   ⇒ 同一次运行里另打出货版(更新源 = GitHub,不打补丁),云上当场核:更新源地址、与被测版逐文件只差更新源、清单字节;上传三样资产。
2. **「所有用户」分支**(换壳单延期、答应业主发布前补测):读模板发现真 bug —— 选「所有用户」时首装 provision 写进 `C:\ProgramData`,
   而软件运行时读的是当前用户的 `LOCALAPPDATA` ⇒ 全新机器打开就报「还没装好」;业主机器上会留一份没用的配置。修 + 云上业主误点场景 E7。
3. 推送 main + 发布正式 release(三样资产);发布后生产源 smoke(`releases/latest/download/latest.yml` → 安装包 / blockmap 取得到)。
4. 业主两台**手动装一次**(旧更新器认不出新名字),错开一天 ⇒ 真机回显版本 + A0「界面出来了吗」。

## 验收边界与轮次预算

- 承诺:发出去的安装包来自云上测过的同一次运行、与被测版只差更新源;更新源指 GitHub;发布后生产源三样都取得到;
  旧壳 0.98.8 的旧更新器看不见它;选「所有用户」也能装、资料不动、配置落在当前用户下;业主真机 A0。
- 不承诺:下一版经自动更新在**生产**上走通(要等下一版才能真走;云上 E4 已用 GitHub 真实布局替身验过)。
- 实质评审上限:2 轮(impact=high:公开发布 = production_side_effect;改云判据 workflow = judging_control)。每轮派发前先跑 `track preflight`。
