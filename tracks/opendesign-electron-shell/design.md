# Design: opendesign-electron-shell

- Change: opendesign-electron-shell
- Status: draft —— U1~U4 业主已答;Approach v2 已过独立方案挑战(`19f7396`);U2 九跑量完(第九跑证实 D 的增量方案),**下一步写判据(先单独 commit)**

## Goal-to-design check

- **当前行为 → 拟改变的行为**:业主的窗口(pywebview + WebView2 + ctypes 手补缩放边/动画)→ Electron 窗口,
  三按钮照 ZCode 自绘。业主确认过的转述还包括托盘、安装包、自动更新一起换 + 换壳版手动装一次
  (proposal「真问题」一节有逐字原话;「四样全换」是**我的转述**,他答「可以」)。
- **检查深度与触发事实**:命中 4c 第三行 —— 改变用户必经步骤(卸旧装新)、改变默认自动动作(更新器)、
  改变安装/数据根/跨模块契约(哨兵、锁通道、更新清单),选错要跨两台机器迁移才撤得回。
  ⇒ 做了两个不同家族的独立挑战(见下);关键未知转成探路实验(见「下一步」)。
- **关键前提**(可证伪的主张 → 证据):见下表「核实」列。
- **完全实现仍可能失败**:过渡那一刻(卸载/目录/两台机器)与之后第一次自动更新 —— 两腿给了具体场景,已逐条核实。

## 独立挑战与核实(2026-09-21 夜)

- 输入:题面原件 `evidence/20260921-c0-brief.md`(用户原话、现状与出处、约束、拟改变的行为、三问;
  **不含**我的方向)。我的方向在派发前已落盘:`evidence/20260921-c0-my-direction-before-dispatch.md`
  (原件在仓外,交卷后复制进仓,一字未改)。
- 两条腿、两个家族、互不知情,都能自读仓库快照:
  - Cursor / cursor-grok-4.6-high(xai)→ `evidence/20260921-c1-challenge-cursor-grok.md`
  - DeepSeek / deepseek-flash(agent 底座)→ `evidence/20260921-c2-challenge-deepseek.md`
  - 两腿 rc=0,各一次派发,无重试。
- **两腿一致的方向**:只把窗口(+托盘)换成 Electron;安装器(NSIS)与自动更新(Python 旁路换名接力器)**不换**;
  安装布局、`OpenDesign.exe`、哨兵 `ds\bin\ds_shell.py`、`ds\版本号.txt` 的身份约定不动。

| # | 腿的主张 | 出处 | 核实 | 处置 |
|---|---|---|---|---|
| 1 | electron-updater 就地覆盖,Python 进程攥着安装树里的 .exe/.pyd ⇒ 半新半旧、无回滚 | 两腿 | 09-08 否掉就地覆盖的理由属实(`bin/ds_update_apply.py` 模块头 ①②③、`installer/OpenDesign.nsi:130`「RMDir 删不掉会悄悄跳过」)。electron-updater 在**我们这棵树**上的实际行为**未实测** | **未核实、影响高** ⇒ 若仍换更新器,必须先在 windows-update-e2e 里实测 |
| 2 | 换 electron-updater = 换掉磨出来的发现通道(全 prerelease、VPN 出口 60 次/小时限流) | 两腿 | `bin/ds_update.py` 模块头属实(`/releases/latest` 跳过 prerelease;限流已真咬过、改走 releases.atom + 清单)。electron-updater 的 GitHub provider 走不走 api.github.com **未核实** | 成立为风险;细节未核实 |
| 3 | electron-builder 的默认目录 ≠ 业主自选的 `F:\`/`D:\AI\OpenDesign`,不读我们的 `InstallDirRegKey` ⇒ 装出第二份 | DeepSeek | 我们靠 `OpenDesign.nsi:88` `InstallDirRegKey HKCU Software\OpenDesign` 记目录属实;electron-builder 不读这个键 —— 依据是它的文档/惯例,**未实测** | 成立(高可能);只影响「换安装器」 |
| 4 | 旧卸载项还在时点它,旧卸载器凭哨兵认门 ⇒ 把同目录的新装一起删 | DeepSeek | `OpenDesign.nsi:327-329`:只要 `$INSTDIR\ds\bin\ds_shell.py` 在就 `RMDir /r "$INSTDIR"` —— **属实** | 成立;只影响「换安装器 + 同目录」 |
| 5 | 手动卸载时软件还在托盘里 ⇒ 删不干净留半棵树;卸载页那个「连资料一起删」他可能勾 | Cursor | `OpenDesign.nsi:136` 卸载页要他先去托盘退出;`:130` 注释「删不掉会悄悄跳过」;删资料是默认不勾的可选节 `:339-341` —— **属实** | 成立;这是「手动卸旧装新」**独有**的风险,自动更新从不走卸载 |
| 6 | 两台机器的过渡会分叉 | 两腿(结论相反) | 旧更新器只认 tag `win-installer-<num>` + 资产 `OpenDesign-Setup-<num>.exe`(`bin/ds_update.py:47-48`);`verify_new_tree` 只查哨兵 + 版本号(`bin/ds_update_apply.py` `verify_new_tree`)。⇒ 换了名字:没手动装的那台**永远看不见新版**(Cursor 对);保留布局与名字:那台会被**自动升级且判成功**(DeepSeek 对) | 两个都成立,取决于方案 —— 而后者正是「不用手动装」的机会 |
| 7 | 换内核会丢 localStorage 里的项目↔对话映射 ⇒ 他以为聊天没了 | Cursor | **驳回**:装好的应用里 pywebview 以 `private_mode=True` 运行,localStorage **本来就不跨重启保存**(`evidence/20260921-f1-localstorage-private-mode.md`,读出货包源码;未在 Windows 实测)。没有东西可丢 | 驳回 |
| 8 | 单实例锁同时是「存 key 后重启网关」「更新交棒」的通道,Electron 的单实例锁不接这两个动词 | Cursor | `bin/ds_web.py:329,357` 走 `ds_shell_core.LOCK_HELLO + LOCK_RESTART`;`bin/ds_shell.py` `update_handoff` 接 `on_update` —— **属实** | 成立;我的方向(管家留 Python)本来就留着它 |
| 9 | 两套单实例机制并存会打架 | DeepSeek | 设计点,非阻断 | 设计时定顺序:Electron 锁先拿,只有首份 Electron 才起 Python 管家 |
| 10 | 八个 `.win-grip-*` 缩放把手必须删,留着会压在原生缩放边上 | DeepSeek | `web/src/workspace/WindowChrome.tsx`/`app.css` 的 grip 属实 | 采纳 |
| 11 | 换更新器后更新界面两个真相源(ds-web `/api/update/*` vs 主进程);「同一版只自动试一次」那本账没有归处 | DeepSeek | `bin/ds_web.py` 更新端点、`bin/ds_auto_update.py` 属实 | 成立;只影响「换更新器」 |
| 12 | 08-13 真机否过 Electron | Cursor | **驳回**:08-13 是「轻方案真机跑通,所以不采纳 Electron」(`tracks/opendesign-windows-installer/design.md:386`),不是 Electron 被否 | 驳回 |
| 13 | 重开选型的触发条件不是「看到一份开源前端」 | Cursor | **驳回**:08-25 条件③已成立(`windows-package-probe`/`windows-update-e2e` 已建,窗口层仍只有业主能验);且是业主拍板 | 驳回 |
| 14 | 业主认可的是转述,不是对安装器/更新器取舍的知情同意 | Cursor | 属实 —— 「四样」是我从「都一起换」「参考 zcode 这一段前端代码」扩出来的 | **成立 ⇒ 回去问业主** |
| 15 | 锁通道与 Job 应由 Node 侧接管 | DeepSeek | 不采纳:Cursor 与我都主张 Python 管家留着;DeepSeek 自己把这两处列为「全部新增风险面」 | 不采纳 |
| 16 | 关键前提:Electron 退出 ⇒ Python 树也退出,接力脚本的收摊闸等得到 | DeepSeek | 接力脚本 `:wait_gone` 查端口 + 哨兵可写属实(`render_relay`);Electron 真退得干不干净**未实测** | 未核实 ⇒ 探路实验必测 |
| 17 | 托盘还原/最大化后「几何正常、画面只剩底色」可能换个形状再现 | Cursor | ZCode 自己补了 `invalidate()` 双帧重绘(源码事实);我们这份前端上会不会**未实测** | 未核实 ⇒ 探路截图含「还原后 500ms」 |

**我的方向 vs 挑战**:我落盘的 P1(就地覆盖)、P3(旧更新器自己去装新包)、P4(两套卸载项/默认目录)被两腿独立命中并给出具体场景;
**它们多给的**是 #4(旧卸载器删掉新装)、#5(手动卸载的两个坑)、#11(重试无收敛)。我的 P5(localStorage)被我自己的核查驳掉了 Cursor 的 #7。
P6(管家语言)三方里两方站 Python。

**我的结论**:同意两腿 —— 安装器与更新器换掉,给业主的收益只剩「增量下载(省多少未测)」和「和 ZCode 一样」;
代价是把两个月磨出来的更新安全性清零,并**凭空多出一个手动卸旧装新的步骤**(#4 #5 #6 全是这一步带来的)。
业主要解决的是窗口,「参考一下 zcode 这一段前端代码」指的也是窗口那段。**但这改的是他确认过的范围,必须回去问他。**

## 未解决项(能改方向,先解决)

- ~~**U1(业主)**:安装包和自动更新换不换~~ **已答:「全换吧」**(听完两家劝阻与我的推荐之后)。
  ⇒ 上表 #1~#6 #11 #16 #17 从「劝退理由」变成「必须堵上的清单」,各自的堵法由 U2 实验定,见下。
- **U2(实验,全换版)**:云 Windows 探路,每条对应上表一个风险,**先量再写判据**:
  - E1 构建:electron-builder NSIS 带上免装 Python(extraResources),量包体、构建时长。
  - E2 起窗:窗口先出来、Python 管家起后台、界面出来;截图首屏 / 最大化(任务栏在不在)/ 托盘隐藏再还原后 500ms(#17);
    三按钮与关窗进托盘可被自动点;托盘退出后无残留 python(#16);杀掉 Electron 主进程后 Python 管家与后台也收掉。
  - E3 过渡(#3 #4 #5 #6):先装真的 0.98.9(自选带空格目录、在托盘里跑着)→ 双击新安装包 ⇒ 旧程序被关掉、旧卸载项消失、
    装回同一目录、资料根与 key 一个字节不少、开机自启指向新 exe、桌面图标能用;旧版的更新器看不见新 release(tag/资产名都不匹配)。
  - E4 更新(#1 #2 #11):v1 → v2 走 electron-updater;Python 后台在跑时装 ⇒ 结果整棵是新版;量实际下载字节(增量省多少);
    发现通道不碰 api.github.com(github.com 下载地址)、不依赖 prerelease 过滤。

### U2 第一跑(run 35622694746,2026-09-22 凌晨)—— `evidence/20260922-u2r1-run35622694746.md`

- **E1**:构建 150s;安装包 **157.7 MB**(旧 NSIS 包约 45 MB);装开后 10,052 个文件 / 535.8 MB。
- **E3 过渡 12/12 绿**:旧版 0.98.8 装在 `C:\AI Test\OpenDesign`、开机自启开着、在托盘里跑着(6 个 Python 进程)
  → 静默装新包、**不带 /D** ⇒ 装回同一目录、没在默认目录另装、旧程序文件与旧卸载项都没了、「应用和功能」只剩 1 条、
  旧进程全收掉、三份资料(含 key.txt)指纹不变、开机自启与桌面图标都指向新 exe、配置还在。⇒ 表 #3 #4 #5 在这台机器上堵住了。
- **E2 起窗 11/12**:窗口 +489ms 就出来(先显示「正在启动」),工作台界面 +9.1s(同机旧版:窗口 +11.8s、首帧 +15.5s);
  缩放把手已隐藏;最大化不盖任务栏、图标切成「还原」;最小化;关窗=进托盘且后台活着;再双击 305ms 叫回;
  **托盘还原后 500ms 截图界面完整**(#17 这一次没复现);托盘退出 468ms 内安装目录里不剩进程(#16 正常退出这条成立)。
  任务栏图标是我们自己的(旧版一直是 Python 的)。
- **唯一 FAIL = 量具坏了**:E2.crash 的 taskkill 没杀掉主进程(杀前杀后同一个 pid 还在),「硬杀后管家自己收摊」这个场景**根本没发生**。
  不是放行,是没量到 ⇒ 第二跑改成问 Electron 自己要主进程 pid、先断言它真没了再看其余进程。
- 看图备注:1024x768 的云机器上页面底部有横向滚动条(内容比窗口宽),旧版在同尺寸下同样超宽,不是换壳带来的。

### U2 第二跑(run 35623869350)—— 全绿,`evidence/20260922-u2r2-run35623869350.md`

- **E2.crash 量到了**:硬杀 Electron 主进程(先确认 pid 真没了)→ 管家与后台 **502ms** 内全收掉(stdin 断 → 管家收摊 → Job)。#16 两条路都成立。
- **E4 更新 0.98.10 → 0.98.11 成功**:后台在跑时下载、管家先收摊、再交安装器;装完自己重新打开、后台应答、「应用和功能」仍 1 条、
  没另装一份、资料指纹不变。⇒ 表 #1(就地覆盖半新半旧)在这台机器上**没出现**:我们先收管家 + 安装器侧再收一遍,文件不被占。
- **增量下载**:electron-updater 算出只需 **915 KB / 158 MB(1%)**,但它一次要 6 段,我的替身服务器只认单段 ⇒ 416 ⇒ 退回整包。
  亲测 GitHub:单段 206、多段 **501** ⇒ 生产必须 `useMultipleRangeRequest:false`。
- 🔴 **新发现:更新时软件消失约 2 分钟**(安装器 exe 换版本 78s、新版重新应答 128s;静默装,屏幕上什么都没有)。
  旧的「装到旁边再换名」是边用边装、只停几秒。⇒ 第三跑:带进度界面装,看业主会看到什么;并量一次**真改了代码**的增量。

### U2 第三跑(run 35625592442)—— E4 两条红,`evidence/20260922-u2r3-run35625592442.md`

- E1/E3/E2 全绿;**真改了一个 .py + 一个前端 js 的增量:下 1 MB / 158.1 MB(0.6%)**,单段请求成立。
- **E4 红 = 从头到尾没装**:`quitAndInstall(false, true)` 拉起的是向导模式安装器(`oneClick:false`),
  停在第一页「装给所有人 / 只给我 → 下一步」等人点(截图 `evidence/20260922-u2r3-e4-00-wizard-waiting.png`)。
- ZCode 自己也是非静默 `autoUpdater.quitAndInstall()`(`packages/desktop/src/main/autoUpdater.ts:470`,`zai-org/ZCode@872ad96`)⇒ 它的用户每次更新都点一遍向导;
  它的更新由用户点「重启以更新」触发,人在跟前。我们是开机自启、后台自动更新 ⇒ **这一处不能照抄**。

### 更新时业主看到什么(待定项,第四跑先量)

读 electron-builder 26.15.3 的 NSIS 模板(`app-builder-lib/templates/nsis/`)定出每一页的处置(要人点的是其中三页):

| 页 | 模板行为 | 处置 |
|---|---|---|
| 装给谁(`multiUserUi.nsh` PAGE_INSTALL_MODE) | 更新时**不跳过**(第三跑停的就是它) | `customInstallMode` 置 `$isForceCurrentInstall=1` ⇒ 固定只给当前用户(旧版本来就是 HKCU),首装也不再问 |
| 选目录(`assistedInstaller.nsh`) | `skipPageIfUpdated`,更新时自己跳过 | 不动 |
| 进度页 | 显示 | **留着 = 业主在那一分多钟里看到的东西** |
| 完成页 | 非静默时不自动启动,等人点「完成」(`installSection.nsh`:只在 `isForceRun && Silent` 才启动) | `customFinishPage`:更新时拉起新版并跳过此页;首装照旧 |

另把安装器界面定为简体中文(`installerLanguages: [zh_CN]`、`language: 2052`,只一种语言 ⇒ 不弹语言选择)。
**第四跑要量的**:更新全程零点击(安装器自己退出)、时间线(安装器起 / 退 / exe 换版 / 新版应答)、每 10 秒一张整屏。
量完拿截图给业主看「更新时屏幕上是什么、停多久」—— 这是体验取舍,与旧版「只停几秒」相比是退步,**要他知情**。

### U2 第四跑(run 35689840996)—— FAIL 0,`evidence/20260922-u2r4-run35689840996.md`

- **零点击成立**:带界面的安装器没人点也自己走完(`--updated --force-run`、无 /S);「应用和功能」卸载串带 `/currentuser`(customInstallMode 生效)。
- **业主看到的**:软件关掉 → 约 10s 后弹中文进度窗口「正在安装,请等候」(三个按钮全灰,点不了取消)→ 新版自己打开。
  进度窗口从 +10s 到 115~163s 之间(量具换版后分辨率约 50s,见收据)⇒ **约 2~2.5 分钟**。增量 0.9 MB / 158 MB。
- 新版窗口回来时落在别的窗口后面(没抢到前台)—— 实现细节,定稿时写进判据。
- 没测:首装的带界面路径(CI 只走 /S)。

⇒ **E1~E4 都量过了,T2 完成**。剩下的不是技术问题而是体验取舍,见 U3。

- ~~**U3(业主)**:新版下好以后**什么时候装**。~~ **已答(09-22):「c吧」** —— 照 ZCode:后台下好 → 提示 →
  他点「重启以更新」→ 向导里自己点(非静默 `quitAndInstall()` 默认参数,同 ZCode `autoUpdater.ts:470`)。
  我推荐的是 ②,他听完三种的利弊选了 ③,不再劝。⇒ 第四跑加的 customInstallMode/customFinishPage 撤回,第五跑量 ③ 的向导走不走得通。
  原题:装一次屏幕上是约 2~2.5 分钟的进度窗口(旧版只停几秒),可选:
  ① 下好就装(第四跑的样子,可能打断正在做的事);② 下好先提示,他点「现在更新」才装,之后零点击;
  ③ 照 ZCode:点「重启以更新」+ 向导里自己点几页。
  排除「打开软件时装」:0.98.7 业主已经否过「打开软件干等」(track `opendesign-startup-not-blocked-by-update`)。
  排除「退出时自动装」:ZCode 在 Windows 上特意关掉(`autoUpdater.ts:1502-1505`,紧接着关机会装一半)。
  我的推荐:②。

### U2 第五、六跑 —— 方案 C(照 ZCode)走通

- 第五跑(`evidence/20260922-u2r5-run35691247054.md`)E4 红 = 替人点向导的量具(UI Automation 版)一下没点,不是产品问题。
- **第六跑(`evidence/20260922-u2r6-run35692682755.md`)FAIL 0**:更新时业主按两下 ——「安装选项」页「下一步」(默认已选「仅为我安装」)、
  「安装完成」页「完成」(「运行 OpenDesign」默认勾上);中间进度页约 1 分 50 秒;新版 +130s 应答、**在最前面**。
- ~~**待业主(U4)**:「安装选项 / 为哪位用户」这一页照 ZCode 留着还是单独去掉。~~ **已答(09-22):「留着和zcode一样」**
  (我推荐去掉,他听完「点成所有用户会搬家」的风险仍选留着 ⇒ 不加 customInstallMode,不再劝)。原题:留着的风险(读模板源码,未实测):
  点成「所有用户」⇒ 要管理员授权 ⇒ 装进 `C:\Program Files\OpenDesign`(更新时选目录页跳过)、`installSection.nsh:54-57` 顺手卸掉他自选目录那份 ⇒ 搬家;
  开机自启键仍指旧路径(customInstall/customUnInstall 在 --updated 时都不碰)⇒ 推断会失效。去掉 = `customInstallMode` 置 `$isForceCurrentInstall=1`(第四跑已验证可行)。

## 实施方案的独立挑战与核实(2026-09-22)

- 触发(4c 第三行):默认自动动作变了(自动装 → 他点)、退役跨模块契约(ds-web 更新端点、锁通道交棒)、发布通道变了。
- 输入:题面 `evidence/20260922-a0-approach-brief.md`;我的方向与最危险前提**派发前**落盘在仓外,交卷后原样复制为
  `evidence/20260922-a0-my-direction-before-dispatch.md`。腿读的是**去掉 design.md / verify.md / 上次两家报告、无 git 历史**的快照。
- 腿:Cursor / grok-4.7-high(xai)。第 1 次 15 分钟超时(rc=124,55 次读码、无报告;思考日志里四条我核实成立,已先补进 v1 —— `f09498c`);
  第 2 次放宽到 35 分钟(`PANEL_HEALTH_OVERRIDE` 解冷却 = 基础设施重试),rc=0,报告原样 `evidence/20260922-a1-approach-challenge-cursor-grok47.md`。
  花名册:`subcursor.grok-4.7-high=EXPLORE(rc=0,coverage=none)`(`/root/aiwork/logs/explore-electron-approach-20260922-1440r2.roster`)。
- 追加第二条腿?**不追加** —— 下表没有需要第二家来分辨的具体分歧;有分歧的那条(.old 退路)是取舍,我给了理由。

| # | 腿的主张 | 核实 | 处置 |
|---|---|---|---|
| a1 | 首装带界面那条路没跑过,选目录页未必停在旧目录 | 第七跑截图 `C:\AI Test\OpenDesign` 就是默认值(旧 InstallDir);那跑因我的点击量具不认「安装(I)」按钮卡住,第八跑补全 | 成立为未测 ⇒ 判据 E3 改带界面 |
| a2 | 「不论选哪都去卸旧目录」会 `RMDir /r` 他原目录里的一切 | 属实(`installer/OpenDesign.nsi` `un.OpenDesign`);但**不这么做**就是新旧并存、托盘里旧版照跑、两条卸载项 | 保留该做法;他往程序目录里放自己文件的可能性低,且旧卸载器本来就这么删 |
| a3 | 换壳当晚两台都失去退路(0.98.8 已被卸);建议改名 `.old`、新版自报版本对上才删 | 属实:退路只剩发布页重下 + 先卸新版再装旧版,对他是多步。`.old` 方案要在安装器 cwd=`$INSTDIR`(模板 `.onInit` `SetOutPath $INSTDIR`)时改名该目录、处理旧卸载项与配置里写死的旧路径 —— 都未验证 | **不采纳 .old**,换成零代码的做法:**两台错开装**(先装一台、用一天确认界面正常再装另一台),发布页保留 0.98.8;写进 T6 业主说明 |
| a4 | 判「装好了」只看有应答;第二跑 exe 0.98.11 而后台报 0.98.9;旧更新器有「版本号 + nonce」这道闸,方案把它一起退役了 | 属实(`bin/ds_update_apply.py:86-92`;探路 v2 只给 `ds_web.py` 追加注释没改 VERSION) | **采纳**:管家 `ready` 带后台版本,主进程比对 `app.getVersion()`,对不上弹人话(抓安装被打断的半新半旧);判据 E3/E4 断言「健康检查版本 = exe 版本 = ds_web.VERSION」,探路第八跑起 v1/v2 都改 VERSION |
| a5 | 「重启以更新」若只在设置弹层里,不点就成了默认;侧栏「设置」行上的更新圆点是专门为此加的,方案没说留 | 属实(`web/src/workspace/Sidebar.tsx:461` `hasUpdateBadge`;`update.ts:68`) | **采纳**:圆点保留;「重启以更新」放在收起的「设置」那一行上,弹层里再放一份 + 「约 2 分钟,期间请别关机」 |
| a6 | 先开软件后开 VPN ⇒ 下载失败,要等 4 小时再查 | 旧更新器为此每次请求现建代理(`ds_update._open`)属实;electron-updater 走 Chromium 网络栈、跟随系统代理变化 —— **未实测** | 采纳一半:失败后 15 分钟重查 + 手动「重试」;不为此造代理层 |
| a7 | 换壳那一次跑 `ds_provision` 合并配置,E3 只查 config.json 在不在 | 属实 | 采纳:判据核配置里的业务字段(key 引用、模型选择)前后不变 |
| a8 | `installer/RELEASE.md` 写死 `--prerelease`,与 latest/download 冲突 | 属实(`installer/RELEASE.md:24`) | 采纳:发布说明随旧工具链重写,新版写明正式 release |
| a9 | 看不到他下载后的 SmartScreen | 首装:与旧安装包一样未签名,他装过 30 多版;更新:electron-updater 自己下载的文件不带网络来源标记 —— 推理,未实测 | 记为未测风险,不改方案 |
| a10 | 更简单:探路版 installer.nsh 原样当产品 | 等于回到 a2 的并存问题 | 驳回 |

## Approach(v2,2026-09-22;已按上表挑战结果修订)

依据:U1「全换吧」、U2 六跑实测、U3「c吧」(更新照 ZCode:点「重启以更新」+ 向导自己点)、U4「留着和zcode一样」。
**原则**:ZCode 做过的照 ZCode;ZCode 没有、我们有的(Python 后台、锁通道、诊断、迁移)照探路版已量过的做法;
其余不新增。

### A. 进程与目录(照探路版,已在云 Windows 量过)

- 产品代码放 `desktop/`(Electron 主进程 `main.js`、`preload.js`、`loading.html`、`package.json`、`build/installer.nsh`)
  + `bin/ds_host.py`(管家)。探路版 `tracks/.../spike/` 只作参照,不直接搬。
- **Electron 主进程**:窗口(frame:false、不关 thickFrame、resized/show 后双帧 invalidate —— ZCode `desktopWindowChrome.ts`)、
  托盘(打开 / 导出本次启动诊断 / 退出)、单实例(`requestSingleInstanceLock`,第二份 → 把第一份叫到前台)、
  外链交系统浏览器、窗口内只许停在本机工作台、更新器(见 D)、日志 `%LOCALAPPDATA%\OpenDesign\Logs\electron.log`。
- **管家 `bin/ds_host.py`**(Python,留着的理由见表 #15/P6):复用 `ds_shell.start_backend`(挑端口、改配置、Job 收整棵树)、
  `InstanceLock`(**只留** ds-web「存 key 后重启网关」通道;`on_update` 交棒退役)、看门狗、诊断。
  协议 = stdout 一行一个 JSON 事件(`ready{web_port, version}` / `show` / `already-running` / `backend-died{report}` / `fatal{message}`),
  stdin 一行一个命令(`quit` / `export-diagnostics` / `report{event,detail}` / `window-shown`),**stdin EOF = 收摊**
  (Electron 被硬杀时管道断 ⇒ 管家自己收摊;第二跑量到 502ms)。
- **版本自检**(挑战 a4):主进程收到 `ready` 时比对后台版本与 `app.getVersion()`,对不上 ⇒ 弹人话(「这次安装没装完整,请重新运行安装包」)
  并写日志 —— 抓安装被打断留下的半新半旧(旧更新器「版本号 + nonce」那道闸的替身)。
- **单实例顺序**(表 #9):Electron 锁先拿;只有拿到锁的那份才起管家;管家拿不到 InstanceLock ⇒ `already-running` ⇒ Electron 弹一句人话退出。
- **收摊顺序**(表 #1 #16):托盘退出 / 更新 ⇒ 先关管家 stdin、等它退(Job 收整棵树),15s 不退才强杀,再退 Electron。
- **`bin/ds_shell.py` 拆两半**:后台那一半(`start_backend` / `build_env` / `user_home` / key 读取 / 日志)留下供管家用;
  窗口那一半(`WindowApi` / `Shell` / `main` / pystray 托盘 / pywebview)退役。ds-web 与 `ds_credential` 对 `build_env` 的依赖不变。
- **版本号只有一个来源**:`bin/ds_web.py` `VERSION`。`desktop/package.json` 的 version(安装包文件名、
  「应用和功能」、electron-updater 比较的都是它)**提交时就与它同值**,发版时两处一起改,判据 c4 钉住不许分叉;
  构建不改写版本(攻题 #12 提的「构建时生成」是另一种等价做法,选手工同值 + 判据,少一个会出错的构建步骤)。探路版两处各写各的(exe 0.98.11 / 后台报 0.98.9),正式版不许。

### B. 窗口栏与前端

- preload 暴露**新名字** `window.odShell`(不再冒充 `pywebview`):`minimize / toggleMaximize / close / windowState / onWindowState /
  reportStartup / update.*`(见 D)。`WindowChrome.tsx`、`startupReport.ts` 改接它;`pywebviewready` 那套等待注入的逻辑删掉
  (preload 在页面脚本之前就位,没有「注入晚于首帧」这回事)。
- 拖动交给 Chromium:`app.css` 里窗口栏 `-webkit-app-region: drag`、按钮 `no-drag`;八个 `.win-grip-*` 与 `RESIZE_EDGES` 删掉
  (表 #10;缩放边是系统的)。`SHELL_MARK`(`?shell=1`)保留 —— 首帧就知道要不要画窗口栏,浏览器里一个按钮都不画(判据 s-w1 不变)。
- 右键复制粘贴原生菜单(ZCode 有,旧版 WebView2 自带;不做会是回归)。

### C. 安装包(electron-builder NSIS,照探路版 + ZCode 配置)

- `oneClick:false`、`perMachine:false`(「为哪位用户」页照 ZCode 保留,U4)、`allowToChangeInstallationDirectory:true`、
  `installerLanguages:[zh_CN]`、`deleteAppDataOnUninstall:false`、`artifactName: OpenDesign-${version}-electron-setup.${ext}`。
- `installer.nsh` 照探路版(E3 六跑全绿):preInit 把旧 `HKCU\Software\OpenDesign\InstallDir` 转成默认目录、记下旧版开机自启;
  customCheckAppRunning 收掉安装目录里所有进程、用旧卸载器静默卸掉旧程序(资料节默认不选);首装跑 `ds_provision`;更新时不碰资料根。
- **旧版在哪就去哪收**(方案挑战腿思考日志里提出、我核实成立):探路版的 customCheckAppRunning 只看 `$INSTDIR` ——
  首装时业主若在选目录页换了目录,原目录的旧版不收进程、不卸 ⇒ 新旧并存、两条卸载项、托盘里旧版照跑。
  ⇒ 另按 `HKCU\Software\OpenDesign\InstallDir` 记的**旧目录**收进程、跑旧卸载器(与 `$INSTDIR` 相同则只做一次)。
- **旧卸载器跑完要核**:探路版只记退出码不判。⇒ 卸完若哨兵 `ds\bin\ds_shell.py` 仍在 ⇒ 再收一次进程重试一次,仍在就弹人话并退出,
  不许新旧文件混装(09-08 否掉就地覆盖的同一个形状)。
- 资料根仍在 `%LOCALAPPDATA%\OpenDesign`(安装目录外);卸载不删资料(旧版那个「连资料一起删」可选项随旧卸载器退役)。
- **开机自启**:过渡时沿用旧版的选择(E3 已验);**全新安装默认关、安装时没有勾选项**(旧版是安装页上一个默认不勾的选项)
  ⇒ 已知回归,延期到设置页开关(另单),在业主真机清单里写明。

### D. 自动更新(electron-updater,U3 = 照 ZCode)

- 主进程持有更新器:`autoDownload=true`(增量约 1MB,后台下)、`autoInstallOnAppQuit=false`(ZCode `autoUpdater.ts:1502-1505`:
  退出后紧接着关机会装一半)、`disableWebInstaller=true`;publish = generic
  `https://github.com/SunJ1ayu/OpenDesign/releases/latest/download`、`useMultipleRangeRequest:false`(GitHub 多段 501,第二跑亲测)。
  不碰 api.github.com(VPN 出口 60 次/小时限流那个坑,表 #2)。
- **增量要能在真发布布局下成立**(写方案时我自己发现的洞):electron-updater 找旧版 blockmap 的地址 = 新安装包地址
  **把路径里所有新版本号换成旧版本号**(`electron-updater/out/providers/Provider.js:22-25`);`releases/latest/download/` 下只有最新 release
  的资产 ⇒ 旧 blockmap 404 ⇒ 退整包 158MB。
  - ~~`previousBlockmapBaseUrlOverride`~~ **第八跑证伪**:它只换得了主机 —— 路径是绝对路径,`new URL(路径, override)` 丢掉 override 的路径,
    日志照样去 `latest/download/OpenDesign-0.98.10-…blockmap` ⇒ 404 ⇒ 实下 158MB/158MB。我只读到它被传进去,没读 `newUrlFromBase`。
  - **改为**:发布时把 `latest.yml` 里安装包的 `url`/`path` 改写成带版本号的绝对地址
    `https://github.com/SunJ1ayu/OpenDesign/releases/download/v<新版>/OpenDesign-<新版>-electron-setup.exe`(sha512 不变)。
    换号后正好是 `…/download/v<旧版>/OpenDesign-<旧版>-electron-setup.exe.blockmap` = 旧版自己 release 里的资产;跳版更新同样成立。
    `latest.yml` 本身仍从 `releases/latest/download/` 取(发现通道不变)。
    **第九跑证实**(run 35698706347):替身源按 GitHub 真实布局摆,旧 blockmap 从 `download/v0.98.10/` 取到,实下 1.06MB / 165.7MB(0.6%),零 404。
- 查的时机:窗口出来后延迟一小段查一次,之后每 4 小时一次;**绝不挡启动**(0.98.8 的教训)。
- 状态 `idle / checking / available / downloading(进度) / downloaded(版本) / error(人话)` 经 `odShell.update.onState` 推给前端;
  `update.check()` 手动查;`update.install()` = 先收管家、再 `quitAndInstall()` 默认参数 ⇒ 向导(安装选项「下一步」→ 进度 →
  「完成」勾着「运行」)⇒ 新版在最前面(第六跑)。
- 前端设置页的更新一栏改接 `odShell.update`:下载好了才出现「重启以更新」按钮;**查不动不许说「已是最新」**(旧判据 u3 的保证搬过来)。
  **按钮不能只藏在弹层里**(挑战 a5):侧栏收起的「设置」行上的更新圆点(`Sidebar.tsx` `hasUpdateBadge`)保留,
  「重启以更新」就放在那一行上,弹层里再放一份。
  浏览器形态(Linux / git-pull)没有更新器:只显示当前版本 + 发布页链接。
- 「重启以更新」旁写明「约 2 分钟,期间请别关机」(向导进度页不能取消,关机会装一半)。
- **交给安装器失败**(`quitAndInstall` 抛了):管家已经收了 ⇒ 弹人话并**把软件重新拉起来**(`app.relaunch()`),不留一个连不上后台的空窗口(攻题 #8,mc16)。
- **下载失败不许静默**:下载出错 ⇒ 状态 error(**带着那一版的版本号**)⇒ 更新一栏说「0.98.x 下载失败」+ 「重试」,且侧栏「设置」行上的圆点亮(du8;单纯「查不到」不亮 —— 他常先开软件后开 VPN,每次开机亮一个点是骚扰,而且我们并不知道有没有新版)。**整包回退本身允许**(旧 blockmap 取不到时 electron-updater 退回下整包,只是慢;攻题 #6 把它读成要拦 —— 这里写明不拦,发布流程由 r1~r8 保证 blockmap 在该在的地方)。
  出错后 15 分钟再自动查一次(挑战 a6:他常先开软件后开 VPN),不等 4 小时。
- **回滚随旧更新器退役**(已接受的保证损失,写进判据迁移账):旧版「装到旁边、新版起不来就退回」做不到了 ——
  electron-updater 是就地重装。补救:每一版发布前云 Windows 判据全过才发;旧版安装包一直留在发布页,出事可以直接装回旧版。
- **退役**(表 #11 的两个真相源因此只剩一个):`bin/ds_update.py`、`ds_update_apply.py`、`ds_update_startup.py`、`ds_auto_update.py`、
  ds-web `/api/update/*`、前端开机更新画面 / 自动更新横幅 / 自动更新偏好。退役清单与每条旧判据的去向见下「判据迁移账」。
- **旧安装包工具链一起退役**:`installer/OpenDesign.nsi`、`installer/build-installer.sh`、`installer/check-installer.py`、
  `.github/workflows/windows-package-probe.yml` / `windows-update-e2e.yml`(及其 `.github/scripts/*.ps1`)由新的云 Windows 判据 workflow 取代。
  **已发布的 0.98.x 安装包不动**(E3 要从它们过渡,业主机器上跑的也是它们)。

### E. 发布通道

- Electron 版起:tag `v<版本>`、**正式 release(非 prerelease)**,资产 = 安装包 + `.blockmap` + `latest.yml`。
  旧版(0.98.x)只认 `win-installer-*` tag 与 `OpenDesign-Setup-*.exe` ⇒ **看不见**新版(已本地核 ASSET_RE/TAG_RE)⇒ 两台机器各手动装一次(业主选 A)。
- 安装包在 CI 的 windows-latest 上构建(E1 已跑六次;本机 2G 内存且 electron-builder 出 Windows 包要 Wine,不在本机造):
  新 workflow 手动触发 → 产出安装包 + blockmap + latest.yml 当 artifact → 我下载、核 `latest.yml` 的 sha512 与安装包逐字节一致
  → **改写 latest.yml 的安装包地址为 `download/v<版本>/` 绝对地址**(见 D)→ 业主 `!` 跑 `gh release create`(发布权限在他那)。`installer/RELEASE.md` 写死的 `--prerelease` 随旧工具链退役,
  新发布说明写明**正式 release**(挑战 a8)。
- **换壳那一版两台错开装**(挑战 a3):先装一台、用一天确认界面正常,再装另一台;0.98.8 安装包留在发布页。
  出事时另一台还能干活,不用当晚开 VPN 重下旧版。(`.old` 退路方案的取舍见挑战表 a3。)

### F. 保持不坏

- Linux 浏览器形态、`bin/start.ps1` git-pull 形态:ds-web 与后台不变,只少了更新端点。
- 界面内容、后台、助手行为不改。

### 判据迁移账(退役的旧判据 → 保证去哪了)

T3 逐文件列:每个被删的测试写「它守的是什么 → 新判据编号 / 因行为退役而不再需要(理由)」。**不许只删不记**;
仍成立的保证(例:u3 查不动不说已是最新、s-w1 浏览器不画按钮、Job 收整棵树、资料根不动)必须在新判据里有对应编号。

### Jev 读数(2026-09-22,Approach 草案 v1 之后、方案挑战进行中;业主问起才补跑 —— 之前漏了)

`triage --track tracks/opendesign-electron-shell`(jev-1.13.0):unverified_premise 0.63 / data_or_authorization_change 0.54 /
runtime_delivery_change 0.99 / judging_surface_change 0.91 / deploy_target_outside_repo 0.96 → next_step **measure**(0.38)。
只当提醒:impact=high、uncertainty=high、方案挑战本来就在做,**没改方向**;它促成的一件事 ——
**blockmap 取旧版 release 的那条(新前提,未实测)在写判据前先上云 Windows 量**:替身源按 GitHub 真实布局摆
(`latest/download/` 只放新版资产、`download/v<旧版>/` 放旧版 blockmap),量第一次更新的实际下载字节。
「做完」的标准仍是业主机器上**运行中的**软件回显新版本号(T6)。

## Test strategy (oracle)(T3 定稿,2026-09-22;判据先单独 commit,再动实现)

**接缝由判据定**(实现照这些名字写;要改名先改判据、单独 commit、写理由):

| 接缝 | 文件 | 形状 |
|---|---|---|
| 管家 | `bin/ds_host.py` | `serve(inp, out, *, make_lock, start_backend, home, diag, app_dir, log, watch_interval=3.0, first_frame_timeout=90.0) -> int`(`inp`/`out` 是**字节流**);`main()` 接真依赖(`sys.stdin.buffer` / `sys.stdout.buffer` / `core.InstanceLock` / `ds_shell.start_backend` …) |
| 管家协议 | 同上 | 一行一个 JSON、UTF-8。事件(管家→外壳)`ready{web_port,version}` / `show` / `already-running` / `fatal{message}` / `alert{message}` / `backend-died{names,message}` / `diagnostics{path}` 或 `diagnostics{error}`;命令(外壳→管家)`{"cmd":"quit"}` / `export-diagnostics` / `report{event,detail}` / `window-shown`;**stdin EOF = quit**;坏行忽略、不崩 |
| 主进程控制器(攻题后补) | `desktop/lib/controller.js`、`desktop/lib/menus.js` | `createController(deps)` → `hostStdout(chunk)` / `hostExit(code)` / `setQuitting()` / `navigate(url)→是否拦` / `startUpdates()` / `checkNow()` / `updateState()` / `installUpdate(host)`;deps = `appVersion, loadWorkbench, showWindow, showError, revealFile, openExternal, log, updater, pushUpdateState, setTimeout, clearTimeout, relaunch, graceMs`。**main.js 只接 Electron 的东西,判断全在控制器里**(c10 钉 main.js 真用它)。
**main.js 的接法(复核后补,c10~c10e 静态钉;写法照这里,判据才看得见)**:管道原始块原样交 `ctl.hostStdout(chunk)`(Buffer 或 setEncoding 后的字符串,**不许逐块 toString**);
`host.on("close", (code) => ctl.hostExit(code))`(**close 不是 exit**:exit 时 stdout 可能没读完,最后一行 fatal 会排在「意外退出」后面);
`relaunch: () => { app.relaunch(); app.exit(0); }`(只 relaunch 当前进程不退);查更新 / 交安装器**只在控制器里**(main.js 不许出现 `checkForUpdates` / `quitAndInstall`);
要调到 `startUpdates` / `checkNow` / `updateState` / `installUpdate` / `setQuitting`;deps 接真的 `shell.openExternal` / `shell.showItemInFolder`;`setWindowOpenHandler` 用 `windowOpenDecision`;
`trayMenuTemplate({ onOpen: …, onExport: …, onQuit: … })` **回调就地写**(onOpen 叫出窗口 / onExport 让管家出包 / onQuit 先 setQuitting 再退)。`menus.js`:`trayMenuTemplate({onOpen,onExport,onQuit})` / `contextMenuTemplate(params)` |
| 主进程纯逻辑 | `desktop/lib/*.js`(CommonJS,**不 require electron**,无 node_modules 也加载得了) | `hostProtocol.js`:`parseHostLine` / `createHostDecoder(onEvent)→{push,end}`(管道分块、UTF-8 切半)/ `encodeCommand` / `hostExitMessage(code, {quitting, fatalShown})`;`versionCheck.js`:`versionMismatch`;`navPolicy.js`:`navDecision(url, origin)` / `windowOpenDecision`;`updateState.js`:`initialUpdateState` / `reduceUpdate(state, {type,…})` / `canInstall` / `nextCheckDelayMs` / `FIRST_CHECK_DELAY_MS` / `configureUpdater(u, {log})`;`lifecycle.js`:`shutdownHost(child, {graceMs})` / `installUpdate({state, host, updater, graceMs, recover?}) -> Promise<bool>`(`quitAndInstall` 抛了 ⇒ `recover(err)`、返回 false)|
| 打包 | `tracks/opendesign-windows-installer/spike/build-package.sh <out> --electron` | 出 `pkg/python` + `pkg/ds`(不带 pywebview / pythonnet / pystray);`desktop/package.json` 的 extraResources 从 `pkg/` 取 |
| 发布 | `desktop/scripts/release-feed.mjs` | `rewriteLatestYml(text, version, base = GitHub 的 releases/download)` / `sha512Base64(buf)` / `verifyFeed(text, buf) -> {ok, reason}`;`ghReleaseCommand({version, installer, blockmap, latestYml, latestYmlText}) -> gh 的 argv`(正式 release、tag v<版本>、恰好三样资产、latest.yml 必须改写过);命令行 `verify <latest.yml> <安装包>`、`rewrite <入> <出> <版本> [--base URL]`、`gh-command …`(云 Windows 判据摆替身源用的就是它) |
| 前端 | `web/src/desktopShell.ts`、`web/src/desktopUpdate.ts` | `OdShell` 类型 + `shellApi(win)`(`window.odShell` 齐了才给,否则 null);`desktopUpdateLabel(state, version)` / `showRestart(state)` / `showRetry(state)` / `hasDesktopUpdateBadge(state)` / `RESTART_HINT`;DOM 钩子 `data-ui=settings-toggle`(收起的「设置」行)/ `update-badge`(那一行上的圆点)/ `update-status` / `update-retry`(弹层里)/ `update-restart`(**收起的那一行上**)—— e2e desktop_update 与云 Windows 判据点它们 |

更新状态(主进程 → 前端同一形状):`{phase: idle|checking|latest|downloading|downloaded|error, version?, percent?, error?}`。

**Linux(进 run-all,断网)**

- `tests/test_ds_host.py` h1~h14:ready 带端口与版本(= `ds_web.VERSION`);EOF / quit ⇒ `sup.shutdown()` + 锁释放;
  拿不到锁 ⇒ `already-running` 且不起后台;起后台时 `die()` ⇒ 一条 `fatal`、**不弹第二个框**(原 `alert` 不被叫)、serve 不抛;
  重启网关失败的 `alert` ⇒ `alert` 事件;看门狗只问 `take_dead`(c21)、报一次 `backend-died`;`report` 只收白名单(s7);
  `export-diagnostics` 出 zip 且带 `electron.log`;`window-shown` 两次只上一次膛(s14),首帧到了不写快照;
  锁的 SHOW / RESTART 接到;UPDATE-HANDOFF 不再让管家收摊;stdout 每行都是协议;输入输出都按 UTF-8(子进程真跑一次,`PYTHONIOENCODING=gbk` 模拟中文 Windows 管道)。
- `tests/test_desktop_main.mjs` m1~m20:协议解析与坏行;退出提示(收摊中/已报 fatal 不再弹);版本自检(a4);
  导航(同源放行、`127.0.0.1:8766@evil` 与 `:87661` 不算同源、非 http 一律拒);更新状态机(下好之前不给装、error 不说已是最新、
  失败 15 分钟重查、平时 4 小时、首查不挡启动);`configureUpdater`(autoDownload / 不在退出时装 / disableWebInstaller);
  `installUpdate` 先收管家再 `quitAndInstall()` **零参数**(U3 = 照 ZCode);`shutdownHost` 15 秒不走才强杀。
- `tests/test_desktop_release.mjs` r1~r6:latest.yml 改写成 `download/v<版本>/` 绝对地址、sha512/size 不动、幂等、
  换号后正好落在旧版 release 的 blockmap(第九跑的机制);版本对不上拒绝;sha512 校验抓得到换过的安装包。
- `tests/test_desktop_config.py` c1~c10:nsis 各项(U4 照 ZCode、中文、不删资料);不加 customInstallMode / customFinishPage(U3/U4);
  publish = generic GitHub `latest/download`、`useMultipleRangeRequest:false`、无 github provider;版本号唯一来源;
  0.98.8 已发布代码的 ASSET_RE/TAG_RE(`git show win-installer-0.98.8:bin/ds_update.py`)认不出新名字;
  preload 暴露的方法 ⊇ 前端调用的(x2 的 Electron 版)、preload 的每个通道主进程都有 handle;退役清单里的文件已删、
  ds-web 与前端不再有 `/api/update`、前端不再读 `pywebview`。
- `tests/test_desktop_ui.mjs` du1~du12:更新一栏各状态措辞(u3 搬过来)、「重启以更新」只在 downloaded、错误态有「重试」、
  圆点只在 downloaded、提示写明约 2 分钟别关机;`shellApi` 不认 pywebview;s-w1(浏览器零按钮)照旧在 `test_shell_window.mjs`;
  窗口栏 CSS:拖动带 drag、按钮 no-drag、无 `.win-grip`。

**云 Windows(`.github/workflows/electron-e2e.yml`,断言写死,FAIL 0 才算过)**:从探路版转正,用 `desktop/` 的产品代码构建;
测试版只用 electron-builder 命令行把 publish 地址换成本机替身源(构建期,不在运行时留口子)。

- E1 构建:版本号从 `ds_web.VERSION` 来;包里不带 pywebview / pythonnet / pystray。
- E5 全新机器带界面首装:改选带空格自选目录 → 装到所选目录、1 条卸载项、开机自启默认关、资料根与配置建好、版本三方一致。
- E6 在托盘里跑着时卸载:进程全收、安装目录清空、卸载项没了、资料根原样。
- E3 从**已发布的** 0.98.8 过渡(带界面):选目录页默认 = 旧目录(`WM_GETTEXT`,第十跑验量具)、旧文件/卸载项/进程全收、
  配置业务字段(模型选择、key 引用、登录口令)前后不变(a7)、版本三方一致(a4)、开机自启/桌面图标指新 exe、资料指纹不变。
- E3b 旧版装在 A、首装时改选 B:A 的旧版进程收掉、旧卸载器跑过、只剩 1 条卸载项(「旧版在哪就去哪收」)。
- E2 起窗:10 秒内出窗口、三按钮、关窗进托盘且后台活着、再双击叫回且**不多起一份管家**、托盘还原 500ms 截图非纯色(#17)、
  窗口内跳外站不离开工作台、退出后零进程、硬杀主进程 30 秒内收干净。
- E4 更新:先不开替身源 ⇒ 更新一栏说「没查到」不说「已是最新」、出现「重试」;开源点重试 ⇒ 下好、侧栏出现「重启以更新」
  → 点它 → 向导按两下 → 新版应答、在前台、版本三方一致、原目录、1 条卸载项、资料不变、实下 < 10%、旧 blockmap 取自 `download/v<旧版>/`。
- **攻题后补(`/root/aiwork/logs/opendesign-electron-shell-t4-attack.out`,23 条逐条处置见 `evidence/20260922-t4-attack-disposition.md`)**:`tests/test_desktop_controller.mjs` mc1~mc18(接线:分块解码、版本不一致不加载、fatal 不双弹、调度只排一只、下载失败、装失败重新拉起、外链真外开、托盘 / 右键菜单);h13b(64 线程同时 emit 不粘行)、h14 按语法树认 serve 的字节流实参且 already-running 判前提不成立;c6c 分方向、c10 main.js 真接线、c2 改钉 `$isForceCurrentInstall`、c7c 改钉工具;r8 发布命令;du4b/du8;`tests/e2e/desktop_update.e2e.mjs`(真页面上各状态的 DOM);云 Windows 重排为 **E3 → E2 → E2v → E4 → E6 → E3b → 清空 → E5**(旧版过渡必须是干净机器上的第一件事),E3 植登录口令 / 大脑选择哨兵,E2v 故意改旧后台版本看弹框,E2.repaint 只量窗口内容区,E2.second 100ms 采样新 Python,E4.front 15 秒轮询,E6 等临时卸载器退出 + 配置原样,E5.pages 三页。
- **延期(发布前 / T6)**:「为哪位用户」点成「所有用户」的真实后果 —— 发布前在云 Windows 探一次、结论写进业主说明(U4 时说的是推断);托盘菜单真点(通知区 UI Automation 不稳,改为 T6 业主清单 + mc17 模板);发布后从生产 `latest/download` 做一次 smoke(T6 发布门)。
- 业主真机(T6):A0 界面出来了吗;装新版时旧版在托盘里 → 装完资料/key/档案都在;下一版走一次「重启以更新」;两台错开装;托盘三项各点一次。
