# 挑战腿 2:DeepSeek(deepseek-flash,agent 底座自读仓库),subdeepseek-agent explore,rc=0

> 原始日志 `/root/aiwork/logs/explore-electron-shell-20260921-2339.deepseek.log`(流 `.deepseek.stream.jsonl`)。下面是 .log 全文,未删改。

# subdeepseek-agent explore log
time: 2026-09-21T23:39:43+08:00
mode: explore (agent base: claude-code headless -> deepseek)
base_url: https://api.deepseek.com/anthropic
model: deepseek-flash
repo: /root/.openclaw/workspace/projects/design-studio
task: /root/aiwork/tasks/opendesign-electron-shell-challenge-brief.md
视野: 底座腿 —— 自己读仓库(Read/Glob/Grep)+ 只读 git(自己跑 git diff/log/show)。

  → Bash ls -la && git log --oneline -8

  → Bash ls tracks/opendesign-electron-shell/ 2>/dev/null && find tracks/opendesign-electron-shell -type f | head -50

  → Read /root/.openclaw/workspace/projects/design-studio/tracks/opendesign-electron-shell/proposal.md

  → Read /root/.openclaw/workspace/projects/design-studio/tracks/opendesign-electron-shell/design.md

  → Bash wc -l bin/*.py installer/* web/src/*.ts* 2>/dev/null | tail -40

  → Bash ls bin installer .github/workflows web/src web/src/workspace

  → Read /root/.openclaw/workspace/projects/design-studio/web/src/workspace/WindowChrome.tsx

  → Read /root/.openclaw/workspace/projects/design-studio/web/src/shellWindow.ts

  → Read /root/.openclaw/workspace/projects/design-studio/bin/ds_update_startup.py

  → Read /root/.openclaw/workspace/projects/design-studio/bin/ds_auto_update.py

  → Read /root/.openclaw/workspace/projects/design-studio/bin/ds_update_apply.py

  → Bash grep -rn "DS_SHELL_LOCK_PORT\|OPENDESIGN_AUTO_UPDATE\|_app_dir\|def _data_root\|LOCALAPPDATA" bin/*.py | head -40

  → Bash grep -n "def \|class " bin/ds_shell_core.py | head -80

  → Read /root/.openclaw/workspace/projects/design-studio/bin/ds_shell_core.py

  → Read /root/.openclaw/workspace/projects/design-studio/bin/ds_shell_core.py

  → Bash grep -n "^def \|^class \|^    def \|APP = \|MARK\|SHELL_MARK" bin/ds_shell.py | head -80

  → Read /root/.openclaw/workspace/projects/design-studio/bin/ds_shell.py

  → Read /root/.openclaw/workspace/projects/design-studio/bin/ds_shell.py

  → Bash grep -n "SENTINEL\|DATA_ROOT\|InstallDirRegKey\|UpdateMode\|/UPDATE\|InstallDir\|Section\|版本号\|provision" installer/OpenDesign.nsi | head -60

  → Bash cat installer/launcher.nsi && echo ---- && sed -n '1,60p' installer/build-installer.sh

  → Bash grep -n "ASSET_RE\|releases.atom\|prerelease\|def \|MANIFEST\|update.json" bin/ds_update.py | head -60

  → Read /root/.openclaw/workspace/projects/design-studio/installer/make-update-manifest.py

  → Bash grep -n "BACKGROUND_FIRST_CHECK_MS\|500\|api/update\|checkForUpdate\|handleStartupAutoCheck\|auto" web/src/update.ts | head -40

  → Bash grep -n "update\|health\|nonce\|VERSION =" bin/ds_web.py | grep -i "def \|route\|VERSION =\|nonce" | head -50

  → Bash grep -rn "版本号.txt" --include=*.sh --include=*.py --include=*.yml --include=*.nsi . | head -20

  → Bash ls .github/scripts/ 2>/dev/null; ls .github/workflows; sed -n '1,40p' .github/workflows/windows-update-e2e.yml

  → Read /root/.openclaw/workspace/projects/design-studio/bin/ds_update.py

  → Bash ls tests | grep -i "shell\|window\|chrome" && grep -n "def x[0-9]\|def s_\|win-grip\|RESIZE_EDGES" tests/test_shell_window_contract.py | head -30

  → Bash grep -n "win-grip\|has-window-chrome\|win-bar\|win-btns" web/src/app.css | head -30

## Direction
**换壳不换更新器**:Electron 只当"窗口 + 托盘 + python 后端的宿主",安装布局与 `OpenDesign.exe`/`ds\bin\ds_shell.py`/`ds\版本号.txt` 的身份约定一字不改,打包仍走现成的 NSIS 那 6 道闸,更新仍走 python 的"装到旁边再换名 + 回滚"接力器;electron-builder / electron-updater 要等一条 windows-latest 实验证明它们能替掉接力器,才有资格进来。

## Core bet
**ZCode 那套 `quitAndInstall` 之前"等 host/子进程退完"的套路,隐含前提是"我要退出的那个东西就是我自己"。** ZCode 是**同种运行时**(Electron 主进程 + `utilityProcess.fork` 的 Node host,全在 `resources\app.asar` 里),文件占用问题是它自己几个进程之间的事。OpenDesign 是**异种运行时**:Electron 主进程之外还有 `install_root()/python/python.exe`(`bin/ds_shell.py:192`)、两条后台腿、工具服务,它们**全都住在安装树里**,在 Windows 上活着时 `.exe`/`.pyd` 全被文件系统锁着。ZCode 的更新/退出故事里"谁锁着文件、谁来等我"这一段,在这里整套失效——这正是 09-08 否掉"就地覆盖"、改成"装到旁边再换名"的理由(`bin/ds_update_apply.py:19-23`)。**这个前提如果是假的,"四样一起换"的地基就没了,而它和 Electron 好不好用完全无关。**

## How it works
- **主进程**:`OpenDesign.exe` 仍是安装根下那一个文件(`installer/launcher.nsi` 的初衷:稳定身份、快捷方式、开机自启都指它),只是内容从小 NSIS 壳变成 Electron。它依次做:单实例 + 那条 TCP 通道(`ds_shell_core.InstanceLock` 必须在 Node 侧有个等价物,**且只许留一个**——`app.requestSingleInstanceLock()` 和 python 那把锁同时存在,双击第二次两个机制会打架)、挑端口、改写 nanobot 配置、起 python 两条腿、`child_env` 照旧塞 `DS_SHELL_LOCK_PORT`(`bin/ds_shell_core.py:1217`)、子进程进 Job(等价 `_assign_windows_job`,`ds_shell_core.py:925`)、托盘、看门狗、关窗收托盘。
- **窗口**:`frame:false` + 不关 `thickFrame`,缩放边/贴边/最小化动画由 Electron 保住 ⇒ **把八个 `.win-grip-*` 和 `begin_resize` 删掉,不是移植**(`web/src/app.css:249-262`)。留着它们就是八块透明玻璃压在原生缩放边上,拖边出现死区。`tests/test_shell_window_contract.py` 的 x7/x8 要从"把手与方向一一对应"**反过来**改成"把手不许存在"。
- **前端接口压到最小**:`?shell=1` 约定(`web/src/shellWindow.ts:37`)和 `inDesktopShell()` 一个字不改——它是 Linux 上唯一跑得了的那条判据;`window.pywebview.api` 换成 preload 上暴露的**同名四方法**(`minimize/toggle_maximize/close_window/window_state`)。改动面只剩 `WindowChrome.tsx` 一个文件,而且 Electron 的 preload 是**同步可用**的,那段"注入时机栽过四次"的历史(`WindowChrome.tsx:31-38`)换个形状消失。
- **安装包**:`installer/build-installer.sh` + `OpenDesign.nsi` 原样,只是在 `python\`、`ds\` 旁边多铺一个 Electron 目录。数据根仍 `%LOCALAPPDATA%\OpenDesign\`(`OpenDesign.nsi:38`),key 仍在 `UserData\.openDesign\key.txt`(`ds_shell.py:196`)——**卸载/更新碰不到资料这条死线,一个字不用重证**。
- **更新**:不动。`update_preflight_problem`(`ds_update_apply.py:392`)要的 `OpenDesign.exe` + `ds\bin\ds_shell.py` 两个锚点都还在;`verify_new_tree` 比 `ds\版本号.txt` 也还在;接力脚本 `:wait_gone` 的"端口空 + 哨兵文件没人锁"继续成立;前端那条 500ms 只读盘的启动路径(`web/src/update.ts:372`)继续成立;`why_not_auto` 的账本与 `no_shell` 判据(`ds_auto_update.py:50-78`)继续成立。
- **必须同版本一起改的只有两处**:① 收摊交棒——`ds_web` 请外壳关软件那一下(`on_update` 动词,`ds_shell_core.py:528-554`)现在要关的是 Electron,必须由 Node 侧接住这个 TCP 动词;② Job 对象。这两处就是全部新增风险面。
- **过渡**:第一版 Electron 用**两个更新器都解析不了的形状**发布(tag 不叫 `win-installer-<num>`、资产名不匹配 `ASSET_RE`,见 `bin/ds_update.py:44-52`),两台机器谁都看不见它 ⇒ 真正的"手动装一次",而不是"我以为是手动"。下一版恢复常规命名,自动更新链**原路返回**。

## Best at
- 把**唯一在他真机上反复出事的那一层**(窗口)换掉,同时**不碰**那套用 9 个 Windows 端到端场景、3 轮外审、一本"同一版自动只试一次"的账换来的更新契约。
- 让 Electron 真正兑现它最大的好处:**这一层能在 Linux CI 上跑真窗口**(xvfb + `_electron`),而 pywebview + WebView2 永远做不到。0.89 开机崩、0.90 窗口栏整块没画、0.93 全白、以及 08-25 那次根因未定的白屏——全是"只有业主真机能验"造成的。判据该建在这上面。**能验的从"手感对不对"涨到"窗口层有没有画出来"。**
- 一次手动安装只搬一件事;盘上布局没变 ⇒ Electron 起不来时,卸载就是删目录,旧路径原地可用。

## Sacrifices
- 放弃 electron-updater 现成的进度/重启/静默体验和"和 ZCode 一样"的对称美。
- 装出来的树多约 180MB Chromium,**每版更新包的下载体积也会跟着涨**(不只是首装)。业主在 VPN 上,这是真代价,得明说。
- 多一次手动安装(先换壳;更新器若最终要换,另起一版)。这点和你转述给他的"选 a"有张力——但 a 的原意是"过渡版不走自动更新",不是"只能按一次"。
- NSIS 那 6 道构建闸 + 23 条静态判据 + 两条 Windows 探针要继续养着,不能靠 electron-builder 的免费能力顶掉。
- 长期架构债:更新 UI 在 ds-web 里,更新动作在主进程里,两个真相源。

## Blind spots in the brief
1. **"身份锚点"整个漏了。** 全系统判断"我是不是一个装出来的 OpenDesign"只靠一个文件 `ds\bin\ds_shell.py`:安装形状预检(`ds_update_apply.py:39,395`)、新树完整性(`:443`)、收摊闸的文件锁探测(`render_relay` 的 `:wait_gone`)、启动器的完整性检查(`launcher.nsi`)、**旧卸载器的"是不是我们的"**(`OpenDesign.nsi:328`)。窗口搬到 Electron 后这个文件还在,但**它不再是那个跑起来的东西**。于是:旧 NSIS 卸载器(注册表键 `HKCU\Software\OpenDesign`)和新 electron-builder 卸载器(另一套键)会**同时**出现在"应用和功能"里,两个 OpenDesign。他不是程序员,很可能去"清理"那个旧的——而旧卸载器的 `IfFileExists "$INSTDIR\${SENTINEL}"` 在新树上**照样通过**,`$INSTDIR` 又正是我们让他装的同一个目录 ⇒ **他点一下,新装的那份没了。** 反过来,为了躲开这一点而不发 `ds\bin\ds_shell.py`,上面五处全要换锚点。这个岔口决定"手动装一次"能不能真只装一次,brief 里一个字都没有。
2. **两个更新源不可能同时看同一个 release。** 旧更新器认 tag `win-installer-<num>`、资产 `OpenDesign-Setup-<num>.exe`、清单 `OpenDesign-update.json`;electron-updater 认 `latest.yml`/`*.blockmap` 并按 **prerelease 规则**过滤。而本仓 **20/20 全是 prerelease**,旧更新器当年正是踩了 `/releases/latest` 404 才改成 atom + 清单(`bin/ds_update.py:6-12`,原文:"功能永远查不到新版本、界面永远显示已是最新——一条恒绿路径")。**换默认 provider 就是把那个坑原样再踩一遍**(ZCode 自己都绕开默认 provider 去自定义清单,这条线索在 brief 里就摆着)。再加上业主 VPN 出口共用、`api.github.com` 60/小时**已经真咬过**(`ds_update.py:14-18`)。
3. **"能选安装位置"在 electron-builder 里不是同一件事。** 今天是 `InstallDirRegKey HKCU Software\OpenDesign InstallDir`(`OpenDesign.nsi:88`)记住上次装哪儿;electron-builder 的 `allowToChangeInstallationDirectory` 是"这次让你选",默认目录是 `%LOCALAPPDATA%\Programs\OpenDesign`,**不是 `F:\AI\OpenDesign`**。他不会把路径重打一遍 ⇒ 大概率装出第二份。而 `relay_path_problem`(`ds_update_apply.py:356`)已经因为 GBK/OEM 代码页和 `%`/`'`/`^` 拒过路径——新安装器必须对他手挑的那两个目录原样做同一套检查。
4. **没人提"没迁移的那台机器"。** 两台机器,他只会手动装一台。另一台会在某次开机时被**旧**更新器自动升级成 Electron——而且会**判定成功**:`verify_new_tree` 只看 `ds\bin\ds_shell.py` 和 `ds\版本号.txt`,Electron 树两者都有。他没同意过那台机器换。
5. **界面会分叉成两个真相。** 所有更新文案绑在 ds-web 的 `/api/update/*`(`bin/ds_web.py:1133-1415`),electron-updater 在主进程。不同步就是"界面说已是最新,后台在偷偷下 200MB"——而这个仓明确把"回一个点名了动词的 OK 而其实什么都不做"判为**最坏的撒谎**(`bin/ds_shell_core.py:529-533`)。
6. **`ds_auto_update` 那本账在新方案里没有归处。** "同一版自动只试一次"是三轮外审挣来的;electron-updater 默认失败会**一直重试**,业主每次开机被弹一次,永远没有收敛点。

## 三问
**1. 完全照上面实现了,目标仍会怎样落空(两个时刻)**

*过渡那一刻*:他双击 electron-builder 的安装器(默认 `oneClick:false` + 目录页),默认目录是 `%LOCALAPPDATA%\Programs\OpenDesign`。他不会重打 `F:\AI\OpenDesign`。于是两台机器上各出现两个 OpenDesign:开始菜单/桌面/开机自启都还指着旧的,Apps & Features 里两条。他打开的还是旧版。某天他"整理一下",在那个旧条目上点了卸载——旧卸载器认的哨兵在新树上通过,`$INSTDIR` 正是同一路径,**新装的那份被删掉**,他看到"卸载完成"、图标没了。

*之后第一次自动更新*:electron-updater 面对一个 20/20 全是 prerelease 的仓 + 共用出口 IP。要么它什么都查不到(和当年 `/releases/latest` 的恒绿路径同一个形状),要么它查到了但要 in-place 覆盖一棵 python 正在跑的树——ZCode 的 `quitAndInstall` 等的是**它自己的 Node host**,不是 `python.exe` 和它加载的 `.pyd`。最坏结果是 09-08 明令禁止的那个形状:一半新一半旧、一声不吭,而且 **electron-updater 没有回滚**(接力器的 `:rollback` 段没有对应物)。

**2. 哪个前提为假,整个方案要重做**

> **「Electron 主进程退出 ⇒ 它树里的 python 也退出,而且接力脚本的收摊闸在 60 秒内等得到。」**

假的表现是:**每一次**更新都退化成"软件关了、没更新、又自己打开"(接力脚本 `:teardown_failed` 分支),而且全程静默。

最小实验(纯 windows-latest,不碰他家机器):复用现成的 `windows-update-e2e`——它已经把**同一 commit 打出的新旧两个安装包** + 替身 GitHub(`.github/scripts/fake_github.py`,hosts + 一次性 CA)跑 9 个场景(e1~e9,含回滚)。**只改一处**:让"旧"那个包的外壳是 Electron 而不是 pywebview。然后看 e1/e2(装完自动重启到新版)和回滚场景过不过。收摊闸在 40 毫秒放行是今天实测过的(`ds_update_apply.py:216`),Electron 退出不杀 python 树的话它会一直等到 60 次重试耗尽——这条断言一眼可读。

顺带的第二条实验(它决定"四样"里更新那一半有没有资格):同一 harness 换成 electron-updater 对着替身 GitHub 真跑一次 in-place 更新,断言结果树**整棵**是新版。出现混合树且无回滚 ⇒ electron-updater 不能当这个 app 的更新器,不管 ZCode 用得多好。

**3. 更简单的方向?** 就是上面这条。它牺牲:装出来的树多约 180MB、更新包也变大、多一次手动安装、放弃 electron-builder 的免费目录页/注册表管理。分辨它和"四样一起换"的最小实验,就是第 2 问里那条 **"Electron 当叶子塞进现有更新 harness"** 的 workflow:过了 ⇒ 现有契约仍然够用,更新器没有换的理由;在收摊闸或回滚上红了 ⇒ 你恰好提前看见了"四样一起换"默默假设掉的那件事,而他家的机器一个字节都没动。

## Smallest first step
把 `.github/workflows/windows-update-e2e.yml` 复制一份成 `windows-electron-shell-probe.yml`,**只动"旧包"的壳**:让 Electron 版本壳接管 `OpenDesign.exe`(同布局、哨兵与 `版本号.txt` 照旧),跑 e1/e2 + 回滚两个场景,断言接力脚本走到 `:ask_health` 并报出新版号。这一步不写任何产品代码、不发任何 release、不联网到他家,却能把上面最大的那个未知变成已知——顺带还白拿一件事:Electron 窗口层从此可以在 Linux/windows CI 里被真跑,不再是"只有业主真机能验"。

------------------------------------------------------------
turns: 47 / 上限 200
(原始 stream-json:/root/aiwork/logs/explore-electron-shell-20260921-2339.deepseek.stream.jsonl)
