# ds-web.ps1 — 启动 OpenDesign 工作台本地服务(纯只读,端口 8766)。
# 用法:  & "D:\AI\OpenDesign\bin\ds-web.ps1"    浏览器开 http://127.0.0.1:8766/
# 换端口:先 $env:DS_WEB_PORT = "8768" 再运行本脚本。
# ds_web.py 纯 stdlib(只用同目录 ds_todo/ds_common),系统 Python 直跑;
# 若 venv 存在则用 venv(与 ds-nanobot.ps1 同一个),保持解释器一致。

$ErrorActionPreference = "Stop"

$Root  = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$VPy   = Join-Path $env:USERPROFILE ".venvs\design-studio\Scripts\python.exe"
$Py    = if (Test-Path $VPy) { $VPy } else { "python" }

& $Py (Join-Path $Root "bin\ds_web.py")
exit $LASTEXITCODE
