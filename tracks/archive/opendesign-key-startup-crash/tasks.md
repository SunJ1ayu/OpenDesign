# Tasks: opendesign-key-startup-crash

- [x] 判据先行:`test_shipped_names.py` + `test_ds_shell_startup.py`(红检 rc=1)
- [x] 修 `bin/ds_shell.py:202` 的 NameError(绿检 rc=0)
- [x] 判据先行:c18/c19/c20(红检 rc=1,三条全红)
- [x] 修 `restart()` 收树 / 先除名 / `dead_reports()` + 外壳看门狗接上(w6)
- [x] 无边框窗口:`WindowApi` + `WindowChrome.tsx` + CSS + 两道判据(含变异验证)
- [x] 品牌名去掉那个点(连它专用的 CSS 一起删)
- [x] bump 0.89.0
- [x] 总跑五段:0 红(2 条要活 gateway 的 e2e 没跑,认账见 verify.md)
- [x] full 四审**第一轮**(13 条发现,逐条落地)
- [x] full 四审**第二轮**(在最终代码上重跑;subkimi BLOCK 成立,F-1 是真 bug)
- [x] 判据修判据 + 修 F-1/F-2/F-3/F-4/F-6/D-3/D-4/D-5(`eb3bb4d` / `36aefe8`)
- [x] 变异重跑:窗口 8 咬 0 漏、core 15 咬 0 漏
- [x] 总跑五段(在最终代码上再跑一遍):0 红,python 1268,e2e 35/0/2SKIP,rc=3
- [x] **重**编安装器 `OpenDesign-Setup-0.89.0.exe` —— ⚠️ 08-16 那份编在会话临时目录里、
      而且比这两轮修复**旧**,已作废重编(23 条静态闸 + 7 条成品闸全过,59.7 MB)
- [x] 亲自核对包里装的是**修完之后**的前端:
      `.win-btns{position:fixed;top:0;right:0;height:30px;z-index:220}` 在 exe 的 CSS 里
- [x] 发布 pre-release `win-installer-0.89.0`(回读远端:asset 已 uploaded)
- [x] push(`4abb02e`,已 fetch 回读确认)
- [ ] **业主真机走一趟**(`真机清单-0.89.0.md`,A~G 七组)← 只有他做得了
- [x] 归档

> ⚠️ 08-16 那版 tasks.md 上「full 四审」和「编安装器」两个勾是**提前打的**
> (打勾时 panel 才跑了 3 分钟、subkimi 被断线砍成半截)。已作废重来。
> **教训:勾是给下一个接手的人看的收据,不是给自己的进度条。**

## 👉 下次接手先读这里

**22:32:11 那次网关无声死亡,至今没有根因。** 这一版没有修它,修的是"下次查得动"
(`dead_reports()` 会打退出码 + 日志尾巴)。业主再遇到同样的弹窗时,
**先要 `外壳.log`** —— 里面现在有退出码。别再从"它为什么死"开始猜。
