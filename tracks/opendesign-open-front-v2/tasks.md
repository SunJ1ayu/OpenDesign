# Tasks: opendesign-open-front-v2

- base-ref: afea90a

## Oracle(先行,已红检 7 条)

- [x] `ActivateEscalation` a01/a02/a03 —— 够用不升级 / 升级必成对解绑 / 拒绝时不谎报
- [x] `FocusDiagnostics` d01–d04 —— 命中、未命中(带 seen 标题)、异常、假成功

## 实现

- [x] `_win_activate`:注入 user32/kernel32,温和档→升级档,以 GetForegroundWindow 判定真伪
- [x] `_win_focus_folder`:`log=` 注入,三种结局各落一行 `[open-front] …`(默认写 stderr)
- [x] 旧判据 f01 随规格更新(假激活器要显式返回真值 —— 返回值语义变了)
- [x] 版本号 0.45.0

## 收货

- [x] oracle 26/26、`pytest tests/` 604 passed、build 绿
- [ ] **真机**:用户更新后点一次「打开文件夹」,看 `dsweb.err.log` 里的 `[open-front]` 行
      —— 这一行决定下一步是"抢焦点被拒"还是"根本没找到窗口"
