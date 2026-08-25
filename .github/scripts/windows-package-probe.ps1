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

# ── 1 下载业主真正装的那个包 ──────────────────────────────────────
try {
    & gh release download $Tag --repo $env:GITHUB_REPOSITORY --pattern $Asset --dir $OutDir --clobber
    $setup = Join-Path $OutDir $Asset
    $mb = [Math]::Round((Get-Item $setup).Length / 1MB, 1)
    Say '1 下载安装包' "OK - $Asset,$mb MB"
} catch { Say '1 下载安装包' "FAIL - $($_.Exception.Message)"; throw }

# ── 2 静默安装(NSIS /S,每用户装到 %LOCALAPPDATA%\Programs) ────────
try {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $p = Start-Process (Resolve-Path $setup) -ArgumentList '/S' -PassThru -Wait
    $sw.Stop()
    Say '2 静默安装' "退出码 $($p.ExitCode),耗时 $([int]$sw.Elapsed.TotalSeconds)s"
} catch { Say '2 静默安装' "FAIL - $($_.Exception.Message)" }

# ── 3 装完了吗:查文件,不查安装器的自述 ────────────────────────────
$must = @("$InstallDir\OpenDesign.exe", "$InstallDir\python\pythonw.exe", "$InstallDir\ds\bin\ds_shell.py")
$missing = $must | Where-Object { -not (Test-Path $_) }
if ($missing) { Say '3 装完查文件' "FAIL - 少了:$($missing -join ', ')" }
else {
    $size = [Math]::Round(((Get-ChildItem $InstallDir -Recurse -File | Measure-Object Length -Sum).Sum) / 1MB, 0)
    Say '3 装完查文件' "OK - 三个关键文件都在,装完 $size MB"
}

# ── 4 双击它(业主每天做的动作) ────────────────────────────────────
try {
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
try {
    Save-Screen "$OutDir/11-app-window.png"
    $b = Test-Blankness "$OutDir/11-app-window.png"
    Say '7 截图与白屏体检' "颜色种类 $($b.Colors),近白像素 $($b.WhitePct)%（整块白≈颜色种类个位数 + 近白很高）"
} catch { Say '7 截图与白屏体检' "FAIL - $($_.Exception.Message)" }

# ── 8 把现场收走:外壳.log 是业主报"没按钮"时唯一的现场 ─────────────
try {
    $log = "$DataRoot\Logs\外壳.log"
    if (Test-Path $log) {
        Copy-Item $log "$OutDir/外壳.log" -Force
        Say '8 收日志' "OK - 外壳.log $((Get-Item $log).Length) 字节"
    } else { Say '8 收日志' "FAIL - 没有 $log" }
} catch { Say '8 收日志' "FAIL - $($_.Exception.Message)" }

Get-Process OpenDesign, pythonw, python -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue

"" ; "==================== VERDICT ===================="
foreach ($k in $phases.Keys) { "{0,-16} {1}" -f $k, $phases[$k] }
"================================================="
"图和日志在构件里。**这段文字不是结论** —— 主 agent 看图之后才下。"
