# 应用内更新的端到端:在用完就扔的 Windows runner 上,把"点更新 → 自己关 → 换版本 → 自己回来"真跑五遍。
#
# track opendesign-in-app-update-install §3。设计与每个场景为什么这么注入:design.md「§3 Windows CI 怎么搭」。
#
# 🔴 这支脚本**只采事实、只做注入**,不下判断。判定在 update_e2e_verdict.py(本机有判据守着)。
#    理由是 windows-package-probe 付过的学费:本机没有 pwsh,写在 .ps1 里的判断谁都验不了。
#
# 🔴 这台机器上的 api.github.com / github.com **是假的**(hosts 指到本机替身,替身 CA 进了受信根)。
#    只在这台 runner 上这么做:业主的软件看不见任何测试 release,产品代码零改动。
#
# 退出码:五个场景的裁决收据全是 rc=0 ⇒ 0,否则 1。workflow 里另一步独立复核 verdicts.tsv。
# ⚠️ 帮手函数里**只用 Write-Host 打日志**:pwsh 函数往管道吐的任何东西都会混进返回值。

param(
    [Parameter(Mandatory = $true)] [string]$OldSetup,
    [Parameter(Mandatory = $true)] [string]$NewSetup,
    [Parameter(Mandatory = $true)] [string]$OldVersion,
    [Parameter(Mandatory = $true)] [string]$NewVersion,
    [Parameter(Mandatory = $true)] [string]$CertDir,
    [string]$OutDir = 'e2e-out'
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONIOENCODING = 'utf-8'
Add-Type -AssemblyName System.Windows.Forms, System.Drawing

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$OutDir     = (Resolve-Path $OutDir).Path
$OldSetup   = (Resolve-Path $OldSetup).Path
$NewSetup   = (Resolve-Path $NewSetup).Path
$CertDir    = (Resolve-Path $CertDir).Path
$Scripts    = $PSScriptRoot
$RepoRoot   = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Py         = (Get-Command python).Source

$InstallDir = "$env:LOCALAPPDATA\Programs\OpenDesign"
$NewDir     = "$InstallDir.new"
$OldDir     = "$InstallDir.old"
$DataRoot   = "$env:LOCALAPPDATA\OpenDesign"
$PortSpan   = 8766..8786
# 与 ds_update_apply.apply_update 写接力脚本的位置同一处:tempfile.gettempdir() 读的就是 TEMP。
$RelayPath  = Join-Path ([IO.Path]::GetTempPath()) 'opendesign-update-relay.cmd'
$ModeFile   = Join-Path $OutDir 'fake-mode.txt'
# 查更新走哪条来源(track opendesign-update-check-rate-limit,rl12):feed = 订阅源 + 清单、替身的 API 回 403 限流(默认,
# 业主 09-15 夜实测的那种网络);api = 订阅源回 503、API 正常(只有 e8 用)。替身每个请求现读这个文件。
$SourceFile = Join-Path $OutDir 'fake-source.txt'
$FakeLog    = Join-Path $OutDir 'fake-github.log'
$VerdictLog = Join-Path $OutDir 'verdicts.tsv'
# e6/e7 必须排在最后:它们把安装目录换成带空格的那个(Use-SpacedInstallDir),换过去就不换回来。
# e8 在 e1 之后、搬去带空格目录之前:它只换查更新的来源,装在原来的目录里。
# e9(真 WebView 里的倒计时整条链)同样装在原来的目录里,排在 e8 之后、搬去带空格目录之前。
$Expected   = @('e2', 'e3', 'e4', 'e5', 'e1', 'e8', 'e9', 'e6', 'e7')
# t33/t34 的真机半用的目录:**带空格、纯 ASCII**。不能带中文 —— runner 是英文 Windows(代码页 437),
# 非 ASCII 路径会被 t36 在动手之前拒掉(那是对的),e6 就测不到它要测的事。
$SpacedInstallDir = 'C:\OD e2e space\Programs\OpenDesign'
# e5 注入的版本号:新版起得来,但收口认不出它。
$InjectVersion = '0.0.1'
# ── 打开软件倒计时自动更新(track opendesign-auto-update-countdown)────────────────────
# 🔴 旧版一被拉起,窗口里的页面就会自己查到替身的新版、倒计时 10 秒、**自己发自动更新**。
#    e1~e8 是脚本自己按节奏发 apply、自己布置注入的,让产品抢跑 = 两条更新流程互相撞(攻题 #16)。
#    ⇒ 整支脚本默认把自动更新关掉(产品认这个环境变量,why_not="disabled");只有 e9 摘掉它,让真页面自己跑完整条链。
#    名字**不许以 DS_ 开头**:外壳 child_env 会把 DS_* 全部剥掉再交给 ds_web(bin/ds_shell_core.py)。
$AutoKnob   = 'OPENDESIGN_AUTO_UPDATE'
Set-Item -Path "Env:$AutoKnob" -Value 'off'
# 自动更新记账文件:「这个版本自动试过」。每个场景复位时清掉,场景之间互不污染。
$AutoRecord = "$DataRoot\Logs\auto-update-attempts.json"
# hosts 重定向的两个域名。**必须覆盖软件会碰的全部主机**:
# 查更新 = ds_update.releases_url() 的主机,下载 = 替身给的 browser_download_url 的主机。
# tests/test_update_e2e_harness.py 拿真的 ds_update 核这两个名字就是这里这两行。
$RedirectHosts = @('api.github.com', 'github.com')

function Note([string]$s) { Write-Host ("[{0:HH:mm:ss}] {1}" -f (Get-Date), $s) }

Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class W32 {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassNameW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern int GetWindowThreadProcessId(IntPtr h, out int pid);
  public static int Pid(IntPtr h) { int p; GetWindowThreadProcessId(h, out p); return p; }
  public static string Text(IntPtr h) { var sb = new StringBuilder(2048); GetWindowTextW(h, sb, 2048); return sb.ToString(); }
  public static string Cls(IntPtr h) { var sb = new StringBuilder(256); GetClassNameW(h, sb, 256); return sb.ToString(); }
}
"@

# ── 帮手:进程 / 目录 / 健康 ───────────────────────────────────────────

function Get-OurProcs {
    # 活树、.new、.old 三棵树都以 $InstallDir 开头 ⇒ 一个前缀全认。runner 自己的 python(替身、判定器)不在里面。
    return @(Get-CimInstance Win32_Process | Where-Object {
        $_.ExecutablePath -and $_.ExecutablePath.StartsWith($InstallDir, [StringComparison]::OrdinalIgnoreCase) })
}

function Get-RelayProcs {
    return @(Get-CimInstance Win32_Process -Filter "Name='cmd.exe'" |
        Where-Object { $_.CommandLine -like '*opendesign-update-relay*' })
}

function Stop-All {
    foreach ($p in (Get-RelayProcs)) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
    for ($i = 0; $i -lt 15; $i++) {
        $ps = Get-OurProcs
        if ($ps.Count -eq 0) { return }
        foreach ($p in $ps) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 1
    }
    Note "WARN: processes still alive under $InstallDir after 15s"
}

function Remove-Tree([string]$Path) {
    for ($i = 0; $i -lt 15 -and (Test-Path -LiteralPath $Path); $i++) {
        Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $Path) { Start-Sleep -Seconds 1 }
    }
    if (Test-Path -LiteralPath $Path) { throw "cannot remove $Path" }
}

function Get-Health {
    # 🔴 只问**正在监听**的端口(run 34848924198 量出来的):Windows 上连一个没人听的本机端口
    #    要 ~2 秒才失败,扫一整段 21 个端口 = 一次 42 秒 ⇒ 等接力脚本的轮询粒度被拖成 43 秒,
    #    "它活了多久"这个事实就量不出来了。
    $listening = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalPort -ge $PortSpan[0] -and $_.LocalPort -le $PortSpan[-1] } |
        ForEach-Object { $_.LocalPort } | Sort-Object -Unique)
    foreach ($p in $listening) {
        try {
            $h = Invoke-RestMethod -Uri "http://127.0.0.1:$p/api/health" -TimeoutSec 2 -NoProxy
            if ($h.version) { return @{ port = $p; version = "$($h.version)" } }
        } catch { }
    }
    return $null
}

# 等到 $Want 在答为止;$Want 为空 = 谁答都行。等不到就交出**最后看见的那个**(事实里要看得出是谁在答)。
function Wait-Health([string]$Want, [int]$Seconds) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $last = $null
    while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
        $h = Get-Health
        if ($h) {
            $last = $h
            if (-not $Want -or $h.version -eq $Want) { return $h }
        }
        Start-Sleep -Seconds 2
    }
    return $last
}

# 等接力脚本结束。顺带记下这期间**谁答过健康**(e5 要确认"坏新版真的起来过")。
function Wait-Relay([int]$Seconds) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $seen = $false
    # 🔴 第一次改名到底发生过没有(run 34860373658:e4 判了 OK,而接力脚本其实走的是"改名一直失败、放弃",
    #    根本没到它要测的"第二次改名失败 ⇒ 回滚"—— 两条路的终态长得一样)。.old 出现过 = 第一次改名做成了。
    $oldSeen = $false
    $versions = [Collections.Generic.List[string]]::new()
    while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
        $running = (Get-RelayProcs).Count -gt 0
        # 🔴 这一行必须在 if/elseif 链**之外**(run 34863116162):上一版插在 `if ($running)` 和 `elseif` 之间,
        #    elseif 就挂到了这一行上 ⇒ 没有 .old 时直接 `elseif ($seen) { break }` ⇒ 等了 0 秒就走,五个场景全被量早了。
        if (Test-Path -LiteralPath $OldDir) { $oldSeen = $true }
        if ($running) { $seen = $true }
        elseif ($seen) { break }
        elseif ($sw.Elapsed.TotalSeconds -gt 30) { break }      # 30 秒都没出现过 = 没起来
        $h = Get-Health
        if ($h -and -not $versions.Contains($h.version)) { $versions.Add($h.version) }
        Start-Sleep -Seconds 1
    }
    $ended = (Get-RelayProcs).Count -eq 0
    Note ("relay seen=$seen ended=$ended after {0:N0}s; versions answering meanwhile: {1}" -f $sw.Elapsed.TotalSeconds, ($versions -join ','))
    return @{ relay = @{ seen = $seen; ended = $ended; seconds = [Math]::Round($sw.Elapsed.TotalSeconds, 1); old_seen = $oldSeen };
              versions = @($versions) }
}

function Get-Manifest([string]$Dir, [string]$Name) {
    $out = Join-Path $OutDir "manifest-$Name.json"
    $line = & $Py (Join-Path $Scripts 'fake_github.py') manifest $Dir $out
    if ($LASTEXITCODE -ne 0) { Note "manifest failed for $Dir (rc=$LASTEXITCODE)"; return $null }
    $digest = ("$line".Trim() -split ' ')[0]
    if ($digest -eq 'MISSING') { return $null }
    return $digest
}

function Show-ManifestDiff([string]$A, [string]$B) {
    $pa = Join-Path $OutDir "manifest-$A.json"; $pb = Join-Path $OutDir "manifest-$B.json"
    if ((Test-Path $pa) -and (Test-Path $pb)) {
        Note "manifest diff $A -> $B :"
        & $Py (Join-Path $Scripts 'fake_github.py') diff $pa $pb | ForEach-Object { Write-Host "    $_" }
    }
}

function Get-LiveVersion {
    $f = Join-Path $InstallDir 'ds\版本号.txt'
    if (Test-Path -LiteralPath $f) { return (Get-Content -LiteralPath $f -Raw -Encoding utf8).Trim() }
    return $null
}

# ── 帮手:业主从哪儿打开它(t26 的真机半)──────────────────────────────
# 更新之后,注册表里的"装在哪"、卸载条目、开始菜单和桌面快捷方式都必须还指着**活树那个路径**。
# 更新档装进的是 .new,两次改名后那个路径不存在 ⇒ 指过去 = 业主的图标打不开。

# 🔴 快捷方式指向哪,用 IShellLinkW(Unicode)读,不用 WScript.Shell(run 34851863087 量出来的):
#    英文 Windows 上 WScript.Shell 对"卸载 OpenDesign.lnk"(目标 卸载.exe)读回空串,
#    五个场景因此全红 —— 那是量具读不了中文,不是快捷方式指错了。读不出来照样判红,不放宽。
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
[ComImport, Guid("000214F9-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IShellLinkWPath {
  void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszFile, int cch, IntPtr pfd, uint fFlags);
}
[ComImport, Guid("0000010b-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IPersistFileLoad {
  void GetClassID(out Guid pClassID);
  [PreserveSig] int IsDirty();
  void Load([MarshalAs(UnmanagedType.LPWStr)] string pszFileName, uint dwMode);
}
[ComImport, Guid("00021401-0000-0000-C000-000000000046")] public class ShellLinkCo {}
public static class Lnk {
  public static string Target(string path) {
    object link = new ShellLinkCo();
    ((IPersistFileLoad)link).Load(path, 0);
    var sb = new StringBuilder(1024);
    ((IShellLinkWPath)link).GetPath(sb, sb.Capacity, IntPtr.Zero, 0);
    return sb.ToString();
  }
}
"@

function Get-Pointers {
    $app = Get-ItemProperty -LiteralPath 'HKCU:\Software\OpenDesign' -ErrorAction SilentlyContinue
    $un  = Get-ItemProperty -LiteralPath 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\OpenDesign' -ErrorAction SilentlyContinue
    $run = Get-ItemProperty -LiteralPath 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -ErrorAction SilentlyContinue
    $links = [ordered]@{}
    $programs = [Environment]::GetFolderPath('Programs')
    $desktop  = [Environment]::GetFolderPath('Desktop')
    foreach ($lnk in @("$programs\OpenDesign\OpenDesign.lnk", "$programs\OpenDesign\卸载 OpenDesign.lnk", "$desktop\OpenDesign.lnk")) {
        if (Test-Path -LiteralPath $lnk) {
            try { $links[$lnk] = [Lnk]::Target($lnk) } catch { $links[$lnk] = "unreadable: $($_.Exception.Message)" }
        }
    }
    return @{
        live        = $InstallDir
        install_dir = $app.InstallDir
        uninstall   = @{ InstallLocation = $un.InstallLocation; UninstallString = $un.UninstallString
                         DisplayIcon = $un.DisplayIcon; DisplayVersion = $un.DisplayVersion }
        autorun     = $run.OpenDesign
        shortcuts   = $links
    }
}

# ── 帮手:档案标记(死线 t13 的真机半)──────────────────────────────────

$MarkerDirs = @('Data', 'UserData')
function Seed-Markers {
    foreach ($sub in $MarkerDirs) {
        $dir = Join-Path $DataRoot "$sub\e2e-档案标记"
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
        $bytes = [byte[]]::new(262144)
        # 不用静态 Fill():它的参数是 Span<byte>,pwsh 不会把 byte[] 自动转过去。
        [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
        [IO.File]::WriteAllBytes((Join-Path $dir '客户资料-e2e.bin'), $bytes)
        [IO.File]::WriteAllText((Join-Path $dir '项目备忘-e2e.md'), "# e2e 标记 $([Guid]::NewGuid())")
    }
}

function Get-Markers {
    $m = [ordered]@{}
    foreach ($sub in $MarkerDirs) {
        $dir = Join-Path $DataRoot "$sub\e2e-档案标记"
        if (Test-Path -LiteralPath $dir) {
            foreach ($file in (Get-ChildItem -LiteralPath $dir -File | Sort-Object Name)) {
                $m["$sub/$($file.Name)"] = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLower()
            }
        }
    }
    return $m
}

# ── 帮手:替身、端点、窗口、收据 ───────────────────────────────────────

function Get-FakeLogCount {
    if (Test-Path -LiteralPath $FakeLog) { return @(Get-Content -LiteralPath $FakeLog).Count }
    return 0
}

function Get-FakeLogSince([int]$Skip) {
    $out = @()
    if (Test-Path -LiteralPath $FakeLog) {
        foreach ($line in (@(Get-Content -LiteralPath $FakeLog) | Select-Object -Skip $Skip)) {
            try { $out += , ($line | ConvertFrom-Json -AsHashtable) } catch { }
        }
    }
    return , $out
}

function Invoke-Check($Port) {
    try { return (Invoke-RestMethod -Uri "http://127.0.0.1:$Port/api/update/check?force=1" -TimeoutSec 90 -NoProxy) }
    catch { return @{ _error = "$($_.Exception.Message)" } }
}

function Invoke-Apply($Port) {
    # 和界面上那个按钮发的是同一个请求(按钮自身的接线由 u27~u37 管)。
    try {
        return (Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$Port/api/update/apply" `
                -TimeoutSec 900 -NoProxy -ContentType 'application/json' -Body '{}')
    } catch { return @{ _error = "$($_.Exception.Message)" } }
}

function Save-Screen([string]$Path) {
    try {
        $b = [System.Windows.Forms.SystemInformation]::VirtualScreen
        $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        $g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
        $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
        $g.Dispose(); $bmp.Dispose()
    } catch { Note "screenshot failed: $($_.Exception.Message)" }
}

$script:wins = @()
function Get-AllWindows {
    $script:wins = @()
    $cb = [W32+EnumProc]{ param($h, $l)
        if ([W32]::IsWindowVisible($h)) {
            $t = [W32]::Text($h)
            if ($t) {
                $script:wins += @{ title = $t; cls = [W32]::Cls($h)
                                   proc = (Get-Process -Id ([W32]::Pid($h)) -ErrorAction SilentlyContinue).ProcessName }
            }
        }
        return $true }
    [void][W32]::EnumWindows($cb, [IntPtr]::Zero)
    return , $script:wins
}

# 窗口在不在由 bin/probe_verdict.py 的 window 判(报错框和真窗口按窗口类分),等到它说 OK 或到点为止。
function Wait-Window([int]$Seconds) {
    $judge = Join-Path $RepoRoot 'bin\probe_verdict.py'
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        Start-Sleep -Seconds 4
        $procs = @(Get-Process | Where-Object { $_.MainWindowTitle } |
                   ForEach-Object { "$($_.ProcessName):「$($_.MainWindowTitle)」" })
        $facts = @{ wins = (Get-AllWindows); procs = $procs }
        $json = $facts | ConvertTo-Json -Depth 6 -Compress -EscapeHandling EscapeNonAscii
        $said = $json | & $Py $judge window 2>$null
        $rc = $LASTEXITCODE
        Note "window check rc=$rc : $said"
    } while ($rc -ne 0 -and (Get-Date) -lt $deadline)
    return $facts
}

function Copy-Relay([string]$Kind) {
    if (Test-Path -LiteralPath $RelayPath) {
        Copy-Item -LiteralPath $RelayPath -Destination (Join-Path $OutDir "relay-$Kind.cmd") -Force
    }
}

function Judge([string]$Kind, $Facts) {
    $factsPath = Join-Path $OutDir "facts-$Kind.json"
    $Facts | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $factsPath -Encoding utf8
    $errPath = Join-Path $OutDir "judge-$Kind.err"
    $said = & $Py (Join-Path $Scripts 'update_e2e_verdict.py') $Kind $factsPath 2> $errPath
    $rc = $LASTEXITCODE
    $line = ("$said" -replace "`r?`n", ' ').Trim()
    if (-not $line) { $line = "FAIL $Kind - judge printed nothing"; if ($rc -eq 0) { $rc = 2 } }
    ("{0}`t{1}`t{2}" -f $rc, $Kind, ($line -replace "`t", ' ')) | Add-Content -LiteralPath $VerdictLog -Encoding utf8
    Write-Host "VERDICT $Kind rc=$rc : $line"
}

function Finish-Scenario([string]$Kind, $Facts) {
    Save-Screen (Join-Path $OutDir "$Kind-end.png")
    if (Test-Path -LiteralPath "$DataRoot\Logs") {
        Copy-Item -LiteralPath "$DataRoot\Logs" -Destination (Join-Path $OutDir "logs-$Kind") -Recurse -Force
    }
    Judge $Kind $Facts
}

# ── 场景前:重装旧版并拉起 ──────────────────────────────────────────────

function Reset-Old([switch]$NoLaunch) {
    Note "reset: stop everything, wipe install trees, install $OldVersion"
    Stop-All
    Remove-Item -LiteralPath $RelayPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $AutoRecord -Force -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $AutoRecord) { throw "cannot remove $AutoRecord" }
    foreach ($d in @($InstallDir, $NewDir, $OldDir)) { Remove-Tree $d }
    # 🔴 显式 /D=:更新档(修好之前)会把"上次装在哪"写成 .new(run 34848924198 就是这么把
    #    e4/e5/e1 带崩的)。场景之间要互不污染,就不能让上一个场景写坏的注册表决定这次装哪。
    #    注册表**有没有被写坏**是每个场景自己的 pointers 事实,不靠这里藏起来。
    $ip = Start-Process -FilePath $OldSetup -ArgumentList "/S /D=$InstallDir" -PassThru
    $null = $ip.Handle          # 不先碰 Handle,进程退出后 ExitCode 可能读成 null(pwsh 的老坑)
    if ($ip.WaitForExit(240000)) { $rc = $ip.ExitCode }
    else { Stop-Process -Id $ip.Id -Force -ErrorAction SilentlyContinue; $rc = 'timeout' }
    Note "reset: installer rc=$rc"
    if ($NoLaunch) { return @{ installer_rc = $rc; health = $null } }
    Start-Process -FilePath "$InstallDir\OpenDesign.exe" | Out-Null
    $h = Wait-Health $OldVersion 180
    Note "reset: health = $($h | ConvertTo-Json -Compress)"
    return @{ installer_rc = $rc; health = $h }
}

function New-Facts([switch]$NoLaunch) {
    $f = [ordered]@{ old_version = $OldVersion; new_version = $NewVersion }
    $f.source = (Get-Content -LiteralPath $SourceFile -Raw).Trim()
    $f.fake_log_start = Get-FakeLogCount
    $f.reset = Reset-Old -NoLaunch:$NoLaunch
    $f.markers_before = Get-Markers
    return $f
}

# ── 场景 ─────────────────────────────────────────────────────────────

function Run-e2 {
    Set-Content -LiteralPath $ModeFile -Value 'corrupt'
    $f = New-Facts
    $port = $f.reset.health.port
    $f.live_before = Get-Manifest $InstallDir 'e2-before'
    $f.check = Invoke-Check $port
    $f.apply = Invoke-Apply $port
    Note "e2 apply -> $($f.apply | ConvertTo-Json -Compress)"
    Start-Sleep -Seconds 3
    $f.live_after = Get-Manifest $InstallDir 'e2-after'
    Show-ManifestDiff 'e2-before' 'e2-after'
    $f.new_exists = Test-Path -LiteralPath $NewDir
    $f.old_exists = Test-Path -LiteralPath $OldDir
    $f.health_after = Wait-Health $OldVersion 30
    $f.pointers = Get-Pointers
    $f.markers_after = Get-Markers
    $f.fake_log = Get-FakeLogSince $f.fake_log_start
    Finish-Scenario 'e2' $f
}

function Run-e3 {
    Set-Content -LiteralPath $ModeFile -Value 'normal'
    $f = New-Facts
    $port = $f.reset.health.port
    $f.live_before = Get-Manifest $InstallDir 'e3-before'
    $f.check = Invoke-Check $port
    $lock = $null
    $sentinel = Join-Path $InstallDir 'ds\bin\ds_shell.py'
    try {
        $lock = [IO.File]::Open($sentinel, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::None)
        $f.inject = @{ landed = $true; detail = 'holding live ds\bin\ds_shell.py with FileShare.None' }
    } catch {
        $f.inject = @{ landed = $false; detail = "could not lock sentinel: $($_.Exception.Message)" }
    }
    $f.apply = Invoke-Apply $port
    Note "e3 apply -> $($f.apply | ConvertTo-Json -Compress)"
    Copy-Relay 'e3'
    $w = Wait-Relay 420
    $f.relay = $w.relay
    $f.seen_versions = $w.versions
    $f.health_after = Wait-Health '' 10                 # 只是读数:它自己回来了吗
    Stop-All                                            # 放手之前先把一切停住,免得放手那一刻接力脚本接着往下走
    if ($lock) { $lock.Dispose() }
    $f.live_after = Get-Manifest $InstallDir 'e3-after' # 必须在放手之后:锁着的文件读不了
    Show-ManifestDiff 'e3-before' 'e3-after'
    $f.new_exists = Test-Path -LiteralPath $NewDir
    $f.old_exists = Test-Path -LiteralPath $OldDir
    Start-Process -FilePath "$InstallDir\OpenDesign.exe" -ErrorAction SilentlyContinue | Out-Null
    $f.relaunch = @{ health = (Wait-Health $OldVersion 180) }
    $f.pointers = Get-Pointers
    $f.markers_after = Get-Markers
    $f.fake_log = Get-FakeLogSince $f.fake_log_start
    Finish-Scenario 'e3' $f
}

# e4 / e5 的注入要赶在"新树装好(接力脚本已写出)"和"第二次改名"之间 ⇒ 另开线程盯着。
# 打中的判据:注入时 .new 这个路径还在 —— 第二次改名之后它就不存在了,打晚了一定打不中。
$InjectBlock = {
    param($relay, $newDir, $flagDir, $mode, $injectVersion)
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $result = @{ landed = $false; detail = 'relay script never appeared within 900s' }
    $fs = $null
    while ($sw.Elapsed.TotalSeconds -lt 900) {
        if (Test-Path -LiteralPath $relay) {
            try {
                if ($mode -eq 'lock') {
                    $target = Join-Path $newDir 'ds\bin\ds_shell.py'
                    $fs = [IO.File]::Open($target, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::None)
                    $result = @{ landed = $true; detail = ("locked {0} at {1:N1}s" -f $target, $sw.Elapsed.TotalSeconds) }
                } else {
                    $target = Join-Path $newDir 'ds\bin\ds_web.py'
                    $txt = [IO.File]::ReadAllText($target)
                    $patched = [regex]::Replace($txt, '(?m)^VERSION = "[^"]+"', "VERSION = `"$injectVersion`"")
                    if ($patched -eq $txt) { throw 'VERSION line not found in new ds_web.py' }
                    [IO.File]::WriteAllText($target, $patched)
                    $result = @{ landed = $true; version = $injectVersion
                                 detail = ("patched VERSION={0} in {1} at {2:N1}s" -f $injectVersion, $target, $sw.Elapsed.TotalSeconds) }
                }
            } catch {
                $result = @{ landed = $false; detail = ("inject failed at {0:N1}s: {1}" -f $sw.Elapsed.TotalSeconds, $_.Exception.Message) }
            }
            break
        }
        Start-Sleep -Milliseconds 50
    }
    $result | ConvertTo-Json -Compress | Set-Content -LiteralPath (Join-Path $flagDir 'inject.json') -Encoding utf8
    if ($fs) {
        $release = Join-Path $flagDir 'release'
        while (-not (Test-Path -LiteralPath $release)) { Start-Sleep -Milliseconds 200 }
        $fs.Dispose()
    }
}

function Run-Rollback([string]$Kind, [string]$Mode) {
    Set-Content -LiteralPath $ModeFile -Value 'normal'
    $f = New-Facts
    $port = $f.reset.health.port
    $f.live_before = Get-Manifest $InstallDir "$Kind-before"
    $f.check = Invoke-Check $port
    $flagDir = Join-Path $OutDir "inject-$Kind"
    New-Item -ItemType Directory -Force -Path $flagDir | Out-Null
    Remove-Item -LiteralPath $RelayPath -Force -ErrorAction SilentlyContinue
    $job = Start-ThreadJob -ScriptBlock $InjectBlock -ArgumentList $RelayPath, $NewDir, $flagDir, $Mode, $InjectVersion
    $f.apply = Invoke-Apply $port
    Note "$Kind apply -> $($f.apply | ConvertTo-Json -Compress)"
    Copy-Relay $Kind
    $w = Wait-Relay 600
    $f.relay = $w.relay
    $f.seen_versions = $w.versions
    $f.health_after = Wait-Health $OldVersion 180
    $injectFile = Join-Path $flagDir 'inject.json'
    $f.inject = if (Test-Path -LiteralPath $injectFile) {
        Get-Content -LiteralPath $injectFile -Raw | ConvertFrom-Json -AsHashtable
    } else { @{ landed = $false; detail = 'injector wrote no record' } }
    Note "$Kind inject -> $($f.inject | ConvertTo-Json -Compress)"
    $f.live_version_after = Get-LiveVersion
    $f.old_exists = Test-Path -LiteralPath $OldDir
    $f.new_exists = Test-Path -LiteralPath $NewDir
    $f.nested_old_exists = Test-Path -LiteralPath (Join-Path $InstallDir 'OpenDesign.old')
    $f.live_after = Get-Manifest $InstallDir "$Kind-after"
    Show-ManifestDiff "$Kind-before" "$Kind-after"
    New-Item -ItemType File -Force -Path (Join-Path $flagDir 'release') | Out-Null
    Wait-Job $job -Timeout 30 | Out-Null
    Receive-Job $job -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "    injector: $_" }
    Remove-Job $job -Force
    $f.pointers = Get-Pointers
    $f.markers_after = Get-Markers
    $f.fake_log = Get-FakeLogSince $f.fake_log_start
    Finish-Scenario $Kind $f
}

function Run-e4 { Run-Rollback 'e4' 'lock' }
function Run-e5 { Run-Rollback 'e5' 'patch' }

function Run-FullUpdate([string]$Kind) {
    Set-Content -LiteralPath $ModeFile -Value 'normal'
    $f = New-Facts
    $port = $f.reset.health.port
    $f.check = Invoke-Check $port
    $f.apply = Invoke-Apply $port
    Note "$Kind apply -> $($f.apply | ConvertTo-Json -Compress)"
    Copy-Relay $Kind
    $w = Wait-Relay 600
    $f.relay = $w.relay
    $f.seen_versions = $w.versions
    $f.health_after = Wait-Health $NewVersion 180
    $f.window = Wait-Window 90
    foreach ($s in 0, 20) {
        Start-Sleep -Seconds $s
        Save-Screen (Join-Path $OutDir ("{0}-after-update-{1}s.png" -f $Kind, $s))
    }
    # 截完 20 秒那张之后**再问一次**(切片评审 GPT 腿 #9):新版起来又退出,上面那次 health_after 看不出来。
    $f.health_final = Get-Health
    $f.live_version_after = Get-LiveVersion
    $f.old_exists = Test-Path -LiteralPath $OldDir
    $f.new_exists = Test-Path -LiteralPath $NewDir
    $f.pointers = Get-Pointers
    $f.markers_after = Get-Markers
    $f.fake_log = Get-FakeLogSince $f.fake_log_start
    Finish-Scenario $Kind $f
}

function Run-e1 { Run-FullUpdate 'e1' }

# e8 —— rl12 的备路半:替身的订阅源回 503、API 正常 ⇒ 软件先试订阅源、再问 API,照样完整更新。
# 🔴 切回 feed 必须在 finally 里:e8 中途炸了,后面的 e6/e7 不许留在 api 模式(那样它们就测不到新路)。
function Run-e8 {
    Set-Content -LiteralPath $SourceFile -Value 'api'
    try { Run-FullUpdate 'e8' }
    finally { Set-Content -LiteralPath $SourceFile -Value 'feed' }
}

# e9 —— 真 WebView 里的倒计时整条链(track opendesign-auto-update-countdown,aw2)。
# **脚本一次 apply 都不发**:摘掉关自动更新的环境变量,拉起旧版,由窗口里的页面自己查到新版、倒计时 10 秒、自己发自动更新。
# 注入同 e5(新版起得来但认不出 ⇒ 回滚),于是旧版被接力脚本**重新拉起**,页面再加载一次 ——
# 这一次:不许再倒计时、不许再下载;查更新必须 attempted + recent_failure(横幅在截图里,不进裁决)。
# 这是「同一版本失败一次不再自动试」跨一次真实回滚 + 真页面重开仍然成立的唯一证据,
# 也是「装出来的真桌面版里,打开软件那次查更新真的会开倒计时」的唯一证据(攻题 #6/#7)。
function Wait-RelayStart([int]$Seconds) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
        if ((Get-RelayProcs).Count -gt 0) { return [Math]::Round($sw.Elapsed.TotalSeconds, 1) }
        Start-Sleep -Milliseconds 500
    }
    return $null
}

function Run-e9 {
    Set-Content -LiteralPath $ModeFile -Value 'normal'
    $f = New-Facts -NoLaunch
    $f.live_before = Get-Manifest $InstallDir 'e9-before'
    $flagDir = Join-Path $OutDir 'inject-e9'
    New-Item -ItemType Directory -Force -Path $flagDir | Out-Null
    Remove-Item -LiteralPath $RelayPath -Force -ErrorAction SilentlyContinue
    $job = Start-ThreadJob -ScriptBlock $InjectBlock -ArgumentList $RelayPath, $NewDir, $flagDir, 'patch', $InjectVersion
    Remove-Item -Path "Env:$AutoKnob" -ErrorAction SilentlyContinue
    try {
        $f.auto_knob_at_launch = "$([Environment]::GetEnvironmentVariable($AutoKnob))"
        Start-Process -FilePath "$InstallDir\OpenDesign.exe" | Out-Null
        $f.launch_health = Wait-Health $OldVersion 180
        Save-Screen (Join-Path $OutDir 'e9-launched.png')
        # 页面加载 + 查更新 + 10 秒倒计时 + 下载 + 静默装进 .new,之后接力脚本才出现。
        $f.relay_started_after = Wait-RelayStart 600
        Note "e9 relay started after $($f.relay_started_after)s (nobody but the page asked for it)"
        Copy-Relay 'e9'
        $w = Wait-Relay 600
        $f.relay = $w.relay
        $f.seen_versions = $w.versions
        $f.health_after = Wait-Health $OldVersion 180
        $injectFile = Join-Path $flagDir 'inject.json'
        $f.inject = if (Test-Path -LiteralPath $injectFile) {
            Get-Content -LiteralPath $injectFile -Raw | ConvertFrom-Json -AsHashtable
        } else { @{ landed = $false; detail = 'injector wrote no record' } }
        $f.live_version_after = Get-LiveVersion
        $f.old_exists = Test-Path -LiteralPath $OldDir
        $f.new_exists = Test-Path -LiteralPath $NewDir
        $f.nested_old_exists = Test-Path -LiteralPath (Join-Path $InstallDir 'OpenDesign.old')
        $f.live_after = Get-Manifest $InstallDir 'e9-after'
        Show-ManifestDiff 'e9-before' 'e9-after'
        New-Item -ItemType File -Force -Path (Join-Path $flagDir 'release') | Out-Null
        Wait-Job $job -Timeout 30 | Out-Null
        Receive-Job $job -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "    injector: $_" }
        Remove-Job $job -Force
        # 旧版被拉起之后,给页面足够时间:加载 + 查更新 + (要是还倒计时的话)10 秒 + 开始下载。
        # 判的是**整个场景只下载过一次**(fake_log)+ 这会儿没有第二个接力脚本 —— 不在这里取分界点,
        # 免得页面在分界点之前就开始了第二次下载而被漏数。
        $f.window_after = Wait-Window 60
        Start-Sleep -Seconds 45
        Save-Screen (Join-Path $OutDir 'e9-after-rollback.png')
        $f.relay_again = (Get-RelayProcs).Count -gt 0
        $p2 = if ($f.health_after -and $f.health_after.port) { $f.health_after.port } else { $null }
        $f.check_after = if ($p2) { Invoke-Check $p2 } else { @{ _error = 'old app not answering after rollback' } }
        Note "e9 after rollback: auto_update=$($f.check_after.auto_update | ConvertTo-Json -Compress)"
    } finally {
        Set-Item -Path "Env:$AutoKnob" -Value 'off'
    }
    $f.pointers = Get-Pointers
    $f.markers_after = Get-Markers
    $f.fake_log = Get-FakeLogSince $f.fake_log_start
    Finish-Scenario 'e9' $f
}

# 把后面的场景搬到带空格的安装目录。先按**原来的**前缀把还在跑的都停掉:换了前缀,Get-OurProcs 就认不出它们了。
function Use-SpacedInstallDir {
    if ($script:InstallDir -eq $SpacedInstallDir) { return }
    Stop-All
    $script:InstallDir = $SpacedInstallDir
    $script:NewDir     = "$SpacedInstallDir.new"
    $script:OldDir     = "$SpacedInstallDir.old"
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $SpacedInstallDir) | Out-Null
    Note "install dir is now '$SpacedInstallDir'"
}

# e6 —— t33 的真机半:装在带空格的目录里,点更新照样完整更新。
function Run-e6 {
    Use-SpacedInstallDir
    Run-FullUpdate 'e6'
}

# e7 —— t33/t34 的真 NSIS 半:把修 t33 之前 python 真正发出去的那条参数(带空格的 /D= 被 list2cmdline 加了引号)
# 原样交给新版安装器。NSIS 不认带引号的 /D= ⇒ 安装目录退回注册表 = 活树 ⇒ 更新档守卫必须 rc=3 拒装。
# 旧版故意开着:修之前那一幕就是"软件开着、python 调安装器"。
function Run-e7 {
    Use-SpacedInstallDir
    $f = New-Facts
    $f.live_before = Get-Manifest $InstallDir 'e7-before'
    $f.cmdline = '/S /UPDATE "/D={0}"' -f $NewDir
    Note "e7 new installer args: $($f.cmdline)"
    $ip = Start-Process -FilePath $NewSetup -ArgumentList $f.cmdline -PassThru
    $null = $ip.Handle
    if ($ip.WaitForExit(240000)) { $f.installer_rc = $ip.ExitCode }
    else { Stop-Process -Id $ip.Id -Force -ErrorAction SilentlyContinue; $f.installer_rc = 'timeout' }
    Note "e7 installer rc=$($f.installer_rc)"
    Start-Sleep -Seconds 3
    $f.new_exists = Test-Path -LiteralPath $NewDir
    $f.health_after = Wait-Health $OldVersion 30
    $f.live_after = Get-Manifest $InstallDir 'e7-after'
    Show-ManifestDiff 'e7-before' 'e7-after'
    $f.pointers = Get-Pointers
    $f.markers_after = Get-Markers
    Finish-Scenario 'e7' $f
}

# ── 主流程 ──────────────────────────────────────────────────────────────

Note "old=$OldVersion new=$NewVersion"
$Repo = (& $Py -c "import sys; sys.path.insert(0, r'$RepoRoot\bin'); import ds_update; print(ds_update.REPO)").Trim()
Note "repo the product asks about: $Repo"

# 1. 让这台机器信替身的 CA
# certutil 而不是 Import-Certificate:后者住在 Windows PowerShell 的 PKI 模块里,pwsh 7 能不能直接加载要赌。
$said = certutil -addstore -f Root (Join-Path $CertDir 'ca.crt') 2>&1
if ($LASTEXITCODE -ne 0) { throw "certutil could not trust the stand-in CA (rc=$LASTEXITCODE): $said" }

# 2. hosts:两个域名指到本机
$hostsFile = "$env:SystemRoot\System32\drivers\etc\hosts"
$lines = @('') + @($RedirectHosts | ForEach-Object { "127.0.0.1 $_" })
Add-Content -LiteralPath $hostsFile -Value $lines -Encoding ascii
ipconfig /flushdns | Out-Null

# 3. 起替身
Set-Content -LiteralPath $ModeFile -Value 'normal'
Set-Content -LiteralPath $SourceFile -Value 'feed'
$fakeArgs = '"{0}" serve --repo {1} --version {2} --setup "{3}" --cert "{4}" --key "{5}" --mode-file "{6}" --log "{7}" --source-file "{8}"' -f `
    (Join-Path $Scripts 'fake_github.py'), $Repo, $NewVersion, $NewSetup,
    (Join-Path $CertDir 'server.crt'), (Join-Path $CertDir 'server.key'), $ModeFile, $FakeLog, $SourceFile
$fake = Start-Process -FilePath $Py -ArgumentList $fakeArgs -PassThru -NoNewWindow `
    -RedirectStandardOutput (Join-Path $OutDir 'fake-github.out') -RedirectStandardError (Join-Path $OutDir 'fake-github.err')
Start-Sleep -Seconds 3
try {
    # feed 模式下替身的 API 故意回 403,所以这里问订阅源(和软件主路同一个主机、同一张证书)。
    $r = Invoke-WebRequest -Uri "https://github.com/$Repo/releases.atom" -TimeoutSec 20 -UseBasicParsing
    Note "stand-in reachable over TLS from pwsh: releases.atom http=$($r.StatusCode)"
} catch { Note "WARN: stand-in NOT reachable from pwsh: $($_.Exception.Message)" }

# 4. 首装一次,种档案标记;顺带用**装出来的那个 python** 走一遍产品的真路径(DNS→TLS→urllib)
Reset-Old | Out-Null
Seed-Markers
$probe = "import sys; sys.path.insert(0, r'$InstallDir\ds\bin'); import ds_update; " +
         "print(ds_update.check_for_update(sys.argv[1]))"
$said = & "$InstallDir\python\python.exe" -c $probe $OldVersion 2>&1
Note "product python sees: $said"

foreach ($s in $Expected) {
    Note "==================== scenario $s ===================="
    try { & "Run-$s" }
    catch {
        $msg = ("{0} @ {1}" -f $_.Exception.Message, $_.InvocationInfo.PositionMessage) -replace "`t|`r|`n", ' '
        Write-Host "scenario $s crashed: $msg"
        ("2`t{0}`tFAIL {0} - harness crashed: {1}" -f $s, $msg) | Add-Content -LiteralPath $VerdictLog -Encoding utf8
        Save-Screen (Join-Path $OutDir "$s-crash.png")
    }
}

Stop-All
if ($fake -and -not $fake.HasExited) { Stop-Process -Id $fake.Id -Force -ErrorAction SilentlyContinue }

"" ; "==================== RECEIPTS ===================="
$receipts = if (Test-Path -LiteralPath $VerdictLog) { @(Get-Content -LiteralPath $VerdictLog) } else { @() }
$receipts | ForEach-Object { "  $_" }
$bad = @()
foreach ($k in $Expected) {
    $mine = @($receipts | Where-Object { ($_ -split "`t")[1] -eq $k })
    if ($mine.Count -ne 1) { $bad += "$k has $($mine.Count) receipt line(s)"; continue }
    if (($mine[0] -split "`t")[0] -ne '0') { $bad += "$k rc=$(($mine[0] -split "`t")[0])" }
}
if ($bad.Count) { "RED: $($bad -join '; ')"; exit 1 }
"all $($Expected.Count) scenarios OK"
exit 0
