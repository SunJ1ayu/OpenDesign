# Design: opendesign-instant-ui

- Change: opendesign-instant-ui
- Status: draft

> 实施前按 panel skill **4c** 检查目标到方案的翻译。只有一种方案、自报 low、Jev 低分都不免检;
> 新增关键行为/改变契约/难撤回的方案先做不同家族挑战,关键未知先实验,方向分叉才扩大探索。
> 主 agent 先落自己的方向,但独立腿不读本轮自审或同伴报告。局部可逆、契约已验证的修改可简写。

## Goal-to-design check

- 当前行为 → 拟改变的行为:业主「为什么启动都会有一个正在启动,zcode好像没有这个吧」→「直接学吧」。
  事实:窗口 +317ms 出现,整页「正在启动」到 +3846ms 才换成工作台(run 35750584881 E2.window/E2.ui,见 release-0989 evidence);
  页面由 ds-web 发,窗口要等管家 `ready`(= 网关 + ds-web 都就绪,`bin/ds_shell.py start_backend`、`bin/ds_host.py:136-138`)。
  拟改:窗口第一个页面就是工作台(带 `?shell=1`、窗口按钮),后台没好时数据区「连接中」,好了自动补上,不整页重载。
- 检查深度与触发事实:改变默认启动路径 + 页面源站(跨模块契约:Electron ↔ ds-web 同源/安全检查、localStorage、导航策略)⇒
  4c 第三行:不同家族独立挑战(已做)+ 关键未知最小实验(云 Windows 探针)。
- 关键前提:见下「前提与核实」。
- 完全实现仍可能失败:①有 key 时网关冷启动可能很久,数据区长时间「连接中」—— 框架虽出来,业主仍在等(本单不承诺后台变快,要在界面里说清在等什么);
  ②挂载时只拉一次的页面(项目/待办/key/同意闸)若在就绪前失败就钉死红字;③首帧上报在管家 stdin 可写前丢失 ⇒ 90s 首帧看门写假诊断;
  ④源站换了 ⇒ localStorage(项目→对话映射、图库列数、侧栏折叠)丢一次。
- 独立意见与核实:见下节。
- 未解决项:P6/P10(app:// 直连 ws、存储持久)等云探针;探针红则改走挑战腿的「回环 http 静态服务」方向。

## 方向(主裁,派挑战腿前已落盘于仓外 `/root/aiwork/tasks/opendesign-instant-ui-my-direction.md` [仓外不承重])

Electron 注册特权协议 `app://opendesign/`,`protocol.handle`:非 /api 从包内 `resources/ds/web/dist` 读(SPA 兜底 index.html);
`/api/*` **挂起到后台就绪**再 `net.fetch` 转给 `http://127.0.0.1:<web_port>`(去掉 Origin/Sec-Fetch-*,ds-web 视为本机非浏览器调用,白名单一行不改)。
窗口创建即 `loadURL("app://opendesign/?shell=1")`,`ready` 只 resolve 就绪 + 核版本,不再 loadWorkbench。聊天 ws 仍直连 127.0.0.1:8765。

## 独立挑战(xai / Cursor grok-4.7-high,`/root/aiwork/logs/panel-opendesign-instant-ui-challenge-20260923-1236.subcursor.grok-4.7-high.log` [仓外不承重])

| 挑战要点 | 核实 | 取舍 |
|---|---|---|
| 字面 `loadFile` 不行:dist 用根路径 `/assets/...`,file:// 下全白;API 相对路径到不了后台 | 成立(`web/dist/index.html:7-8`,`web/src/api.ts`) | 本来就不走 loadFile;app:// 标准 scheme 下根路径与相对 /api 都成立(探针 P0/P1/P8) |
| `?shell=1` 只在首个地址读一次,`WindowChrome` 定死 | 成立(`web/src/shellWindow.ts`、`WindowChrome.tsx` useState) | 首个地址就带 `?shell=1` |
| 项目/待办/key/同意闸只挂载时拉一次,失败钉死 | 成立(`App.tsx:226` 等) | 我的方向是**挂起**而非 503:就绪前请求不失败,只是晚到 ⇒ 不必给每页加重试;另加全局「正在连接后台…」横条(IPC 后台状态) |
| ready = 网关+ds-web 都好,有 key 时可能很久 | 成立(`ds_shell.start_backend` 顺序) | 挂起无上限会让页面长时间转圈 ⇒ 横条要说「正在启动助手/后台」;后台真死走 fatal/backend-died 弹框(不变)。**不改启动顺序**(非目标) |
| 首帧上报在管家 stdin 可写前被丢 ⇒ 假首帧诊断 | 成立(`desktop/main.js sendHost` 在 host 未起时 return) | 本单修:管家起来前先攒着 |
| navPolicy 的 origin 要等 ready,空 origin 把站内当外链 | 成立(`controller.js` ready 分支才设 origin) | 创建窗口即设为 app://opendesign |
| 反方向:主进程开回环 http 静态服务(源站仍是 http://127.0.0.1) | 可行;代价:多一个回环端口 = 多一个本机攻击面、要复刻 Host/同站检查;端口被占时源站会变 ⇒ localStorage 每次可能丢 | 暂不选;作为探针红时的备选 |
| ws 端口写死 8765,被挤会连错 | 成立,但现状问题、非本单引入 | 延期,不扩大范围 |

## 前提与核实(最小实验:云 Windows 探针 `spike/probe/`,判读规则先写死在 `check.mjs`)

P1 挂起到就绪 / P2 后台看到的头 / P3 5MB 上传流式代理 / P4 JSON POST / P5 图片 / P6 app:// 页面直连 ws://127.0.0.1 /
P7 系统代理指向死端口时回环照通 / P8 深链兜底 / P9-P10 localStorage 写入并跨重启持久。

**结果(run 35820084450,真 Windows,Electron 44.4.3):10 OK / 1 FAIL。** P0/P1(挂起 2888ms 后返回)/P3(5242880 字节到齐)/P4/P5/P6(`echo:hi`)/P7/P8/P9/P10(`written-run1`)全过。
P2 红:后台看到 `Sec-Fetch-Site: none`(net.fetch 自己加的,删不掉)。**判读规则比真实契约严** —— ds-web `_same_site_ok`
(`bin/ds_web.py:2500`)对 `none` 放行、无 Origin 放行 ⇒ 前提「ds-web 把代理请求当本机非浏览器调用」成立。
认账:这是我写的判读规则错,不是改考卷 —— 规则问的是「会不会被 403」,真正该比的是 `_same_site_ok` 的放行集合。
(第一跑 run 35819783664 是探针工作流没取到 Electron 二进制,量具坏、未产出任何判读。)
⇒ **方向定为 app:// 协议;回环 http 备选不用。** 初版首跑 P8 的 SPA 兜底不采用:ds-web `_static` 本来就不回落(工作台是 `#/` 路由),照它。

## Approach

- `desktop/lib/appProtocol.js`(不 require electron,Linux 可测):`APP_ORIGIN/APP_URL`、`createAppHandler({distRoot, readFile, backendPort, fetch, log})`。
  静态规则照抄 ds-web `_static`(`\\`/NUL 拒、realpath 不出 dist、类型表、入口 no-cache、资源 immutable、nosniff);只认主机 `opendesign`;
  `/api/` 前缀挂起到 `backendPort()` 再转发,去 Origin/Referer/Sec-Fetch-*,流体 duplex=half,连不上 502 JSON。
- `desktop/lib/hostSender.js`:管家起来之前的命令先攒(上限 200),attach 后按序补发。
- 控制器:`ready` → 版本核对 → `deps.backendReady(port)` + `pushBackendState({phase:"ready"})`;不再 loadWorkbench;导航源站固定 app://opendesign。
- main.js:顶层 registerSchemesAsPrivileged;whenReady 里 protocol.handle;createWindow 直接 `loadURL(APP_URL)`;删 loading.html。
- 前端:`web/src/backendState.ts backendBanner()`、`desktopShell.ts backendApi()`(旧 preload 无 backend 也认外壳);App 顶部 `data-ui="backend-connecting"` 横幅。

## Key trade-offs / risks

- <关键取舍与风险>

## Alternatives considered

- <考虑过但没选的方向 + 为什么没选>

## Test strategy (oracle)

- 本地:`tests/test_desktop_instant.mjs`(a1~a11 协议处理、n1 导航、hs1~3 管家通道、bs1~3 控制器、fb1~2 前端、s1~s4 接线);
  改写旧判据:`test_desktop_controller.mjs` mc2b/mc2c/mc3/mc4/mc9/mc19(ready 不再换页)、`test_desktop_main.mjs` m21(地址换 app://)。
- 云 Windows(`e2-drive.mjs`):E2.instant(首个地址 = app://opendesign/?shell=1;窗口栏先于后台就绪)、E2.connecting(那一刻横幅可见)、
  E2.noreload(就绪后横幅消失、全程只 1 次导航、没钉死「读不到项目列表」);E2.nav 改前缀比(Node 对 app:// 的 origin 恒为 "null")。

**这个 oracle 能被什么骗过?**

- 云上 CI 没有 key ⇒ 网关不起,后台就绪只 ~3.5s;业主有 key 时网关可能久得多,横幅要挂更久 —— 云上量不到「很久」时界面是否仍可用,
  只能靠真机(T5 真机清单里写明:有 key 冷启动,看横幅文字与各页是否只转圈不报错)。
- E2.instant 比的是「窗口栏先于后台」,若某次 CI 后台异常快会假红 —— 红了先看数字,不许放宽判读。
- 各页「挂着」期间显示什么由各页现有 loading 态决定;判据只保证不钉死红字,不保证每页都有好看的加载态(截图人工看一眼)。
