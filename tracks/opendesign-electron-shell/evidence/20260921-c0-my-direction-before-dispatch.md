# 主 agent 的方向 —— 派发前落盘的原件副本

> 原件在仓外 `/root/panel-my-reviews/opendesign-electron-shell-my-direction.md`(派发前写,两条腿读不到)。
> 两腿交卷后才复制进仓,内容一字未改。


**不喂给任何腿。** 放仓外。读外部报告之前写完,之后不改;对账写在仓内 design.md。

## 业主已拍板的(不是我的推导)

- 换 Electron(09-21「我觉得我们得换 Electron」)。
- 「都一起换了吧,参考一下 zcode 这一段前端代码」—— 我转述为「窗口、托盘、安装包、自动更新全换成
  ZCode 那一套」,他答「可以」。
- 换壳那一版**手动装一次**(卸旧装新),之后回到自动更新(「可以就选a」)。

## 我的方向

1. **Electron main 只管窗口/托盘/单实例/右键菜单/外链/报错框**,照 ZCode `desktopWindowChrome.ts`:
   Windows `frame:false`(不关 thickFrame)、三按钮前端自绘走 preload IPC、`app-region` 拖动、
   resized/show 后 `webContents.invalidate()` 双帧重绘、setWindowOpenHandler→openExternal、
   contextIsolation/sandbox、只许导航到自己的 loopback origin。窗口先出来显示「正在启动」,后台就绪再 loadURL。
2. **管家进程留 Python**(= ds_shell_core 那半 + ds_shell.py 的 start_backend/看门狗/诊断,去掉 WindowApi/pystray/pywebview)。
   Electron spawn 它,stdin/stdout JSON 行协议;stdin EOF = 父进程死了 ⇒ 收摊(Job 仍由 Python 建)。
   理由:KILL_ON_JOB_CLOSE、build_env 注 key(0.98.9)、ds-web 锁通道协议都在这,有判据锁着。
3. **安装包:electron-builder NSIS**(oneClick:false、可选目录、per-user、extraResources 装 python/ 与 ds/),
   自定义 include 脚本移植:数据根在安装目录外、卸载默认不删资料、非空目录闸、开机自启勾选、provisioning。
   去掉 WebView2 引导程序与 .NET。构建放 GitHub windows-latest(Linux 上改 exe 资源要 wine 的可能性高)。
4. **更新:electron-updater + GitHub provider(allowPrerelease)**;下载在后台,「打开就装已下好的」语义保留;
   quitAndInstall 前先让 Python 管家把子进程全收掉(ZCode `autoUpdater.ts:441` 同一问题)。
   Python 的 ds_update*/ds_auto_update 退役,前端 update.ts 改接 preload 事件。
5. **过渡**:新版安装包**改名**(不匹配旧 ASSET_RE `OpenDesign-Setup-<版本>.exe`),或旧清单不列它,
   **让旧版的自动更新看不见它** —— 否则 0.98.7+ 的「启动即装已下好的」会自己去装 Electron 版,
   走我们刻意不想走的 .new 改名路径。业主手动:托盘退出 → 卸载(不勾删资料)→ 装新版。
6. 顺序:探路包(云 Windows:装→开→截图→Playwright 点按钮→关窗进托盘→退出无孤儿→量包体/启动耗时/增量更新下载量)
   → 管家瘦身 → Electron 壳 → 前端 → 安装/更新 → 发版 + 业主真机(A0 界面出来了吗)。

## 最危险的前提(我可能错在哪)

- **P1 electron-updater 就地覆盖 vs 我们 09-08 否掉就地覆盖的理由**(装到一半一半新一半旧、RMDir 删不掉静默跳过)。
  electron-builder 的 NSIS 在 --updated 下是先卸旧再装新;Python 进程攥着 .pyd 时会怎样?没量过。
- **P2 增量更新省不省**:NSIS 安装包是 LZMA 实心压缩,blockmap 对它的效果未知;164MB Python 运行时每次都算"变了"
  的话,每次更新下 ~120MB。
- **P3 旧版自动更新会不会自己去装新包**(上面第 5 条)—— 我认为会,且是最坏的那种失败(无人值守、半装)。
- **P4 手动装的路径**:旧安装器的卸载项叫 `OpenDesign`,electron-builder 用 appId GUID 做卸载键 ⇒ 两套卸载项并存?
  业主装到 D:\AI\OpenDesign 这类自选目录,新安装器默认目录不同 ⇒ 装到别处、老快捷方式/开机自启指向死路径?
- **P5 localStorage**:换 origin 存储(项目↔对话映射、自动更新开关)会丢;而 pywebview 默认 private_mode
  下现在可能本来就不持久 —— 未核实。
- **P6 Python 管家要不要其实并进 Electron**:少一个进程、少一层协议;代价是 Job 对象要 koffi 之类原生 ffi。
  我倾向留 Python,但这是我最可能被挑战的一条。
- **P7 本机 2G 内存 / 4G 盘**跑 electron + xvfb 的本地 e2e 不一定跑得动 ⇒ 大部分验证压在云 Windows 上。
