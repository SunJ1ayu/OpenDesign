# 真安装包探针 —— 把业主真正双击的那个 45MB 安装包搬上云 Windows 机器,
# 走完「下载 → 静默装 → 启动 → 等它活过来 → 截图 → 收日志」,再把图交出来。
#
# 它要替业主挡掉的是这一类(而不是"动画好不好看"):
#   0.89 装完打开就崩 / 0.90 窗口栏整块没画出来 / 0.93 打开全是白的
#
# 🔴 退出码的契约(2026-08-30 重写,原来那句是**假的**):
#    旧文案写"脚本自己崩了才 exit 非零",但脚本末尾没有 exit 语句 ⇒ pwsh 拿
#    **最后一个原生命令的 $LASTEXITCODE** 当脚本退出码。run 33306843034 就是这么
#    红的:第 9 相那个 python 因为打印中文炸了(见下),rc=1 泄漏出来染红整个 run,
#    而产品一点问题都没有。反过来更坏:第 10 相真喊 "🔴 FAIL" 时,只要后面没有
#    原生命令,整个 run 照样是**绿的**。
#    现在改成:**任何一相自报 FAIL ⇒ exit 1**,否则 exit 0(见文件末尾)。
#    ⚠️ 绿**不等于**产品没问题 —— 白屏体检给的是读数(颜色数 / 近白百分比),
#    判读仍然要主 agent 看图。闸只兜机器能独自断定的那几件:装机退出码、
#    配置 rc、导出 rc、端口通不通、窗口在不在、文件在不在。

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
# 🔴 应用用 `core.pick_ports([8766,…], span=20)` 挑端口,被占就往后挪(ds_shell.py:248)。
#    探针原来把 8766 写死 ⇒ 8767 上健康启动也判 FAIL(**健康假红**)。扫整段。
$PortSpan   = 8766..8786
function Say([string]$k, [string]$v) { $phases[$k] = $v; "PHASE $k : $v" }

# 🔴 判定("机器事实 → 该不该 FAIL")**不在这个脚本里**。
#    这支脚本本机跑不了(没有 pwsh)⇒ 写在这里的判定谁都验不了,而 2026-08-30 那一晚
#    它被外部评审连打回十几次(极性、取值、守卫、终止条件、参数,每一种静态判据都全绿)。
#    ⇒ 探针只**采事实**,判定交给 bin/probe_verdict.py(纯函数,有 11 条行为判据守着)。
#    用**仓库里这一份**(和本脚本同版本),不是装出来的那份旧的。
function Get-Verdict([string]$kind, $facts) {
    $judge = Join-Path $PSScriptRoot '..\..\bin\probe_verdict.py'
    $py     = "$InstallDir\python\python.exe"
    $errLog = Join-Path $OutDir ("judge-{0}.err" -f $kind)
    if (-not (Test-Path $judge)) { return "FAIL - 判定器不在:$judge" }
    if (-not (Test-Path $py))    { return "FAIL - 判定器跑不成:找不到 $py" }
    try {
        # 🔴 `-EscapeHandling EscapeNonAscii`:把中文转成 \uXXXX。
        #    不加的话,PowerShell 往原生进程写管道用的是**控制台代码页**
        #    (en-US runner = cp1252)⇒ 中文键被打坏 ⇒ 判定器一个都查不到 ⇒ **假红**。
        #    run 33321769218 就是这么红的:第 8 相说三份日志全缺席,而同一秒第 9 相
        #    导出的包里它们明明在。纯 ASCII 的 JSON 任何代码页都打不坏。
        $json = $facts | ConvertTo-Json -Depth 6 -Compress -EscapeHandling EscapeNonAscii
        # 🔴 **stdout 和 stderr 必须分开抓**。原来是 `2>&1`:判定器语法错/import 炸时
        #    traceback 全在 stderr、stdout 是空的,合并之后"输出非空" ⇒ rc=1 穿过下面的
        #    守卫 ⇒ **traceback 被当成裁决原样 Say 出去**,闸找不到 FAIL ⇒ exit 0。
        #    第 2e 轮外部评审用一个语法错的判定器逐行模拟过。**裁决只能来自 stdout。**
        $out  = $json | & $py $judge $kind 2>$errLog
        $rc   = $LASTEXITCODE
    } catch { return "FAIL - 判定器炸了:$($_.Exception.Message)" }
    $errText = if (Test-Path $errLog) { (Get-Content $errLog -Raw) } else { "" }
    if (-not $out) { return "FAIL - 判定器没有输出(rc=$rc,stderr:$errText)" }
    # 🔴 **rc 只有 0(OK)和 1(FAIL)是裁决,别的都是"判定器自己坏了"**。
    #    上面那句 `2>&1` 把 stderr 并进了 $out,所以"输出非空"根本不等于"给了裁决":
    #    判定器 import 期炸(traceback 在 stderr)、kind 分发键被改名(rc=2 + 用法串),
    #    都会变成一句没有 FAIL 的话被原样 Say 出去 ⇒ 整趟绿。第 2d 轮外部评审实测过。
    if ($rc -ne 0 -and $rc -ne 1) { return "FAIL - 判定器异常退出(rc=$rc):$out" }
    return (("$out" -replace "`r?`n", " ").Trim())
}

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
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassNameW(IntPtr h, StringBuilder s, int n);
  public static string Text(IntPtr h) {
    var sb = new StringBuilder(2048); GetWindowTextW(h, sb, 2048); return sb.ToString();
  }
  public static string Cls(IntPtr h) {
    var sb = new StringBuilder(256); GetClassNameW(h, sb, 256); return sb.ToString();
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

$script:appwins = @()
# 「标题里带 $Match 的可见顶层窗口」+ **它的窗口类**。
# 🔴 类名是分开"报错框"和"真窗口"的唯一可靠依据:MessageBoxW 弹的框窗口类恒为
#    `#32770`(Windows 的对话框类),而 pywebview 的主窗口不是。
#    **标题分不开** —— ds_shell.py 的 alert()/die() 用的标题就是 APP = OpenDesign。
function Get-AppWindows([string]$Match = 'OpenDesign') {
    $script:appwins = @()
    $cb = [W32+EnumProc]{ param($h, $l)
        if ([W32]::IsWindowVisible($h)) {
            $t = [W32]::Text($h)
            if ($t -like "*$Match*") {
                $script:appwins += [PSCustomObject]@{ Title = $t; Class = [W32]::Cls($h) }
            }
        }
        return $true }
    [void][W32]::EnumWindows($cb, [IntPtr]::Zero)
    return $script:appwins
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
        # 🔴 非零退出码就是"装失败",文案必须带 FAIL —— 否则末尾那道闸看不见它。
        $r2 = if ($ip.ExitCode -eq 0) { "退出码 0" } else { "FAIL - 退出码 $($ip.ExitCode)" }
        Say '2 静默安装' "$r2,耗时 $([int]$sw.Elapsed.TotalSeconds)s"
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
        Say '3.5 配置初始化说了什么' $(if ($rc -eq 0) { "rc=0" } else { "FAIL - rc=$rc" })
    } else { Say '3.5 配置初始化说了什么' "FAIL - 找不到 python 或 ds_provision.py" }
} catch { Say '3.5 配置初始化说了什么' "FAIL - $($_.Exception.Message)" }

# ── 4 双击它(业主每天做的动作) ────────────────────────────────────
try {
    $script:launch = [Diagnostics.Stopwatch]::StartNew()
    Start-Process "$InstallDir\OpenDesign.exe" | Out-Null
    Say '4 启动' "OK - 已拉起 OpenDesign.exe"
} catch { Say '4 启动' "FAIL - $($_.Exception.Message)" }

# ── 5 它活过来了吗:问它自己的健康端点(不看窗口,看服务) ──────────────
$answers = @{}
foreach ($p in $PortSpan) { $answers["$p"] = $null }
for ($i = 0; $i -lt 60; $i++) {
    foreach ($p in $PortSpan) {
        try {
            $h = Invoke-RestMethod -Uri "http://127.0.0.1:$p/api/health" -TimeoutSec 2
            if ($h.version) { $answers["$p"] = "$($h.version)" }
        } catch { }
    }
    if ($answers.Values | Where-Object { $_ }) { break }
    Start-Sleep -Seconds 3
}
Say '5 服务活了吗' (Get-Verdict 'health' @{ answers = $answers })

# ── 6 窗口在不在:等 **OpenDesign 自己的**窗口出现 ─────────────────
# 🔴 2026-08-30 修:原来问的是"屏幕上有没有**任何**带标题的窗口",而 CI 机器上
#    永远有一个 WindowsTerminal ⇒ **这一相永远不会红**。这不是推的:run 33310976051
#    当场照出来 —— 那一刻 OpenDesign 的窗口根本不在列表里(41s 的截图上它才出现),
#    而这一相照样报了 OK。这恰恰是本探针存在的理由那一问(0.89 崩 / 0.91 窗口栏
#    没画出来 / 0.93 白屏),却是全脚本唯一一处**结构上不可能红**的断言。
#    改成:轮询等标题里带 OpenDesign 的那个(照第 5 相的写法),60s 没等到才 FAIL。
#    固定 sleep 8s 本来就是抽签 —— 上一趟抽中了,这一趟没抽中。
# 🔴 2026-08-30 第二处(第二轮外部评审报的):光认**标题**不够 —— ds_shell.py 的
#    alert()/die() 弹的报错框标题**就是** APP = OpenDesign,所以"后端活着 + 屏幕上
#    只剩报错框"会整趟绿,而业主眼里软件压根没打开。⇒ 还得看窗口**类**。
# 🔴 2026-08-30 第三处:**判定不在这儿了**。这一段只负责采两样事实 ——
#    `$wins`(标题含 OpenDesign 的顶层窗口 + 它们的窗口类)和 `$ours`(老口径:
#    进程主窗口标题)。"哪种算真窗口、哪种是报错框、枚举不到时怎么办"全在
#    `bin/probe_verdict.py::window_verdict`,那里有 11 条行为判据守着。
#    原因:这支脚本本机跑不了,写在这里的判定谁都验不了(那一晚被打回十几次)。
$appTitle = 'OpenDesign'          # = bin/ds_shell.py:37 的 APP,窗口标题的唯一来源
$deadline = (Get-Date).AddSeconds(60)
do {
    Start-Sleep -Seconds 4
    $all  = @(Get-Process | Where-Object { $_.MainWindowTitle } |
              ForEach-Object { "$($_.ProcessName):「$($_.MainWindowTitle)」" })
    $ours = @($all | Where-Object { $_ -like "*$appTitle*" })      # 老口径,只在枚举不到时兜底
    $wins = @(Get-AppWindows $appTitle)                            # 新口径:标题 + **窗口类**
} while ($ours.Count -eq 0 -and $wins.Count -eq 0 -and (Get-Date) -lt $deadline)
Say '6 窗口在不在' (Get-Verdict 'window' @{
    wins = @($wins | ForEach-Object { @{ title = $_.Title; cls = $_.Class } })
    ours = $ours
})

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
# 🔴 2026-08-30 第二处(同一轮评审):原来三份**全缺席**也只写"缺席"两个字、
#    不带 FAIL ⇒ 末尾那道闸(`-match 'FAIL'`)看不见它 ⇒ "应用根本没起来、
#    现场是空的"这种最该红的情况,整趟是绿的、构件是空的。
#    **哪几份必须有**(外壳/工作台必须、网关豁免)写在
#    `bin/probe_verdict.py::REQUIRED_LOGS` —— 这一段只采"谁在、多大"。
try {
    $present = @{}
    foreach ($n in @('外壳.log', '工作台.log', '网关.log')) {
        $log = "$DataRoot\Logs\$n"
        if (Test-Path $log) {
            Copy-Item $log "$OutDir/$n" -Force
            $present[$n] = (Get-Item $log).Length
        } else { $present[$n] = $null }
    }
    Say '8 收日志' (Get-Verdict 'logs' @{ present = $present })
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
    # 🔴 子进程的 stdout 在 Windows 上是 ANSI 代码页(en-US runner = cp1252),
    #    print 中文文件名 ⇒ UnicodeEncodeError ⇒ 这一相拿到的是栈、不是答案。
    #    仓里现成写法:bin/ds_provision.py:273 自己把流转成 utf-8(所以 3.5 相的
    #    中文一直打得出来)。这里照抄。本机已逐字符复现,见 evidence 里那份红收据。
    $code = @"
import sys, zipfile
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'$InstallDir\ds\bin')
import ds_diag
d = ds_diag.StartupLog(emit=lambda s: None)
out = r'$OutDir\诊断包-windows.zip'
d.export_bundle(out, app_dir=r'$DataRoot')
print('NAMES=' + '|'.join(zipfile.ZipFile(out).namelist()))
"@
    $r = & $py -c $code 2>&1
    $rc9 = $LASTEXITCODE
    $t9  = "$r" -replace "`r?`n", " "
    Say '9 托盘导出诊断(直接跑那段代码)' $(if ($rc9 -eq 0) { $t9 } else { "FAIL - rc=$rc9 $t9" })
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
    $answers2 = @{}
    foreach ($p in $PortSpan) { $answers2["$p"] = $null }
    while ($sw.Elapsed.TotalSeconds -lt 90) {
        Start-Sleep -Seconds 5
        foreach ($p in $PortSpan) {
            try {
                $h = Invoke-WebRequest -Uri "http://127.0.0.1:$p/api/health" -UseBasicParsing `
                     -TimeoutSec 2 -Proxy $null
                if ($h.StatusCode -eq 200) { $answers2["$p"] = 'up' }
            } catch { }
        }
        if ($answers2.Values | Where-Object { $_ }) { break }
    }
    $ok = [bool]($answers2.Values | Where-Object { $_ })
    Remove-Item Env:HTTP_PROXY, Env:HTTPS_PROXY -ErrorAction SilentlyContinue
    Save-Screen "$OutDir/30-proxy-launch.png"
    $b2 = Test-Blankness "$OutDir/30-proxy-launch.png"
    $v10 = Get-Verdict 'health' @{ answers = $answers2 }
    Say '10 带系统代理启动' ("{0}({1}s,颜色 {2} 种 / 近白 {3}%)" -f `
        $v10, [int]$sw.Elapsed.TotalSeconds, $b2.Colors, $b2.WhitePct)
    Copy-Item "$DataRoot\Logs\外壳.log" "$OutDir/外壳-带代理.log" -Force -ErrorAction SilentlyContinue
} catch { Say '10 带系统代理启动' "FAIL - $($_.Exception.Message)" }

Get-Process OpenDesign, pythonw, python -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue

"" ; "==================== VERDICT ===================="
foreach ($k in $phases.Keys) { "{0,-16} {1}" -f $k, $phases[$k] }
"================================================="
"图和日志在构件里。**这段文字不是结论** —— 主 agent 看图之后才下。"

# ── 退出码:只兜"机器能独自断定"的那几件,不替人判白屏 ────────────────
# 不写这段的话,退出码 = 最后一个原生命令的 $LASTEXITCODE(见文件头)。
$failed = @($phases.GetEnumerator() | Where-Object { $_.Value -match 'FAIL' } | ForEach-Object { $_.Key })
if ($failed.Count) {
    "🔴 自报 FAIL 的相:$($failed -join ', ') ⇒ exit 1"
    exit 1
}
"没有任何一相自报 FAIL ⇒ exit 0(**白屏读数不在闸内**,仍要看图)"
exit 0
