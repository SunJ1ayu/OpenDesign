# 真安装包探针 —— 把业主真正双击的那个 45MB 安装包搬上云 Windows 机器,
# 走完「下载 → 静默装 → 启动 → 等它活过来 → 截图 → 收日志」,再把图交出来。
#
# 它要替业主挡掉的是这一类(而不是"动画好不好看"):
#   0.89 装完打开就崩 / 0.90 窗口栏整块没画出来 / 0.93 打开全是白的
#
# 🔴 同上一支探针:**只报告,不判卷**。脚本自己崩了才 exit 非零。
#    每一相都打印 `PHASE n: OK|FAIL — 细节`,结论由主 agent 看图 + 看日志之后下。
#    "返回成功 ≠ 事情发生了":所以装完要查文件、起完要查端口、截完要查像素。

param(
    [string]$Tag    = "win-installer-0.97.0",
    [string]$Asset  = "OpenDesign-Setup-0.97.0.exe",
    [string]$OutDir = "probe-out"
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$InstallDir = "$env:LOCALAPPDATA\Programs\OpenDesign"
$DataRoot   = "$env:LOCALAPPDATA\OpenDesign"
$phases     = [ordered]@{}
function Say([string]$k, [string]$v) { $phases[$k] = $v; "PHASE $k : $v" }

function Save-Screen([string]$Path) {
    $b = [System.Windows.Forms.SystemInformation]::VirtualScreen
    $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
    $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
}

# 白屏体检:在图的中心区域采样,看颜色有多"单调"。
# 我们的界面是有颜色、有结构的;**一整块白 = 0.93 那次的形状**。
# 这不是判据,是一个能把"白屏"和"正常界面"分开的数字,给主 agent 看图时当参照。
function Test-Blankness([string]$Path) {
    $bmp = New-Object System.Drawing.Bitmap $Path
    $x0 = [int]($bmp.Width * 0.2); $x1 = [int]($bmp.Width * 0.8)
    $y0 = [int]($bmp.Height * 0.2); $y1 = [int]($bmp.Height * 0.8)
    $seen = @{}; $white = 0; $n = 0
    for ($y = $y0; $y -lt $y1; $y += 5) {
        for ($x = $x0; $x -lt $x1; $x += 5) {
            $p = $bmp.GetPixel($x, $y); $n++
            $key = "{0}-{1}-{2}" -f [int]($p.R / 16), [int]($p.G / 16), [int]($p.B / 16)
            $seen[$key] = 1
            if ($p.R -ge 235 -and $p.G -ge 235 -and $p.B -ge 235) { $white++ }
        }
    }
    $bmp.Dispose()
    return [PSCustomObject]@{
        Colors = $seen.Count
        WhitePct = [Math]::Round(100.0 * $white / $n, 1)
    }
}


# 卡住时光有截图不够 —— 弹框可能被别的窗口盖住(第二跑就是这样:装机卡住那 8 分钟里
# 屏幕上盖着 runner 自己的终端,弹框在它后面,图上一个字都看不见)。
# 所以直接问 Windows 要那个框里的**文字**:枚举它的子控件,把 text 全掏出来。
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class W32 {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr p, EnumProc cb, IntPtr l);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  public static string Text(IntPtr h) {
    var sb = new StringBuilder(2048); GetWindowTextW(h, sb, 2048); return sb.ToString();
  }
}
"@ -ErrorAction SilentlyContinue

$script:dlg = @()
function Dump-Dialogs([string]$Match = 'OpenDesign') {
    $script:dlg = @()
    $ccb = [W32+EnumProc]{ param($c, $m)
        $ct = [W32]::Text($c); if ($ct) { $script:dlg += "    L $ct" }; return $true }
    $cb = [W32+EnumProc]{ param($h, $l)
        if ([W32]::IsWindowVisible($h)) {
            $t = [W32]::Text($h)
            if ($t -like "*$Match*") {
                $script:dlg += "  window: [$t]"
                [void][W32]::SetForegroundWindow($h)
                [void][W32]::EnumChildWindows($h, $ccb, [IntPtr]::Zero)
            }
        }
        return $true }
    [void][W32]::EnumWindows($cb, [IntPtr]::Zero)
    return $script:dlg
}

# ── 1 下载业主真正装的那个包 ──────────────────────────────────────
try {
    & gh release download $Tag --repo $env:GITHUB_REPOSITORY --pattern $Asset --dir $OutDir --clobber
    $setup = Join-Path $OutDir $Asset
    $mb = [Math]::Round((Get-Item $setup).Length / 1MB, 1)
    Say '1 下载安装包' "OK - $Asset,$mb MB"
} catch { Say '1 下载安装包' "FAIL - $($_.Exception.Message)"; throw }

# ── 2 静默安装(NSIS /S) ─────────────────────────────────────────
# 🔴 **不用 -Wait**。第一跑(32798142734)在这里挂了 15 分钟、最后被我掐掉,
#    而 -Wait 的形状是「卡住了就什么都看不见」—— 连一张能说明卡在哪的图都没有。
#    NSIS 的规矩:`/S` 只跳过安装界面,**`MessageBox` 照弹**(除非带 /SD 默认值
#    或被 IfSilent 挡住),而 installer/OpenDesign.nsi 里 4 个 MessageBox 一个都没有。
#    所以这里改成:边等边截图、边列窗口标题 —— **让"它在等谁点确定"变成看得见的**。
try {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $ip = Start-Process (Resolve-Path $setup) -ArgumentList '/S' -PassThru
    $tick = 0
    while (-not $ip.HasExited -and $sw.Elapsed.TotalMinutes -lt 3) {
        Start-Sleep -Seconds 45; $tick++
        Save-Screen ("{0}/2{1}-installing.png" -f $OutDir, $tick)
        $t = Get-Process | Where-Object { $_.MainWindowTitle } |
             ForEach-Object { "$($_.ProcessName):「$($_.MainWindowTitle)」" }
        "  [装机中 $([int]$sw.Elapsed.TotalSeconds)s] 屏幕上的窗口: $(if($t){$t -join ' | '}else{'(无)'})"
        Dump-Dialogs | ForEach-Object { $_ }
    }
    $sw.Stop()
    if ($ip.HasExited) {
        Say '2 静默安装' "退出码 $($ip.ExitCode),耗时 $([int]$sw.Elapsed.TotalSeconds)s"
    } else {
        Save-Screen "$OutDir/29-installer-stuck.png"
        $t = Get-Process | Where-Object { $_.MainWindowTitle } |
             ForEach-Object { "$($_.ProcessName):「$($_.MainWindowTitle)」" }
        "---- 卡住时那个框里到底写的什么 ----"
        Dump-Dialogs | ForEach-Object { $_ }
        Save-Screen "$OutDir/29b-dialog-front.png"
        Say '2 静默安装' "FAIL - 3 分钟没退出,**卡住了**。屏幕上的窗口: $(if($t){$t -join ' | '}else{'(无标题窗口)'})"
        Stop-Process -Id $ip.Id -Force -ErrorAction SilentlyContinue
    }
} catch { Say '2 静默安装' "FAIL - $($_.Exception.Message)" }

# ── 3 装完了吗:查文件,不查安装器的自述 ────────────────────────────
$must = @("$InstallDir\OpenDesign.exe", "$InstallDir\python\pythonw.exe", "$InstallDir\ds\bin\ds_shell.py")
$missing = $must | Where-Object { -not (Test-Path $_) }
if ($missing) { Say '3 装完查文件' "FAIL - 少了:$($missing -join ', ')" }
else {
    $size = [Math]::Round(((Get-ChildItem $InstallDir -Recurse -File | Measure-Object Length -Sum).Sum) / 1MB, 0)
    Say '3 装完查文件' "OK - 三个关键文件都在,装完 $size MB"
}

# ── 3.5 那句"配置初始化没有成功(错误码 2)"到底是什么 ────────────
# 弹框只给了错误码,**人话那一段被静默安装吞掉了**(nsExec::ExecToLog 写进
# 安装器的日志窗,而 /S 根本不开那个窗)。所以这里自己把同一条命令再跑一遍,
# 把 stderr 原样接住 —— ds_provision.py 承诺过"给业主的是人话不是栈"。
try {
    $py = "$InstallDir\python\python.exe"
    $pv = "$InstallDir\ds\bin\ds_provision.py"
    if ((Test-Path $py) -and (Test-Path $pv)) {
        $o = & $py $pv --home "$DataRoot\UserData" --ds-root "$InstallDir\ds" 2>&1
        $rc = $LASTEXITCODE
        "---- ds_provision.py 原样输出(rc=$rc) ----"
        $o | ForEach-Object { "  $_" }
        Say '3.5 配置初始化说了什么' "rc=$rc"
    } else { Say '3.5 配置初始化说了什么' "FAIL - 找不到 python 或 ds_provision.py" }
} catch { Say '3.5 配置初始化说了什么' "FAIL - $($_.Exception.Message)" }

# ── 4 双击它(业主每天做的动作) ────────────────────────────────────
try {
    $script:launch = [Diagnostics.Stopwatch]::StartNew()
    Start-Process "$InstallDir\OpenDesign.exe" | Out-Null
    Say '4 启动' "OK - 已拉起 OpenDesign.exe"
} catch { Say '4 启动' "FAIL - $($_.Exception.Message)" }

# ── 5 它活过来了吗:问它自己的健康端点(不看窗口,看服务) ──────────────
$health = $null
for ($i = 0; $i -lt 60; $i++) {
    try {
        $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8766/api/health' -TimeoutSec 3
        break
    } catch { Start-Sleep -Seconds 3 }
}
if ($health) { Say '5 服务活了吗' "OK - /api/health 通,version=$($health.version)" }
else { Say '5 服务活了吗' "FAIL - 3 分钟内 127.0.0.1:8766 一直不通" }

# ── 6 窗口在不在:列出有标题的顶层窗口 ─────────────────────────────
Start-Sleep -Seconds 8
$wins = Get-Process | Where-Object { $_.MainWindowTitle } |
        ForEach-Object { "$($_.ProcessName):「$($_.MainWindowTitle)」" }
if ($wins) { Say '6 窗口在不在' "OK - $($wins -join ' | ')" }
else { Say '6 窗口在不在' "FAIL - 一个有标题的顶层窗口都没有" }

# ── 7 截图 + 白屏体检 ─────────────────────────────────────────────
# 🔴 **一张图分不开"还在加载"和"真的白"**(0.98 那一跑:窗口开了、服务通了、
#    日志零报错,而截图整块白 —— 这两种可能当时分不开,分不开就不许挑一个说)。
#    所以隔一段拍一张,让"白不白"变成一条**随时间的曲线**:
#    一路白到底 = 真白屏(0.93 那个至今没定案的病);中途有东西了 = 我截早了。
try {
    $shots = @()
    foreach ($wait in 0, 20, 30, 30, 60) {
        if ($wait -gt 0) { Start-Sleep -Seconds $wait }
        $t = [int]$script:launch.Elapsed.TotalSeconds
        $f = "{0}/1{1}-app-{2}s.png" -f $OutDir, $shots.Count, $t
        Save-Screen $f
        $b = Test-Blankness $f
        $shots += "启动后 ${t}s: 颜色 $($b.Colors) 种 / 近白 $($b.WhitePct)%"
        "  [白屏体检] $($shots[-1])"
    }
    Say '7 截图与白屏体检' ($shots -join " | ")
} catch { Say '7 截图与白屏体检' "FAIL - $($_.Exception.Message)" }

# ── 8 把现场收走 ───────────────────────────────────────────────
# 🔴 2026-08-30 业主一句「你的机子是 linux,github 的云 windows 你不一定看得全是不是」
#    问出来的:这里原来**只收 外壳.log** —— 而 0.98.1 改的时间戳有一半在 工作台.log 上,
#    那一半在 Windows 上从没被验证过。三份一起收,别再自己给自己留盲区。
try {
    $names = @('外壳.log', '工作台.log', '网关.log')
    $got = @()
    foreach ($n in $names) {
        $log = "$DataRoot\Logs\$n"
        if (Test-Path $log) {
            Copy-Item $log "$OutDir/$n" -Force
            $got += "$n $((Get-Item $log).Length)B"
        } else { $got += "$n 缺席" }
    }
    Say '8 收日志' ($got -join " | ")
} catch { Say '8 收日志' "FAIL - $($_.Exception.Message)" }

# ── 9 托盘导出诊断:在 Windows 上真跑一遍那段代码 ────────────────────
# 🔴 同一问问出来的第二个盲区:探针不做任何交互 ⇒ 0.98.1 的**主打功能**
#    「导出本次启动诊断」在 Windows 上**一次都没跑过**。右键点托盘不好自动化,
#    但那段代码本身可以用装好的那个 python 直接跑 —— 至少证明中文文件名、
#    zip、路径这些在真 Windows 上是成立的(不能证明菜单点得动,那条留给业主)。
try {
    # 🔴 路径:python 在 $INSTDIR\python\,**不在** ds\python\(第一版写错,当场 FAIL —— 探针自己坏了)。
    #    出处:installer/OpenDesign.nsi:245 那行 ExecToLog 用的就是 "$INSTDIR\python\python.exe"。
    $py = "$InstallDir\python\python.exe"
    $code = @"
import sys, zipfile
sys.path.insert(0, r'$InstallDir\ds\bin')
import ds_diag
d = ds_diag.StartupLog(emit=lambda s: None)
out = r'$OutDir\诊断包-windows.zip'
d.export_bundle(out, app_dir=r'$DataRoot')
print('NAMES=' + '|'.join(zipfile.ZipFile(out).namelist()))
"@
    $r = & $py -c $code 2>&1
    Say '9 托盘导出诊断(直接跑那段代码)' ("$r" -replace "`r?`n", " ")
} catch { Say '9 托盘导出诊断(直接跑那段代码)' "FAIL - $($_.Exception.Message)" }

# ── 10 带系统代理再启动一次:验 0.98.1 修的那个"软件打不开" ──────────
# 🔴 第三个盲区,而且是最要命的:CI 机器上**没有系统代理**,而业主机器上**有**
#    (跑着 VPN)。0.98.1 修的正是"就绪探针走了系统代理 ⇒ 死等 60s ⇒ 启动失败"。
#    不在这儿造一个代理,那个修复在 Windows 上就是**未验证**的。
try {
    Get-Process OpenDesign, pythonw, python -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
    $env:HTTP_PROXY  = 'http://127.0.0.1:9'    # 9 端口没人听 = 走代理必失败
    $env:HTTPS_PROXY = 'http://127.0.0.1:9'
    $sw = [Diagnostics.Stopwatch]::StartNew()
    Start-Process "$InstallDir\OpenDesign.exe"
    $ok = $false
    while ($sw.Elapsed.TotalSeconds -lt 90) {
        Start-Sleep -Seconds 5
        try {
            $h = Invoke-WebRequest -Uri 'http://127.0.0.1:8766/api/health' -UseBasicParsing `
                 -TimeoutSec 5 -Proxy $null
            if ($h.StatusCode -eq 200) { $ok = $true; break }
        } catch { }
    }
    Remove-Item Env:HTTP_PROXY, Env:HTTPS_PROXY -ErrorAction SilentlyContinue
    Save-Screen "$OutDir/30-proxy-launch.png"
    $b2 = Test-Blankness "$OutDir/30-proxy-launch.png"
    if ($ok) {
        Say '10 带系统代理启动' ("OK - {0}s 起来了,颜色 {1} 种 / 近白 {2}%" -f `
            [int]$sw.Elapsed.TotalSeconds, $b2.Colors, $b2.WhitePct)
    } else {
        Say '10 带系统代理启动' "🔴 FAIL - 90s 没起来 ⇒ 代理修复在真 Windows 上不成立"
    }
    Copy-Item "$DataRoot\Logs\外壳.log" "$OutDir/外壳-带代理.log" -Force -ErrorAction SilentlyContinue
} catch { Say '10 带系统代理启动' "FAIL - $($_.Exception.Message)" }

Get-Process OpenDesign, pythonw, python -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue

"" ; "==================== VERDICT ===================="
foreach ($k in $phases.Keys) { "{0,-16} {1}" -f $k, $phases[$k] }
"================================================="
"图和日志在构件里。**这段文字不是结论** —— 主 agent 看图之后才下。"
