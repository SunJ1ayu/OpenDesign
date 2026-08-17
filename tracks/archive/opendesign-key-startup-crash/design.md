# Design: opendesign-key-startup-crash

## 一、为什么 0.88.0 那条崩溃能穿过所有防线

`bin/ds_shell.py:202` 读了一个重构后已经不存在的名字 `env`(应为 `envs["网关"]`)。
它躲过了:五段总跑、四审三腿、17 份收据。原因只有一个 ——

    那一行在 `if "网关" in plan["start"]:` 里面,
    而这个分支**只有"填过 key 的机器"才进得去**;判据机上没有 key.txt。

再叠上第二层:`bin/ds_shell.py` 的文件头写着「这一层没有任何自动考卷验得了」。
**那句话说得太满** —— 真正要 Windows 的只有 `main()` 里的 `import webview` 和托盘;
`start_backend()` 从头到尾只是读配置、拼 env、把两条腿交给 Supervisor。
把 Supervisor 换成替身,它在 Linux 上跑得好好的。洞就长在那句话下面。

⇒ 两道闸,一道堵形状、一道堵那句话:
- `tests/test_shipped_names.py`:零依赖(stdlib `symtable`)扫全部发货 py,
  问"每个被读的名字存不存在"。Python 只在**执行到**那一行才报 NameError ⇒
  行为判据够不着的分支里,拼错的名字可以一路绿着出厂。用 pyflakes 3.4.0 复核过,
  两者结论一致、零误报。**不引 pyflakes 当依赖**:装了包才跑的闸在没装的解释器上
  会整块 SKIP,而"没跑被印成绿"是本仓库栽过三次的假绿形态。
- `tests/test_ds_shell_startup.py`:替身 Supervisor + 真跑 `start_backend()`。

## 二、进程那三条(c18/c19/c20)

现场证据:网关日志最后一句 `Agent loop started`,**之后什么都没有**;同一份日志里
有两条完整 traceback ⇒ 它有能力打栈 ⇒ **不是 Python 崩的**。而外壳只说了
`[后台退出] ['网关']`,连退出码都没有 ⇒ 无法分辨"被杀"与"原生崩溃"。

- **c20 dead_reports()**:退出码 + 那条腿日志的尾巴。这是本单最重要的一条 ——
  它不修任何 bug,它修的是**我查不下去**。
- **c18 重启收整棵树**:`restart()` 以前只 `_terminate_tree`,而 Windows 上那只是
  `proc.terminate()`;收树靠关 Job(KILL_ON_JOB_CLOSE)。现在补上
  `_kill_tree` + `_close_job` + 关日志句柄,和 `shutdown()` 同一套。
  ⚠️ **这条 bug 在 Linux 上验不出来**(那边 `_terminate_tree` 打 killpg,孙子跟着走)。
  判据第一版正是这么写的、当场绿了 —— 已改成问机制。
- **c19 先除名再动手**:原顺序里旧腿"已经杀了、还挂在名册上",看门狗问过去会答
  "网关死了" ⇒ 弹「意外退出,请退出后重新打开」。窗口窄(<100ms),时间上对不上
  22:32:11 那次(差 26 秒)⇒ **不认它是根因**,但它是真的,顺手修掉。

## 三、无边框窗口

业主要求。查了 pywebview 5.4 源码(`platforms/winforms.py:235`)确认:
`frameless=True` → `FormBorderStyle.None`,**同时把 resizable 覆盖掉** ——
系统不再给 resize border。所以"自己接回四边四角"不是锦上添花,是必须的补偿。

做法选了**原生窗口消息**(`ReleaseCapture` + `SendMessage(WM_NCLBUTTONDOWN, 命中码)`),
不用"自己算坐标 move 窗口":后者会飘、掉帧、没有吸附。
经 `form.Invoke(Action(...))` marshal 回 UI 线程 —— `ReleaseCapture()` 只对调用它的
线程有效,在 js_api 的工作线程上做会**安静地不生效**(最难查的那一类)。

最大化用 `Screen.WorkingArea` 而非 `WindowState.Maximized`:无边框窗口用后者会盖住
任务栏。**已知偏差**:业主把窗口拖到屏幕顶边时是 Windows 自己发 SC_MAXIMIZE,
不经过我的代码 ⇒ 那一路仍会盖住任务栏。接受(修它要 hook WM_GETMINMAXINFO = 改窗口
过程,风险远大于收益),写进真机清单让业主看一眼。

判据只问机器答得了的:`test_shell_window.mjs`(8 条纯逻辑)+
`test_shell_window_contract.py`(跨语言对表:方向名 ↔ HIT 映射、前端叫的 api 方法名
Python 那边真有)。后者**变异验过**:改一个边名 / 把 close_window 写成 close,
两条都当场红。"按下去动不动"只有真机答得了。
