# 独立方案挑战:OpenDesign 换 Electron —— 实施方案(第二次挑战,上一次挑的是「换不换」)

你是独立的第二意见。仓库快照是 OpenDesign(室内设计师用的本地 AI 助手,Windows 桌面应用)。
请**先从业主目标推演失败场景,再挑战下面拟议的改变**。不要写代码,只读仓库快照。
`tracks/opendesign-electron-shell/` 里有:业主原话(proposal.md)、探路版代码(spike/,已在云 Windows 跑过六次)、
六次实测的收据与截图(evidence/20260922-u2r*)。

## 业主是谁、原话(逐字)

- 室内设计师,不是程序员,唯一使用者;两台 Windows(公司 `F:\AI\OpenDesign`、家里 `D:\AI\OpenDesign`,都是他在安装器里自选的目录)。
  开机自启、软件常驻托盘。在中国,开商用 VPN。
- 换不换、换多少:见 proposal.md「真问题」一节(「我觉得我们得换 Electron」→「都一起换了吧,参考一下 zcode 这一段前端代码」→
  听完劝他只换窗口的理由后「全换吧」;换壳那一版「可以就选a」= 他手动装一次)。
- 2026-09-22 看了云 Windows 实拍截图后选更新方式。给他的三个选项原文:
  A「下载好就马上装」—— 坏处:你正在用的时候软件可能突然关掉,要等 2 分多钟;
  B「下载好先提醒你,你点『现在更新』才装」(agent 推荐)—— 点一下,后面不用管;坏处:一直不点就一直旧版;
  C「和 ZCode 完全一样」—— 你点『重启以更新』,然后在安装窗口里自己点几次『下一步』;坏处:比 B 多点几下。
  另两种未列:「打开软件时装」(0.98.7 这么做过,他用下来觉得打开要干等,0.98.8 已改掉)、「关软件时自动装」(关后马上关机会装一半)。
  **业主答:「c吧」。**
- 之后看了 C 的四张实拍(安装选项页『下一步』→ 进度约 1 分 50 秒 → 安装完成页『完成』→ 新版在最前面),
  被问「第一页『为哪位用户安装』要不要去掉」,并被告知点成「所有用户」会要管理员授权、软件搬到 C:\Program Files、原目录被卸、开机自启可能失效。
  **业主答:「留着和zcode一样」。**

## ZCode(agent 读 `zai-org/ZCode@872ad96` 得到的事实,你读不到那个仓)

Electron 桌面应用;electron-builder NSIS `oneClick:false`、可选目录、未设 perMachine;electron-updater `autoDownload=false`
(有「自动下载并安装」设置项)、Windows 上 `autoInstallOnAppQuit=false`(注释:窗口关后安装器异步启动,紧接着关机会被打断留下半更新);
下载好后菜单/按钮变「重启以更新」,用户点 → 先等 host/子进程退完 → `autoUpdater.quitAndInstall()`(默认参数,非静默 ⇒ 用户走向导);
generic provider + `useMultipleRangeRequest:false`(注释:CDN 多段请求不行,关掉后仍走差分)。

## 现在的行为(均可在快照里核)

- 外壳 `bin/ds_shell.py` + `bin/ds_shell_core.py`(pywebview + pystray;单实例锁兼 ds-web 回呼通道;`start_backend` 起网关与工作台、Job;看门狗;首帧看门与诊断导出)。
- 更新:`bin/ds_update.py` / `ds_update_apply.py` / `ds_update_startup.py` / `ds_auto_update.py`,ds-web `/api/update/*`,
  前端 `web/src/update.ts`、`App.tsx`(开机更新画面、自动更新偏好、横幅、回滚提示)。发现通道 releases.atom + 随包清单;全部 release 是 prerelease;
  tag `win-installer-<版本>`、资产 `OpenDesign-Setup-<版本>.exe`。
- 安装包 `installer/OpenDesign.nsi`(Linux 上 makensis 编;组件页有「桌面图标」默认勾、「开机时自动启动」默认不勾;卸载页有默认不勾的「连资料一起删」)。
- 判据:`tests/`(run-all.sh 总跑);Windows 探针 `.github/workflows/windows-package-probe.yml`、`windows-update-e2e.yml`。
- 版本号只许加第三位;`bin/ds_web.py` `VERSION` 现为 0.98.9(0.98.9 已构建未发布;业主两台机器现跑 0.98.8)。

## 拟改变的行为(实施方案)

1. **进程**:Electron 主进程管窗口(frame:false、不关 thickFrame、resized/show 后补重绘)、托盘(打开 / 导出本次启动诊断 / 退出)、
   单实例(`requestSingleInstanceLock`,第二份叫出第一份)、外链交系统浏览器、更新器。Python「管家」`bin/ds_host.py`
   复用 `ds_shell.start_backend` 与 `InstanceLock`(只留 ds-web「存 key 后重启网关」通道),stdout 一行一个 JSON 事件、
   stdin 一行一个命令,stdin EOF = 收摊。收摊顺序:先关管家 stdin 等它退(Job 收整棵树),15 秒不退强杀,再退 Electron。
   `ds_shell.py` 的窗口半边(WindowApi/Shell/main/pystray/pywebview)退役,后台半边留下。
2. **前端**:preload 暴露 `window.odShell`(minimize/toggleMaximize/close/windowState/onWindowState/reportStartup/update.*),
   `WindowChrome.tsx`/`startupReport.ts` 改接它;拖动用 CSS `-webkit-app-region`;八个缩放把手删掉;`?shell=1` 标记保留。
3. **安装包**:electron-builder NSIS,`oneClick:false`、`perMachine:false`、可选目录、简体中文、不删资料;
   自定义段照探路版(把旧版记下的目录转成默认目录、收掉安装目录里所有进程、用旧卸载器静默卸旧程序、首装初始化配置、沿用旧版开机自启选择)。
   全新安装**没有**开机自启勾选项(默认关)。桌面图标默认建。
   另按旧版注册表记的旧目录收进程、跑旧卸载器(不论业主在选目录页选了哪里);旧卸载器跑完核旧版标志文件,还在就重试一次,仍在就弹人话退出。
4. **更新**:主进程 electron-updater;`autoDownload=true`(后台下,增量约 1MB)、`autoInstallOnAppQuit=false`;
   generic `https://github.com/SunJ1ayu/OpenDesign/releases/latest/download`、`useMultipleRangeRequest:false`;
   旧版 blockmap 从 `releases/download/v<当前版本>/` 取(`previousBlockmapBaseUrlOverride`);窗口出来后延迟查一次、之后每 4 小时一次,不挡启动;
   状态经 preload 推给前端设置页,下载好了才出现「重启以更新」,点了 → 先收管家 → `quitAndInstall()` 默认参数 → 向导两下。
   浏览器形态(Linux / git-pull)只显示版本 + 发布页链接。
   「重启以更新」旁写「约 2 分钟,期间请别关机」;下载失败显示人话 + 重试,不静默。
   旧版的「装到旁边、新版起不来就退回」回滚随旧更新器退役;补救 = 每版发布前云 Windows 判据全过、旧安装包留在发布页可装回。
   **退役**:四个 Python 更新模块、ds-web `/api/update/*`、开机更新画面 / 自动更新偏好 / 横幅 / 回滚提示,以及对应约 20 个判据文件(逐条记去向)。
5. **发布**:tag `v<版本>`、**正式 release(非 prerelease)**,资产 = 安装包 + blockmap + latest.yml;在 GitHub Actions windows-latest 上构建,
   agent 下载核对 latest.yml 的 sha512,业主自己跑 `gh release create`。旧版 0.98.x 看不见新版 ⇒ 两台各手动装一次。
6. **版本号**唯一来源 `ds_web.VERSION`,打包时写进 package.json。
7. **旧安装包工具链退役**(`installer/*.nsi`、build/check 脚本、两条旧 Windows workflow),由新的云 Windows 判据 workflow 取代。

## 请回答三件事(不必凑数,没有就说没有)

1. **完全按上面实现了,业主的目标仍会怎样落空?** 给具体场景(什么时候、他做了什么、看到什么、实际发生什么)。
   特别留意:手动装那一次、之后第一次「重启以更新」、两台机器、他不点按钮的情况、退役掉的东西里藏着的仍然需要的保证。
2. **哪个前提如果是假的,就要重做?** 指出它,并说用什么最小实验能证伪(能放进 GitHub Actions windows-latest 的更好)。
3. **有没有更简单的实施方式**(在业主已拍板的范围内:四样全换、手动装一次、更新照 ZCode、第一页保留)?它牺牲什么;用什么最小实验分辨。

引用仓库代码时给文件路径与函数名。业主已拍板的事(换不换、A/C/留着)不必再劝。
