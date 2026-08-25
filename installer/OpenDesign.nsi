; OpenDesign Windows 安装器(track opendesign-windows-installer,S1c)
;
; 业主要的:双击装完、开始菜单出图标、不装 Python、不装 Git、不开 PowerShell、不答向导。
; 这个文件就是那句话的全部实现。
;
; ## 三条贯穿全文的决定(理由在 design.md,别在这儿重新讨论)
;
;   1. **每用户安装**(`$LOCALAPPDATA\Programs`,`RequestExecutionLevel user`)。
;      装进 Program Files 的话,将来的"应用内一键更新"要写自己的目录 = 每次弹 UAC。
;   2. **数据在安装根之外**(`$LOCALAPPDATA\OpenDesign`)。卸载/更新的边界从"约定"
;      变成"路径" —— 清单会漏,目录边界不会。
;   3. **不经手任何凭据**。安装器只把配置铺到"起得起来"的程度,key 由业主自己放,
;      口令由程序自己生成自己管(见 bin/ds_provision.py)。
;
; ## 为什么这份脚本被一份静态闸盯着(installer/check-installer.py)
;
; 这东西在业主的机器上以他的身份跑,而**我一次也跑不了它**(makensis 在 Linux 上能编,
; 编出来的 PE 只有 Windows 能执行)。可验证性只有两处:那份静态闸 + 他真机装一趟。
; NSIS 的经典事故全都是静态可判的(卸载删数据、$INSTDIR 空串递归删、写 HKLM 要管理员),
; 所以它们逐条变成了 G1~G17。**改这个文件之后必须跑一遍那份闸。**

Unicode true

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"

!define APP        "OpenDesign"
!ifndef APPVER
  !define APPVER   "0.0.0"
!endif
!ifndef PAYLOAD
  !define PAYLOAD  "payload"
!endif

; 数据根 —— 与 bin/ds_shell.py 的 user_home() / _log_path() 是同一处约定。
; 那边写的是 %LOCALAPPDATA%\OpenDesign\{UserData,Logs},这里只认它的父目录。
!define DATA_ROOT  "$LOCALAPPDATA\${APP}"
!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP}"
!define RUN_KEY    "Software\Microsoft\Windows\CurrentVersion\Run"
; 哨兵:递归删安装目录之前先确认"这确实是我们装的地方"。
; NSIS 最出名的一次性事故就是 $INSTDIR 变成空串之后 RMDir /r 从当前目录往下删。
!define SENTINEL   "ds\bin\ds_shell.py"
; 微软官方的 WebView2 检测键(每机器装 / 每用户装两处)。
!define WV2_GUID   "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

Name "${APP} ${APPVER}"
OutFile "${APP}-Setup-${APPVER}.exe"
InstallDir "$LOCALAPPDATA\Programs\${APP}"
InstallDirRegKey HKCU "Software\${APP}" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
; 300MB 的树铺开要一会儿,让业主看得见在动,免得他以为卡死了去点叉。
ShowInstDetails show
ShowUnInstDetails show

VIProductVersion "${APPVER}.0"
VIAddVersionKey "ProductName"     "${APP}"
VIAddVersionKey "FileDescription" "${APP} 安装程序"
VIAddVersionKey "FileVersion"     "${APPVER}.0"
VIAddVersionKey "ProductVersion"  "${APPVER}"
VIAddVersionKey "LegalCopyright"  "OpenDesign"

!define MUI_ICON   "opendesign.ico"
!define MUI_UNICON "opendesign.ico"
!define MUI_ABORTWARNING

!define MUI_WELCOMEPAGE_TITLE "安装 ${APP} ${APPVER}"
; 这段话要替业主回答两个他一定会遇到的问题,不然他会来问我:
;   ① 没有代码签名 ⇒ Windows 会弹"未知发布者"(design 已记账,签名要花钱);
;   ② 覆盖安装时如果程序正在跑,文件是锁着的。
!define MUI_WELCOMEPAGE_TEXT "这个安装程序会把 ${APP} 装到你自己的用户目录里,\
不需要管理员权限,也不会改动系统。$\r$\n$\r$\n\
如果 ${APP} 正在运行,请先在右下角托盘图标上点“退出”,再继续安装。$\r$\n$\r$\n\
你的资料(备忘、对话、工作区设置)存在安装目录之外,\
更新和卸载都不会碰它。"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_COMPONENTS
; 目录页要有人守:卸载时会把安装目录**整棵**删掉,所以不能让业主随手指到一个
; 本来就有东西的文件夹(见 CheckDirEmpty)。
!define MUI_PAGE_CUSTOMFUNCTION_LEAVE CheckDirEmpty
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES

!define MUI_FINISHPAGE_RUN "$INSTDIR\${APP}.exe"
!define MUI_FINISHPAGE_RUN_TEXT "现在就打开 ${APP}"
!define MUI_FINISHPAGE_TEXT "装好了。开始菜单里可以找到 ${APP}。$\r$\n$\r$\n\
第一次打开时,如果还没填过大模型的 API key,它会告诉你要把 key 放在哪个文件里。"
!insertmacro MUI_PAGE_FINISH

; 程序在跑的时候文件是锁着的,而 `RMDir /r` 删不掉会**悄悄**跳过 ——
; 卸载器会显示"完成",盘上却剩半棵树。所以先提醒。
; ⚠️ 这句话在 0.86.0 之前是**假的**:项目档案、客户备忘、共享参考图库、工作区设置
; 当时都住在 $INSTDIR\ds 里,普通卸载(RMDir /r $INSTDIR)照样删。
; track opendesign-data-outside-install 把它们搬到了 $LOCALAPPDATA\${APP}\Data 之后,
; 这句才成立。**改这句之前先确认实现真的搬完了**(判据 tests/test_data_root.py)。
!define MUI_UNCONFIRMPAGE_TEXT_TOP "如果 ${APP} 正在运行,请先在右下角托盘图标上点“退出”,再继续卸载。$\r$\n$\r$\n你的项目档案、参考图库、和助手的对话、工作区设置都放在别处,默认不会被删除。$\r$\n你自己的设计文件(CAD/SU/效果图)本来就在你自己的文件夹里,卸载完全不碰。"
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_COMPONENTS
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "SimpChinese"

; ─────────────────────────────────────────────────────────────── 安装

Section "${APP} 主程序" SecMain
  SectionIn RO
  ; 每用户:$SMPROGRAMS / $DESKTOP 都要取当前用户的那一份,不是 All Users
  ; (取错的话装的时候不报错,卸载时删不掉 —— 因为那需要管理员)。
  SetShellVarContext current

  SetOutPath "$INSTDIR"
  ; 整棵树一次铺进去。**故意不逐个 File 点名**:点名清单会跟真实树漂移,
  ; 而"少铺了半棵树"这种事编译期不报错。谁保证它全:成品闸 P4/P5
  ; 逐个文件比对 makensis 自己打印的清单与 payload 树。
  File /r "${PAYLOAD}\*"

  WriteRegStr HKCU "Software\${APP}" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\${APP}" "Version"    "${APPVER}"

  ; 卸载条目("设置 → 应用"里那一条)。
  WriteRegStr   HKCU "${UNINST_KEY}" "DisplayName"     "${APP}"
  WriteRegStr   HKCU "${UNINST_KEY}" "DisplayVersion"  "${APPVER}"
  WriteRegStr   HKCU "${UNINST_KEY}" "Publisher"       "OpenDesign"
  WriteRegStr   HKCU "${UNINST_KEY}" "DisplayIcon"     "$INSTDIR\${APP}.exe"
  WriteRegStr   HKCU "${UNINST_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr   HKCU "${UNINST_KEY}" "UninstallString" '"$INSTDIR\卸载.exe"'
  WriteRegStr   HKCU "${UNINST_KEY}" "QuietUninstallString" '"$INSTDIR\卸载.exe" /S'
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINST_KEY}" "NoRepair" 1
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKCU "${UNINST_KEY}" "EstimatedSize" "$0"

  WriteUninstaller "$INSTDIR\卸载.exe"

  CreateDirectory "$SMPROGRAMS\${APP}"
  CreateShortcut "$SMPROGRAMS\${APP}\${APP}.lnk" "$INSTDIR\${APP}.exe"
  CreateShortcut "$SMPROGRAMS\${APP}\卸载 ${APP}.lnk" "$INSTDIR\卸载.exe"

  Call EnsureWebView2
  Call ProvisionConfig
SectionEnd

Section "在桌面上放一个图标" SecDesktop
  SetShellVarContext current
  CreateShortcut "$DESKTOP\${APP}.lnk" "$INSTDIR\${APP}.exe"
SectionEnd

; `/o` = 默认不勾。业主拍板"开机自启做成选项";默认关还有第二个理由:
; 常驻 + 自启会把底座的 dream(每 2 小时回顾对话、会写 SOUL.md)放大到 24 小时,
; 那件事 design.md 记在 backlog 里、本单不动 —— 那就更不该默认替他打开。
Section /o "开机时自动启动" SecAutorun
  SetShellVarContext current
  WriteRegStr HKCU "${RUN_KEY}" "${APP}" '"$INSTDIR\${APP}.exe"'
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecMain}    "${APP} 本体(必装)。"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} "在桌面上放一个 ${APP} 图标。"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecAutorun} "开机后自动把 ${APP} 挂到右下角托盘里。"
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; ─────────────────────────────────────────────────────────────── 装机时的三件事

Function CheckDirEmpty
  ; 🔴 卸载时会 `RMDir /r "$INSTDIR"` —— 整棵删。所以"装到哪儿"这件事,
  ; 一旦业主把路径改成一个本来就有东西的文件夹(`D:\文档` 这种),卸载就会把他的东西
  ; 一起删光。**G6 那个哨兵挡不住这一种**:装完之后哨兵文件就在那儿了,它会说"是我们的"。
  ;
  ; 所以在这里拦:目录存在、非空、又不是上一次装的 OpenDesign ⇒ 让他确认一次。
  ; 不直接禁止 —— 他可能真的想装回一个自己清理过的文件夹。
  ; NSIS 的 `IfFileExists 文件 有则跳 [无则跳]`;`0` = "不跳,往下走"(标准惯用法)。
  ; 把语义写在这儿是因为它属于"Linux 上验不了、写反了也没有闸看得出来"的那一类
  ; (四审 subdeepseek F6 点名的最后一处不可验控制流)。
  IfFileExists "$INSTDIR\${SENTINEL}" ok        ; 上一次装的就是这儿,覆盖安装,放行
  IfFileExists "$INSTDIR\*.*" 0 ok              ; 有 ⇒ 往下数内容;没有(新目录)⇒ 放行

  FindFirst $0 $1 "$INSTDIR\*.*"
  loop:
    StrCmp $1 "" done
    StrCmp $1 "." next
    StrCmp $1 ".." next
    ; 找到了第一个真实条目 ⇒ 非空
    FindClose $0
    MessageBox /SD IDCANCEL MB_OKCANCEL|MB_ICONEXCLAMATION \
      "这个文件夹里已经有别的东西了:$\n$INSTDIR$\n$\n\
卸载 ${APP} 的时候会把整个文件夹删掉,里面原有的东西也会一起没。$\n$\n\
建议换一个空文件夹(比如默认的那个)。一定要用这里的话,点“确定”。" \
      IDOK ok
    Abort
  next:
    FindNext $0 $1
    Goto loop
  done:
  FindClose $0
  ok:
FunctionEnd

Function EnsureWebView2
  ; S1a 的账:两台机器上 WebView2 都在,但那只证明了**那两台**。缺了的话窗口根本开不出来,
  ; 而业主看到的会是一串 CLR 英文栈。⇒ 检测 + 带微软官方引导程序补装,不许赌。
  ; 读 HKLM 是允许的(闸 G7 只禁止**写**);安装器是 32 位进程,读 HKLM\SOFTWARE
  ; 会被自动重定向到 WOW6432Node —— 正好是 Edge 在 64 位系统上写的那一处。
  ClearErrors
  ReadRegStr $0 HKLM "SOFTWARE\Microsoft\EdgeUpdate\Clients\${WV2_GUID}" "pv"
  ${If} $0 == ""
  ${OrIf} $0 == "0.0.0.0"
    ReadRegStr $0 HKCU "Software\Microsoft\EdgeUpdate\Clients\${WV2_GUID}" "pv"
  ${EndIf}
  ${If} $0 != ""
  ${AndIf} $0 != "0.0.0.0"
    DetailPrint "WebView2 运行时已在(版本 $0),不用补装。"
    Return
  ${EndIf}

  DetailPrint "这台电脑上没有 WebView2 运行时,正在装微软官方的那一份(要联网)…"
  ; ⚠️ 这条路径**在业主的两台机器上都不会被走到**(WebView2 都在),所以它没有真机证据。
  ;    另:微软的引导程序装的是"每机器"运行时 ⇒ **这一步会弹 UAC**,
  ;    "全程不要管理员"那句承诺在缺 WebView2 的机器上不成立。已写进真机清单。
  ClearErrors
  ExecWait '"$INSTDIR\MicrosoftEdgeWebview2Setup.exe" /silent /install' $1
  ; 起都没起来(被杀软秒删、文件损坏)时 ExecWait 置 error flag,而 $1 此时不可信 ——
  ; 不查的话会错印"装好了"(四审 subkimi F4)。
  IfErrors 0 +2
    StrCpy $1 "启动失败"
  ${If} $1 != 0
    ; 装不上不拦住整个安装:业主可能只是暂时没网。第一次打开时外壳会再说一次人话。
    MessageBox /SD IDOK MB_ICONEXCLAMATION "没能装上微软的 WebView2 运行时(错误码 $1)。$\n$\n\
${APP} 仍然装好了,但第一次打开可能会报错。$\n\
联网之后重新运行一次这个安装程序就行。"
  ${Else}
    DetailPrint "WebView2 运行时装好了。"
  ${EndIf}
FunctionEnd

Function ProvisionConfig
  ; 把配置铺到"后台起得起来"的程度。**不问业主任何东西** —— 这一步是非交互的,
  ; 而且幂等(已经装过一次的机器,他自己的设置原样留着)。细节全在
  ; bin/ds_provision.py,那边有 15 条判据 + 12 条红检盯着。
  DetailPrint "正在准备配置…"
  ; **一行写完,不用续行**:NSIS 的续行拼出来到底是什么样,我在 Linux 上验不了,
  ; 而"命令拼歪了"的表现是装机时静默失败 —— 少一个验不了的机制比省几个字重要。
  nsExec::ExecToLog '"$INSTDIR\python\python.exe" "$INSTDIR\ds\bin\ds_provision.py" --home "${DATA_ROOT}\UserData" --ds-root "$INSTDIR\ds"'
  Pop $0
  ${If} $0 != 0
    ; 不 Abort:文件已经铺好了,而外壳自己会把"到底缺什么"说得比这里清楚
    ; (那段话在业主真机上验过)。这里只负责别让它悄悄过去。
    MessageBox /SD IDOK MB_ICONEXCLAMATION "配置初始化没有成功(错误码 $0)。$\n$\n\
${APP} 的文件已经装好了。第一次打开时它会告诉你还缺什么。"
  ${EndIf}
FunctionEnd

; ─────────────────────────────────────────────────────────────── 卸载

Section "un.${APP}" SecUnMain
  SectionIn RO
  SetShellVarContext current

  DeleteRegValue HKCU "${RUN_KEY}" "${APP}"
  DeleteRegKey   HKCU "${UNINST_KEY}"
  DeleteRegKey   HKCU "Software\${APP}"

  Delete "$DESKTOP\${APP}.lnk"
  Delete "$SMPROGRAMS\${APP}\${APP}.lnk"
  Delete "$SMPROGRAMS\${APP}\卸载 ${APP}.lnk"
  RMDir  "$SMPROGRAMS\${APP}"

  ; 🔴 递归删之前先认门。$INSTDIR 可能因为注册表被人动过而变成空串或别的目录,
  ; 那时候 `RMDir /r` 会从那里往下把东西删光。哨兵是这份闸(G6)要求的形状。
  IfFileExists "$INSTDIR\${SENTINEL}" 0 not_ours
    RMDir /r "$INSTDIR"
    Goto done
  not_ours:
    MessageBox /SD IDOK MB_ICONEXCLAMATION "这个目录看起来不是 ${APP} 装的地方,为安全起见没有删:$\n$INSTDIR"
  done:
SectionEnd

; `/o` = 默认不勾。业主两年的档案在这底下 —— 删掉不可恢复,必须是他主动勾的。
Section /o "un.连我的资料一起删掉(不可恢复)" SecUnData
  SetShellVarContext current
  IfFileExists "${DATA_ROOT}\*.*" 0 no_data
    RMDir /r "${DATA_ROOT}"
    DetailPrint "资料目录已删除:${DATA_ROOT}"
    Goto after
  no_data:
    DetailPrint "没有找到资料目录:${DATA_ROOT}"
  after:
SectionEnd

!insertmacro MUI_UNFUNCTION_DESCRIPTION_BEGIN
  !insertmacro MUI_DESCRIPTION_TEXT ${SecUnMain} "卸载 ${APP} 程序本体(你的资料不会被删)。"
  !insertmacro MUI_DESCRIPTION_TEXT ${SecUnData} "连同项目档案、参考图库、对话记录、工作区设置一起删掉。删了就找不回来了。(你自己的设计文件不在这儿,不受影响。)"
!insertmacro MUI_UNFUNCTION_DESCRIPTION_END
