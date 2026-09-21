# Design: opendesign-electron-shell

- Change: opendesign-electron-shell
- Status: draft —— 方案挑战已做完;**业主 09-21 深夜拍板四样全换**;下一步探路实验(U2)

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

## Approach

(U1 答复后定稿。管家留 Python、窗口照 ZCode 的部分已定。)

## Test strategy (oracle)

(U1、U2 之后写。)
