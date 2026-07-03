# ds-nanobot.ps1 — Windows 启动 OpenDesign 的 nanobot(大脑 = MiMo,工具 = ds MCP)。
# ⚠️ UNTESTED 草稿(2026-07-03,track opendesign-windows-prep T8):无 Windows 目标机,
#    只做过静态走查;真机首跑时逐行核对,尤其路径与 key 注入。
#
# key 注入(按 docs/deploy-security.md §1,D1 拍板 = 机主自备):key 是**机主自己买的
# LLM 的 key**(任何 OpenAI 兼容端点;部署者不发 key),放本机
# %USERPROFILE%\.openDesign\key.txt(内容只有 key 一行),或直接预设环境变量 DS_LLM_KEY。
# config 里引用 ${DS_LLM_KEY},不硬编码;端点/模型在 config 的 providers/model_presets 填。
#
# 用法:  .\ds-nanobot.ps1 gateway        |  .\ds-nanobot.ps1 status
#        .\ds-nanobot.ps1 agent -m "..."
# 前置:  python -m venv %USERPROFILE%\.venvs\design-studio
#        <venv>\Scripts\pip install nanobot-ai mcp
#        <venv>\Scripts\nanobot onboard   (生成 config;再按模板改 mcpServers/provider)

$ErrorActionPreference = "Stop"

$Venv    = Join-Path $env:USERPROFILE ".venvs\design-studio"
$Nanobot = Join-Path $Venv "Scripts\nanobot.exe"
$KeyFile = Join-Path $env:USERPROFILE ".openDesign\key.txt"

if (-not (Test-Path $Nanobot)) {
    Write-Error "ds-nanobot: 找不到 $Nanobot(先建 venv 并 pip install nanobot-ai mcp)"
}

if (-not $env:DS_LLM_KEY) {
    if (Test-Path $KeyFile) {
        $env:DS_LLM_KEY = (Get-Content $KeyFile -Raw).Trim()
    } else {
        Write-Error "ds-nanobot: 未设 DS_LLM_KEY 且找不到 $KeyFile(把机主自己的 LLM key 放入该文件,或预设环境变量 DS_LLM_KEY)"
    }
}

# DS_ROOT:本仓库根 = 本脚本所在 bin\ 的上一级(与 Python 侧 fallback 同一推导)
$env:DS_ROOT = Split-Path -Parent $PSScriptRoot

& $Nanobot @args
exit $LASTEXITCODE
