# install.ps1 — OpenDesign Windows 一键安装(clone 仓库后运行本脚本,其余全自动)。
# ⚠️ UNTESTED 草稿(2026-07-03):无 Windows 目标机,只做过静态走查;真机首跑逐步核对。
#
# 用法(不依赖执行策略,Bypass 只对本次进程生效):
#     powershell -ExecutionPolicy Bypass -File C:\OpenDesign\bin\install.ps1
#
# 交互只有三处:nanobot onboard(设 WebUI 口令)、粘贴机主自己的 LLM key(D1)、
# (可选)改 apiBase/model。脚本可重复运行:已完成的步骤自动跳过。
#
# 手动逐步安装(脚本失败时的排查路径)见 docs/install-windows.md。

$ErrorActionPreference = "Stop"

function Step([int]$n, [string]$msg) {
    Write-Host ""
    Write-Host "[$n/7] $msg" -ForegroundColor Cyan
}

$DsRoot      = Split-Path -Parent $PSScriptRoot
$Venv        = Join-Path $env:USERPROFILE ".venvs\design-studio"
$VPython     = Join-Path $Venv "Scripts\python.exe"
$Nanobot     = Join-Path $Venv "Scripts\nanobot.exe"
$NanobotHome = Join-Path $env:USERPROFILE ".nanobot"
$ConfigJson  = Join-Path $NanobotHome "config.json"
$KeyDir      = Join-Path $env:USERPROFILE ".openDesign"
$KeyFile     = Join-Path $KeyDir "key.txt"

Step 1 "检查 Python(需要 3.10+)"
# 注意 Windows 自带的 python 可能是 Microsoft Store 的假别名(跑了只会弹商店),
# 所以不看命令存在与否,直接执行拿版本号。
$pyv = ""
try { $pyv = (& python -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null) } catch {}
if (-not $pyv) {
    Write-Error "没找到可用的 Python。装法:winget install -e --id Python.Python.3.12(或 python.org 官方安装器,勾 Add to PATH),装完新开 PowerShell 再跑本脚本。"
}
$parts = $pyv.Split("."); $major = [int]$parts[0]; $minor = [int]$parts[1]
if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
    Write-Error "Python $pyv 太旧,需要 3.10+。winget install -e --id Python.Python.3.12 后新开 PowerShell 再跑。"
}
Write-Host "  Python $pyv OK"

Step 2 "放开当前用户执行策略(RemoteSigned,以后启动 ds-nanobot.ps1 需要)"
$pol = Get-ExecutionPolicy -Scope CurrentUser
if ($pol -eq "RemoteSigned" -or $pol -eq "Unrestricted" -or $pol -eq "Bypass") {
    Write-Host "  已是 $pol,跳过"
} else {
    Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force
    Write-Host "  已设为 RemoteSigned"
}

Step 3 "建 venv 并安装 nanobot-ai + mcp"
if (-not (Test-Path $VPython)) {
    python -m venv $Venv
    if ($LASTEXITCODE -ne 0) { Write-Error "python -m venv 失败,报错见上" }
}
& $VPython -m pip install nanobot-ai mcp
if ($LASTEXITCODE -ne 0) { Write-Error "pip install 失败,报错见上(常见:网络;可加 -i 镜像源重试)" }

Step 4 "nanobot onboard(交互:开 WebSocket 通道 + 设 WebUI 口令,口令记下来)"
if (Test-Path $ConfigJson) {
    Write-Host "  已有 $ConfigJson,跳过 onboard(要重跑:删掉该文件后再运行本脚本)"
} else {
    & $Nanobot onboard
    if (-not (Test-Path $ConfigJson)) {
        Write-Error "onboard 结束但没生成 $ConfigJson,把上面的输出发回给部署者"
    }
}

Step 5 "LLM key(D1:机主自备,任何 OpenAI 兼容端点;部署者不提供)"
if (Test-Path $KeyFile) {
    Write-Host "  已有 $KeyFile,跳过(要换 key 直接编辑该文件)"
} else {
    New-Item -ItemType Directory -Path $KeyDir -Force | Out-Null
    $key = Read-Host "  粘贴 LLM key 后回车"
    $key = $key.Trim()
    if (-not $key) { Write-Error "key 为空,重跑本脚本" }
    # ascii 避免 PS5.1 默认编码带 BOM;key 都是 ASCII 字符
    Set-Content -Path $KeyFile -Value $key -NoNewline -Encoding ascii
    Write-Host "  已写入 $KeyFile"
}

Step 6 "合并 config(providers/model_presets/agents/mcpServers 四段;channels 不动)"
Write-Host "  模板默认大脑 = MiMo(https://token-plan-cn.xiaomimimo.com/v1, mimo-v2.5)。"
$apiBase = Read-Host "  用别家 LLM 就填它的 OpenAI 兼容 base URL,直接回车 = 用 MiMo 默认"
$model   = ""
while ($apiBase.Trim() -and -not $model.Trim()) {
    $model = Read-Host "  对应的 model 名(换了端点就必须填)"
}
$mergeArgs = @((Join-Path $DsRoot "config\nanobot.config.windows.jsonc"), $ConfigJson)
if ($apiBase.Trim()) { $mergeArgs += @("--api-base", $apiBase.Trim()) }
if ($model.Trim())   { $mergeArgs += @("--model", $model.Trim()) }
& $VPython (Join-Path $DsRoot "bin\ds_merge_config.py") @mergeArgs
if ($LASTEXITCODE -ne 0) { Write-Error "config 合并失败,报错见上" }

Step 7 "部署 workspace(AGENTS.md/SOUL.md + skills)"
$Ws = Join-Path $NanobotHome "workspace"
New-Item -ItemType Directory -Path (Join-Path $Ws "skills") -Force | Out-Null
Copy-Item (Join-Path $DsRoot "workspace\AGENTS.md"), (Join-Path $DsRoot "workspace\SOUL.md") $Ws -Force
Copy-Item (Join-Path $DsRoot "skills\*") (Join-Path $Ws "skills\") -Recurse -Force
Write-Host "  已拷入 $Ws"

Write-Host ""
Write-Host "安装完成。启动:" -ForegroundColor Green
Write-Host "    & `"$DsRoot\bin\ds-nanobot.ps1`" gateway"
Write-Host "然后浏览器开 http://127.0.0.1:8765/ ,用 onboard 设的口令登录,验证三件:"
Write-Host "  1) 问“有什么待办” -> 应调 list_todos 返回(脑通 + MCP 通)"
Write-Host "  2) 让它扫桌面提整理方案 -> 只出 dry-run 清单,不动文件(.approved 闸生效)"
Write-Host "  3) 记一条测试变更 -> 项目 md 里 C<n> 追加正常"
Write-Host "以后更新:在 $DsRoot 里 git pull(config/key 不会被动到)。"
