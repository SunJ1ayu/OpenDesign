# 替业主点安装 / 卸载向导 —— 云 Windows 判据 electron-e2e 的「手」(track opendesign-electron-shell;探路 U2 十跑磨出来的,
# 第十跑起读输入框走 WM_GETTEXT)。**只按 ID=1 的按钮(下一步 / 安装 / 完成 / 卸载),绝不碰「取消」。**
# 跑在 Windows PowerShell 5.1,走 Win32:按进程号枚举向导的顶层对话框(类名 #32770)→ ID=1 的按钮可用 ⇒ 发 WM_COMMAND(IDOK)。
#   NSIS 自己会再查一遍按钮是否可用(进度页上它是灰的,发了也不动)。
# 每 15 秒把看到的所有 #32770 顶层窗口(标题/进程号/按钮字)记一行,点不动时能看出卡在哪。
# 每到一页:记页头、单选/勾选状态、可见输入框的内容(选目录页的目录),截整屏,再按。同一页 5 秒没翻过去会再按一次;最多按 8 下。
# -SetDir:在有输入框的那一页先把目录改成它(像业主在选目录页自己改),日志记「原值 → 新值」。
# 日志直接写 UTF-8(5.1 的标准输出被重定向时按控制台代码页编码,中文会变问号);每按一下的行带 ASCII 标记 CLICK#。
# 用法:powershell.exe -File click-wizard.ps1 <输出目录> <日志文件> [总超时秒] [-ProcLike 名字模式,…] [-SetDir 目录] [-Tag 截图前缀]
param([Parameter(Mandatory)][string]$OutDir, [Parameter(Mandatory)][string]$LogPath, [int]$TimeoutSec = 480,
      [string[]]$ProcLike = @('*electron-setup*'), [string]$SetDir = '', [string]$Tag = 'wizard')
function Say([string]$m) { Add-Content -Path $LogPath -Value $m -Encoding UTF8 }
# -File 方式传进来的「a,b」是一整个字符串,不是数组 ⇒ 自己拆
$ProcLike = @($ProcLike | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
Add-Type -TypeDefinition @"
using System; using System.Text; using System.Collections.Generic; using System.Runtime.InteropServices;
public static class W {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr parent, EnumProc cb, IntPtr l);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder sb, int n);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder sb, int n);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] static extern int GetWindowLong(IntPtr h, int idx);
  [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, StringBuilder l);
  [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] public static extern IntPtr GetDlgItem(IntPtr h, int id);
  [DllImport("user32.dll")] public static extern bool IsWindowEnabled(IntPtr h);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  public static string Text(IntPtr h) { if (h == IntPtr.Zero) return ""; var sb = new StringBuilder(1024); GetWindowText(h, sb, 1024); return sb.ToString(); }
  // 输入框的内容要发 WM_GETTEXT 取:GetWindowText 读别的进程的控件只拿到标题,输入框没有标题 ⇒ 永远是空(第八、九跑的 E3.guidir 假红)
  public static string EditText(IntPtr h) { var sb = new StringBuilder(1024); SendMessage(h, 0x000D, (IntPtr)1024, sb); return sb.ToString(); }
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, string l);
  public static void SetEditText(IntPtr h, string v) { SendMessage(h, 0x000C, IntPtr.Zero, v); }
  public static IntPtr FirstEdit(IntPtr dlg) {
    IntPtr found = IntPtr.Zero;
    EnumChildWindows(dlg, (h, l) => { if (found == IntPtr.Zero && Cls(h) == "Edit" && IsWindowVisible(h)) found = h; return true; }, IntPtr.Zero);
    return found;
  }
  public static string Cls(IntPtr h) { var sb = new StringBuilder(256); GetClassName(h, sb, 256); return sb.ToString(); }
  public static uint Pid(IntPtr h) { uint p; GetWindowThreadProcessId(h, out p); return p; }
  public static List<IntPtr> Dialogs() {
    var r = new List<IntPtr>();
    EnumWindows((h, l) => { if (IsWindowVisible(h) && Cls(h) == "#32770") r.Add(h); return true; }, IntPtr.Zero);
    return r;
  }
  // 单选/勾选框:「字=1」选中,「字=0」没选
  public static string Options(IntPtr dlg) {
    var parts = new List<string>();
    EnumChildWindows(dlg, (h, l) => {
      if (Cls(h) == "Button" && IsWindowVisible(h)) {
        int st = GetWindowLong(h, -16) & 0xF;
        if (st == 2 || st == 3 || st == 4 || st == 9) parts.Add(Text(h) + "=" + ((long)SendMessage(h, 0x00F0, IntPtr.Zero, IntPtr.Zero) == 1 ? "1" : "0"));
      }
      if (Cls(h) == "Edit" && IsWindowVisible(h)) parts.Add("EDIT=" + EditText(h));
      return true; }, IntPtr.Zero);
    return string.Join(" ; ", parts.ToArray());
  }
  public static void PressOk(IntPtr dlg) { PostMessage(dlg, 0x0111, (IntPtr)1, GetDlgItem(dlg, 1)); }
}
"@
$Shot = Join-Path $PSScriptRoot 'shot.ps1'
$sw = [Diagnostics.Stopwatch]::StartNew(); $seen = $false; $clicks = 0; $lastPage = ''; $lastAt = -99; $lastDiag = -99
while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec -and $clicks -lt 8) {
    $t = [int]$sw.Elapsed.TotalSeconds
    $pids = @(Get-Process | Where-Object { $n = $_.ProcessName; @($ProcLike | Where-Object { $n -like $_ }).Count } | ForEach-Object { [uint32]$_.Id })
    if (-not $pids.Count) { if ($seen) { break }; Start-Sleep -Milliseconds 500; continue }
    if (-not $seen) { $seen = $true; Say "+${t}s 安装器起来了,进程号 $($pids -join ',')" }
    $dlgs = [W]::Dialogs()
    if ($t - $lastDiag -ge 15) {
        $lastDiag = $t
        $d = @($dlgs | ForEach-Object { "[$([W]::Text($_))] pid=$([W]::Pid($_)) 按钮1=[$([W]::Text([W]::GetDlgItem($_, 1)))] 可用=$([W]::IsWindowEnabled([W]::GetDlgItem($_, 1)))" }) -join ' ; '
        Say "+${t}s 看到:安装器进程号 $($pids -join ',');顶层对话框 $($dlgs.Count) 个 $d"
    }
    foreach ($dlg in $dlgs) {
        if ($pids -notcontains [W]::Pid($dlg)) { continue }
        $ok = [W]::GetDlgItem($dlg, 1)
        $okText = [W]::Text($ok)
        if (-not ([W]::IsWindowEnabled($ok) -and [W]::IsWindowVisible($ok))) { continue }
        # 首装时选目录页是进度页前的最后一页,按钮字是「安装(I)」(第七跑卡在这里 6 分钟);卸载向导是「卸载(U)」/「关闭(C)」
        if (-not ($okText -like '下一步*' -or $okText -like '安装*' -or $okText -like '完成*' -or $okText -like '卸载*' -or $okText -like '关闭*')) { continue }
        $head = "$([W]::Text([W]::GetDlgItem($dlg, 1037))) / $([W]::Text([W]::GetDlgItem($dlg, 1038)))"
        $page = "$head | $okText"
        if ($page -eq $lastPage -and $t - $lastAt -lt 5) { continue }   # 刚按过、还没翻页
        # 页头和按钮先换、页面内容后画:慢机器上一翻页就读,内容区还是一片空白(T5 修复跑 E3.guidir,截图为证)。
        # ⇒ 等选项出现且 200ms 内不再变(最多 3 秒)再读、再截图、再按。真空着 3 秒就照空的记 —— 判据照样红。
        $waited = 0; $raw = [W]::Options($dlg)
        while ($waited -lt 3000) {
            Start-Sleep -Milliseconds 200; $waited += 200
            $now = [W]::Options($dlg)
            if ($now -and $now -eq $raw) { break }
            $raw = $now
        }
        $opts = ((($raw -replace '=1\b', '=选中') -replace '=0\b', '=未选') -replace 'EDIT=', '输入框=')
        $edit = [W]::FirstEdit($dlg)
        if ($SetDir -and $edit -ne [IntPtr]::Zero) {
            $was = [W]::EditText($edit)
            [W]::SetEditText($edit, $SetDir)
            Start-Sleep -Milliseconds 300
            $opts += " ; 改目录:[$was] → [$([W]::EditText($edit))]"
        }
        $clicks++; $lastPage = $page; $lastAt = $t
        Say "+${t}s CLICK#$clicks 页头:[$head] 选项:[$opts](等页面内容 ${waited}ms)⇒ 按「$okText」"
        & powershell.exe -NoProfile -File $Shot (Join-Path $OutDir ("{0}-{1}-{2:000}s.png" -f $Tag, $clicks, $t)) | Out-Null
        [W]::PressOk($dlg)
        Start-Sleep -Seconds 1
    }
    Start-Sleep -Milliseconds 500
}
Say "+$([int]$sw.Elapsed.TotalSeconds)s 结束:安装器$(if ($seen) { '出现过' } else { '从没出现' }),共按 $clicks 下"
