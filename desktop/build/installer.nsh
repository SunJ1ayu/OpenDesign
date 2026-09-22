; OpenDesign Electron 安装包自定义段。
!define OD_OLD_KEY "Software\OpenDesign"
!define OD_RUN_KEY "Software\Microsoft\Windows\CurrentVersion\Run"
!define OD_DATA "$LOCALAPPDATA\OpenDesign"

!macro preInit
  Var /GLOBAL odAutostart
  Var /GLOBAL odOldDir
  StrCpy $odAutostart "0"
  ReadRegStr $odOldDir HKCU "${OD_OLD_KEY}" "InstallDir"
  ${if} $odOldDir != ""
    ReadRegStr $1 HKCU "${INSTALL_REGISTRY_KEY}" "InstallLocation"
    ${if} $1 == ""
      WriteRegExpandStr HKCU "${INSTALL_REGISTRY_KEY}" "InstallLocation" "$odOldDir"
    ${endIf}
  ${endIf}
  ReadRegStr $0 HKCU "${OD_RUN_KEY}" "OpenDesign"
  ${if} $0 != ""
    StrCpy $odAutostart "1"
  ${endIf}
!macroend

!macro customCheckAppRunning
  DetailPrint "OpenDesign:先关掉还在运行的 OpenDesign…"
  nsExec::ExecToLog `"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -Command "$$roots=@('$INSTDIR\','$odOldDir\') | Where-Object { $$_ } | Select-Object -Unique; for($$i=0;$$i -lt 40;$$i++){ $$p=@(Get-CimInstance Win32_Process | Where-Object { $$x=$$_.ExecutablePath; $$x -and @($$roots | Where-Object { $$x.StartsWith($$_,[StringComparison]::OrdinalIgnoreCase) }).Count }); if($$p.Count -eq 0){ exit 0 }; if($$i -ge 4){ $$p | ForEach-Object { Stop-Process -Id $$_.ProcessId -Force -ErrorAction SilentlyContinue } }; Start-Sleep -Milliseconds 500 }; exit 1"`
  Pop $0
  ${if} $0 != "0"
    MessageBox MB_ICONSTOP "OpenDesign 还在运行，关不掉。请在右下角托盘图标上点「退出」，再重新运行安装程序。" /SD IDOK
    Quit
  ${endIf}

  ${if} ${FileExists} "$INSTDIR\ds\bin\ds_shell.py"
  ${andIf} ${FileExists} "$INSTDIR\卸载.exe"
    ExecWait '"$INSTDIR\卸载.exe" /S _?=$INSTDIR' $1
    ${if} ${FileExists} "$INSTDIR\ds\bin\ds_shell.py"
      nsExec::ExecToLog `"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -Command "$$d='$INSTDIR\'; Get-CimInstance Win32_Process | Where-Object { $$_.ExecutablePath -and $$_.ExecutablePath.StartsWith($$d,[StringComparison]::OrdinalIgnoreCase) } | ForEach-Object { Stop-Process -Id $$_.ProcessId -Force -ErrorAction SilentlyContinue }"`
      Pop $0
      ExecWait '"$INSTDIR\卸载.exe" /S _?=$INSTDIR' $1
    ${endIf}
    Delete "$INSTDIR\卸载.exe"
    ${if} ${FileExists} "$INSTDIR\ds\bin\ds_shell.py"
      MessageBox MB_ICONSTOP "旧版 OpenDesign 没能完整卸载。为避免新旧文件混在一起，安装已经停止。请重启电脑后再运行安装包。" /SD IDOK
      Quit
    ${endIf}
  ${endIf}

  ${if} $odOldDir != ""
  ${andIf} $odOldDir != $INSTDIR
  ${andIf} ${FileExists} "$odOldDir\ds\bin\ds_shell.py"
  ${andIf} ${FileExists} "$odOldDir\卸载.exe"
    ExecWait '"$odOldDir\卸载.exe" /S _?=$odOldDir' $1
    ${if} ${FileExists} "$odOldDir\ds\bin\ds_shell.py"
      nsExec::ExecToLog `"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -Command "$$d='$odOldDir\'; Get-CimInstance Win32_Process | Where-Object { $$_.ExecutablePath -and $$_.ExecutablePath.StartsWith($$d,[StringComparison]::OrdinalIgnoreCase) } | ForEach-Object { Stop-Process -Id $$_.ProcessId -Force -ErrorAction SilentlyContinue }"`
      Pop $0
      ExecWait '"$odOldDir\卸载.exe" /S _?=$odOldDir' $1
    ${endIf}
    Delete "$odOldDir\卸载.exe"
    ${if} ${FileExists} "$odOldDir\ds\bin\ds_shell.py"
      MessageBox MB_ICONSTOP "原目录里的旧版 OpenDesign 没能完整卸载。为避免电脑里留下两份，安装已经停止。请重启电脑后再运行安装包。" /SD IDOK
      Quit
    ${endIf}
  ${endIf}
!macroend

!macro customInstall
  ${ifNot} ${isUpdated}
    nsExec::ExecToLog '"$INSTDIR\resources\python\python.exe" "$INSTDIR\resources\ds\bin\ds_provision.py" --home "${OD_DATA}\UserData" --ds-root "$INSTDIR\resources\ds"'
    Pop $0
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
