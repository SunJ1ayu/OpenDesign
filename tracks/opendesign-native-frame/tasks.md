# Tasks: opendesign-native-frame

base-ref: eead395

## 0. 开工前必须先过的闸

- [x] **P0 探针(FAIL,见 evidence/p0-result.md):pythonnet 能不能覆写 `WndProc(ref Message m)`**
      —— design.md 未知 #1。**探针没绿之前不许写实现。**
      这一步需要一台 Windows;Linux 上无解。
- [ ] `track-record validate --phase dispatch`(**当前被权限拦住,欠**)
- [ ] 双出 / panel-explore(`design-uncertainty: high`)——
      要问的第一个问题就是 P0 失败时的退路

## 1. 判据先行(单独 commit,先红后绿)

- [ ] s1 样式位常量对表 winuser.h(新增 `WS_CAPTION` / `WS_THICKFRAME`)
- [ ] s2 `needed` 必须同时含 CAPTION + THICKFRAME;**去掉任一位必须红**
      (这条钉死 0.92 的错误规格,防止有人为"外观安全"又砍回去)
- [ ] s3 `WM_NCCALCSIZE` 分支区分 wParam 真假,真分支改 rgrc 且置 Result=0
- [ ] s4 新增 ctypes 调用点 argtypes **和** restype 都声明(继承既有判据)
- [ ] s5 `show_window()` 不许对最大化窗口无条件 restore(D3 连带)
- [ ] s6 结构闸:加了 CAPTION 就必须存在 NCCALCSIZE 处理(防中间态发版)
- [ ] 红检:每条判据都要有能咬动它的变异

## 2. 实现(顺序不能换)

- [ ] D1 样式位扩到五个(**不许单独发版**)
- [ ] D2 `NativeWindow` 子类化 + `WM_NCCALCSIZE`(含最大化客户区修正)
- [ ] D2b 日志:第一次真收到 NC 消息时打一行,不是挂载时打
- [ ] D3 拆假最大化 → `WindowState.Maximized`;同步改 `_is_max` 与 `show_window()`
- [ ] D5 圆角/阴影不劣化(未知 #2)
- [ ] D4 **真机确认系统拖拽正常之后**,再删自绘的 resize 热区(单独 commit)

## 3. 收口

- [ ] 全量回归(用 venv 解释器,不是系统 python3)
- [ ] 四审 panel-review(impact=standard ⇒ 预算 1,可加证据不可减)
- [ ] bump 版本 + 打安装包 + 成品闸
- [ ] **真机清单:两台机器都要走**(公司 F: 那台若是 Win10,`wParam==0` 那条分支
      在 22000 以下要另处理 —— WinFormedge 专门打过补丁)

## 明确不做(继承 proposal 的 non-goals)

- 自绘动画、等 pywebview 7.0、改前端按钮外观、给 pywebview 提 PR
