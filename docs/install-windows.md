# OpenDesign Windows 安装清单(一页)

- 状态:✅ 2026-07-04 真机首装验证通过(Windows 11,装机路径 `D:\AI\OpenDesign`);
  当时踩的坑已全部修进脚本或写进本页 §7。
- 决策依据:`docs/deploy-security.md`(D0–D5 已全部拍板,2026-07-03)。

## 快捷安装(推荐):两条命令 + 最多四次交互

前置只有 Python 3.10+ 和 Git(没有就 `winget install -e --id Python.Python.3.12 Git.Git`,
Python 用官网安装器的话勾 Add to PATH;装完**新开** PowerShell)。然后:

```powershell
git clone https://github.com/SunJ1ayu/OpenDesign.git C:\OpenDesign   # 首次弹浏览器授权 GitHub
powershell -ExecutionPolicy Bypass -File C:\OpenDesign\bin\install.ps1
```

`install.ps1` 自动做:执行策略、venv + pip、onboard、**开 WebUI 通道**、key 文件、
config 合并(`bin/ds_merge_config.py`,channels 段不碰)、workspace/skills 拷贝。
交互最多四处:onboard 向导、设 WebUI 登录口令、粘贴机主自己的 LLM key(D1)、
可选改 apiBase/model(回车 = MiMo 默认)。脚本可重复运行,已完成的步骤自动跳过。
装完照 §5 启动验证。

**脚本中途失败**:把报错原文发回部署者;下面 §0–§5 是同一流程的手动逐步版,用于排查。

## 0. 前置

- Windows 10/11,Python 3.10+(`python --version` 确认;装官方版勾 Add to PATH)。
- Git(可选:装了以后更新走 `git pull`;不装则每次更新重拷仓库文件,见 deploy-security §7)。
- 取仓库(私有仓,需先在目标机登录 GitHub:装 [Git for Windows](https://git-scm.com) 后
  `gh auth login` 或首次 clone 时按提示用浏览器授权):
  ```powershell
  git clone https://github.com/SunJ1ayu/OpenDesign.git C:\OpenDesign
  ```
  记路径为 `<DS_ROOT>`(下文以 `C:\OpenDesign` 为例);以后更新 = 在该目录 `git pull`。
- **机主自己的 LLM key + 端点**(D1:机主自备,任何 OpenAI 兼容端点;部署者不提供)。

## 1. 装 nanobot

```powershell
python -m venv "$env:USERPROFILE\.venvs\design-studio"
& "$env:USERPROFILE\.venvs\design-studio\Scripts\pip" install nanobot-ai==0.2.2 mcp==1.28.1
& "$env:USERPROFILE\.venvs\design-studio\Scripts\nanobot" onboard
```

(路径必须带引号:`& $env:USERPROFILE\...` 不引号时 PS 会在 `\` 处截断变量名报错。)

⚠️ `onboard` **实测不会开 WebUI 通道**(7-04 真机:装完 `channels.websocket.enabled=false`、
token 空 → gateway 报 `No channels enabled`,浏览器打不开)。手动装时必须补一步:

```powershell
& "$env:USERPROFILE\.venvs\design-studio\Scripts\python" C:\OpenDesign\bin\enable_webui.py <登录口令>
```

(幂等,改前自动备份 `config.json.bak`,只动 websocket 段。口令用于浏览器登录,
防同机/局域网他人,见 deploy-security §2。`install.ps1` 已含这一步。)

## 2. 填机主的 key(D1)

```powershell
mkdir "$env:USERPROFILE\.openDesign" -Force
notepad "$env:USERPROFILE\.openDesign\key.txt"   # 只放一行:机主自己的 LLM key
```

## 3. 合并 config

把 `config/nanobot.config.windows.jsonc` 的几段合并进 `%USERPROFILE%\.nanobot\config.json`(去掉注释),要改的:

- `providers.custom.apiBase` + `model_presets.primary.model` → 换成**机主买的那家 LLM**(模板里是 MiMo 示例)。
- `DS_ORGANIZE_ROOTS`:默认已按 D4 = 桌面+下载;机主要管别的目录,分号追加。
- 飞书段保持 `enabled: false`(可选通道,机主要用自己去开放平台建应用填凭据)。

## 4. 部署 workspace(操作契约 + skills)

拷进 `%USERPROFILE%\.nanobot\workspace\`(源都在本仓库内):

```powershell
Copy-Item C:\OpenDesign\workspace\AGENTS.md,C:\OpenDesign\workspace\SOUL.md `
          "$env:USERPROFILE\.nanobot\workspace\"
Copy-Item C:\OpenDesign\skills\* "$env:USERPROFILE\.nanobot\workspace\skills\" -Recurse -Force
```

## 5. 启动与验证

一条命令拉起全套(gateway + 工作台,隐藏窗口跑,就绪后自动开浏览器;重复运行安全,
已在跑的腿自动跳过;停止 = 末尾加 `stop`):

```powershell
powershell -ExecutionPolicy Bypass -File C:\OpenDesign\bin\start.ps1
```

日志在 `%USERPROFILE%\.openDesign\logs\`(gateway.log / dsweb.log,起不来先看
对应 .err.log)。排查或只想单起一腿时,旧的两条命令仍可用:

```powershell
& "<DS_ROOT>\bin\ds-nanobot.ps1" gateway    # 只起 gateway(前台窗口,看得到日志)
& "<DS_ROOT>\bin\ds-web.ps1"                # 只起工作台
```

⚠️ Windows 默认执行策略(Restricted)会拒跑 .ps1。首次先放开当前用户(一次性):

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

浏览器开 `http://127.0.0.1:8765/`,用安装时设的 WebUI 口令登录。
(打不开且 gateway 日志有 `No channels enabled` → 回 §1 补跑 `enable_webui.py` 再重启。)
验证三件:

1. 问一句"有什么待办"→ 应调 `list_todos` 返回(证明 MCP 通、脑通);
2. 让它扫桌面提整理方案 → 只应返回 dry-run 清单,**不动文件**(`.approved` 闸生效);
3. 记一条测试变更再关闭 → 项目 md 里 `C<n>` 追加、状态流转正常。

## 5b. 工作台(可选,track opendesign-workbench P0)

聊天之外的第二个入口:本地网页工作台(纯只读,不动任何文件)。`start.ps1` 已含
这一腿,单起用 `& "<DS_ROOT>\bin\ds-web.ps1"`。

浏览器开 `http://127.0.0.1:8766/`(与 8765 的聊天 WebUI 并行,互不影响;
端口被占先 `$env:DS_WEB_PORT = "8768"` 再跑)。前端产物已随仓带
(`web/dist/`),不用装 Node;`git pull` 即更新,刷新页面生效。
想要桌面感:Edge 地址栏右侧"安装为应用",得到独立窗口+任务栏图标。

装完(或 git pull 后)跑一次测试即真机验证:

```powershell
python "<DS_ROOT>\tests\test_ds_web.py"
```

## 6. 交代给机主的三句话(D2:不做专门文书)

1. 你的文件永远在这台机器上;AI 读过的内容会随对话经**你自己的** LLM 账号上云。
2. 整理文件永远先出方案,你在终端跑 `ds-approve` 批准后才会动;删除功能没有。
3. 出问题把日志/截图发给部署者(没有远程通道),修好后拉更新即可(deploy-security §7)。

## 7. 踩坑实录(2026-07-04 真机首装,按发生顺序)

- **假 Python**:Windows 自带的 `python` 可能是 Microsoft Store 的"应用执行别名"
  (跑了只弹商店)。装 `winget install -e --id Python.Python.3.12` 后**新开** PowerShell;
  `install.ps1` 已改为直接执行拿版本号来识破它。
- **git clone 连不上 GitHub,但浏览器能开 google**:代理软件的"系统代理"只管浏览器,
  **不管 git**。解法 = 开代理软件的 **TUN 模式**(Clash Verge:设置 → TUN Mode)。
  另查残留:`git config --global --get http.proxy` 有值且端口不对就
  `git config --global --unset http.proxy`(之前误设过的会一直毒化 git)。
- **执行策略告警**:用 `-ExecutionPolicy Bypass` 启动时,脚本内 `Set-ExecutionPolicy`
  会抛"被进程级 Bypass 覆盖"的告警——无害,CurrentUser 实际已设上;脚本已吞掉,
  看到深灰提示不用管。
- **WebUI 打不开 / `No channels enabled`**:onboard 不开 WebSocket 通道,见 §1 的
  `enable_webui.py`;`install.ps1`(2026-07-06 起)已自动做。
- **改配置一律跑仓库里的 .py 脚本**(git pull 后执行),别往 PowerShell 粘多行
  `python -c "..."`——PS 会把长单行拆碎,报 IndentationError。
- **更新的生效边界**:MCP 工具直接从 `<DS_ROOT>\bin\*.py` 运行,`git pull` 后**重启
  gateway 即生效**;但 `workspace\AGENTS.md`/`SOUL.md`/`skills\` 是**部署副本**,
  更新后要重拷(重跑 `install.ps1` 第 8 步,或手动 `Copy-Item`)。
- **启动脚本读的配置**:`ds-nanobot.ps1` 用默认 `%USERPROFILE%\.nanobot\config.json`;
  排查"改了配置没生效"先确认改的是这个文件。key 在 `%USERPROFILE%\.openDesign\key.txt`。
