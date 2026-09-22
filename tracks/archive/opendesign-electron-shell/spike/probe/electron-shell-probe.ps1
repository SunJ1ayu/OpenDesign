# Electron 换壳探路 —— E3 过渡 + E2 起窗(track opendesign-electron-shell,U2)。**不是回归判据。**
#
# 它替业主走一遍「换壳那一版」的真实处境:
#   旧版 0.98.x 装在自选的带空格目录里、开机自启开着、正在托盘里跑、资料和 key 都在
#   → 双击新安装包(这里用 /S 静默,不带 /D:目录必须由安装包自己认出来)
#   → 看旧程序被关掉、旧卸载项没了、装回同一目录、资料一个字节不少、开机自启与桌面图标指向新 exe
#   → 再把装好的新版真跑起来点三个按钮(e2-drive.mjs)。
# 每条判读一行 `OK  |FAIL <名字> :: <事实>`;有 FAIL 就 exit 1。**绿不等于产品没问题** —— 图由主 agent 看。
param(
    [string]$OldTag   = "win-installer-0.98.8",
    [string]$OldAsset = "OpenDesign-Setup-0.98.8.exe",
    [Parameter(Mandatory)][string]$NewSetup,
    [Parameter(Mandatory)][string]$AppDir,
    [string]$UpdDir   = "",          # E4:放 v2 的 latest.yml / 安装包 / blockmap(+ v1 的 blockmap)的目录;空 = 跳过 E4
    [string]$NewVer   = "0.98.11",
    [string]$OutDir   = "probe-out"
)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$OutDir   = (Resolve-Path $OutDir).Path
$Dir      = "C:\AI Test\OpenDesign"          # 业主那种自选目录,带空格
$Data     = "$env:LOCALAPPDATA\OpenDesign"
$Shot     = Join-Path $PSScriptRoot 'shot.ps1'
$script:fail = 0
function V([string]$name, [bool]$ok, [string]$detail) {
    if (-not $ok) { $script:fail++ }
    "{0} {1} :: {2}" -f $(if ($ok) { 'OK  ' } else { 'FAIL' }), $name, $detail
}
function Shot([string]$name) { "  [截图] $name $(pwsh -NoProfile -File $Shot (Join-Path $OutDir "$name.png"))" }
function ProcsUnder([string]$d) {
    @(Get-CimInstance Win32_Process | Where-Object {
        $_.ExecutablePath -and $_.ExecutablePath.StartsWith("$d\", [StringComparison]::OrdinalIgnoreCase)
    } | ForEach-Object { "$($_.ProcessId) $($_.Name)" }) -join ', '
}
function UninstallEntries {
    @(Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall' -ErrorAction SilentlyContinue |
      ForEach-Object { Get-ItemProperty $_.PSPath } |
      Where-Object { $_.DisplayName -like 'OpenDesign*' } |
      ForEach-Object { "[$($_.PSChildName)] $($_.DisplayName) | $($_.UninstallString)" })
}
function WaitHealth([int]$limitSec) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $limitSec) {
        foreach ($p in 8766..8786) {
            try {
                $r = Invoke-WebRequest "http://127.0.0.1:$p/api/health" -NoProxy -TimeoutSec 2 -UseBasicParsing
                if ($r.StatusCode -eq 200) { return "$p $($r.Content)" }
            } catch {}
        }
        Start-Sleep -Seconds 2
    }
    return $null
}

# 健康检查报的版本(JSON 里的 version)是否等于 exe 的产品版本(去掉尾巴上的 .0)。挑战 a4:旧更新器靠「版本号 + nonce」认新版,
# 探路第二跑出现过 exe 0.98.11 而后台报 0.98.9 —— 只看「有应答」会把半新半旧判成装好了。
function SameVersion([string]$health, [string]$exe) {
    if (-not $health) { return $false }
    $m = [regex]::Match($health, '"version":\s*"([^"]+)"')
    return $m.Success -and ($exe -replace '(\.0)+$', '') -eq $m.Groups[1].Value
}
function QuickHealth {
    $ports = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
               Where-Object { $_.LocalPort -ge 8766 -and $_.LocalPort -le 8786 } | Select-Object -ExpandProperty LocalPort -Unique)
    foreach ($p in $ports) {
        try {
            $r = Invoke-WebRequest "http://127.0.0.1:$p/api/health" -NoProxy -TimeoutSec 2 -UseBasicParsing
            if ($r.StatusCode -eq 200) { return "$p $($r.Content)" }
        } catch {}
    }
    return $null
}

# ---------------------------------------------------------------- E3-1 装旧版
"== E3-1 下载并静默装旧版 $OldAsset 到「$Dir」"
gh release download $OldTag -p $OldAsset -D "$OutDir\old" --clobber
$p = Start-Process "$OutDir\old\$OldAsset" -ArgumentList "/S /D=$Dir" -PassThru
if (-not $p.WaitForExit(300000)) { Shot 'e3-00-old-install-stuck'; throw "旧版安装 5 分钟没结束" }
V 'E3.old 旧版装上了' ((Test-Path "$Dir\ds\bin\ds_shell.py") -and (Test-Path "$Dir\卸载.exe")) "退出码 $($p.ExitCode)"
$oldReg = (Get-ItemProperty 'HKCU:\Software\OpenDesign' -ErrorAction SilentlyContinue).InstallDir
V 'E3.old 旧版记下了自选目录' ($oldReg -eq $Dir) "HKCU\Software\OpenDesign InstallDir = $oldReg"

# 业主当初勾了「开机自动启动」(旧版默认不勾,这里替他勾上,看新版会不会跟着走)
Set-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'OpenDesign' -Value "`"$Dir\OpenDesign.exe`""

# 资料与 key:放几样「丢了就出事」的东西,记下指纹
$marks = @(
    "$Data\UserData\.openDesign\key.txt",
    "$Data\Data\probe-档案-marker.md",
    "$Data\UserData\.openDesign\probe-marker.txt"
)
foreach ($m in $marks) {
    New-Item -ItemType Directory -Force -Path (Split-Path $m) | Out-Null
    if (-not (Test-Path $m)) { Set-Content -Path $m -Value "probe $([guid]::NewGuid())" -Encoding utf8 }
}
$before = @{}; foreach ($m in $marks) { $before[$m] = (Get-FileHash $m).Hash }
$dataCountBefore = @(Get-ChildItem "$Data\Data" -Recurse -File -ErrorAction SilentlyContinue).Count

# ---------------------------------------------------------------- E3-2 旧版在托盘里跑着
"== E3-2 启动旧版,等它活过来"
Start-Process "$Dir\OpenDesign.exe" | Out-Null
$h = WaitHealth 240
V 'E3.oldrun 旧版跑起来了(工作台应答)' ([bool]$h) "$h"
"  旧版进程:$(ProcsUnder $Dir)"
Shot 'e3-01-old-running'
"  装新版前的卸载项:"; UninstallEntries | ForEach-Object { "    $_" }

# ---------------------------------------------------------------- E3-3 双击新安装包(第七跑起:带界面,像业主那样一页页点)
"== E3-3 带界面装新版 $NewSetup(不带参数;click-wizard 替业主按「下一步/完成」,选目录页不改)"
$e3Log = Join-Path $OutDir 'e3-click-wizard.log'
$e3Clicker = Start-Process powershell.exe -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot 'click-wizard.ps1'), $OutDir, $e3Log, '420') -PassThru -WindowStyle Hidden -RedirectStandardError "$e3Log.err"
$sw = [Diagnostics.Stopwatch]::StartNew()
$p = Start-Process $NewSetup -PassThru
$tick = 0
while (-not $p.HasExited -and $sw.Elapsed.TotalMinutes -lt 6) {
    Start-Sleep -Seconds 30; $tick++; Shot ("e3-02-installing-{0}" -f $tick)
}
if (-not $p.HasExited) { Shot 'e3-02-install-stuck'; throw "新版安装 6 分钟没结束" }
"  新安装包退出码 $($p.ExitCode),耗时 $([int]$sw.Elapsed.TotalSeconds)s"
V 'E3.install 新安装包退出码 0' ($p.ExitCode -eq 0) "$($p.ExitCode)"
if (-not $e3Clicker.WaitForExit(30000)) { Stop-Process -Id $e3Clicker.Id -Force -ErrorAction SilentlyContinue }
"  ---- 替业主点首装向导(click-wizard.ps1)----"; Get-Content $e3Log, "$e3Log.err" -ErrorAction SilentlyContinue | ForEach-Object { "    $_" }
$dirLine = @(Get-Content $e3Log -ErrorAction SilentlyContinue | Where-Object { $_ -match 'CLICK#' -and $_ -match '输入框=' }) | Select-Object -First 1
V 'E3.guidir 选目录页默认显示的就是旧版那个自选目录' ($dirLine -and $dirLine.Contains("输入框=$Dir")) "$dirLine"
Start-Sleep -Seconds 3

# ---------------------------------------------------------------- E3-4 核对
V 'E3.dir 装回了旧版那个自选目录' ((Test-Path "$Dir\OpenDesign.exe") -and (Test-Path "$Dir\resources\app.asar")) "$Dir"
$strays = @("$env:LOCALAPPDATA\Programs\OpenDesign\OpenDesign.exe") | Where-Object { Test-Path $_ }
V 'E3.dir 没在默认目录另装一份' (-not $strays) "$strays"
V 'E3.oldgone 旧程序文件没了(python\ ds\ 卸载.exe)' (-not ((Test-Path "$Dir\python") -or (Test-Path "$Dir\ds") -or (Test-Path "$Dir\卸载.exe"))) ((Get-ChildItem $Dir -Name -ErrorAction SilentlyContinue | Select-Object -First 12) -join ' ')
$ents = UninstallEntries
"  装新版后的卸载项:"; $ents | ForEach-Object { "    $_" }
V 'E3.oldkey 旧卸载项没了' (-not (Test-Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\OpenDesign')) ""
V 'E3.newkey 「应用和功能」里只剩一个 OpenDesign' ($ents.Count -eq 1) "$($ents.Count) 条"
$left = ProcsUnder "$Dir\python"
V 'E3.oldproc 旧版进程全收掉了' (-not $left) "$left"
$exeVer = (Get-Item "$Dir\OpenDesign.exe").VersionInfo.ProductVersion
$h3 = WaitHealth 120
V 'E3.samever 完成页拉起的新版,后台报的版本 = exe 版本' (SameVersion $h3 $exeVer) "exe $exeVer;$h3"
foreach ($m in $marks) {
    $ok = (Test-Path $m) -and ((Get-FileHash $m).Hash -eq $before[$m])
    V "E3.data 资料原样:$(Split-Path $m -Leaf)" $ok $m
}
$dataCountAfter = @(Get-ChildItem "$Data\Data" -Recurse -File -ErrorAction SilentlyContinue).Count
V 'E3.data 档案目录文件数没少' ($dataCountAfter -ge $dataCountBefore) "$dataCountBefore → $dataCountAfter"
$run = (Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -ErrorAction SilentlyContinue).OpenDesign
V 'E3.autostart 开机自启还在、指向新 exe' ($run -eq "`"$Dir\OpenDesign.exe`"") "$run"
$lnk = "$([Environment]::GetFolderPath('Desktop'))\OpenDesign.lnk"
$target = if (Test-Path $lnk) { (New-Object -ComObject WScript.Shell).CreateShortcut($lnk).TargetPath } else { '(没有)' }
V 'E3.shortcut 桌面图标指向新 exe' ($target -eq "$Dir\OpenDesign.exe") "$target"
V 'E3.config 配置文件还在' (Test-Path "$Data\UserData\.nanobot\config.json") ""

# ---------------------------------------------------------------- E2 把新版真跑起来点
"== E2 起窗 / 三按钮 / 托盘 / 退出 / 硬杀"
Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like "$Dir\*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Push-Location $AppDir
node e2-drive.mjs "$Dir\OpenDesign.exe" $OutDir
$e2 = $LASTEXITCODE
Pop-Location
V 'E2 起窗探针整体' ($e2 -eq 0) "e2-drive.mjs rc=$e2(逐条见上)"

# ---------------------------------------------------------------- E4 自动更新(electron-updater)
if ($UpdDir) {
    "== E4 v1 → $NewVer:后台在跑时下载并安装"
    $serveLog = Join-Path $OutDir 'e4-serve.log'
    $srv = Start-Process node -ArgumentList @((Join-Path $PSScriptRoot 'serve.mjs'), $UpdDir, '8900', $serveLog) -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 2
    Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like "$Dir\*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    $v1 = (Get-Item "$Dir\OpenDesign.exe").VersionInfo.ProductVersion
    # 第五跑(业主选 C = 照 ZCode):向导由人点。click-wizard.ps1 替业主点「下一步」「完成」,每页先截图、记下页上的字与选项。
    $clickLog = Join-Path $OutDir 'e4-click-wizard.log'
    $clicker = Start-Process powershell.exe -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $PSScriptRoot 'click-wizard.ps1'), $OutDir, $clickLog, '480') -PassThru -WindowStyle Hidden -RedirectStandardError "$clickLog.err"
    $env:OD_SPIKE_UPDATE = '1'
    Start-Process "$Dir\OpenDesign.exe" | Out-Null
    Remove-Item Env:\OD_SPIKE_UPDATE
    # 一条时间线量到底 —— 安装器何时起、何时退、exe 何时换版、新版何时应答。每 10 秒一张整屏。
    $sw = [Diagnostics.Stopwatch]::StartNew(); $ver = $v1
    $lastShot = -99; $instSeen = $null; $instGone = $null; $flip = $null; $h = $null
    while ($sw.Elapsed.TotalMinutes -lt 8 -and -not $h) {
        Start-Sleep -Seconds 3
        $t = [int]$sw.Elapsed.TotalSeconds
        $inst = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -like '*electron-setup*' })
        if ($inst.Count -and $null -eq $instSeen) { $instSeen = $t; "  +${t}s 安装器起来了:$($inst[0].CommandLine)" }
        if ($null -ne $instSeen -and -not $inst.Count -and $null -eq $instGone) { $instGone = $t; "  +${t}s 安装器退出了" }
        if ($t - $lastShot -ge 10) { $lastShot = $t; Shot ("e4-00-updating-{0:000}s" -f $t) }
        try { $ver = (Get-Item "$Dir\OpenDesign.exe" -ErrorAction Stop).VersionInfo.ProductVersion } catch { $ver = '(读不到:正在换文件?)' }
        if ($null -eq $flip -and $ver -like "$NewVer*") { $flip = $t; "  +${t}s exe 版本换成 $ver" }
        if ($null -ne $flip) { $h = QuickHealth }
    }
    $t = [int]$sw.Elapsed.TotalSeconds
    # 新版应答时安装器可能还在退出(「完成」页先拉起新版再退;第八跑 +149s 新版应答时它还在)⇒ 最多再等 30 秒
    for ($k = 0; $k -lt 30 -and $null -ne $instSeen -and $null -eq $instGone; $k++) {
        if (-not @(Get-CimInstance Win32_Process | Where-Object { $_.Name -like '*electron-setup*' }).Count) { $instGone = [int]$sw.Elapsed.TotalSeconds } else { Start-Sleep -Seconds 1 }
    }
    "  时间线:安装器起 +$instSeen s / 安装器退 +$instGone s / exe 换版 +$flip s / 新版应答 $(if ($h) { "+$t s" } else { '没等到' })(上限 480s)"
    if (-not $clicker.WaitForExit(30000)) { Stop-Process -Id $clicker.Id -Force -ErrorAction SilentlyContinue }
    "  ---- 替业主点向导(click-wizard.ps1)----"; Get-Content $clickLog, "$clickLog.err" -ErrorAction SilentlyContinue | ForEach-Object { "    $_" }
    $nClicks = @(Get-Content $clickLog -ErrorAction SilentlyContinue | Where-Object { $_ -match 'CLICK#' }).Count
    V 'E4.wizard 向导点完、安装器退出' ($null -ne $instSeen -and $null -ne $instGone -and $nClicks -ge 1) "点了 $nClicks 下;起 +$instSeen s,退 +$instGone s"
    V 'E4.version 装上了新版' ($null -ne $flip) "$v1 → $ver"
    V 'E4.relaunch 装完自己重新打开、后台应答' ([bool]$h) "$h"
    V 'E4.samever 新版后台报的版本 = exe 版本' (SameVersion $h $ver) "exe $ver;$h"
    "  更新后进程:$(ProcsUnder $Dir)"
    Shot 'e4-01-after-update'
    $ents = UninstallEntries
    V 'E4.newkey 更新后「应用和功能」里仍只有一个 OpenDesign' ($ents.Count -eq 1) "$($ents -join ' ; ')"
    V 'E4.dir 仍在原目录、没另装一份' (-not (Test-Path "$env:LOCALAPPDATA\Programs\OpenDesign\OpenDesign.exe")) ""
    foreach ($m in $marks) {
        V "E4.data 资料原样:$(Split-Path $m -Leaf)" ((Test-Path $m) -and ((Get-FileHash $m).Hash -eq $before[$m])) $m
    }
    $full = (Get-ChildItem $UpdDir -Recurse -Filter "*$NewVer*.exe" | Select-Object -First 1).Length
    $sent = 0; Get-Content $serveLog | ForEach-Object { if ($_ -match '\.exe .* sent=(\d+)$') { $sent += [int64]$Matches[1] } }
    "  E4 实际下载 $([math]::Round($sent/1MB,1)) MB / 整包 $([math]::Round($full/1MB,1)) MB($([math]::Round(100.0*$sent/[math]::Max($full,1),1))%)"
    # 第七跑:替身源按 GitHub 真实布局摆(latest/download/ 只有新版资产)。增量成立的前提是旧版 blockmap 从它自己的 release 取到。
    $v1s = $v1 -replace '(\.0)+$', ''
    $oldMapPath = "download/v$v1s/OpenDesign-$v1s-electron-setup.exe.blockmap"
    $oldMap = @(Get-Content $serveLog | Where-Object { $_.StartsWith("200 GET $oldMapPath ") })
    $miss = @(Get-Content $serveLog | Where-Object { $_ -match '^404 ' })
    V 'E4.oldmap 旧版 blockmap 从它自己那个 release 的路径取到' ($oldMap.Count -ge 1) "要 $oldMapPath;实到 $($oldMap -join ' | ')"
    V 'E4.delta 实际下载不到整包的 10%(增量成立)' ($full -gt 0 -and $sent -lt 0.1 * $full) "$sent / $full 字节;404:$($miss -join ' | ')"
    "  ---- 替身服务器请求 ----"; Get-Content $serveLog | Select-Object -First 60 | ForEach-Object { "    $_" }
    Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like "$Dir\*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Stop-Process -Id $srv.Id -Force -ErrorAction SilentlyContinue
}

# ---------------------------------------------------------------- 收尾:日志
New-Item -ItemType Directory -Force -Path "$OutDir\logs" | Out-Null
Copy-Item "$Data\Logs\*" "$OutDir\logs\" -Recurse -ErrorAction SilentlyContinue
"== 探针结束:FAIL $script:fail 条"
exit $(if ($script:fail) { 1 } else { 0 })
