# 替业主点安装向导(第五跑,业主选 C = 照 ZCode:更新时向导由人点)。**只点「下一步」「完成」,绝不点「取消」。**
# 跑在 Windows PowerShell 5.1(UI Automation 走 .NET Framework,不依赖 pwsh 带不带 WindowsDesktop)。
# 每到一页:打印页上的文字、单选/勾选框的状态,截一张整屏,再点。最多点 6 下。安装器进程出现过又消失 ⇒ 结束。
# 用法:powershell.exe -File click-wizard.ps1 <输出目录> <日志文件> [总超时秒]
# 日志直接写 UTF-8 文件:5.1 的标准输出被重定向时按控制台代码页编码,中文会变问号。每点一下的行带 ASCII 标记 CLICK#。
param([Parameter(Mandatory)][string]$OutDir, [Parameter(Mandatory)][string]$LogPath, [int]$TimeoutSec = 480)
function Say([string]$m) { Add-Content -Path $LogPath -Value $m -Encoding UTF8 }
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes
$AE = [System.Windows.Automation.AutomationElement]
$TS = [System.Windows.Automation.TreeScope]
$CT = [System.Windows.Automation.ControlType]
$Shot = Join-Path $PSScriptRoot 'shot.ps1'
$sw = [Diagnostics.Stopwatch]::StartNew(); $seen = $false; $clicks = 0; $lastPage = ''
function Of($el, $type) { $el.FindAll($TS::Descendants, (New-Object System.Windows.Automation.PropertyCondition($AE::ControlTypeProperty, $type))) }
while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec -and $clicks -lt 6) {
    $procs = @(Get-Process | Where-Object { $_.ProcessName -like '*electron-setup*' })
    if (-not $procs.Count) { if ($seen) { break }; Start-Sleep -Milliseconds 500; continue }
    if (-not $seen) { $seen = $true; Say "+$([int]$sw.Elapsed.TotalSeconds)s 安装器起来了" }
    foreach ($p in $procs) {
        $wins = $AE::RootElement.FindAll($TS::Children, (New-Object System.Windows.Automation.PropertyCondition($AE::ProcessIdProperty, $p.Id)))
        foreach ($w in $wins) {
            $texts = @(Of $w $CT::Text | ForEach-Object { $_.Current.Name } | Where-Object { $_ }) -join ' | '
            $opts = @(@(Of $w $CT::RadioButton) + @(Of $w $CT::CheckBox) | ForEach-Object {
                $on = $null
                try { $on = $_.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Current.IsSelected } catch {}
                if ($null -eq $on) { try { $on = ($_.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern).Current.ToggleState -eq 'On') } catch {} }
                "$($_.Current.Name)=$(if ($on) { '选中' } else { '未选' })"
            }) -join ' ; '
            $btn = @(Of $w $CT::Button | Where-Object { ($_.Current.Name -like '下一步*' -or $_.Current.Name -like '完成*') -and $_.Current.IsEnabled }) | Select-Object -First 1
            if (-not $btn) { continue }
            $page = "$texts || $opts || $($btn.Current.Name)"
            if ($page -eq $lastPage) { continue }   # 同一页刚点过、还没翻过去
            $lastPage = $page; $clicks++
            $t = [int]$sw.Elapsed.TotalSeconds
            Say "+${t}s CLICK#$clicks 文字:[$texts] 选项:[$opts] ⇒ 点「$($btn.Current.Name)」"
            & powershell.exe -NoProfile -File $Shot (Join-Path $OutDir ("e4-wizard-{0}-{1:000}s.png" -f $clicks, $t)) | Out-Null
            $btn.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
            Start-Sleep -Seconds 1
        }
    }
    Start-Sleep -Milliseconds 500
}
Say "+$([int]$sw.Elapsed.TotalSeconds)s 结束:安装器$(if ($seen) { '出现过' } else { '从没出现' }),共点 $clicks 下"
