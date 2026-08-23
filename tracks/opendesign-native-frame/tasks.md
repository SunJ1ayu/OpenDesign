# Tasks: opendesign-native-frame

base-ref: eead395

## 0. 开工前必须先过的闸

- [x] **P0 探针(FAIL,见 evidence/p0-result.md):pythonnet 能不能覆写 `WndProc(ref Message m)`**
      —— design.md 未知 #1。**探针没绿之前不许写实现。**
      这一步需要一台 Windows;Linux 上无解。
- [x] **P1 探针 PASS(evidence/p1-result.md):改用 ctypes `SetWindowLongPtrW(GWLP_WNDPROC)` 经典子类化、绕开 pythonnet ⇒ 未知 #1 定案,方案 B 可行**
- [x] `track-record validate --phase dispatch`(**当前被权限拦住,欠**)
- [x] 双出:**没花 panel-explore**。P0/P1 两轮真机探针把最大的分叉(pythonnet 还是 ctypes)
      直接定案了 —— 那比任何模型意见都硬。premise attack 三份一手证据已落盘。

## 1. 判据先行(单独 commit,先红后绿)

- [x] s1 样式位常量对表 winuser.h(新增 `WS_CAPTION` / `WS_THICKFRAME`)
- [x] s2 `needed` 必须同时含 CAPTION + THICKFRAME;**去掉任一位必须红**
      (这条钉死 0.92 的错误规格,防止有人为"外观安全"又砍回去)
- [x] s3 `WM_NCCALCSIZE` 分支区分 wParam 真假,真分支改 rgrc 且置 Result=0
- [x] s4 新增 ctypes 调用点 argtypes **和** restype 都声明(继承既有判据)
- [x] s5 `show_window()` 不许对最大化窗口无条件 restore(D3 连带)
- [x] s6 结构闸:加了 CAPTION 就必须存在 NCCALCSIZE 处理(防中间态发版)
- [x] 红检:每条判据都要有能咬动它的变异

## 2. 实现(顺序不能换)

- [x] D1 样式位扩到五个(**不许单独发版**)
- [x] D2 `NativeWindow` 子类化 + `WM_NCCALCSIZE`(含最大化客户区修正)
- [x] D2b 日志:第一次真收到 NC 消息时打一行,不是挂载时打
- [x] D3 拆假最大化 → `WindowState.Maximized`;同步改 `_is_max` 与 `show_window()`
- [ ] D5 圆角/阴影不劣化(未知 #2)—— **代码没碰,留真机 C4 观察**
- [ ] D4 **真机确认系统拖拽正常之后**,再删自绘的 resize 热区(单独 commit)

## 3. 收口

- [x] 全量回归(用 venv 解释器,不是系统 python3)
- [x] 四审 panel-review(impact=standard ⇒ 预算 1,可加证据不可减)
- [x] bump 版本 + 打安装包 + 成品闸
- [ ] **真机清单:两台机器都要走**(公司 F: 那台若是 Win10,`wParam==0` 那条分支
      在 22000 以下要另处理 —— WinFormedge 专门打过补丁)

## 明确不做(继承 proposal 的 non-goals)

- 自绘动画、等 pywebview 7.0、改前端按钮外观、给 pywebview 提 PR


## 收口状态(2026-08-23 深夜)

- **代码面主裁 PASS**;产品面不给结论(证据边界,见 verify.md)。
- 安装包已打:`/root/aiwork/out/opendesign-0.93.0/OpenDesign-Setup-0.93.0.exe`
  (59.8 MB,7 条成品闸 0 不合格;安装包里的 ds_shell.py 与仓库逐字节一致)。
- 已 push(远端 `1d9680a` 回读确认);已发 pre-release `win-installer-0.93.0`
  (远端 digest 与本地 sha256 逐字节一致)。
- **暂不归档,等真机**。0.92 就是归档之后被真机证伪、只好另开一单;
  这次把 track 挂着,真机绿了再归档,红了直接在这一单里接着修。
