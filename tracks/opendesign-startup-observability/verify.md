# Verify: 启动可观测性(第一刀)

- Date: 2026-08-30

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录
> `decision.json`;这里保留检查、理由、发现与主 Agent 仲裁说明,不复制枚举。

## Mechanical checks

- [x] 判据先行,先红后绿(红收据 3 份、绿收据 2 份,见下)
- [x] 红检 `tests/mutation-startup-diag.sh`:**咬 18 漏 0**
- [x] e2e `startup_report.e2e.mjs`:全部通过,**且用控制变异证明它不是恒真的**
- [x] 全量回归:1357 项 rc=0
- [x] no secrets / unsafe ops(不碰网络、不加对外出口 —— 业主 08-30 定"先做 C")
- [x] 四审 panel-review(impact=high ⇒ 预算 2,实派 3 腿)—— **孤腿 BLOCK,已全修**
- [ ] Windows CI 端到端 —— 未跑
- [ ] 业主真机 —— 只有他答得了

## 机器打印的收据(逐字节,别改数)

判据先红:
```
runlog: python rc=1 commit=95369a9 dirty=yes at=2026-08-30T07:38:48Z file=tracks/opendesign-startup-observability/evidence/20260830T073848Z-01-python.txt
runlog: python rc=1 commit=95369a9 dirty=yes at=2026-08-30T07:39:33Z file=tracks/opendesign-startup-observability/evidence/20260830T073933Z-01-python.txt
runlog: python rc=1 commit=95369a9 dirty=yes at=2026-08-30T07:40:01Z file=tracks/opendesign-startup-observability/evidence/20260830T074001Z-01-python.txt
```
转绿:
```
runlog: python rc=1 commit=95369a9 dirty=yes at=2026-08-30T07:41:14Z file=tracks/opendesign-startup-observability/evidence/20260830T074114Z-01-python.txt
runlog: python rc=0 commit=95369a9 dirty=yes at=2026-08-30T07:41:40Z file=tracks/opendesign-startup-observability/evidence/20260830T074140Z-01-python.txt
```
红检与总跑:
```
runlog: mutation-startup-diag rc=1 commit=4f9db1d dirty=yes at=2026-08-30T08:10:01Z file=tracks/opendesign-startup-observability/evidence/20260830T081001Z-01-mutation-startup-diag.txt
runlog: run-all rc=1 commit=6a6cf47 dirty=no at=2026-08-30T08:11:42Z file=tracks/opendesign-startup-observability/evidence/20260830T081142Z-01-run-all.txt
```

**run-all 那份是红的,原因说清楚**:6 段里 5 段 PASS,唯一红的是 e2e 总跑
(4 PASS / 32 FAIL / 2 SKIP)。真因 `Cannot find module 'playwright-core'` ——
这台机器上 e2e 的 playwright 依赖没了(helpers.mjs 从一个**写死的 npx 缓存路径**加载,
那个缓存被清了)。与本单无关,已单独用 `E2E_PW_MODULES` 指到别处真跑过。
**不擅自装依赖**;这是一笔该单独开单的账。

## 空壳红检:哪些断言是"守卫型"

用一个什么都不干的空实现跑判据,**4 条仍然绿**(s5b/s8b/s9/s12)——
它们禁止某事发生,空实现当然满足 ⇒ **只能靠变异证明有用**。
变异 M7/M12/M13/M15 逐条覆盖,**全部咬住**。
我事先预判 3 条、实际 4 条:量比猜准。

## Review(主 agent 自审 —— **在读任何腿的输出之前落盘**)

### 我自己抓到的、并且已修的

1. **🔴 前端首帧判定是错的,而且正是"每次开机都误报"那个形态。**
   第一版 `reportFirstFrame()` 在 `render()` 之后同步等两帧就下结论,而 React 18 的
   `createRoot().render()` 是**异步**的 ⇒ 健康启动可能被判成"根节点尺寸异常"、
   且永不报 `frame_submitted` ⇒ 外壳的首帧看门每次都写诊断。
   已改成在帧预算内轮询(240 帧 ≈ 4s)。
   **诚实标注:这条修复在本机 e2e 里咬不动**(把预算退回 1 帧仍全绿 ——
   这台 Linux 上 React 提交比第一帧还快)。它只在慢机器上才现形 ⇒
   **属于防御性修复,不是被判据逼出来的**,别在文档里写成"已验证必要"。

2. **🔴 诊断快照差点偷走看门狗的证据。** 原本要调 `sup.poll_dead()`,
   读实现才发现它内部走 `take_dead()`、是**破坏性**的 ⇒ 后台崩溃时业主会看到
   "XX 退出了"但**原因是空的**(08-17 判据 c21 治的正是这形状)。改成只读。

3. **想当然引用了不存在的 `open_folder`。** 本项目为"打开文件夹"有过三种写法、
   已统一到 `ds_openfolder` ⇒ 改为复用它,不造第四种。

### 我自己造出来的假绿(记下来,比结论值钱)

4. **追加判据时写在了 `unittest.main()` 后面** ⇒ 新类没被收集,屏幕照印 `OK`。
   唯一线索是"14 条"这个数字没涨。
5. **红检时把 `npm run build` 输出重定向到 /dev/null** ⇒ 构建失败被吞掉,
   e2e 跑的是**旧包**,于是我得出"控制变异没咬住"的**错误结论**并已写给业主一次。
   换成能编过的变异后,e2e 当场红成 0 事件 —— **它是咬得动的**。
   ⇒ 教训:**量具的输出不许静音**;顺带发现 **单跑 e2e 不检查 dist 新鲜度**
   (总跑里有那道闸,单跑没有)⇒ 这是一笔该开单的账。
6. **判据自己少 import / 引用了不存在的 `shell.VERSION` / 变异锚点串味**
   (`except Exception: return False` 在 ds_shell.py 第一处出现在 103 行,
   我的 M18 打到了完全不相干的函数上)。三处都在红检里现形并修掉。

### 已知的取舍与仍敞着的

7. **`manifest()` 会 `import ds_web`** 只为拿版本号(唯一来源)。代价是外壳进程多一次
   import ⇒ **观测本身给启动加了一点点时间**。选它是因为抄一份版本号会过期,
   本项目栽过。量到再说,不预先优化。
8. **导出的诊断 zip 落在 app 目录里,反复导出会堆积。** 本单不做清理。
9. **`FIRST_FRAME_TIMEOUT = 90s` 没有依据。** 已知唯一硬数据是云端冷启虚机 20~40 秒,
   业主机器上从没量过。**正因为不弹框,这个数字不承重** —— 拿到他第一份诊断包再谈收紧。
10. **前端上报链在真 Windows + 真 WebView2 下没验过。** 本机 e2e 用的是 chromium +
    自造的假桥。真桥(pywebview 注入)只有 Windows CI / 真机答得了。

## Panel(2026-08-30)

花名册(机器写的,别手抄):
```
# impact-risk=high requested-budget=2 selected-count=3
# selected=submimo(xiaomi),subdeepseek(deepseek),subgemini(google)
# escalation=incomplete   snapshot=head:cb1e53d
submimo=PASS(verdict=UNKNOWN) subdeepseek=PASS(verdict=BLOCK) subglm=SKIP(rotation) subkimi=SKIP(rotation) subgemini=PASS(verdict=PASS)
```

### 🔴 先记我自己造的账:反锚定作废

**两条判 PASS 的腿都在读我的 verify.md。** 证据:subgemini 提到"第一版两帧即判"
(该信息**只**存在于我的工件与 commit,现有代码里看不出来);submimo 直接引用
`verify.md:60-62`。它们列的"已知取舍"四条与我 verify 第 7~10 条一一对应,
**没有一条是我没写过的**。

根因是我把顺序做反了:panel skill 写明「正确节奏是先派发、后写 verify.md」,
而我先写完 verify.md 并提交了才派发。`git checkout` 堵不住这条 ——
底座腿自己读仓库,**文件在树上就够得着**。
⇒ **这两条 PASS 的证据价值按接近零计。** 下一单必须先派发后落工件。

### 逐条对账(孤腿 subdeepseek 的 BLOCK)

| # | 它说的 | 我的核实 | 处置 |
|---|---|---|---|
| F1 HIGH | `web_ready_probe` 走 urlopen ⇒ 不绕系统代理 ⇒ 配代理的机器上健康服务被判未就绪 ⇒ 死等 60s ⇒ StartupFailed ⇒ **软件打不开** | **亲手复现**:设 `http_proxy` 后对健康服务返回 False,裸 socket 对照组正常;`proxy_bypass('127.0.0.1')` 确为 False。**业主本机跑 VPN(Clash 类会设系统代理)⇒ 很可能正中他** | **接受,已修**(空 ProxyHandler);判据 s13 + 变异 M19 |
| F2 MED | 首帧看门无幂等闸,托盘还原再发 Shown ⇒ 必然超时 ⇒ 假诊断 | 读码属实:`start_first_frame_watch` 挂在 `events.shown`、无护栏;且 `report_from_ui` 按进程去重会丢掉重报 | **接受,已修**(只上一次膛);s14 + M20 |
| F3 MED | 白名单只到文件级,`工作台.log` 请求行带项目名/文件名 | 属实。**而我 08-30 亲口对业主说过"包里不会有项目档案、客户资料" ⇒ 那是半真话** | **接受,已修**(请求行只留前两段路径,端点形状与状态码留住);s16 + M22 |
| F6 LOW | `report_startup → note_first_frame → seen()` 无判据 | 属实,且违反本单自己的"接线要钉死"标准(s6/s11 都做了) | **接受,已补** s15 + M21 |
| F4 LOW | 去重按事件名一次性 ⇒ 先发合法事件可压掉真事件 | 属实,但前提是页面已被攻破;本地单用户、口子只对本窗口 | **接受意见、不动作**,记为已知取舍 |
| — | `begin_resize` 日志拼未截断网页字符串 | 属实,但**不在本单 diff 内** | 记入 backlog,不混进本单 |

**它没说、但我自己记着的**:F1 那条正是本单设计里"观测层绝不能成为新的故障源"
这条红线的字面违反 —— **而红线是我自己写的**。19 条判据在 Linux 上全绿,
对"探针走不走代理"零覆盖,这是本单最大盲区,已由 s13 补上。

### 裁决(主 agent,唯一仲裁者)

**代码面 PASS。** 依据是我自己的复核与 22 条变异全咬,不是腿的票数 ——
两条 PASS 腿的独立性已作废,不计入证据。
**产品面不给结论**:真 Windows + 真 WebView2 下的前端上报链、以及 F1 修复在
真代理机器上的效果,只有 CI / 真机答得了。

## 最终收据(**最后一次编辑之后那一遍**,干净树)

```
runlog: run-all rc=1 commit=fb9398e dirty=no at=2026-08-30T08:54:28Z file=tracks/opendesign-startup-observability/evidence/20260830T085428Z-01-run-all.txt
```
六段:5 PASS,唯一红的是 e2e 总跑 **36 PASS / 1 FAIL / 2 SKIP**。
那一条是 `stage_timer.e2e.mjs`,**已证死与本单无关**:在本单开工前的提交
`d0840c1` 上单独跑,同样 4 FAIL(`connect-modal-mask` 挡住点击 = 既有的
"e2e 悄悄依赖活网关"那笔账)。**是量出来的,不是推的。**

> 另记:本机 e2e 的 playwright 依赖来自一个**写死的 npx 缓存路径**,那个缓存已被清空
> ⇒ 直接跑总跑时 32 条全红。用 `E2E_PW_MODULES` 指到别处才跑得起来。**该单独开一单。**

## 端到端:云 Windows 机器装 0.98.1(2026-08-30,run 33304106398)

静默装 rc=0/47s;`/api/health` **自报 version=0.98.1**(运行中的目标回显版本,
满足本机"部署要在使用现场验证"那条规矩);**亲眼看图确认**界面完整
(`evidence/20260830-云机器-0.98.1-界面-39s.png`:左栏 + 填 key 弹窗 = 全新机器该有的样子)。

### 🎯 第一次拿到真实的启动时间线(这就是这一单的目的)

逐字抄自 `evidence/20260830-云机器-0.98.1-外壳.log`:

```
09:29:11 版本清单 OpenDesign=0.98.1 Windows=Windows-2025Server-10.0.26100-SP0
         位数=64 Python=3.12.10 WebView2=151.0.4129.101
 +9422ms lock.acquired
+10000ms backend.ready
+10234ms window.create_returned
+10234ms webview.loop_entered
+18718ms window.shown
+24765ms frontend.bundle_started / frame_submitted 1028x709 / react_committed
```

**四条一手结论(以前一条都答不出来):**

1. **到界面出来 24.8 秒。**
2. **最大的一块是开头那 9.4 秒** —— 进程起来到拿到单实例锁,期间只有 Python 启动和
   import。**这是全程最大的单块,而我们此前完全不知道它存在。**
3. 后端就绪只花 0.6 秒(9.4→10.0)—— **"后端慢"这个假设当场被证伪。**
4. `webview.start()` 到窗口真显示 **8.5 秒**(10.2→18.7),再到前端首帧又 **6.0 秒**。

**WebView2 版本第一次被记下来了**:`151.0.4129.101`。08-25 白屏那晚要的正是这个数,
当时只能靠业主去翻文件夹。

### 🔴 真实数据当场暴露的一个新缺陷(判据看不见)

三条前端事件**全部落在同一个 +24765ms 上,而且顺序是乱的**
(`bundle_started → frame_submitted → react_committed`,react 明明该在 frame 之前)。

根因:前端事件在桥没到位时**缓存在内存里**,等 `pywebviewready` 才一次性补发;
时间戳是**外壳收到的那一刻**打的,不是浏览器里真正发生的时刻。
而同一批补发是并发 promise,到达顺序不保证。

⇒ **"网页这一层内部慢在哪"仍然答不出来** —— 只知道整段 6 秒。
本单交付的分辨率到 `window.shown → 首帧` 为止,再往里是黑的。
**修法是前端自己带上时间戳**(它有 `performance.now()`),不是外壳这边猜。
⇒ 记为本单**已知缺陷**,进第三刀(或单独开单)。**不在本单补,免得又一次实验两个变量。**

> 这一条只有真机数据看得出来:19 条判据 + 22 条变异 + e2e 全绿,一条都没提示过它。
> **"判据全绿但答不出业主的问题"的活标本。**

---

# 0.98.2:白屏真因之一(2026-08-30 傍晚)

## 由来:业主一句话挡下了一个假结论

原话:「但是你确定 windows 的测试你能看到吗,你的机子是 linux github 的云 windows
你不一定看得全是不是」。

我本来打算拿 0.98.1 那次 CI 绿灯当"Windows 上验过了"写进结论。去查才发现探针
**只收 `外壳.log` 一份**、**从不做任何交互**、**机器上没有系统代理** ——
也就是说:我改的时间戳有一半没验、主打功能(托盘导出)一次没跑、
而**最要命的代理修复恰恰是在一台没有代理的机器上"验证"的**。
⇒ 又一次"我说'实测过',测的却不是我要保证的那件事",被业主挡下。

## 补探针 ⇒ 当场撞出一次真白屏 ⇒ 抓到机制

带 `HTTP_PROXY` 再启动一次(0.98.1),截图 **颜色 3 种 / 近白 98.9%** = 整片空白,
而同一次的日志:

```
+11359ms frontend.frame_submitted 1028x749      ← 界面确实画出来过
+11359ms frontend.error Uncaught TypeError: c.window_state is not a function
```

**完整机制**(本机 e2e `api_partial_injection.e2e.mjs` 也复现得出来,root 子节点=0):

1. pywebview **分步**注入 api ⇒ 存在"对象在了、方法还没挂上"的一瞬;
2. `WindowChrome.tsx:62` 的 `api()?.window_state()` —— `?.` 只挡"对象是空的",
   于是变成 `undefined()`:**同步抛**,后面的 `.catch` 接不到;
3. 异常在 `useEffect` 里冒上去,而**全仓没有任何 ErrorBoundary**
   ⇒ React 18 卸载整棵树 ⇒ **整页白**。

**这条路一直都在,以前完全隐形** —— 没有前端错误上报时,它就只是
"打开全是白的,没有任何线索"。**0.98.1 发出去几小时,它自己带的报警器把它照出来了。**
这是本项目栽的**第四次**"注入时机"(0.89/0.90/0.91 各一次)。

> ⚠️ **不敢说这就是 08-25 那次的根因**(那次还有 WebView2 换版的嫌疑,见
> `[[opendesign-white-screen-webview2]]`)。它是**一条被真机复现、机制完整的**白屏路径。

## 它顺带照出我自己的洞

`frame_submitted` 原来只查根节点**有没有尺寸** —— 而树被卸载后 `#root` 还在、尺寸照旧
⇒ **成功信号会撒谎**。真机那句 `1028x749` 正是"报了成功、屏幕是空的"。已加"必须有子节点"。

## 0.98.2 端到端(run 33306843034):前后对比很干净

| 探针步骤 | 0.98.1 | **0.98.2** |
|---|---|---|
| 带系统代理启动 | 颜色 **3** 种 / 近白 **98.9%**(空白) | 颜色 **50** 种 / 近白 **38.7%**(健康) |
| 三份日志 | (0.98.1 起才收全)外壳 1001B / 工作台 2794B / 网关缺席 | 外壳 1187B / 工作台 2794B / 网关缺席 |
| 托盘导出诊断 | 路径写错,没跑成 | **真跑成了**,见 `evidence/20260830-0.98.2-真Windows生成的诊断包.zip` |

诊断包在**真 Windows** 上生成:`['本次启动.txt', 'Logs/外壳.log', 'Logs/工作台.log']`,
中文文件名正常。**涂抹实测生效**:原始日志 27 条三段以上路径,包里 **0 条漏网**。

## 🔴 涂抹的残留(不许再说半真话)

包里第一行含 `DS_DATA_ROOT=C:\Users\<用户名>\AppData\Local\OpenDesign\Data`
—— **Windows 用户名会跟着包走**。涂抹只覆盖 HTTP 请求行,不覆盖其它内容。
不是项目名/客户名,但**"包里完全没有个人信息"这句话不成立**。已当面告知业主。

## 冷热对比(顺带量到的)

| | 第一次(冷) | 第三次(热) |
|---|---|---|
| 到 lock.acquired | 9.4s | **9.2s** |
| 到界面出来 | 24.8s | 11.4s |

⇒ **我"9 秒是杀毒扫新文件"的猜测不成立** —— 热启动它一点没少。
后半段(内核初始化 + 网页加载)15s→2s 确实是缓存效应;
**开头那 9 秒是结构性的,每次都付。** 这是我今天第二次被数据纠正。

## 仍然敞着(下一单)

**全仓没有 ErrorBoundary。** 这次只堵了**一处**会抛的地方,而
"任何一处 JS 异常都能把整页打没"这个结构问题还在。
**它是产品决策**(炸了之后给业主看什么:一句人话?一个重试按钮?)⇒ 单独开单,不混进本单。
