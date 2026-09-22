# T3 判据迁移账(2026-09-22,主 agent 亲写)

design.md「判据迁移账」的兑现:**每个要退役或改写的旧判据,写清它守的是什么 → 新判据编号,或因行为退役而不再需要(理由)**。
不许只删不记。**执行方式(09-22 派活前定)**:判据侧的删除与改写全由主 agent 在一个单独的判据 commit 里做完(执行腿不许删文件、
不许动判卷);退役的**产品代码文件**也由主 agent 在派活前删掉(腿只负责把剩下的接好)。因此派活前的基线上:
新判据红、改写过的判据红(目标还不存在)、被删代码的调用方红 —— 全部由 T4 实现变绿。

新判据(本单 T3 写,先单独 commit):
`tests/test_ds_host.py` h1~h15 · `tests/test_desktop_main.mjs` m1~m22 · `tests/test_desktop_release.mjs` r1~r7 ·
`tests/test_desktop_config.py` c1~c9 · `tests/test_desktop_ui.mjs` du1~du12 · 云 Windows `.github/workflows/electron-e2e.yml`(E1~E6)。

## 一、仍然成立、必须有新编号的保证(design 点名的四条先列)

| 旧保证 | 旧判据 | 新判据 |
|---|---|---|
| 查不动不许说「已是最新」 | u3(test_update_ui)、t9b | m14、du4、**E4.offline**(云 Windows 真跑一遍) |
| 浏览器里一个窗口按钮都不画 | s-w1/s-w2/s-w2b/s-w2c(test_shell_window.mjs)、x4、x11 | s-w1~s-w2c **原样保留**;m21(外壳地址带同一个标记) |
| Job 收整棵树 / 硬杀外壳后后台不成孤儿 | c-组(test_ds_shell_core,保留)、探路 E2.crash | h2(EOF⇒收摊)、m18/m19/m22、**E2.crash / E2.quit** |
| 资料根不动 | t13/t23/au10(更新器)、探路 E3.data | **E3/E4/E6 .data**(指纹)、E6.config、c1(deleteAppDataOnUninstall=false) |
| 版本号 + nonce 认新版(半新半旧不算装好) | t18a~f、t19、t37 | m5~m7(版本自检)、h1(ready 带版本)、c4(唯一来源)、**E3/E4/E5 .samever 三方一致** |
| 不往回装 / 同版不重装 | t3a/t3b/su10 | m17(`allowDowngrade=false`;electron-updater 只在远端版本 > 本机时提示) |
| 下载的东西要核过才装 | t15、pr3/pr4、su9、ai9 | electron-updater 自带 sha512 校验;r6(发布时核 latest.yml 与安装包逐字节一致) |
| 失败不许被缓存几个小时 / 业主点了必须真去查 | t8c/t8d、t9c | m16(失败 15 分钟重查)、c6b(`update.check` 存在)、**E4.offline→重试** |
| 查更新绝不挡启动 | su_net1~3、0.98.8 的 startup-not-blocked | m16(`FIRST_CHECK_DELAY_MS` > 0)、E2.window(10 秒内出窗口) |
| 不碰 api.github.com(VPN 出口限流) | t1b、rl4、rl7a | c3、c3b |
| 带空格 / 中文的安装路径照常 | t36b、windows-update-e2e 的带空格目录 | E3(`C:\AI Test\…`)、E3b、**E5(`C:\OD 新装\…`,空格 + 中文)** |
| 装之前把正在跑的旧版收干净(否则文件被占、半新半旧) | t6a/t6b、t22c、w9 | m20(先收管家再交安装器)、**E3.oldproc、E3b.oldproc、E6.proc** |
| 前端报的启动事件只收白名单 / 限长 / 去重 | s7 | h8(管家这一侧仍走 `ds_diag.report_from_ui`,s7 本身留在 test_startup_diag) |
| 诊断包白名单 | s10 | h9(且带上 electron.log);s10 本身保留 |
| 首帧看门只上一次膛 / 首帧到了不写快照 | s14/s15 | h10/h10b |
| 启动时间线分阶段 | s6、s17 | h15(lock.acquired → backend.ready → window.shown);s17 **改写**,见下 |
| 看门狗一眼看全死因 / 报退出码 | w6/w7、c20/c21 | h7、h7b |
| 锁通道:存 key 后重启网关 | w3/w4、b11 | h1(锁端口进后台)、h11;b1~b14 保留 |
| 静默模式下每个框自己有答案 | installer_silent s1~s4 | c2c |
| 两份名单对得上(按下去有人接) | x1/x2/x3 | c6/c6b/c6c(preload ↔ 前端 ↔ 主进程) |
| 窗口按钮不被拖动吃掉 | x5/x6/x8 | du12(按钮区 `no-drag`)、E2.max/min/close 真点 |
| 窗口栏整块画出来(标记在首帧就在) | x10 | m21、E2(`page.waitForURL(/shell=1/)` + `[data-ui=window-bar]`) |
| 退出幂等、后台只收一次 | ShellState f5/f8/f9 | m22;f8/f9 的**线程竞态**在 Node 单线程事件循环里不存在(见下) |
| 关窗=进托盘 / 托盘叫回 / 只有托盘退出才真退 / 第二次打开叫回 | ShellState f1~f4 | **E2.close / E2.second / E2.quit**(真窗口真点;逻辑写在 Electron 事件里,Linux 上没有可单测的状态机了) |

## 二、逐文件去向

### A. 整个文件退役(它守的代码整个删掉;判据文件在派活前的判据 commit 里删,被测代码由主 agent 派活前删)

| 文件(条数) | 守的是什么 | 去向 / 不再需要的理由 |
|---|---|---|
| test_ds_update.py(33) | 旧更新器挑版本:全 prerelease 里挑最新、资产名/草稿、版本比较、缓存、坏响应不抛 | 挑版本/比较/缓存由 electron-updater + generic 源承担(`latest.yml` 只有一个版本);保留的保证见上表(t3→m17、t8→m16、t1b→c3)。**两段式 tag / 补零**:新 tag 由我们发布时写 `v<ds_web.VERSION>`,版本三段,c4 + r5 钉住名字 |
| test_ds_update_apply.py(82) | 接力脚本「装到旁边再换名 + 回滚」、nonce 认新版、Job breakaway、NSIS 更新档、路径安全 | 换名接力整体退役(electron-updater 就地重装)。**回滚是已接受的保证损失**(design D);补救 = 发布前云 Windows 判据全过 + 发布页留旧版 + 两台错开装(a3)。nonce → m5~m7/三方一致;路径 → E3/E5 |
| test_ds_update_startup.py(37) | 「打开软件时装」的启动决策、状态文件原子写、后台备货 | 行为退役:U3 = 照 ZCode,他点「重启以更新」才装;0.98.7 业主否过「打开时装」。备货由 electron-updater `autoDownload` 承担(pending 目录它自己管) |
| test_ds_update_source.py(40) | 发布页订阅源 / 清单 / API 回落、限流与失败说人话 | 源换成 generic `releases/latest/download`(c3),不再有 API 回落这条链;「失败说人话、不甩英文」→ du4 |
| test_ds_update_eligibility.py(22) | 「同一版只自动试一次」的资格账 | 行为退役:不再自动装(U3),没有「自动试」这件事 |
| test_ds_web_auto_update.py(27) | ds-web 自动更新资格端点、记账原子写 | 同上;端点删(c8) |
| test_ds_web_auto_install_local.py(9) | 自动装只用本地包、不联网 | 同上 |
| test_ds_web_update.py(26) | `/api/update/*` 端点、健康检查回显 nonce、交棒动词 | 端点整组删(c8,表 #11 两个真相源只剩主进程一个);nonce → m5~m7;交棒 → m20 |
| test_ds_web_update_roots.py(3) | 更新状态文件只有一份、落在数据根 | 状态文件随旧更新器消失 |
| test_update_manifest.py(5) | 发布清单 `OpenDesign-update.json` 生成器 | 清单随旧通道退役;新发布物的核对 → r6(`verifyFeed`) |
| test_update_e2e_harness.py(41) | 旧 windows-update-e2e 的替身 GitHub、证书、判定器 | 旧云判据退役;新的替身源 = `.github/scripts/electron-e2e/serve.mjs`(探路十跑磨过),判读写死在 e2e.ps1 |
| test_window_native_styles.py(7) | WinForms 样式位 / 最小化前补位 | pywebview+WinForms 退役;Electron `frame:false` 不关 thickFrame(照 ZCode)⇒ 最小化动画/贴边由系统给;真机效果 → E2.min/max + T6 业主看 |
| test_window_native_frame.py(13) | WM_NCCALCSIZE 接管、真最大化 | 同上;E2.max「最大化不盖任务栏」保留了唯一业主可见的那条 |
| test_window_frame_experiment.py(9) | 窗口动画实验开关(`关掉窗口动画.on`) | 同上;逃生门随手补的窗口层一起消失(`frame_animation_on` 与 `DISABLE_FLAG` 在 T4 删) |
| test_window_frame_late.py(6) | 边框动作挪到首次使用、量了不对自动撤 | 同上 |
| test_update_ui.mjs(46) | 旧更新一栏的措辞、发布说明摘要、下载链接闸、自动装倒计时 | u3 → du4;u1/u5 → du5/du1;u4 → du2;蓝点 u(hasUpdateBadge)→ du8;发布说明摘要/下载链接(u6~u37、rl11、ac*)随「下载去发布页」这条路一起退役 —— 新流程在应用内下好再装 |
| test_startup_gate.mjs(10) | 打开软件时的更新闸画面 | 行为退役(同 test_ds_update_startup) |
| e2e/update_notice.e2e.mjs、e2e/auto_update_countdown.e2e.mjs | 旧更新一栏、倒计时的浏览器 e2e | 同上;新流程的真机 e2e = E4(offline → 重试 → 按钮在收起那一行 → 交棒) |
| e2e/api_partial_injection.e2e.mjs | pywebview 分步注入那一瞬(方法还没挂上) | preload 在页面脚本之前就位,没有「注入晚于首帧」;残余的「半个对象」情形 → du11(缺一个方法就当没有) |
| mutation-ds-update*.sh、mutation-update-*.sh/.py、mutation-auto-update-*.sh、mutation-ds-web-update.sh、mutation-window-chrome.sh、mutation-native-frame.sh、mutation-frame-*.sh、mutation-shell-restart.sh、mutation-startup-diag.sh | 上面各文件的变异收据(shell-restart 一半是交棒;startup-diag 一半是旧探针判定器) | 随被测文件删;mutation-ds-shell-core.sh 只去掉 M13(ShellState 退出加锁 → m22)。本单的变异在 T5 前对新判据重做 |

### B. 文件保留、部分用例退役或改写

| 文件 | 退役 | 改写 | 保留 |
|---|---|---|---|
| test_ds_shell_core.py | `SingleInstance` 的 m1~m4(UPDATE-HANDOFF 动词:唯一发送方是退役的 ds-web 更新端点);`ShellState` f1~f9(状态机随 Shell 删;保证去向见上表) | — | b1~b14 与其余全部(锁、端口、配置、Supervisor、Job 都留给管家用) |
| test_ds_shell_wiring.py | w8/w9(锁接交棒回调 / 交棒真收摊);w6/w7(看门狗问 take_dead、只看一眼 —— 看门狗搬进管家,h7 用「poll_dead 一调就炸」的假 Supervisor 从行为上钉,比查函数名强) | w3/w4 的目标从 `ds_shell.py` 换成 `ds_host.py`(`make_lock(on_restart=…)` / `start_backend(lock_port=…)`)—— 行为版已由 h1/h11 钉,静态版留作第二道 | w1/w2/w5/w10(`start_backend` 留在 ds_shell.py) |
| test_ds_shell_startup.py | — | — | s1~s6 全留(`start_backend` 不动) |
| test_startup_diag.py | s6(`window.shown` 由 pywebview shown 事件报 → Electron 发 window-shown,h15);s14/s15(首帧看门接在 `Shell` 上 → h10/h10b);s18~s22(旧 windows-package-probe 的判定器 `bin/probe_verdict.py` 与收据双路;该 workflow 退役,判定器进 c7 退役清单) | s17 读的文件从 `ds_shell.py` 换成 `ds_host.py`(`main.entered` / `manifest.done` / `lock.acquired` 跟着 `main()` 搬家);`shell.imports_done` 仍在 ds_shell 模块尾 | s1~s5、s7~s16 全留(ds_diag 不动)。s18~s22 的**原则**已搬进 e2e.ps1:子驱动 rc 必判(`E2/E4 整体`)、每个等待都有墙钟上限、有 FAIL 就 exit 1 —— **不再有单独的判定器进程与收据文件,所以不移植那几条元判据**(接受的偏差,写进 verify) |
| test_shell_window_contract.py | x1/x7/x8/x9(八个把手随表 #10 删);x12(等 pywebview.api 到位) | x2/x3 → c6(名单对表的 Electron 版);x10 → m21 | x4/x5/x6/x11 改读新文件后保留(浏览器不画、没东西盖住窗口栏、点按钮不连带拖动、标记是唯一闸) |
| test_shell_window.mjs | s-w7(把手指针) | — | s-w1~s-w2c |
| test_no_console_window.py | — | — | 全留:Python 那侧起子进程仍走 `spawn_kwargs()`;管家本身由 Electron `spawn(…, {windowsHide:true})` 起 —— T4 核 main.js 有 windowsHide(E2 截图里不许有黑框) |
| test_shipped_names.py | — | — | 全留;T4 核它的扫描范围把 `ds_host.py` 算进去(n1「有文件可看」会提醒) |
| test_comment_references.py | — | — | 全留;删掉 ds_auto_update 等之后,注释里点名它们的地方要一起清(这道闸会红,是对的) |
| test_win_ctypes_decls.py | — | 豁免清单去掉 `ReleaseCapture`(随 WindowApi 删;留着 = 空头豁免,它自己的第二条会红) | 全留:`alert` 的 MessageBoxW 还在 ds_shell,ds_shell_core 的 Job 调用也在 |
| test_installer_slim.py | — | — | 全留(打包脚本 build-package.sh 保留,加 `--electron` 形态) |
| e2e/shell_chrome.e2e.mjs | 八个把手那几段 | 注入对象 `window.pywebview.api` → `window.odShell`(断言不变:浏览器零按钮、外壳里三按钮真点、没东西盖住) | 其余 |
| e2e/startup_report.e2e.mjs | 「pywebviewready 之后补发」那一段 | 注入对象换成 `window.odShell.reportStartup`(preload 在页面前就位 ⇒ 不再需要缓存补发;断言「真被调用、只报白名单事件」不变) | 其余 |
| e2e/helpers.mjs | — | — | 全留(只在注释里讲 `/api/update/check` 的由来,没有拦截代码;核过) |

### C. 云 Windows workflow

| 退役 | 守的是什么 | 去向 |
|---|---|---|
| windows-package-probe.yml + .ps1 | 旧 NSIS 包装得上、起得来、不白屏、日志三份在 | electron-e2e E1/E5(装得上、起得来)、E2.repaint(不是一片底色)、E2.window;日志随 e2e-out 上传 |
| windows-update-e2e.yml + .ps1 | 旧更新器端到端(真替身 GitHub、带空格目录、限流回落、自动装) | electron-e2e E4(真 electron-updater、真替身源、GitHub 真实布局、增量字节、版本三方一致) |
| electron-shell-probe.yml(探路) | U2 十跑 | 转正为 electron-e2e;spike/ 目录留作参照 |
| windows-nonempty-probe.yml + .ps1 | 旧 NSIS 包静默装进非空目录 / 卸载会不会连带删业主的东西(量的是 `installer/OpenDesign.nsi` 的 CheckDirEmpty 与卸载认门) | 随旧安装包退役(派活前删产品文件时核出它依赖 OpenDesign.nsi,09-22 补记);新安装包的同类风险 → E3b/E6(旧卸载器只卸旧程序、卸载时资料根原样) |
| windows-gui-probe / windows-atomic-probe | 与换壳无关的旧探针 | **不动**(本单不碰;核过不引用退役文件) |

## 三、已知不再有判据的东西(接受,写明)

- **更新失败后自动回滚到旧版**:electron-updater 做不到(design D)。补救见上。
- **ShellState 的线程竞态(f8/f9)**:Node 主进程单线程事件循环,不存在「两条线程同时 quit」;并发两次调用由 m22 管。
- **「打开时自动检查」开关**(test_update_ui u9~u12 / App.tsx `AUTO_CHECK_PREF`):随「自动更新偏好」退役(design D 退役清单)。
  事实依据:装好的应用里 localStorage 本来不跨重启保存(f1)⇒ 这个开关在业主机器上**每次重启都回到「开」**,从没真正关住过。
  ⚠️ 这是业主看得见的一项消失,**T6 说明里要告诉他**;他要的话另开单做成设置页开关(那时存到后台,不存 localStorage)。
- **ds_diag 版本清单里的 `WebView2=`**:换壳后不再用 WebView2,这一项会一直是「查不到」。不影响任何判据;另记一条小账(让管家报 Electron/Chromium 版本),不在本单。

**T4 补记(2026-09-22 19:30,主 agent 跑 python 全量时抓到)**:`tests/test_installer_silent.py`(上表「静默模式下每个框自己有答案」那一行,保证已去 c2c)
本该随它量的 `installer/OpenDesign.nsi` 一起在 `4b90d84` 退役,当时漏删 ⇒ 全量里 4 条 FileNotFoundError。现在删掉;
`tests/fixtures/update/`(只有已退役的旧更新器判据读它,全仓再无引用)一并退役。都是判卷面,单独 commit。
