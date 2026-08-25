# 一次性探针:静默安装(`/S`)装进一个**非空**目录,到底会不会被拦?
#
# 要定案的那件事(2026-08-25,track opendesign-fresh-install-fix 的评审冲突):
#   installer/OpenDesign.nsi 的 CheckDirEmpty 挂在 MUI 目录页的 **leave 回调**上
#   (`!define MUI_PAGE_CUSTOMFUNCTION_LEAVE CheckDirEmpty`),而 NSIS 在 `/S` 下
#   跳过所有页面。于是它那句 `/SD IDCANCEL` **可能根本执行不到** ——
#   而 `/SD` 只在静默下起作用 ⇒ 如果推断成立,那道"防线"在它唯一生效的模式里是惰性的。
#
#   一条腿(glm)说不可达、另一条腿(mimo)说它是对的保守侧,而我自己派发前也怀疑不可达。
#   **三方都在读文档/读源码推理,没有一方量过。** 这支探针就是去量它。
#
# 顺带量第二件(它才是真正要紧的后果):CheckDirEmpty 的注释自己写着
#   「G6 那个哨兵挡不住这一种:装完之后哨兵文件就在那儿了,它会说"是我们的"」
#   ⇒ 卸载段 `IfFileExists $INSTDIR\ds\bin\ds_shell.py` 认门通过 ⇒ `RMDir /r "$INSTDIR"`
#   ⇒ **业主本来就放在那个文件夹里的东西一起没**。这里真跑一次卸载,看那个文件还在不在。
#
# 🔴 判读规则 —— **写在看到结果之前**(免得事后往有利方向解释):
#   A. 安装进程正常退出 + 目录里出现哨兵 ⇒ CheckDirEmpty **没被调用** ⇒ 推断成立。
#   B. 安装进程卡住不退、或退了但什么都没装进去 ⇒ 它**拦住了** ⇒ 推断被证伪,
#      verify.md 原来那句「/SD IDCANCEL 让这条在静默下直接中止安装」是对的。
#   C. 卸载跑完之后,业主那个文件**还在** ⇒ 数据损失链不成立;**不在了** ⇒ 成立。
#
# 🔴 同别的探针:**只报告,不判卷**。脚本自己崩了才 exit 非零;结论由主 agent 下。
#    机器是一次性的云虚机,被删的是本脚本自己刚种下去的假文件,不碰任何真数据。
param(
    [string]$Tag    = 'win-installer-0.98.0',
    [string]$Asset  = 'OpenDesign-Setup-0.98.0.exe',
    [string]$OutDir = 'probe-out',
    [string]$Target = 'C:\od-nonempty',
    [int]   $WaitSec = 240
)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
function Say([string]$k, [string]$v) { "PHASE $k : $v" }

Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class W32N {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr p, EnumProc cb, IntPtr l);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  public static string Text(IntPtr h) { var sb = new StringBuilder(2048); GetWindowTextW(h, sb, 2048); return sb.ToString(); }
}
"@ -ErrorAction SilentlyContinue

# 卡住时弹框可能被别的窗口盖住(0.97 那次就是),所以直接问 Windows 要框里的文字。
function Dump-Dialogs {
    $script:dlg = @()
    $ccb = [W32N+EnumProc]{ param($c, $m)
        $ct = [W32N]::Text($c); if ($ct) { $script:dlg += "    L $ct" }; return $true }
    $cb = [W32N+EnumProc]{ param($h, $l)
        if ([W32N]::IsWindowVisible($h)) {
            $t = [W32N]::Text($h)
            if ($t) { $script:dlg += "  window: [$t]"; [void][W32N]::EnumChildWindows($h, $ccb, [IntPtr]::Zero) }
        }
        return $true }
    [void][W32N]::EnumWindows($cb, [IntPtr]::Zero)
    return $script:dlg
}

# ── 1 下载业主真正装的那个包 ─────────────────────────────────────
& gh release download $Tag --repo $env:GITHUB_REPOSITORY --pattern $Asset --dir $OutDir --clobber
$setup = (Resolve-Path (Join-Path $OutDir $Asset)).Path
Say '1 下载安装包' ("OK - {0},{1} MB" -f $Asset, [Math]::Round((Get-Item $setup).Length / 1MB, 1))

# ── 2 造一个"业主本来就有东西"的文件夹 ───────────────────────────
Remove-Item -Recurse -Force $Target -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Target | Out-Null
$mine = Join-Path $Target '业主的东西.txt'
Set-Content -Path $mine -Value '这是业主本来就放在这个文件夹里的文件。装机不该动它;卸载才是真正的风险点。' -Encoding UTF8
$mineHash = (Get-FileHash $mine -Algorithm SHA256).Hash
Say '2 造非空目录' "OK - $Target 里有 1 个文件(业主的东西.txt,sha256 $($mineHash.Substring(0,12))…)"

# ── 3 静默安装进这个非空目录 ─────────────────────────────────────
# NSIS 规矩:`/D=` 必须是**最后一个**参数,且**不能加引号**。
$sw = [Diagnostics.Stopwatch]::StartNew()
$ip = Start-Process $setup -ArgumentList "/S /D=$Target" -PassThru
while (-not $ip.HasExited -and $sw.Elapsed.TotalSeconds -lt $WaitSec) {
    Start-Sleep -Seconds 20
    "  [装机中 $([int]$sw.Elapsed.TotalSeconds)s] " + ((Dump-Dialogs) -join ' ')
}
$sw.Stop()
if ($ip.HasExited) {
    Say '3 静默安装' "退出了 —— 退出码 $($ip.ExitCode),耗时 $([int]$sw.Elapsed.TotalSeconds)s"
} else {
    Say '3 静默安装' "**没退出** —— 等了 $([int]$sw.Elapsed.TotalSeconds)s 还在跑(八成卡在弹框上)"
    (Dump-Dialogs) | ForEach-Object { $_ }
}

# ── 4 装进去了没有(看哨兵) ─────────────────────────────────────
$sentinel = Join-Path $Target 'ds\bin\ds_shell.py'
$installed = Test-Path $sentinel
Say '4 装到底了吗' ("哨兵 ds\bin\ds_shell.py {0};目录里现在有 {1} 个顶层条目" -f `
    $(if ($installed) { '在 —— 装进去了' } else { '不在 —— 没装进去' }),
    (Get-ChildItem $Target -Force -ErrorAction SilentlyContinue).Count)

# ── 5 业主那个文件被动过吗(装机阶段) ───────────────────────────
$aliveAfterInstall = Test-Path $mine
Say '5 装完之后业主的文件' ("{0}" -f $(if ($aliveAfterInstall) {
    if ((Get-FileHash $mine -Algorithm SHA256).Hash -eq $mineHash) { '还在,内容没变' } else { '还在,但内容变了' }
} else { '**没了**' }))

# ── 6 真跑一次卸载,看那个文件还在不在 ───────────────────────────
$uninst = Join-Path $Target '卸载.exe'
if (Test-Path $uninst) {
    $u = Start-Process $uninst -ArgumentList "/S _?=$Target" -PassThru
    $usw = [Diagnostics.Stopwatch]::StartNew()
    while (-not $u.HasExited -and $usw.Elapsed.TotalSeconds -lt 120) { Start-Sleep -Seconds 10 }
    $usw.Stop()
    Start-Sleep -Seconds 5
    Say '6 静默卸载' ("{0},耗时 $([int]$usw.Elapsed.TotalSeconds)s" -f `
        $(if ($u.HasExited) { "退出码 $($u.ExitCode)" } else { '**没退出**' }))
    $alive = Test-Path $mine
    Say '7 卸载之后业主的文件' ("{0}(目录本身 {1})" -f `
        $(if ($alive) { '**还在**' } else { '**没了 —— 被 RMDir /r 一起删了**' }),
        $(if (Test-Path $Target) { '还在' } else { '也没了' }))
} else {
    Say '6 静默卸载' "跳过 —— $uninst 不存在(说明第 3 相压根没装进去)"
    Say '7 卸载之后业主的文件' '不适用'
}

"";"════ 原始事实到此为止,判读规则见本文件头部,结论由主 agent 下 ════"
