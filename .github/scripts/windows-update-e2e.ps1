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
$FakeLog    = Join-Path $OutDir 'fake-github.log'
$VerdictLog = Join-Path $OutDir 'verdicts.tsv'
$Expected   = @('e2', 'e3', 'e4', 'e5', 'e1')
# e5 注入的版本号:新版起得来,但收口认不出它。
$InjectVersion = '0.0.1'
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
    $versions = [Collections.Generic.List[string]]::new()
    while ($sw.Elapsed.TotalSeconds -lt $Seconds) {
        $running = (Get-RelayProcs).Count -gt 0
        if ($running) { $seen = $true }
        elseif ($seen) { break }
        elseif ($sw.Elapsed.TotalSeconds -gt 30) { break }      # 30 秒都没出现过 = 没起来
        $h = Get-Health
        if ($h -and -not $versions.Contains($h.version)) { $versions.Add($h.version) }
        Start-Sleep -Seconds 1
    }
    $ended = (Get-RelayProcs).Count -eq 0
    Note ("relay seen=$seen ended=$ended after {0:N0}s; versions answering meanwhile: {1}" -f $sw.Elapsed.TotalSeconds, ($versions -join ','))
    return @{ relay = @{ seen = $seen; ended = $ended; seconds = [Math]::Round($sw.Elapsed.TotalSeconds, 1) };
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

function Reset-Old {
    Note "reset: stop everything, wipe install trees, install $OldVersion"
    Stop-All
    Remove-Item -LiteralPath $RelayPath -Force -ErrorAction SilentlyContinue
    foreach ($d in @($InstallDir, $NewDir, $OldDir)) { Remove-Tree $d }
    # 🔴 显式 /D=:更新档(修好之前)会把"上次装在哪"写成 .new(run 34848924198 就是这么把
    #    e4/e5/e1 带崩的)。场景之间要互不污染,就不能让上一个场景写坏的注册表决定这次装哪。
    #    注册表**有没有被写坏**是每个场景自己的 pointers 事实,不靠这里藏起来。
    $ip = Start-Process -FilePath $OldSetup -ArgumentList "/S /D=$InstallDir" -PassThru
    $null = $ip.Handle          # 不先碰 Handle,进程退出后 ExitCode 可能读成 null(pwsh 的老坑)
    if ($ip.WaitForExit(240000)) { $rc = $ip.ExitCode }
    else { Stop-Process -Id $ip.Id -Force -ErrorAction SilentlyContinue; $rc = 'timeout' }
    Note "reset: installer rc=$rc"
    Start-Process -FilePath "$InstallDir\OpenDesign.exe" | Out-Null
    $h = Wait-Health $OldVersion 180
    Note "reset: health = $($h | ConvertTo-Json -Compress)"
    return @{ installer_rc = $rc; health = $h }
}

function New-Facts {
    $f = [ordered]@{ old_version = $OldVersion; new_version = $NewVersion }
    $f.fake_log_start = Get-FakeLogCount
    $f.reset = Reset-Old
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

function Run-e1 {
    Set-Content -LiteralPath $ModeFile -Value 'normal'
    $f = New-Facts
    $port = $f.reset.health.port
    $f.check = Invoke-Check $port
    $f.apply = Invoke-Apply $port
    Note "e1 apply -> $($f.apply | ConvertTo-Json -Compress)"
    Copy-Relay 'e1'
    $w = Wait-Relay 600
    $f.relay = $w.relay
    $f.seen_versions = $w.versions
    $f.health_after = Wait-Health $NewVersion 180
    $f.window = Wait-Window 90
    foreach ($s in 0, 20) {
        Start-Sleep -Seconds $s
        Save-Screen (Join-Path $OutDir ("e1-after-update-{0}s.png" -f $s))
    }
    $f.live_version_after = Get-LiveVersion
    $f.old_exists = Test-Path -LiteralPath $OldDir
    $f.new_exists = Test-Path -LiteralPath $NewDir
    $f.pointers = Get-Pointers
    $f.markers_after = Get-Markers
    $f.fake_log = Get-FakeLogSince $f.fake_log_start
    Finish-Scenario 'e1' $f
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
$fakeArgs = '"{0}" serve --repo {1} --version {2} --setup "{3}" --cert "{4}" --key "{5}" --mode-file "{6}" --log "{7}"' -f `
    (Join-Path $Scripts 'fake_github.py'), $Repo, $NewVersion, $NewSetup,
    (Join-Path $CertDir 'server.crt'), (Join-Path $CertDir 'server.key'), $ModeFile, $FakeLog
$fake = Start-Process -FilePath $Py -ArgumentList $fakeArgs -PassThru -NoNewWindow `
    -RedirectStandardOutput (Join-Path $OutDir 'fake-github.out') -RedirectStandardError (Join-Path $OutDir 'fake-github.err')
Start-Sleep -Seconds 3
try {
    $r = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases?per_page=100" -TimeoutSec 20
    Note "stand-in reachable over TLS from pwsh: tag=$($r[0].tag_name)"
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
"all five scenarios OK"
exit 0
