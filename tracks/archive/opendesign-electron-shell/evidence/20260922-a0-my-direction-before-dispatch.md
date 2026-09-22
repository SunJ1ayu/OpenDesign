# 我的方向与最危险前提(派发独立方案挑战之前落盘,**不给挑战腿看**)

- 时间:2026-09-22,派发前。方向全文 = design-studio `tracks/opendesign-electron-shell/design.md` 的「Approach(草案 v1)」
  (commit 93c6925 + 未提交的 blockmap 一条);挑战腿拿到的仓库快照里删掉了 design.md / verify.md / 上次两家的挑战报告,且无 git 历史。

## 方向一句话
照探路版:Electron 主进程(窗口/托盘/单实例/更新器)+ Python 管家 `bin/ds_host.py`(stdin/stdout JSON);前端改接 `window.odShell`;
electron-builder NSIS(oneClick:false、为哪位用户页保留);electron-updater 后台下增量、用户点「重启以更新」→ 向导两下;
旧 Python 更新器 / ds-web 更新端点 / 开机更新画面 / 旧安装包工具链整体退役;发布改 `v<版本>` 正式 release、CI 构建、业主发布;
版本号唯一来源 ds_web.VERSION;blockmap 取旧版自己 release 的(previousBlockmapBaseUrlOverride)。

## 我最担心的前提(按危险度)
1. **业主一直不点「重启以更新」**:C 把「自动」变成「提醒 + 点」,旧的开机自动装与「同一版只试一次」「回滚提示」全退役 ⇒ 若提醒不醒目,
   两台机器会长期停在旧版,而我们以为更新通道是好的。没有任何遥测能告诉我们他没点。
2. **第一次更新的增量**:previousBlockmapBaseUrlOverride 指向 `releases/download/v<旧版>/` —— 未实测 GitHub 该路径对 blockmap 的 Range/重定向行为;
   失败退整包 158MB,在业主网络上(VPN)可能很慢,期间界面要有进度,不能看起来卡死。
3. **CI 构建 + 业主手动发布**:安装包字节来自 GitHub Actions,我只能下载核对 latest.yml 的 sha512;若业主发布时传错文件/漏传 latest.yml 或 blockmap,
   更新通道静默断掉(旧版更新器那套「清单随包」的闸也退役了)。
4. **退役面太大**:约 20 个更新判据文件 + 15 个外壳判据文件一次性删除/改写,容易把仍然成立的保证(查不动不说已是最新、资料根不动、Job 收整棵树)跟着删掉。
5. 全新电脑安装没有开机自启勾选项(已知回归,延期)。
6. 10,067 个文件每次更新全量重铺,Defender 在业主机器上可能把 2 分钟拉长到更久。
