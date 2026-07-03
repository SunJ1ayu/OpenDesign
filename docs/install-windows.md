# OpenDesign Windows 安装清单(一页)

- 状态:⚠️ 全流程 UNTESTED(无目标机);首装 = 部署者自己的 Windows,逐步核对。
- 决策依据:`docs/deploy-security.md`(D0–D5 已全部拍板,2026-07-03)。

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
& "$env:USERPROFILE\.venvs\design-studio\Scripts\pip" install nanobot-ai mcp
& "$env:USERPROFILE\.venvs\design-studio\Scripts\nanobot" onboard
```

(路径必须带引号:`& $env:USERPROFILE\...` 不引号时 PS 会在 `\` 处截断变量名报错。)

`onboard` 按 Quick Start 走:开 WebSocket 通道(=WebUI)、**设 WebUI 口令**(防同机/局域网他人,见 deploy-security §2)。

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

拷进 `%USERPROFILE%\.nanobot\workspace\`:

- `AGENTS.md`(操作契约,瘦路由)+ `SOUL.md`(口吻)——从开发机 workspace 取;
- `skills/organize/SKILL.md`、`skills/refs/SKILL.md` ——从本仓库 `skills/` 拷。

## 5. 启动与验证

```powershell
& "<DS_ROOT>\bin\ds-nanobot.ps1" gateway
```

浏览器开 `http://127.0.0.1:8765/`,用 onboard 设的口令登录。验证三件:

1. 问一句"有什么待办"→ 应调 `list_todos` 返回(证明 MCP 通、脑通);
2. 让它扫桌面提整理方案 → 只应返回 dry-run 清单,**不动文件**(`.approved` 闸生效);
3. 记一条测试变更再关闭 → 项目 md 里 `C<n>` 追加、状态流转正常。

## 6. 交代给机主的三句话(D2:不做专门文书)

1. 你的文件永远在这台机器上;AI 读过的内容会随对话经**你自己的** LLM 账号上云。
2. 整理文件永远先出方案,你在终端跑 `ds-approve` 批准后才会动;删除功能没有。
3. 出问题把日志/截图发给部署者(没有远程通道),修好后拉更新即可(deploy-security §7)。
