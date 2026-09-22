# 挑战腿 1:Cursor CLI / cursor-grok-4.6-high(xai 家族),subcursor explore,rc=0

> 原始日志 `/root/aiwork/logs/explore-electron-shell-20260921-2339.cursor.log`(流 `.cursor.stream.jsonl`)。下面是 .log 全文,未删改。

I'll read the snapshot diff and the current OpenDesign shell, installer, and update paths so the recommendation is grounded in the repo rather than the brief.
The track files are still templates, so I’ll inspect the real shell, installer, updater, and window-chrome code next.
Next I’ll read the shell’s process/window code, the NSIS installer, and the updater, because those are where a full Electron swap would actually fail.
**Direction:** 只把窗口和托盘换成 Electron 宿主；安装器、自动更新、后台两条腿、单实例锁协议一律不动。`installer/OpenDesign.nsi`、`bin/ds_update.py` 的 `ASSET_RE`、`bin/ds_update_apply.py` 的旁路换名、`bin/ds_shell_core.py` 的 `Supervisor` / `InstanceLock` 继续当主路径。ZCode 只拿它的窗口做法（`frame:false`、默认 `thickFrame`、preload IPC、托盘 show 后 `invalidate`），不拿它的安装器和 updater。

**Core bet:** 业主真正要的是「打开还是原来那个界面，右上角能缩小放大退出，缩小有动画、能贴边、能拖边」。把安装器和更新器一并换成 electron-builder / electron-updater，并不会让这句话更真，却会在「卸旧装新」和「之后第一次自动更新」两处把已经用真机买来的安全性质清零。窗口层单独换，现有 `OpenDesign-Setup-<版本>.exe` 管道仍能把 Electron 宿主送上 `F:\AI\OpenDesign` 和 `D:\AI\OpenDesign`，业主甚至不必先卸一次。

---

完全按「四样全换」做完，业主目标仍会落空的具体场景：

1. **过渡那一刻（办公室 `F:\`）。** 他按「选 A」去做：托盘未必先点「退出」（`OpenDesign.nsi` 欢迎页已经警告过程序在跑时 `RMDir /r` 会静默跳过）。旧卸载器认哨兵 `ds\bin\ds_shell.py`，目录非空、文件锁着 → 界面显示卸完，`F:\AI\OpenDesign` 里还剩半棵 Python 树。接着 electron-builder 装进同一目录，两套启动器、两套卸载条目叠在一起。他双击桌面图标，打开的可能是旧 `OpenDesign.exe`（`launcher.nsi` 仍去找 `python\pythonw.exe`），新壳根本没被点到。资料还在 `%LOCALAPPDATA%\OpenDesign`，他却以为「换壳失败、软件坏了」。

2. **过渡那一刻（勾错卸载选项）。** 旧卸载器第二节 `un.连我的资料一起删掉` 默认不勾，但文案对他这个非程序员是可读可勾的。勾了 → `RMDir /r "$LOCALAPPDATA\OpenDesign"`，项目档案、对话、`UserData` 里的 key 文件一起没。新壳装得再漂亮也救不回。这是「选 A」独有的、四样全换才被发明出来的步骤；现有自动更新故意不走卸载。

3. **家里那台还没卸。** 发版资产一旦改成 electron-builder 的 `latest.yml` + 带空格的 Setup 名，家里仍在跑的 `ds_update.py` 只认 `OpenDesign-Setup-<版本>.exe`（`ASSET_RE`，`installer/build-installer.sh` 开头把改名后果写成「静默跳过、不报错」）。他在家打开软件：设置里要么「已是最新」，要么查不到。办公室已经在新壳上，家里冻在旧版。两台电脑、同一人、同一天的使用习惯被劈开。

4. **之后第一次自动更新（已换上 electron-updater 的那台）。** 本仓至今全部 release 都是 prerelease；`ds_update.py` 模块注释写明 `/releases/latest` 会 404，必须自己扫列表。electron-updater 的 GitHub provider 默认跳过 prerelease，再叠加业主商用 VPN 出口已真实咬过的 60 次/小时限流（他们才改成 `releases.atom` + `OpenDesign-update.json`）。第一次检查的结果是：界面像「没有新版本」，实际线上已经有。这不是实现漏了，是发现通道被换掉。

5. **之后第一次自动更新（文件锁）。** `ds_update_apply.py` 开篇写死：活着的 `.exe` / `.pyd` 覆盖不了，09-08 否掉就地覆盖，因为 `RMDir` 删不掉会静默跳过。electron-updater 的 `quitAndInstall` 默认就是退出后就地覆盖。ZCode 只等自己的 host；这边 `start_backend` 还要再起 nanobot 和 `ds_web.py`，Job 在 `Supervisor._assign_windows_job`。Electron 退了、Python 子进程没退干净 → 装到一半一半新一半旧，下一次双击打不开。看起来像「更新完坏了」，和 09-08 否掉的形状相同。

6. **装上之后第一次打开（对话「丢了」）。** 前端把项目↔对话映射、自动更新开关、图库列数写在 `localStorage`（`web/src/App.tsx`、`GalleryPage.tsx`、`chat/projectThread.ts`）。WebView2 档案和 Electron 的 Chromium `userData` 不是同一份。PKB 还在 `%LOCALAPPDATA%\OpenDesign\Data`，但他点进项目会开一条新对话。他看到的是「换壳把聊天弄没了」。

7. **填完 key 聊天仍不通。** 网关重启走的不是「窗口 IPC」，是 `ds_web.ds_shell_bridge_restart` → `InstanceLock` 的 `LOCK_RESTART`。更新交棒是同一条锁上的 `LOCK_UPDATE`（`ds_shell.py` 的 `update_handoff` 必须 `state.on_quit()`，只停后台不够）。Electron `requestSingleInstanceLock()` 只解决第二份进程，不接这两个动词。他在界面里存了 key，前端若还当「已生效」，网关仍是旧 env。

---

**哪个前提是假的，整案就要重做：**  
「electron-updater 可以代替现有发现+旁路换名，并且第一次更新在自定义目录、prerelease、VPN、Python 文件仍锁着的条件下不把活树装坏。」  
这条若假，安装器和更新器那两样必须退回现在的 NSIS / `ds_update_*`，四样全换等于白做，而且还要再做一次身份迁移。

最小证伪（适合 `windows-latest`）：用现有 `windows-update-e2e.yml` 的骨架，旧包仍是今天的 `OpenDesign-Setup-*.exe`，新包改成 electron-builder NSIS；自定义目录带空格（e6/e7 已经在考这个）；子进程故意不退出；发一个 **prerelease**；用替身 GitHub。看三件事：发现阶段是否当「没有新版」、`$INSTDIR` 是否仍是自定义目录、活树是否出现半新半旧。现有 `verify_new_tree` 认的哨兵仍是 `ds\bin\ds_shell.py`——新树形状一对不上，旧更新器也会拒装。

窗口层还有一个更早的前提，假了连「只换壳」都该停：ZCode 的 `frame:false` + 默认 `thickFrame` 在 **本仓库这份前端** 上不会再演出 0.93 那种「几何正常、画面是底色」。ZCode 自己已经要在 resize / 从托盘 show 后 `invalidate()`。08-25 白屏根因未定，`tracks/opendesign-webview2-fixed-version/proposal.md` 仍把系统 WebView2 换核当嫌疑人——换 Chromium 可能躲开那条，也可能只是换一种合成层白屏。这个前提用下面的第一步就能打，不必先动安装器。

---

**How it works:** Electron 主进程只做现在 `bin/ds_shell.py` 里 pywebview / pystray / `WindowApi` 做的事：无边框窗口、托盘、把页面接到 `window_url()` 那种 `http://127.0.0.1:<端口>/?shell=1`。后端启动仍走 `start_backend` → `core.pick_ports` / `patch_config` / `prepare_data_root` / `Supervisor`；key 仍只进网关那条 env（`service_envs`），永不进渲染进程、永不进 ds-web。`WindowChrome.tsx` 的 `window.pywebview.api` 换成 preload 里预先暴露的 `minimize/maximize/close`（preload 在第一帧之前就位，直接拆掉他们栽过四次的注入时机）。拖边交给 Electron 的 `thickFrame`，八个 `.win-grip` 可以撤。启动器仍是 `installer/launcher.nsi` 那只小壳，只把 `Exec pythonw ds_shell.py` 改成启动 `OpenDesign.exe`（Electron）再由它拉 Python。安装器继续 `InstallDirRegKey HKCU Software\OpenDesign`、资料仍在 `$LOCALAPPDATA\OpenDesign`、更新仍 `/S /UPDATE /D=<dir>.new` 再两次改名。Linux 上 git-pull / 浏览器开 ds-web 不带 `shell=1`，`inDesktopShell()` 继续不画按钮。

**Best at:** 业主两台自选目录、卸/更新不许碰资料、打开不被查更新卡住、填 key 后锁通道重启网关——这些已经用真机和 `windows-update-e2e.yml` 买过的性质继续有效。换壳这一版可以走现有自动更新送到两台机器，不必让非程序员执行「卸旧装新」。版本仍只加第三位（现在 `ds_web.py` 的 `VERSION = "0.98.9"`）。

**Sacrifices:** 包里会同时背 embeddable Python 和 Electron（业主 08-30 说过体积不是问题）。得不到 electron-updater 的差量包和 ZCode 那条发版流水线。窗口手感、贴边、最小化动画仍然只有业主真机最终点头；CI 截图只能抓住「界面还在不在 / 最大化有没有盖住任务栏 / 托盘还原是不是只剩底色」。自绘三个按钮暂时还要（ZCode 也是自绘）；08-25 他已经说过「不一定我们自己画」，这条路没有去吃「把按钮交还给 Windows」的更便宜解。

**Blind spots in the brief:** 「窗口、托盘、安装包、自动更新全部换成 ZCode」是 agent 从「参考一下 zcode 这一段前端代码」扩出来的；业主认可的是转述，不是对 `/UPDATE`、prerelease、`ASSET_RE`、旁路换名的知情同意。ZCode 前端解决的是无边框和三个按钮，不是发现通道，也不是「程序在跑时 RMDir 会静默跳过」。选 A 本身是安装器身份一换才出现的步骤；只换宿主则现有更新器可以当桥。Brief 没写第二台电脑会在旧更新器上停多久，也没写 `localStorage` 换内核档案等于丢项目↔对话映射。`InstanceLock` 被写成「单实例」，它同时还是填 key 重启和更新交棒的唯一通道。08-13 已经用真机否过 Electron（`tracks/opendesign-windows-installer/design.md`）；08-25 `opendesign-shell-reselect` 的触发条件是「再有一趟窗口层真机白跑」等，不是「看到一份开源前端」。git-pull / Linux 浏览器路径和「外部执行腿不许联网」在四样全换里最容易被 electron-builder 的 Windows 构建假设踩掉。

**Smallest first step:** 在现有 `.github/workflows/windows-package-probe.yml` 旁边加一支一次性探针：打一个 **不进正式安装器** 的 Electron 试验窗，`frame:false`、`thickFrame` 默认开，load 已装好的 `http://127.0.0.1:<ds-web>/?shell=1`（或把现在的 dist 指过去），截四张图——首屏、最大化（任务栏是否还在）、关进托盘再双击还原、还原后 500ms。附带 `webContents` 是否只剩背景色。这一步不改 `OpenDesign.nsi`，不改 `ds_update_*`，不碰资料根。图是白的或托盘还原只剩底色 → 停，四样全换更不该开。图里界面还在、最大化没盖任务栏 → 再把 `launcher.nsi` 改成拉起这个宿主，用 **现有** `OpenDesign-Setup-0.98.10.exe` 名字走 `windows-update-e2e.yml` 的旁路换名，验证自定义目录和 `/UPDATE` 不跑 `ProvisionConfig`。只有这两步都绿，才存在「要不要再碰安装器身份」这个问题；以现在仓库里已经写明的更新契约，答案应是不必再碰。
