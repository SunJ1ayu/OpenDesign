# 派活前攻题的处置(2026-09-22,主 agent 仲裁)

攻题人:codex `gpt-5.6-sol`,只读、断网;任务书 `/root/aiwork/tasks/opendesign-electron-shell-t4-attack.md`,
原始输出 `/root/aiwork/logs/opendesign-electron-shell-t4-attack.out`(**派活期间留在仓外**,收货后再拷进来)。
结论原话:「目前这套判据还不能作为派活合同」—— 23 条,我逐条核了判据原文后处置如下。

| # | 攻题主张(压缩) | 核实 | 处置 |
|---|---|---|---|
| 1 | 纯函数写对、main.js 不调 ⇒ 版本自检 / 退出提示 / 调度全是死代码 | 属实:m-组只调纯函数 | **修**:新接缝 `controller.js`,mc3~mc16 测接线;c10 钉 main.js 真用它;E2v 真机故意改旧后台版本 |
| 2 | 管道分块:一行切多块 / 多行一块 / UTF-8 切半 | 属实:m1 只喂整行 | **修**:`createHostDecoder`,mc1/mc2;控制器 `hostStdout` 吃原始块 |
| 3 | h14b 搜字符串可被注释喂饱;already-running 让编码检查空转 | 属实 | **修**:h14b 按语法树认 serve 的前两个实参;already-running 判「前提不成立」红。**没采纳**「真进程再发一条中文命令」:起不来后台时管家根本不读 stdin,输入方向的解码由 h8(serve 只收字节)钉 |
| 4 | emit 两次写 ⇒ 多线程粘行 | 属实:没有并发用例 | **修**:h13b 64 线程同时发 |
| 5 | 按钮可能下载中就出现、提示不渲染 | 属实:du6/du9 只测函数 | **修**:新 e2e `desktop_update.e2e.mjs` 往真页面推每种状态看 DOM(整页不许出现「重启以更新」、提示真渲染、点了叫对方法) |
| 6 | 只测了「查失败」,没测「下载失败」与「整包回退」 | 部分属实 | **修**下载失败:mc14 + du4b + du8(带版本号的 error 亮点);**整包回退不拦**,design D 写明理由(攻题人把 design 那句读成要拦,是我原话写得含糊) |
| 7 | 15 分钟重查可以没接线 | 属实 | **修**:mc10~mc13 假时钟,且只许排一只定时器 |
| 8 | quitAndInstall 失败 ⇒ 空壳窗口 | 属实:规格里没写 | **修规格 + 判据**:design D 加「弹人话并重新拉起」;mc16 |
| 9 | IPC 同名反方向也对得上 | 属实 | **修**:c6c 三张表分方向 |
| 10 | 托盘 / 右键菜单可以不实现 | 属实 | **修**:menus.js 模板 mc17/mc18 + c10 钉 main.js 用它;**托盘真点延期**到 T6 业主清单(通知区 UI Automation 在 CI 上不稳,量具假红的代价高于它挡的东西) |
| 11 | 外链可以退化成「全拒」 | 属实 | **修**:mc9 断言 openExternal 恰好一次;浏览器真被拉起不测(CI 默认浏览器行为不可控) |
| 12 | c4 把唯一来源写成两份手工副本 | 规格用词与判据不一致属实;判据本身不错 | **改规格措辞**:提交时同值 + c4 钉,构建不改写(少一个会错的构建步骤) |
| 13 | c2 按宏名禁会误伤、又挡不住换名跳页 | 属实 | **修**:c2 改钉 `$isForceCurrentInstall` 置 1;页面序列由 E5.pages / E4.wizard 按真实向导核 |
| 14 | du8 与「下载失败不许静默」矛盾 | 属实 | **修**:圆点 = downloaded 或带版本的 error;单纯查不到不亮(理由写在 du8 与 design D) |
| 15 | RELEASE.md 禁词误伤、提一句就喂绿 | 属实 | **修**:发布命令由 `ghReleaseCommand` 生成(r8);c7c 只要求说明叫人用 `gh-command` 与 `verify` |
| 16 | E3 的旧版资料被 E5 新版先污染;E3b 不核资料;哨兵不够 | 属实 | **修**:重排为 E3 先跑(干净机器上第一件事);E3 植登录口令 / 大脑选择哨兵;E3b、E6 核资料与配置业务字段 |
| 17 | 「所有用户」分支没走 | 属实;U4 时就说明是推断 | **延期到发布前**:云 Windows 探一次,把真实后果写进业主说明;不挡派活(业主已知情选择保留这一页) |
| 18 | 卸载器临时副本不退、配置被复位看不出 | 属实 | **修**:E6.done 等 Au_/Un_ 全退;E6.config 比业务字段 |
| 19 | 重绘分析整屏、被壁纸喂饱 | 属实 | **修**:shot.ps1 `-Rect` 只量窗口内容区,E2.repaint 用窗口 bounds |
| 20 | E2 退出走 app.quit(),没真点托盘 | 属实 | 同 #10:模板 + 接线静态闸;真点延期 T6 |
| 21 | 第二次打开只看 2.5 秒后的进程数 | 属实 | **修**:E2.second 100ms 采样新 Python PID + 第二份自己退出 |
| 22 | 前台只采一瞬,正确产品会假红 | 属实 | **修**:E4.front 15 秒轮询,当过一次前台就算 |
| 23 | 没验真实发布出去的 release | 属实 | **延期到 T6 发布门**:发布后从生产 `latest/download` 做一次 smoke(读 latest.yml、核三样资产与 sha512) |

另外自己在修判据时抓到的:`Where-Object -Begin` 在 PowerShell 里不存在(本机装了一份 pwsh 实跑确认会抛)⇒ E4/E5 的页头去重会让整场判据在 E4 中途中止,已改 `ForEach-Object`;
e2e.ps1 / click-wizard.ps1 / shot.ps1 已用真 PowerShell 解析器过一遍语法,辅助函数(CfgFacts / HealthVer / V / Marks)用假输入实跑过。

## 复核(2026-09-22 17:27,Cursor `grok-4.7-high`,xai 家族,只读快照)

任务书 `/root/aiwork/tasks/opendesign-electron-shell-t4-recheck.md`,输出 `/root/aiwork/logs/opendesign-electron-shell-t4-recheck-cursor.log`
[仓外不承重]。结论 **BLOCK**:23 条多数已堵、延期站得住;两处处置表写成已修、原文没钉死。会话在复核跑完前断了(额度),19:00 接手后逐条对判据原文核实:

| 复核主张 | 核实 | 处置 |
|---|---|---|
| 必须修 1:解码器测对了,控制器 `hostStdout` 可以仍按块当整行解析(mc3 起每次都喂整行) | 属实:mc1/mc2 只调 `createHostDecoder` | **修**:mc2b 往**控制器**喂三组原始块(一行切三块 / 两行一块 / 中文切在字节中间)、mc2c 字符串块;c10c 禁 main.js 逐块 toString |
| 必须修 2:c10 漏 `startUpdates` / `installUpdate` / `hostExit` / `setQuitting`;main.js 自己 checkForUpdates 一次、直接 quitAndInstall 照样绿 | 属实 | **修**:c10 补齐;c10b **禁** main.js 出现 `checkForUpdates` / `quitAndInstall`(只许经控制器) |
| 同上:mc14 不要求下载失败后再排 15 分钟 | 属实;design「出错后 15 分钟再自动查一次」 | **修**:mc14 断言恰好一只 15 分钟定时器 |
| 同上:mc16 只要求 relaunch 被叫;`app.relaunch()` 本身不退出 | 属实(Electron 文档:relaunch 只登记,要 `app.exit`/`app.quit` 才退) | **修**:c10d 钉 `app.relaunch()` 紧跟 `app.exit(`;mc16 加先弹话、后拉起(反了业主看不到那句话) |
| 同上:托盘三个回调可以是空函数 | 属实 | **修**:c10e 取 `trayMenuTemplate({…})` 就地字面量,三项各自要做事;真点仍延期 T6 |
| #16 E3 的 key 引用没哨兵,`ds_merge_config` 会把 `providers.custom.apiKey` 盖回模板 | 属实(`ds_merge_config.py` 只回写已有 apiBase) | **不在本单**:这是换壳前就有的合并规则,本单不改它;机主不手改 apiKey 引用(key 走 ds_credential,变量名从引用里读)。记账,另开单时先查有没有写口会写非模板的引用 |
| r8 先滤成已知三个路径再比 ⇒ 多带文件不红 | 属实 | **修**:按扩展名认出所有像资产的实参再比 |
| desktop_update 的提示只看整页有没有那两句 | 属实 | **修**:改成对照 —— 下好之前不许有、下好之后必须有 |
| h14b 实参先赋给变量会假红 | 属实 | 不改:接缝表写明 `main()` 直接传 `sys.stdin.buffer` / `sys.stdout.buffer`(派活书也写) |
| #19 非 100% DPI 裁错、#22 前台残留假红 | 属实,当前 runner 不触发 | 不改,记账 |

**同类再扫(主 agent 自己)**:控制器把外链 / 诊断包交给 deps,deps 是空函数照样全绿 ⇒ c10 补 `shell.openExternal` / `shell.showItemInFolder`;
复核说 `setWindowOpenHandler` 是残留不单列 ⇒ 我改为补上(`target=_blank` 开进一个带后台权限的新窗口,和外链全拒是同一类);
**复核没提、我接手时自己想到的**:Node 子进程 `exit` 事件时 stdout 可能还没读完 ⇒ 在 exit 上叫 hostExit,管家退出前最后一行 fatal 会排在「意外退出」之后 ——
mc5 在现场失效。c10c 钉 `close`;mc5b 钉「没换行的最后一行 + 立刻退出」仍只弹 fatal。
（顺带核过:后台子进程的 stdout/stderr 进日志文件,不继承管家的管道 ⇒ `close` 不会被孙进程拖住。）

**判据的判据**:`evidence/c10_samples_check.py` —— 一份写对的样例 main.js 全绿,11 种故意写错的各在对应那一条上红(收据见 verify.md)。
行为判据 mc2b/mc2c/mc5b/mc14/mc16 在还没有 `desktop/lib` 时的红是平凡的红,问不出它们会不会误伤正确实现;收货时若只剩它们红而实现讲得通,先查题面(CLAUDE.md 那条反例)。

