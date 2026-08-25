# 云 Windows 机器可行性探针 —— 一次跑完回答四问
#
# 背景:这个项目一年来唯一的验证路径是"打包发给业主、让他肉眼看、口头回话"。
# 而烧掉真机的三件事(0.89 开机崩溃 / 0.90 窗口栏整块没画出来 / 0.93 界面全白)
# 里有两件是**一张截图就能看出来的**。这个探针只回答一件事:
#
#   GitHub 托管的 windows runner,到底能不能替我们看那一眼?
#
# 🔴 这个脚本**只报告,不判卷**:它自己跑崩了才 exit 非零(=探针坏了)。
#    四问的答案在日志的 VERDICT 段和 probe-out/ 里的图上 —— 结论由主 agent 看图下,
#    不由脚本的绿红下。理由:"返回成功 ≠ 事情发生了" 在本仓已经栽过三次,
#    所以每一问都做**像素核对**,不接受"命令没报错"当证据。

param([string]$OutDir = "probe-out")

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$results = [ordered]@{}

function Save-Screen([string]$Path) {
    $b = [System.Windows.Forms.SystemInformation]::VirtualScreen
    $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
    $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    return "$($b.Width)x$($b.Height)"
}

# 数一张图里有多少像素接近目标色。**这一步是整个探针的支点**:
# 只问"文件生成了没有"是假绿 —— 全黑的截图也会生成文件。
function Count-Color([string]$Path, [int]$R, [int]$G, [int]$B, [int]$Tol = 24) {
    $bmp = New-Object System.Drawing.Bitmap $Path
    $hit = 0; $total = 0
    for ($y = 0; $y -lt $bmp.Height; $y += 4) {
        for ($x = 0; $x -lt $bmp.Width; $x += 4) {
            $p = $bmp.GetPixel($x, $y); $total++
            if ([Math]::Abs($p.R - $R) -le $Tol -and
                [Math]::Abs($p.G - $G) -le $Tol -and
                [Math]::Abs($p.B - $B) -le $Tol) { $hit++ }
        }
    }
    $bmp.Dispose()
    return [PSCustomObject]@{ Hit = $hit; Total = $total; Pct = [Math]::Round(100.0 * $hit / $total, 2) }
}

# ── Q1 这台云机器上到底有没有桌面 ─────────────────────────────────
try {
    $size = Save-Screen "$OutDir/01-desktop.png"
    $results['Q1 有没有桌面(截得到屏幕吗)'] = "OK — 截到了,虚拟屏 $size"
} catch {
    $results['Q1 有没有桌面(截得到屏幕吗)'] = "FAIL — $($_.Exception.Message)"
}

# ── Q2 能不能开一个真窗口、并且截到它 ─────────────────────────────
# 洋红 (255,0,255) 是刻意选的:桌面/壁纸/任何系统 UI 都不会自然出现这个颜色,
# 所以"截图里有大片洋红"= 那个窗口真的被画出来了,而不是我在自我安慰。
$formScript = @'
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$f = New-Object System.Windows.Forms.Form
$f.FormBorderStyle = 'None'
$f.WindowState = 'Maximized'
$f.BackColor = [System.Drawing.Color]::FromArgb(255, 0, 255)
$f.TopMost = $true
$f.Add_Shown({ $f.Activate() })
[System.Windows.Forms.Application]::Run($f)
'@
$formPath = Join-Path $OutDir "_form.ps1"
Set-Content -Path $formPath -Value $formScript -Encoding UTF8
$proc = $null
try {
    $proc = Start-Process powershell -PassThru -ArgumentList @(
        '-STA', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $formPath)
    Start-Sleep -Seconds 6
    Save-Screen "$OutDir/02-winforms-window.png" | Out-Null
    $c = Count-Color "$OutDir/02-winforms-window.png" 255 0 255
    if ($c.Pct -ge 30) {
        $results['Q2 开得出窗口、截得到它吗'] = "OK — 洋红占屏 $($c.Pct)% ⇒ 窗口真的画出来了"
    } else {
        $results['Q2 开得出窗口、截得到它吗'] = "FAIL — 洋红只占 $($c.Pct)% ⇒ 窗口没画出来,或截到的是黑屏"
    }
} catch {
    $results['Q2 开得出窗口、截得到它吗'] = "FAIL — $($_.Exception.Message)"
} finally {
    if ($proc -and -not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
}

# ── Q3 WebView2 运行时在不在 ──────────────────────────────────────
# 我们的界面就是靠它画的。它不在 = 白屏那一族的前提之一。
$wv2 = 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
try {
    $pv = (Get-ItemProperty -Path $wv2 -ErrorAction Stop).pv
    $results['Q3 WebView2 运行时装了吗'] = "OK — 已装,版本 $pv"
} catch {
    $results['Q3 WebView2 运行时装了吗'] = "FAIL — 注册表里没有(路径 $wv2)"
}

# ── Q4 最像我们的那一问:浏览器窗口里的网页,画得出来吗 ──────────────
# 我们的软件 = 一个网页跑在 WebView2 里。0.93 那次"界面全白"的形状就是
# **窗口开了、网页没画出来**。所以这一问用 Edge 的应用窗口装一个纯色网页,
# 再去截图里数那个颜色 —— 这是这台云机器能不能替业主看那一眼的直接证据。
$html = '<html><body style="margin:0;background:#00FF7F"><h1 style="color:#000">OpenDesign CI probe</h1></body></html>'
$htmlPath = (Resolve-Path $OutDir).Path + "\probe.html"
Set-Content -Path $htmlPath -Value $html -Encoding UTF8
$edge = "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
$eproc = $null
try {
    if (-not (Test-Path $edge)) { throw "找不到 Edge:$edge" }
    $eproc = Start-Process $edge -PassThru -ArgumentList @(
        "--app=file:///$($htmlPath -replace '\\','/')", '--window-size=1200,800',
        '--no-first-run', '--disable-features=Translate')
    Start-Sleep -Seconds 10
    Save-Screen "$OutDir/03-edge-app-window.png" | Out-Null
    $c2 = Count-Color "$OutDir/03-edge-app-window.png" 0 255 127
    if ($c2.Pct -ge 10) {
        $results['Q4 浏览器窗口里的网页画得出来吗'] = "OK — 页面绿占屏 $($c2.Pct)% ⇒ 网页真的渲染了"
    } else {
        $results['Q4 浏览器窗口里的网页画得出来吗'] = "FAIL — 页面绿只占 $($c2.Pct)% ⇒ 窗口开了但网页没画出来(=白屏那一族)"
    }
} catch {
    $results['Q4 浏览器窗口里的网页画得出来吗'] = "FAIL — $($_.Exception.Message)"
} finally {
    if ($eproc -and -not $eproc.HasExited) { Stop-Process -Id $eproc.Id -Force -ErrorAction SilentlyContinue }
}

# ── 汇总 ──────────────────────────────────────────────────────────
"" ; "==================== VERDICT ===================="
foreach ($k in $results.Keys) { "{0,-34} {1}" -f $k, $results[$k] }
"================================================="
"图在构件 windows-gui-probe 里,主 agent 亲眼看图之后才下结论 —— 这段文字不是结论。"
