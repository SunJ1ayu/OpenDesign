# Tasks: opendesign-key-startup-crash

- [x] 判据先行:`test_shipped_names.py` + `test_ds_shell_startup.py`(红检 rc=1)
- [x] 修 `bin/ds_shell.py:202` 的 NameError(绿检 rc=0)
- [x] 判据先行:c18/c19/c20(红检 rc=1,三条全红)
- [x] 修 `restart()` 收树 / 先除名 / `dead_reports()` + 外壳看门狗接上(w6)
- [x] 无边框窗口:`WindowApi` + `WindowChrome.tsx` + CSS + 两道判据(含变异验证)
- [x] 品牌名去掉那个点(连它专用的 CSS 一起删)
- [x] bump 0.89.0
- [x] 总跑五段:0 红(2 条要活 gateway 的 e2e 没跑,认账见 verify.md)
- [x] 编安装器 `OpenDesign-Setup-0.89.0.exe`(rc=0,23 条安装器闸全过)
- [x] full 四审
- [ ] **业主真机走一趟**(`真机清单-0.89.0.md`,A~F 六组)← 只有他做得了
- [ ] 归档 + push

## 👉 下次接手先读这里

**22:32:11 那次网关无声死亡,至今没有根因。** 这一版没有修它,修的是"下次查得动"
(`dead_reports()` 会打退出码 + 日志尾巴)。业主再遇到同样的弹窗时,
**先要 `外壳.log`** —— 里面现在有退出码。别再从"它为什么死"开始猜。
