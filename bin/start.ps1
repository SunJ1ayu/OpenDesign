# start.ps1 — OpenDesign 一键启动/停止(track opendesign-start-ps1,2026-07-12)。
# ⚠️ UNTESTED 草稿:无 Windows 目标机,只做过静态走查;真机首跑逐行核对。
#
# 用法:  powershell -ExecutionPolicy Bypass -File D:\AI\OpenDesign\bin\start.ps1
#        powershell -ExecutionPolicy Bypass -File D:\AI\OpenDesign\bin\start.ps1 stop
#
# start(默认):幂等拉起 gateway(nanobot,端口 18790/8765)+ 工作台 ds-web(8766),
#   两者都在隐藏窗口跑,日志落 %USERPROFILE%\.openDesign\logs\,就绪后自动开浏览器。
#   已经在跑的腿跳过不重复起——重复运行本脚本安全。
# stop:按端口找 OwningProcess 停掉两者(不靠 PID 文件:起进程用的是 powershell
#   wrapper,杀 wrapper 不会连带杀 nanobot/python 真身,按端口杀才是真身)。
#
# 起进程复用 ds-nanobot.ps1 / ds-web.ps1(key 注入、venv 推导的单一来源,勿在此复制)。

$ErrorActionPreference = "Stop"

$Root    = Split-Path -Parent $PSScriptRoot
$LogDir  = Join-Path $env:USERPROFILE ".openDesign\logs"
$WebUrl  = "http://127.0.0.1:8766/"

# 端口是否有进程在听(PS 5.1 自带 Get-NetTCPConnection,Win8+)
function Test-PortListen([int]$Port) {
    $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return ($null -ne $c)
}

# 等端口就绪,超时返回 $false
function Wait-PortListen([int]$Port, [int]$Seconds) {
    for ($i = 0; $i -lt $Seconds * 2; $i++) {
        if (Test-PortListen $Port) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return (Test-PortListen $Port)
}

# 停掉在听某端口的进程(真身),报告干了什么
function Stop-PortOwner([int]$Port, [string]$Label) {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) { Write-Host "  $Label(:$Port)本来就没在跑"; return }
    $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $pids) {
        try {
            $p = Get-Process -Id $procId -ErrorAction Stop
            Stop-Process -Id $procId -Force -ErrorAction Stop
            Write-Host "  已停 $Label(:$Port)—— $($p.ProcessName) (PID $procId)"
        } catch {
            Write-Warning "  停 $Label(:$Port,PID $procId)失败:$($_.Exception.Message)"
        }
    }
}

# 隐藏窗口跑一个 .ps1,stdout/stderr 各落一个日志文件(redirect 两文件不能同名)。
# ⚠️ PS 5.1 的 -ArgumentList 拼命令行不自动加引号,-File 路径必须手动引(防装机路径带空格)
function Start-HiddenScript([string]$ScriptPath, [string[]]$ScriptArgs, [string]$LogBase) {
    $psArgs = @("-ExecutionPolicy", "Bypass", "-File", ('"{0}"' -f $ScriptPath)) + $ScriptArgs
    Start-Process -FilePath "powershell.exe" -ArgumentList $psArgs `
        -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $LogDir "$LogBase.log") `
        -RedirectStandardError  (Join-Path $LogDir "$LogBase.err.log") | Out-Null
}

# ---- stop 模式 -------------------------------------------------------------
if ($args.Count -ge 1 -and $args[0] -eq "stop") {
    Write-Host "OpenDesign 停止:"
    Stop-PortOwner 8766 "工作台 ds-web"
    if (Test-PortListen 8765) { Stop-PortOwner 8765 "gateway" }
    elseif (Test-PortListen 18790) { Stop-PortOwner 18790 "gateway" }  # 通道没开时只有 18790
    else { Write-Host "  gateway 本来就没在跑" }
    exit 0
}

# ---- start 模式(默认)-----------------------------------------------------
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Write-Host "OpenDesign 启动(仓库:$Root):"

# 腿 1:gateway(大脑 + MCP 工具 + WebSocket 通道)
if (Test-PortListen 8765) {
    Write-Host "  gateway 已在跑(:8765),跳过"
} else {
    if (Test-PortListen 18790) {
        # 上一次的 gateway 还活着但通道没开——起新的会撞 18790,先停旧的
        Write-Host "  发现无通道的旧 gateway(:18790 在、:8765 不在),先停再起"
        Stop-PortOwner 18790 "旧 gateway"
        Start-Sleep -Seconds 1
    }
    Write-Host "  起 gateway ..."
    Start-HiddenScript (Join-Path $PSScriptRoot "ds-nanobot.ps1") @("gateway") "gateway"
    if (-not (Wait-PortListen 18790 30)) {
        Write-Error "gateway 没起来(30s 内 :18790 无监听)。看日志:$LogDir\gateway.err.log"
    }
    if (-not (Wait-PortListen 8765 30)) {
        Write-Error ("gateway 起了但 WebSocket 通道没开(:8765 无监听)。多半是 config 里 " +
            "websocket 未启用:跑一遍 enable_webui.py(见 docs/install-windows.md §1)再重试。" +
            "日志:$LogDir\gateway.log")
    }
    Write-Host "  gateway 就绪(:18790 / :8765)"
}

# 腿 2:工作台 ds-web(纯只读,8766)
if (Test-PortListen 8766) {
    Write-Host "  工作台已在跑(:8766),跳过"
} else {
    Write-Host "  起工作台 ds-web ..."
    Start-HiddenScript (Join-Path $PSScriptRoot "ds-web.ps1") @() "dsweb"
    if (-not (Wait-PortListen 8766 15)) {
        Write-Error "工作台没起来(15s 内 :8766 无监听)。看日志:$LogDir\dsweb.err.log"
    }
    Write-Host "  工作台就绪(:8766)"
}

Write-Host ""
Write-Host "全部就绪 → $WebUrl (浏览器已打开;停止用: start.ps1 stop)"
Start-Process $WebUrl
