# 云 Windows 判据(track opendesign-electron-shell)—— 换壳版 OpenDesign 在真 Windows 上装、换、跑、更新、卸。
# **断言写死,FAIL 0 才算过**(探路 U2 十跑的 electron-shell-probe.ps1 转正;design.md「Test strategy」E1~E6)。
#
# 顺序(一台干净的 runner 上依次走;攻题 #16 之后重排:**旧版过渡必须是这台机器上的第一件事**,
# 否则新版先建好的配置/资料会冒充「旧版留下的东西」,过渡时把它们弄丢也看不出来):
#   E3 旧版 0.98.8 装在自选带空格目录、开机自启开着、在托盘里跑、配置里有业主改过的值 → 带界面装新版(选目录页不改)
#   E2 把装好的新版真跑起来点(e2-drive.mjs)
#   E2v 故意让后台版本对不上(改装好的 ds_web.VERSION)⇒ 必须弹「重新运行安装包」(挑战 a4 的真机那一半)
#   E4 更新:源不通 → 重试 → 「重启以更新」→ 向导按两下 → 新版(e4-drive.mjs + click-wizard.ps1)
#   E6 软件在跑时从「应用和功能」那条卸载(带界面)
#   E3b 旧版 0.98.8 装在 A、首装新版时改选 B ⇒ A 那份也得被收掉(「旧版在哪就去哪收」),资料不动
#   E3c 旧版装在带单引号的目录、有文件被占住 ⇒ 第一次拒装且可重试 ⇒ 解锁后不带 /D 重装、收干净(T5 R1-1/R1-4)
#   (清空这台机器上的 OpenDesign 痕迹,模拟一台新电脑)
#   E5 全新机器带界面首装,选目录页改成带空格 + 中文的自选目录
# 每条判读一行 `OK  |FAIL <名字> :: <事实>`;有 FAIL 就 exit 1。
param(
    [string]$OldTag   = "win-installer-0.98.8",
    [string]$OldAsset = "OpenDesign-Setup-0.98.8.exe",
    [Parameter(Mandatory)][string]$NewSetup,     # v1 安装包(版本 = $Ver)
    [Parameter(Mandatory)][string]$Ver,          # ds_web.VERSION(版本号唯一来源)
    [Parameter(Mandatory)][string]$UpdDir,       # 替身更新源(按 GitHub 真实布局摆好 v2)
    [Parameter(Mandatory)][string]$NewVer,       # v2 的版本
    [string]$OutDir   = "e2e-out"
)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$OutDir   = (Resolve-Path $OutDir).Path
# 🔴 PowerShell 变量名不分大小写:小写 ver 与参数 Ver 是同一个变量。云跑第二跑 E4 循环里给小写那个赋值,期望版本被悄悄改成新版号
#    ⇒ E5.samever 假红、E4.oldmap 假绿。参数一律只读:再有人赋值当场抛错、整趟红(静态那一道是 C12)。
#    ⚠ 要用 Set-Variable 重建:workflow 里是 `.\e2e.ps1 …` 调用,参数是优化过的局部变量,直接改 .Options 会抛
#      「Cannot set options on the local variable」(云跑第三跑 run 35731332274 就死在这一行;本机 -File 跑不出来)。
foreach ($n in 'OldTag', 'OldAsset', 'NewSetup', 'Ver', 'UpdDir', 'NewVer', 'OutDir') { Set-Variable -Name $n -Value (Get-Variable -Name $n -ValueOnly) -Option ReadOnly -Force }
$Here     = $PSScriptRoot
$Data     = "$env:LOCALAPPDATA\OpenDesign"
$Default  = "$env:LOCALAPPDATA\Programs\OpenDesign"
$Shot     = Join-Path $Here 'shot.ps1'
$RunKey   = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$script:fail = 0
function V([string]$name, [bool]$ok, [string]$detail) {
    if (-not $ok) { $script:fail++ }
    "{0} {1} :: {2}" -f $(if ($ok) { 'OK  ' } else { 'FAIL' }), $name, $detail
}
# 🔴 函数里要给人看的行一律 Write-Host:PowerShell 函数会把**所有**输出当返回值 ——
#    写成裸字符串的话,RunInstaller 返回的就不是退出码而是「几行字 + 退出码」的数组。
function Shot([string]$name) { Write-Host "  [截图] $name $(pwsh -NoProfile -File $Shot (Join-Path $OutDir "$name.png"))" }
function ProcsUnder([string]$d) {
    @(Get-CimInstance Win32_Process | Where-Object {
        $_.ExecutablePath -and $_.ExecutablePath.StartsWith("$d\", [StringComparison]::OrdinalIgnoreCase)
    } | ForEach-Object { "$($_.ProcessId) $($_.Name)" }) -join ', '
}
function KillUnder([string]$d) {
    Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like "$d\*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}
function UninstallEntries {
    @(Get-ChildItem 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall' -ErrorAction SilentlyContinue |
      ForEach-Object { Get-ItemProperty $_.PSPath } |
      Where-Object { $_.DisplayName -like 'OpenDesign*' } |
      ForEach-Object { "[$($_.PSChildName)] $($_.DisplayName) | $($_.UninstallString)" })
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
function WaitHealth([int]$limitSec) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $limitSec) { $h = QuickHealth; if ($h) { return $h }; Start-Sleep -Seconds 2 }
    return $null
}
function HealthVer([string]$health) {
    $m = [regex]::Match("$health", '"version":\s*"([^"]+)"'); if ($m.Success) { $m.Groups[1].Value } else { $null }
}
function ExeVer([string]$exe) { ((Get-Item $exe).VersionInfo.ProductVersion) -replace '(\.0)+$', '' }
# 挑战 a4:健康检查报的版本 = exe 版本 = 期望版本(ds_web.VERSION)。只看「有应答」会把半新半旧判成装好了。
function ThreeWay([string]$name, [string]$health, [string]$exe, [string]$want) {
    $hv = HealthVer $health; $ev = if (Test-Path $exe) { ExeVer $exe } else { '(没有 exe)' }
    V $name (($hv -eq $want) -and ($ev -eq $want)) "后台 $hv / exe $ev / 期望 $want"
}
function Wizard([string]$tag, [string[]]$procLike, [string]$setDir, [int]$timeout) {
    $log = Join-Path $OutDir "$tag-click-wizard.log"
    $argv = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $Here 'click-wizard.ps1'), $OutDir, $log, "$timeout",
           '-ProcLike', "`"$($procLike -join ',')`"", '-Tag', $tag)   # Start-Process 不替带空格的参数加引号
    if ($setDir) { $argv += @('-SetDir', "`"$setDir`"") }
    $p = Start-Process powershell.exe -ArgumentList $argv -PassThru -WindowStyle Hidden -RedirectStandardError "$log.err"
    return [PSCustomObject]@{ Proc = $p; Log = $log }
}
function WizardDone($w) {
    if (-not $w.Proc.WaitForExit(30000)) { Stop-Process -Id $w.Proc.Id -Force -ErrorAction SilentlyContinue }
    Write-Host "  ---- 替业主点向导($(Split-Path $w.Log -Leaf))----"
    Get-Content $w.Log, "$($w.Log).err" -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "    $_" }
    return @(Get-Content $w.Log -ErrorAction SilentlyContinue | Where-Object { $_ -match 'CLICK#' })
}
function RunInstaller([string]$exe, [string]$tag, [int]$limitMin) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $p = Start-Process $exe -PassThru
    $tick = 0
    while (-not $p.HasExited -and $sw.Elapsed.TotalMinutes -lt $limitMin) { Start-Sleep -Seconds 30; $tick++; Shot ("{0}-installing-{1}" -f $tag, $tick) }
    if (-not $p.HasExited) { Shot "$tag-stuck"; throw "${tag}:安装 $limitMin 分钟没结束" }
    Write-Host "  $tag 安装包退出码 $($p.ExitCode),耗时 $([int]$sw.Elapsed.TotalSeconds)s"
    return $p.ExitCode
}
function InstallOld([string]$at) {
    $p = Start-Process "$OutDir\old\$OldAsset" -ArgumentList "/S /D=$at" -PassThru
    if (-not $p.WaitForExit(300000)) { throw "旧版安装 5 分钟没结束" }
    return (Test-Path "$at\ds\bin\ds_shell.py") -and (Test-Path "$at\卸载.exe")
}
# 读桌面图标指向哪:用资源管理器双击图标时走的宽字符接口 IShellLinkW。
# 🔴 WScript.Shell 的 TargetPath 经系统 ANSI 代码页转换(英文 runner = 1252)⇒ 中文目录读回来是 `C:\OD ??\…`
#    (云跑第二跑 E5.shortcut)。它只留作对照打印(ShortcutAnsi),判读表在 evidence/20260922-t4-cloud2-run35728968821.md。
Add-Type -TypeDefinition @'
using System; using System.Text; using System.Runtime.InteropServices; using System.Runtime.InteropServices.ComTypes;
[ComImport, Guid("000214F9-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IOdShellLinkW {
  void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszFile, int cch, IntPtr pfd, uint fFlags);
}
[ComImport, Guid("00021401-0000-0000-C000-000000000046")] public class OdShellLink {}
public static class OdLnk {
  public static string Target(string path) {
    object o = new OdShellLink();
    try {
      ((IPersistFile)o).Load(path, 0);
      var sb = new StringBuilder(32768);
      ((IOdShellLinkW)o).GetPath(sb, sb.Capacity, IntPtr.Zero, 0);
      return sb.ToString();
    } finally { Marshal.ReleaseComObject(o); }
  }
}
'@
function DesktopLnk { "$([Environment]::GetFolderPath('Desktop'))\OpenDesign.lnk" }
function Shortcut { $l = DesktopLnk; if (Test-Path -LiteralPath $l) { [OdLnk]::Target($l) } else { '(没有)' } }
function ShortcutAnsi { $l = DesktopLnk; if (Test-Path -LiteralPath $l) { (New-Object -ComObject WScript.Shell).CreateShortcut($l).TargetPath } else { '(没有)' } }
# 图标指向 = 期望的 exe,且那个文件真的在(只比字符串的话,指向一个不存在的路径也能绿)
function ShortcutOk([string]$want) { $sc = Shortcut; ($sc -eq $want) -and (Test-Path -LiteralPath $sc) }
# 🔴 NSIS 卸载器先把自己拷到 %TEMP% 再跑、父进程马上退 ⇒ 只等父进程 + 睡 5 秒是赌时间(云跑第四跑:E3b 收尾后
#    B 那份卸载项还在 ⇒ E5.pre 红、E5 选目录页默认成了 B)。等拷贝那一份也走完(同 E6,攻题 #18),最多 120 秒。
function SilentUninstall([string]$at) {
    $u = Get-ChildItem $at -Filter 'Uninstall OpenDesign*.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $u) { Write-Host "  (静默卸载 ${at}:没找到卸载程序)"; return }
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $p = Start-Process $u.FullName -ArgumentList '/S' -PassThru; [void]$p.WaitForExit(180000)
    $un = 'x'
    while ($sw.Elapsed.TotalSeconds -lt 120 -and $un) {
        Start-Sleep -Seconds 2
        $un = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -like 'Au_*' -or $_.ProcessName -like 'Un_*' -or $_.ProcessName -like 'Uninstall OpenDesign*' } |
                ForEach-Object { "$($_.Id) $($_.ProcessName)" }) -join ', '
    }
    Write-Host "  (静默卸载 ${at}:$([int]$sw.Elapsed.TotalSeconds)s,还没退的卸载进程:$(if ($un) { $un } else { '无' }))"
}

$cfgPath = "$Data\UserData\.nanobot\config.json"
# 配置里业主在意的那几样(挑战 a7 / 攻题 #16):大脑选择 / 各厂商 key 引用 / 登录口令
function CfgFacts {
    $c = Get-Content $cfgPath -Raw -Encoding utf8 | ConvertFrom-Json
    $keys = @($c.providers.PSObject.Properties | ForEach-Object { "$($_.Name)=$($_.Value.apiKey)" }) -join ','
    "brain=$($c.agents.defaults.modelPreset) | keys=$keys | token=$($c.channels.websocket.token)"
}

# 资料与 key:放几样「丢了就出事」的东西,记下指纹。整场判据共用一份,任何一段动了它都会被抓到。
$marks = @("$Data\UserData\.openDesign\key.txt", "$Data\Data\e2e-档案-marker.md", "$Data\UserData\.openDesign\e2e-marker.txt")
function Marks {
    foreach ($m in $marks) {
        New-Item -ItemType Directory -Force -Path (Split-Path $m) | Out-Null
        if (-not (Test-Path $m)) { Set-Content -Path $m -Value "e2e $([guid]::NewGuid())" -Encoding utf8 }
    }
    $h = @{}; foreach ($m in $marks) { $h[$m] = (Get-FileHash $m).Hash }; return $h
}
function MarksSame([string]$tag, $before) {
    foreach ($m in $marks) { V "$tag.data 资料原样:$(Split-Path $m -Leaf)" ((Test-Path $m) -and ((Get-FileHash $m).Hash -eq $before[$m])) $m }
}

"== 下载已发布的旧版 $OldAsset"
gh release download $OldTag -p $OldAsset -D "$OutDir\old" --clobber

# ================================================================ E3 从已发布的 0.98.8 过渡
$Dir = "C:\AI Test\OpenDesign"
"== E3 旧版装在「$Dir」、开机自启开着、在托盘里跑 → 带界面装新版(选目录页不改)"
V 'E3.old 旧版装上了' (InstallOld $Dir) "$Dir"
$oldReg = (Get-ItemProperty 'HKCU:\Software\OpenDesign' -ErrorAction SilentlyContinue).InstallDir
V 'E3.old 旧版记下了自选目录' ($oldReg -eq $Dir) "InstallDir = $oldReg"
Set-ItemProperty $RunKey -Name 'OpenDesign' -Value "`"$Dir\OpenDesign.exe`""
$before = Marks
$dataCountBefore = @(Get-ChildItem "$Data\Data" -Recurse -File -ErrorAction SilentlyContinue).Count
# 挑战 a7:换壳那一次会跑 ds_provision 合并配置 ⇒ 业主选好的「大脑」、key 引用、登录口令都不许被重置
Start-Process "$Dir\OpenDesign.exe" | Out-Null
V 'E3.oldrun 旧版跑起来了(工作台应答)' ([bool](WaitHealth 240)) ""
$cfg = Get-Content $cfgPath -Raw -Encoding utf8 | ConvertFrom-Json
$cfg.agents.defaults | Add-Member -NotePropertyName modelPreset -NotePropertyValue 'mimo-v2.5-pro' -Force   # 业主换过大脑(模板默认是 mimo-v2.5)
# 登录口令也植一个非默认值(攻题 #16):换壳那一次若重新生成口令,业主手里那张「登录口令.txt」就登不进聊天了
$ws = $cfg.channels.websocket
$ws | Add-Member -NotePropertyName token -NotePropertyValue "e2e-token-$([guid]::NewGuid().ToString('N').Substring(0,12))" -Force
$cfg | ConvertTo-Json -Depth 32 | Set-Content $cfgPath -Encoding utf8
$cfgBefore = CfgFacts
"  配置业务字段(前):$cfgBefore"
Shot 'e3-01-old-running'
$w = Wizard 'e3' @('*electron-setup*') '' 420
$rc = RunInstaller $NewSetup 'e3' 6
$clicks = WizardDone $w
V 'E3.install 新安装包退出码 0' ($rc -eq 0) "$rc"
$dirLine = @($clicks | Where-Object { $_ -match '输入框=' }) | Select-Object -First 1
V 'E3.guidir 选目录页默认显示的就是旧版那个自选目录' ($dirLine -and $dirLine.Contains("输入框=$Dir")) "$dirLine"
Start-Sleep -Seconds 3
V 'E3.dir 装回了旧版那个自选目录' ((Test-Path "$Dir\OpenDesign.exe") -and (Test-Path "$Dir\resources\app.asar")) "$Dir"
V 'E3.dir 没在默认目录另装一份' (-not (Test-Path "$Default\OpenDesign.exe")) "$Default"
V 'E3.oldgone 旧程序文件没了(python\ ds\ 卸载.exe)' (-not ((Test-Path "$Dir\python") -or (Test-Path "$Dir\ds") -or (Test-Path "$Dir\卸载.exe"))) ((Get-ChildItem $Dir -Name -ErrorAction SilentlyContinue | Select-Object -First 12) -join ' ')
V 'E3.oldkey 旧卸载项没了' (-not (Test-Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\OpenDesign')) ""
$ents = UninstallEntries
V 'E3.newkey 「应用和功能」里只剩一个 OpenDesign' ($ents.Count -eq 1) "$($ents -join ' ; ')"
V 'E3.oldproc 旧版进程全收掉了' (-not (ProcsUnder "$Dir\python")) "$(ProcsUnder "$Dir\python")"
$h3 = WaitHealth 180
ThreeWay 'E3.samever 完成页拉起的新版:版本三方一致' $h3 "$Dir\OpenDesign.exe" $Ver
MarksSame 'E3' $before
$dataCountAfter = @(Get-ChildItem "$Data\Data" -Recurse -File -ErrorAction SilentlyContinue).Count
V 'E3.data 档案目录文件数没少' ($dataCountAfter -ge $dataCountBefore) "$dataCountBefore → $dataCountAfter"
$cfgAfter = CfgFacts
V 'E3.config 配置业务字段前后不变(大脑选择 / key 引用 / 登录口令)' ($cfgAfter -eq $cfgBefore) "前 $cfgBefore ;后 $cfgAfter"
$run = (Get-ItemProperty $RunKey -ErrorAction SilentlyContinue).OpenDesign
V 'E3.autostart 开机自启还在、指向新 exe' ($run -eq "`"$Dir\OpenDesign.exe`"") "$run"
V 'E3.shortcut 桌面图标指向新 exe(且那个文件在)' (ShortcutOk "$Dir\OpenDesign.exe") "IShellLinkW=$(Shortcut) ;对照 WScript=$(ShortcutAnsi)"

# ================================================================ E2 起窗
"== E2 起窗 / 三按钮 / 托盘 / 第二次打开 / 重绘 / 导航 / 退出 / 硬杀"
KillUnder $Dir
Push-Location $Here
node e2-drive.mjs "$Dir\OpenDesign.exe" $OutDir
$e2 = $LASTEXITCODE
Pop-Location
V 'E2 起窗判据整体' ($e2 -eq 0) "e2-drive.mjs rc=$e2(逐条见上)"

# ================================================================ E2v 版本对不上要说话
"== E2v 装好的后台版本被改旧 ⇒ 主进程必须弹「重新运行安装包」(安装被打断留下半新半旧的那个形状)"
KillUnder $Dir
$webPy = "$Dir\resources\ds\bin\ds_web.py"
$orig = Get-Content $webPy -Raw -Encoding utf8
($orig -replace '(?m)^VERSION = "[^"]+"', 'VERSION = "0.0.1"') | Set-Content $webPy -NoNewline -Encoding utf8
$elog = "$Data\Logs\electron.log"
$logLen = if (Test-Path $elog) { (Get-Item $elog).Length } else { 0 }
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
# Electron 的对话框在 Windows 上是 TaskDialog:字不在 Win32 子控件里,要走 UI Automation 读
function DialogText([uint32[]]$pids) {
    $root = [Windows.Automation.AutomationElement]::RootElement
    $all = $root.FindAll([Windows.Automation.TreeScope]::Children, [Windows.Automation.Condition]::TrueCondition)
    @($all | Where-Object { $pids -contains [uint32]$_.Current.ProcessId -and $_.Current.ClassName -eq '#32770' } | ForEach-Object {
        $_.FindAll([Windows.Automation.TreeScope]::Descendants, [Windows.Automation.Condition]::TrueCondition) | ForEach-Object { $_.Current.Name }
    }) -join ' '
}
Start-Process "$Dir\OpenDesign.exe" | Out-Null
$sw = [Diagnostics.Stopwatch]::StartNew(); $box = ''; $said = $false
while ($sw.Elapsed.TotalSeconds -lt 120 -and -not (($box -match '重新运行安装包') -and $said)) {
    Start-Sleep -Seconds 2
    $ours = @(Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq "$Dir\OpenDesign.exe" } | ForEach-Object { [uint32]$_.ProcessId })
    if ($ours.Count) { $box = DialogText $ours }
    $tailLog = ''
    if (Test-Path $elog) {
        $fs = [IO.File]::Open($elog, 'Open', 'Read', 'ReadWrite'); [void]$fs.Seek($logLen, 'Begin')
        $tailLog = (New-Object IO.StreamReader($fs, [Text.Encoding]::UTF8)).ReadToEnd(); $fs.Dispose()
    }
    $said = ($tailLog -match '0\.0\.1') -and ($tailLog -match [regex]::Escape($Ver))
}
Shot 'e2v-01-mismatch'
V 'E2v.box 弹了对话框,话里有「重新运行安装包」' ($box -match '重新运行安装包') "$box"
V 'E2v.log electron.log 记下了两个版本号' $said "看 $elog 新增部分"
KillUnder $Dir
Set-Content $webPy -Value $orig -NoNewline -Encoding utf8

# ================================================================ E4 更新
"== E4 $Ver → ${NewVer}:源不通 → 重试 → 「重启以更新」→ 向导"
KillUnder $Dir
$serveLog = Join-Path $OutDir 'e4-serve.log'
$w = Wizard 'e4' @('*electron-setup*') '' 900
Push-Location $Here
node e4-drive.mjs "$Dir\OpenDesign.exe" $OutDir $UpdDir 8900 $serveLog
$e4 = $LASTEXITCODE
Pop-Location
V 'E4 前半段(没查到 / 重试 / 按钮 / 交棒)整体' ($e4 -eq 0) "e4-drive.mjs rc=$e4(逐条见上)"
# 一条时间线量到底 —— 安装器何时起、何时退、exe 何时换版、新版何时应答。每 10 秒一张整屏。
$sw = [Diagnostics.Stopwatch]::StartNew(); $exeNow = $Ver
$lastShot = -99; $instSeen = $null; $instGone = $null; $flip = $null; $h = $null
while ($sw.Elapsed.TotalMinutes -lt 8 -and -not $h) {
    Start-Sleep -Seconds 3
    $t = [int]$sw.Elapsed.TotalSeconds
    $inst = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -like '*electron-setup*' })
    if ($inst.Count -and $null -eq $instSeen) { $instSeen = $t; "  +${t}s 安装器起来了:$($inst[0].CommandLine)" }
    if ($null -ne $instSeen -and -not $inst.Count -and $null -eq $instGone) { $instGone = $t; "  +${t}s 安装器退出了" }
    if ($t - $lastShot -ge 10) { $lastShot = $t; Shot ("e4-00-updating-{0:000}s" -f $t) }
    try { $exeNow = ExeVer "$Dir\OpenDesign.exe" } catch { $exeNow = '(读不到:正在换文件?)' }
    if ($null -eq $flip -and $exeNow -eq $NewVer) { $flip = $t; "  +${t}s exe 版本换成 $exeNow" }
    if ($null -ne $flip) { $h = QuickHealth }
}
$t = [int]$sw.Elapsed.TotalSeconds
for ($k = 0; $k -lt 30 -and $null -ne $instSeen -and $null -eq $instGone; $k++) {
    if (-not @(Get-CimInstance Win32_Process | Where-Object { $_.Name -like '*electron-setup*' }).Count) { $instGone = [int]$sw.Elapsed.TotalSeconds } else { Start-Sleep -Seconds 1 }
}
"  时间线:安装器起 +$instSeen s / 安装器退 +$instGone s / exe 换版 +$flip s / 新版应答 $(if ($h) { "+$t s" } else { '没等到' })(上限 480s)"
$clicks = WizardDone $w
$heads = @($clicks | ForEach-Object { if ($_ -match '页头:\[([^/\]]+)') { $Matches[1].Trim() } })
# 同一页 5 秒没翻过去量具会再按一次 —— 业主那边是一下;连续重复的页头只算一次
$prev = $null; $heads = @($heads | ForEach-Object { if ($_ -ne $prev) { $_ }; $prev = $_ })   # (Where-Object 没有 -Begin,本机 pwsh 实测会抛)
V 'E4.wizard 更新时按两下:「安装选项」→「安装完成」(U3/U4 照 ZCode;选目录页自己跳过)' (($heads -join '|') -eq '安装选项|安装完成') "$($heads -join ' → ')"
V 'E4.version 装上了新版' ($null -ne $flip) "$Ver → $exeNow"
V 'E4.relaunch 装完自己重新打开、后台应答' ([bool]$h) "$h"
ThreeWay 'E4.samever 新版:版本三方一致' $h "$Dir\OpenDesign.exe" $NewVer
Start-Sleep -Seconds 3
Add-Type -TypeDefinition @"
using System; using System.Runtime.InteropServices;
public static class Fg {
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
}
"@
# 攻题 #22:只采一瞬会被 CI 的控制台 / 截图工具抢走前台判假红 ⇒ 15 秒里轮询,**当过一次**前台就算
$sw = [Diagnostics.Stopwatch]::StartNew(); $fgPath = $null; $seenFg = @()
while ($sw.Elapsed.TotalSeconds -lt 15 -and $fgPath -ne "$Dir\OpenDesign.exe") {
    $fgPid = 0; [void][Fg]::GetWindowThreadProcessId([Fg]::GetForegroundWindow(), [ref]$fgPid)
    $fgPath = (Get-CimInstance Win32_Process -Filter "ProcessId=$fgPid" -ErrorAction SilentlyContinue).ExecutablePath
    $seenFg += "$fgPid $fgPath"; Start-Sleep -Milliseconds 500
}
V 'E4.front 新版窗口到过最前面(第四跑零点击那版落在后面)' ($fgPath -eq "$Dir\OpenDesign.exe") "见过的前台:$(($seenFg | Select-Object -Unique) -join ' ; ')"
Shot 'e4-01-after-update'
$ents = UninstallEntries
V 'E4.newkey 更新后「应用和功能」里仍只有一个 OpenDesign' ($ents.Count -eq 1) "$($ents -join ' ; ')"
V 'E4.dir 仍在原目录、没另装一份' (-not (Test-Path "$Default\OpenDesign.exe")) ""
MarksSame 'E4' $before
$full = (Get-ChildItem $UpdDir -Recurse -Filter "*$NewVer*.exe" | Select-Object -First 1).Length
$sent = 0; Get-Content $serveLog -ErrorAction SilentlyContinue | ForEach-Object { if ($_ -match '\.exe .* sent=(\d+)$') { $sent += [int64]$Matches[1] } }
"  E4 实际下载 $([math]::Round($sent/1MB,1)) MB / 整包 $([math]::Round($full/1MB,1)) MB"
$oldMapPath = "download/v$Ver/OpenDesign-$Ver-electron-setup.exe.blockmap"
$oldMap = @(Get-Content $serveLog -ErrorAction SilentlyContinue | Where-Object { $_.StartsWith("200 GET $oldMapPath ") })
$miss = @(Get-Content $serveLog -ErrorAction SilentlyContinue | Where-Object { $_ -match '^404 ' })
V 'E4.oldmap 旧版 blockmap 从它自己那个 release 的路径取到' ($oldMap.Count -ge 1) "要 $oldMapPath;实到 $($oldMap -join ' | ')"
V 'E4.delta 实际下载不到整包的 10%(增量成立)' ($full -gt 0 -and $sent -gt 0 -and $sent -lt 0.1 * $full) "$sent / $full 字节;404:$($miss -join ' | ')"
"  ---- 替身服务器请求 ----"; Get-Content $serveLog -ErrorAction SilentlyContinue | Select-Object -First 60 | ForEach-Object { "    $_" }
KillUnder $Dir
$srvPid = Get-Content (Join-Path $OutDir 'e4-serve.pid') -ErrorAction SilentlyContinue
if ($srvPid) { Stop-Process -Id ([int]$srvPid) -Force -ErrorAction SilentlyContinue }


# ================================================================ E6 软件在跑时卸载
"== E6 卸载「$Dir」那一份(软件在跑,带界面)"
Start-Process "$Dir\OpenDesign.exe" | Out-Null
V 'E6.pre 卸载前软件在跑' ([bool](WaitHealth 180)) ""
$before = Marks
$cfgBefore = CfgFacts
$u = Get-ChildItem $Dir -Filter 'Uninstall OpenDesign*.exe' | Select-Object -First 1
V 'E6.pre 卸载程序在' ([bool]$u) "$($u.FullName)"
$w = Wizard 'e6' @('Au_*', 'Un_*', 'Uninstall OpenDesign*') '' 300
$p = Start-Process $u.FullName -PassThru
[void]$p.WaitForExit(300000)
# NSIS 卸载器先把自己拷到 %TEMP% 再跑 ⇒ 等拷贝那一份也走完(攻题 #18:它挂着不退、完成框一直在,也要判红)
$sw = [Diagnostics.Stopwatch]::StartNew(); $un = 'x'
while ($sw.Elapsed.TotalSeconds -lt 120 -and $un) {
    Start-Sleep -Seconds 2
    $un = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -like 'Au_*' -or $_.ProcessName -like 'Un_*' -or $_.ProcessName -like 'Uninstall OpenDesign*' } |
            ForEach-Object { "$($_.Id) $($_.ProcessName)" }) -join ', '
}
$null = WizardDone $w
V 'E6.done 卸载程序(含拷到临时目录的那一份)自己走完了' (-not $un) "$un"
$left = ProcsUnder $Dir
V 'E6.proc 卸载时在跑的软件被收掉了' (-not $left) "$left"
V 'E6.files 安装目录清空了' (-not (Test-Path "$Dir\OpenDesign.exe") -and -not (Test-Path "$Dir\resources")) ((Get-ChildItem $Dir -Name -ErrorAction SilentlyContinue) -join ' ')
V 'E6.key 卸载项没了' (-not (UninstallEntries)) "$(UninstallEntries)"
V 'E6.shortcut 桌面图标没了' ((Shortcut) -eq '(没有)') "$(Shortcut)"
MarksSame 'E6' $before
$cfgAfter = CfgFacts
V 'E6.config 配置业务字段原样(卸载不许碰资料根)' ($cfgAfter -eq $cfgBefore) "前 $cfgBefore ;后 $cfgAfter"

# ================================================================ E3b 旧版在 A,新版装到 B
$A = "C:\AI Old\OpenDesign"; $B = "C:\AI New\OpenDesign"
"== E3b 旧版装在「$A」在跑 → 首装新版改选「$B」"
$before = Marks
$cfgBefore = CfgFacts
V 'E3b.old 旧版装上了' (InstallOld $A) "$A"
Start-Process "$A\OpenDesign.exe" | Out-Null
V 'E3b.oldrun 旧版跑起来了' ([bool](WaitHealth 240)) ""
$w = Wizard 'e3b' @('*electron-setup*') $B 420
$rc = RunInstaller $NewSetup 'e3b' 6
$null = WizardDone $w
V 'E3b.install 安装包退出码 0' ($rc -eq 0) "$rc"
V 'E3b.dir 装到了 B' (Test-Path "$B\OpenDesign.exe") "$B"
$left = ProcsUnder $A
V 'E3b.oldproc A 那份旧版的进程被收掉了' (-not $left) "$left"
V 'E3b.oldgone A 那份旧版被旧卸载器卸掉了(哨兵没了)' (-not (Test-Path "$A\ds\bin\ds_shell.py")) ((Get-ChildItem $A -Name -ErrorAction SilentlyContinue | Select-Object -First 8) -join ' ')
$ents = UninstallEntries
V 'E3b.newkey 「应用和功能」里只剩一个 OpenDesign' ($ents.Count -eq 1) "$($ents -join ' ; ')"
MarksSame 'E3b' $before
$cfgAfter = CfgFacts
V 'E3b.config 配置业务字段前后不变' ($cfgAfter -eq $cfgBefore) "前 $cfgBefore ;后 $cfgAfter"
KillUnder $B; SilentUninstall $B; KillUnder $A
# E3b 若红了,A 那份旧版可能还在(卸载项 / InstallDir 键)⇒ 不收的话会把 E3 的读数带脏
if (Test-Path "$A\卸载.exe") { $p = Start-Process "$A\卸载.exe" -ArgumentList '/S' -PassThru; [void]$p.WaitForExit(180000); Start-Sleep -Seconds 5 }
Remove-Item $A, $B -Recurse -Force -ErrorAction SilentlyContinue

# ================================================================ E3c 旧版卸不干净 → 拒装 → 解锁(=重启)后重装
# T5 第 1 轮 R1-1 / R1-4(verify.md):旧卸载器**先**删自启项与目录指针、**后**删文件;有文件被占住就卸不干净。
# 那时安装包拒装、提示「重启后再运行」—— 重试要能从同一个状态接着走:卸载器还在、指针与自启写回了,
# 重装(不带 /D,像业主那样直接双击)自己找回原目录、把旧文件收干净、自启指向新 exe、只剩一个卸载项。
# 目录带单引号 + 空格:安装包把路径拼进 PowerShell 单引号串时,这里会误报「关不掉」、旧卸载器根本不跑。
$LockDir = "C:\AI Lock's\OpenDesign"
"== E3c 旧版装在「$LockDir」、有文件被占住 ⇒ 第一次拒装且可重试 ⇒ 解锁后不带 /D 重装"
$before = Marks
$cfgBefore = CfgFacts
$stale = @(Get-ChildItem 'HKCU:\Software' -ErrorAction SilentlyContinue | Where-Object { "$((Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).InstallLocation)" -like '*OpenDesign*' } | ForEach-Object { $_.PSChildName })
V 'E3c.pre 量具:没有卸载项、没有旧目录指针、没有新版的安装位置记录' (-not (UninstallEntries) -and -not (Test-Path 'HKCU:\Software\OpenDesign') -and -not $stale.Count) "$(UninstallEntries) $($stale -join ',')"
V 'E3c.old 旧版装上了' (InstallOld $LockDir) "$LockDir"
Set-ItemProperty $RunKey -Name 'OpenDesign' -Value "`"$LockDir\OpenDesign.exe`""
# 另起一个进程占住哨兵(不共享 ⇒ 删不掉)。它是 pwsh.exe、不在安装目录下 ⇒ 安装包收进程时不会收它 —— 就像杀软 / 别的程序占着文件。
$lockPath = "$LockDir\ds\bin\ds_shell.py"
$env:OD_E2E_LOCK = $lockPath
$lockCmd = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes('$f = [IO.File]::Open($env:OD_E2E_LOCK, "Open", "Read", "None"); Start-Sleep -Seconds 900'))
$locker = Start-Process (Get-Process -Id $PID).Path -ArgumentList "-NoProfile -EncodedCommand $lockCmd" -PassThru -WindowStyle Hidden
function IsLocked([string]$f) { try { [IO.File]::Open($f, 'Open', 'Read', 'None').Dispose(); $false } catch { $true } }
$sw = [Diagnostics.Stopwatch]::StartNew(); while ($sw.Elapsed.TotalSeconds -lt 20 -and -not (IsLocked $lockPath)) { Start-Sleep -Milliseconds 300 }
V 'E3c.lock 量具:旧版的哨兵被别的进程占住了' (IsLocked $lockPath) "$lockPath 占用进程 $($locker.Id)"
$p = Start-Process $NewSetup -ArgumentList '/S' -PassThru
if (-not $p.WaitForExit(600000)) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
V 'E3c.refuse 第一次没装(新版文件没进去)' (-not (Test-Path "$LockDir\resources\app.asar")) "退出码 $($p.ExitCode)"
V 'E3c.refuse 旧卸载器真跑过(没被「关不掉」挡在门外;R1-4 单引号路径)' (-not (Test-Path "$LockDir\python")) ((Get-ChildItem $LockDir -Name -ErrorAction SilentlyContinue) -join ' ')
V 'E3c.refuse 量具:哨兵确实没删掉' (Test-Path $lockPath) ""
V 'E3c.refuse 旧卸载程序还在(R1-1:重试靠它认出这里有旧版)' (Test-Path "$LockDir\卸载.exe") ""
$ptr = (Get-ItemProperty 'HKCU:\Software\OpenDesign' -ErrorAction SilentlyContinue).InstallDir
V 'E3c.refuse 旧目录指针写回了(旧卸载器删过它)' ($ptr -eq $LockDir) "InstallDir = $ptr"
$run = (Get-ItemProperty $RunKey -ErrorAction SilentlyContinue).OpenDesign
V 'E3c.refuse 开机自启写回了(旧卸载器删过它)' ([bool]$run) "$run"
V 'E3c.refuse 「应用和功能」里没有半截新版' (-not (UninstallEntries)) "$(UninstallEntries)"
MarksSame 'E3c.refuse' $before
Stop-Process -Id $locker.Id -Force -ErrorAction SilentlyContinue
$sw = [Diagnostics.Stopwatch]::StartNew(); while ($sw.Elapsed.TotalSeconds -lt 20 -and (IsLocked $lockPath)) { Start-Sleep -Milliseconds 300 }
V 'E3c.unlock 量具:解锁了(相当于业主重启了电脑)' (-not (IsLocked $lockPath)) ""
$p = Start-Process $NewSetup -ArgumentList '/S' -PassThru
if (-not $p.WaitForExit(600000)) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
V 'E3c.retry 重装装回了原目录(没带 /D,自己找回来的)' ((Test-Path "$LockDir\OpenDesign.exe") -and (Test-Path "$LockDir\resources\app.asar")) "退出码 $($p.ExitCode)"
V 'E3c.retry 没在默认目录另装一份' (-not (Test-Path "$Default\OpenDesign.exe")) "$Default"
V 'E3c.retry 旧文件收干净了(ds\ python\ 卸载.exe)' (-not ((Test-Path "$LockDir\ds") -or (Test-Path "$LockDir\python") -or (Test-Path "$LockDir\卸载.exe"))) ((Get-ChildItem $LockDir -Name -ErrorAction SilentlyContinue | Select-Object -First 12) -join ' ')
$ents = UninstallEntries
V 'E3c.retry 「应用和功能」里只有一个 OpenDesign' ($ents.Count -eq 1) "$($ents -join ' ; ')"
$run = (Get-ItemProperty $RunKey -ErrorAction SilentlyContinue).OpenDesign
V 'E3c.retry 开机自启还在、指向新 exe' ($run -eq "`"$LockDir\OpenDesign.exe`"") "$run"
MarksSame 'E3c.retry' $before
$cfgAfter = CfgFacts
V 'E3c.retry 配置业务字段前后不变' ($cfgAfter -eq $cfgBefore) "前 $cfgBefore ;后 $cfgAfter"
KillUnder $LockDir; SilentUninstall $LockDir; KillUnder $LockDir
Remove-Item $LockDir -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Split-Path $LockDir) -Force -ErrorAction SilentlyContinue

# ================================================================ 模拟一台新电脑
"== 清空这台机器上的 OpenDesign 痕迹(E5 要的是全新机器)"
Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like '*OpenDesign*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Remove-Item $Data -Recurse -Force -ErrorAction SilentlyContinue
Remove-ItemProperty $RunKey -Name 'OpenDesign' -ErrorAction SilentlyContinue
Remove-Item 'HKCU:\Software\OpenDesign' -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$([Environment]::GetFolderPath('Desktop'))\OpenDesign.lnk" -Force -ErrorAction SilentlyContinue

# ================================================================ E5 全新机器带界面首装
$Fresh = "C:\OD 新装\OpenDesign"   # 空格 + 中文(旧判据 t36b:中文路径在中文控制台 936 下也得照常)
"== E5 全新首装(带界面),选目录页改成「$Fresh」"
V 'E5.pre 量具:这台机器上已经没有任何 OpenDesign 痕迹' (-not (UninstallEntries) -and -not (Test-Path $Data)) "$(UninstallEntries) $(Test-Path $Data)"
$w = Wizard 'e5' @('*electron-setup*') $Fresh 420
$rc = RunInstaller $NewSetup 'e5' 6
$clicks = WizardDone $w
V 'E5.install 安装包退出码 0' ($rc -eq 0) "$rc"
$heads5 = @($clicks | ForEach-Object { if ($_ -match '页头:\[([^/\]]+)') { $Matches[1].Trim() } })
$prev = $null; $heads5 = @($heads5 | ForEach-Object { if ($_ -ne $prev) { $_ }; $prev = $_ })
V 'E5.pages 首装按三页:安装选项 → 选定安装位置 → 安装完成(U4 照 ZCode 留着「为哪位用户」)' (($heads5 -join '|') -eq '安装选项|选定安装位置|安装完成') "$($heads5 -join ' → ')"
$dirLine = @($clicks | Where-Object { $_ -match '改目录:' }) | Select-Object -First 1
V 'E5.setdir 量具:选目录页确实改成了自选目录' ($dirLine -and $dirLine.Contains("→ [$Fresh]")) "$dirLine"
V 'E5.dir 装到了所选目录' ((Test-Path "$Fresh\OpenDesign.exe") -and (Test-Path "$Fresh\resources\app.asar")) "$Fresh"
V 'E5.dir 没在默认目录另装一份' (-not (Test-Path "$Default\OpenDesign.exe")) "$Default"
$ents = UninstallEntries
V 'E5.newkey 「应用和功能」里一个 OpenDesign' ($ents.Count -eq 1) "$($ents -join ' ; ')"
$run = (Get-ItemProperty $RunKey -ErrorAction SilentlyContinue).OpenDesign
V 'E5.autostart 全新安装默认不开机自启(design C:已知回归,设置页开关另单)' (-not $run) "$run"
V 'E5.shortcut 桌面图标指向新 exe(且那个文件在)' (ShortcutOk "$Fresh\OpenDesign.exe") "IShellLinkW=$(Shortcut) ;对照 WScript=$(ShortcutAnsi)"
V 'E5.provision 配置建好了(ds_provision 跑过)' (Test-Path "$Data\UserData\.nanobot\config.json") "$Data\UserData\.nanobot\config.json"
$h = WaitHealth 180
V 'E5.run 完成页勾着「运行」⇒ 装完软件自己起来了' ([bool]$h) "$h"
ThreeWay 'E5.samever 版本三方一致' $h "$Fresh\OpenDesign.exe" $Ver
Shot 'e5-01-running'
KillUnder $Fresh

# ---------------------------------------------------------------- 收尾:日志
New-Item -ItemType Directory -Force -Path "$OutDir\logs" | Out-Null
Copy-Item "$Data\Logs\*" "$OutDir\logs\" -Recurse -ErrorAction SilentlyContinue
"== 判据结束:FAIL $script:fail 条"
exit $(if ($script:fail) { 1 } else { 0 })
