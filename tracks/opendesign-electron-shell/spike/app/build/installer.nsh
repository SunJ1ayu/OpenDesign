; OpenDesign 安装包的自定义段 —— 探路版(track opendesign-electron-shell,U2 的 E3)。
; 挂在 electron-builder 的 NSIS 模板上(package.json build.nsis.include)。
;
; 它要堵的是两家挑战腿核实过的「换安装器」那几个坑(design.md 表 #3 #4 #5):
;   #3 新安装器不认旧版记下的安装目录     ⇒ preInit:把旧键 HKCU\Software\OpenDesign\InstallDir 转给模板
;   #4 旧卸载项留着、点它会删掉同目录的新装 ⇒ 装之前用旧卸载器自己静默卸掉旧程序(资料那一节默认不选)
;   #5 业主手动卸载时软件还在托盘里 / 手滑勾了「连资料一起删」
;                                        ⇒ 业主根本不用手动卸载;住在安装目录里的进程由这里先收掉
; 另外两件:开机自启跟着旧版的选择走;装机时照旧跑一次 ds_provision(幂等),更新(--updated)时不碰资料根。

!define OD_OLD_KEY "Software\OpenDesign"
!define OD_RUN_KEY "Software\Microsoft\Windows\CurrentVersion\Run"
!define OD_DATA    "$LOCALAPPDATA\OpenDesign"

!macro preInit
  Var /GLOBAL odAutostart
  StrCpy $odAutostart "0"
  ; 旧版(pywebview 那一代)记着业主自己挑的目录,例如 D:\AI\OpenDesign。
  ; 模板的 initMultiUser 会读 INSTALL_REGISTRY_KEY 的 InstallLocation 当默认目录 ——
  ; 这正是 electron-builder 文档里「改默认安装目录」的写法。只在模板自己还没记过时才转。
  ReadRegStr $0 HKCU "${OD_OLD_KEY}" "InstallDir"
  ${if} $0 != ""
    ReadRegStr $1 HKCU "${INSTALL_REGISTRY_KEY}" "InstallLocation"
    ${if} $1 == ""
      WriteRegExpandStr HKCU "${INSTALL_REGISTRY_KEY}" "InstallLocation" "$0"
    ${endIf}
  ${endIf}
  ReadRegStr $0 HKCU "${OD_RUN_KEY}" "OpenDesign"
  ${if} $0 != ""
    StrCpy $odAutostart "1"
  ${endIf}
!macroend

!macro customCheckAppRunning
  ; ① 安装目录里任何还活着的进程(Electron 本体、Python 管家、网关、工作台、旧版的 pythonw)
  ;    先等 2 秒让它自己走,再强收;最多 20 秒。收不掉就不许往下装(半新半旧是 09-08 否掉的形状)。
  DetailPrint "OpenDesign:先关掉还在运行的 OpenDesign…"
  nsExec::ExecToLog `"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -Command "$$d='$INSTDIR\'; for($$i=0;$$i -lt 40;$$i++){ $$p=@(Get-CimInstance Win32_Process | Where-Object { $$_.ExecutablePath -and $$_.ExecutablePath.StartsWith($$d,[StringComparison]::OrdinalIgnoreCase) }); if($$p.Count -eq 0){ exit 0 }; if($$i -ge 4){ $$p | ForEach-Object { Stop-Process -Id $$_.ProcessId -Force -ErrorAction SilentlyContinue } }; Start-Sleep -Milliseconds 500 }; exit 1"`
  Pop $0
  ${if} $0 != "0"
    MessageBox MB_ICONSTOP "OpenDesign 还在运行,关不掉。$\r$\n$\r$\n请在右下角托盘图标上点「退出」,再重新运行安装程序。" /SD IDOK
    Quit
  ${endIf}

  ; ② 同一目录里还躺着旧版(哨兵 ds\bin\ds_shell.py + 旧卸载器)⇒ 用它自己的卸载器静默卸掉。
  ;    /S 下「连资料一起删」那一节是 /o(默认不选)⇒ 资料根不动;它会顺手删掉旧的卸载项、
  ;    开机自启、快捷方式(下面由模板重建)。_?= 让它在原地跑,自己那一个文件删不掉,之后补删。
  ${if} ${FileExists} "$INSTDIR\ds\bin\ds_shell.py"
  ${andIf} ${FileExists} "$INSTDIR\卸载.exe"
    DetailPrint "OpenDesign:卸掉旧版程序(你的资料不动)…"
    ExecWait '"$INSTDIR\卸载.exe" /S _?=$INSTDIR' $1
    DetailPrint "OpenDesign:旧版卸载器退出码 $1"
    Delete "$INSTDIR\卸载.exe"
  ${endIf}
!macroend

!macro customInstall
  ${ifNot} ${isUpdated}
    DetailPrint "OpenDesign:把配置弄到位(幂等)…"
    nsExec::ExecToLog '"$INSTDIR\resources\python\python.exe" "$INSTDIR\resources\ds\bin\ds_provision.py" --home "${OD_DATA}\UserData" --ds-root "$INSTDIR\resources\ds"'
    Pop $0
    DetailPrint "OpenDesign:配置初始化退出码 $0"
    ${if} $odAutostart == "1"
      WriteRegStr HKCU "${OD_RUN_KEY}" "OpenDesign" '"$INSTDIR\OpenDesign.exe"'
    ${endIf}
  ${endIf}
!macroend

!macro customUnInstall
  ${ifNot} ${isUpdated}
    DeleteRegValue HKCU "${OD_RUN_KEY}" "OpenDesign"
  ${endIf}
!macroend


; 更新时的向导页照 ZCode 原样(业主 09-22 选 C):「装给谁」→ 进度 →「完成」都由业主自己点。
; 第四跑试过的 customInstallMode / customFinishPage(零点击)已撤回,见 design.md U3。
