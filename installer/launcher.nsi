; OpenDesign 启动器 —— 业主每天双击的就是这个 exe。
;
; 它不是安装器,只是一个**带自己图标的壳**:确认包是完整的,然后把真正的外壳
; (python\pythonw.exe + ds\bin\ds_shell.py)拉起来,自己立刻退出。
;
; 为什么要有它,而不是让快捷方式直接指 pythonw.exe:
;   · 快捷方式和任务管理器里得是 "OpenDesign" 而不是 "pythonw",
;     图标得是我们自己的(exe 的图标只能编进 exe 里,快捷方式改不了进程的身份);
;   · 开机自启那条注册表值要指一个稳定的东西,将来换启动方式只改这一个文件;
;   · 包被装坏时(杀软吃掉了 python\)业主得看到一句中文,而不是双击没反应。
;
; 用 NSIS 编它是顺手:安装器本来就用 NSIS,不必为一个 40KB 的壳再引一条工具链。
; `SilentInstall silent` = 编出来的 exe 不显示任何安装界面,直接跑 Section。
;
; 判据:installer/check-installer.py 的 L1~L6。

Unicode true

!define APP "OpenDesign"

Name "${APP}"
OutFile "OpenDesign.exe"
Icon "opendesign.ico"
SilentInstall silent
RequestExecutionLevel user

VIProductVersion "${APPVER}.0"
VIAddVersionKey "ProductName"     "${APP}"
VIAddVersionKey "FileDescription" "${APP} 启动器"
VIAddVersionKey "FileVersion"     "${APPVER}.0"
VIAddVersionKey "ProductVersion"  "${APPVER}"
VIAddVersionKey "LegalCopyright"  "OpenDesign"

Section
  ; $EXEDIR = 这个 exe 所在的目录 = 安装根。**不写死路径**:业主可以把安装目录
  ; 挑到别处,而快捷方式和开机自启都是指到这个 exe 的。
  SetOutPath "$EXEDIR"

  IfFileExists "$EXEDIR\python\pythonw.exe" py_ok 0
    MessageBox MB_ICONSTOP "${APP} 好像没装完整:找不到$\n$EXEDIR\python\pythonw.exe$\n$\n请重新运行安装程序。$\n(如果电脑上装了杀毒软件,也可能是它把文件删了。)"
    Abort
  py_ok:

  IfFileExists "$EXEDIR\ds\bin\ds_shell.py" ds_ok 0
    MessageBox MB_ICONSTOP "${APP} 好像没装完整:找不到$\n$EXEDIR\ds\bin\ds_shell.py$\n$\n请重新运行安装程序。"
    Abort
  ds_ok:

  ; pythonw 而不是 python:后者会留一个黑窗口在任务栏上,业主会以为是病毒。
  ; Exec 而不是 ExecWait:起完就退,别让启动器一直挂在任务管理器里。
  Exec '"$EXEDIR\python\pythonw.exe" "$EXEDIR\ds\bin\ds_shell.py"'
SectionEnd
