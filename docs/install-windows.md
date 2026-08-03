# OpenDesign Windows 安装清单(一页)

- 状态:✅ 2026-07-04 真机首装验证通过(Windows 11,装机路径 `D:\AI\OpenDesign`);
  当时踩的坑已全部修进脚本或写进本页 §7。
- 决策依据:`docs/deploy-security.md`(D0–D5 已全部拍板,2026-07-03)。

## 快捷安装(推荐):两条命令 + 最多四次交互

前置只有 Python 3.10+ 和 Git(没有就 `winget install -e --id Python.Python.3.12 Git.Git`,
Python 用官网安装器的话勾 Add to PATH;装完**新开** PowerShell)。然后:

```powershell
git clone https://github.com/SunJ1ayu/OpenDesign.git C:\OpenDesign   # 公开仓,不用登录 GitHub
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
- 取仓库(**公开仓,不需要登录 GitHub**,装了 [Git for Windows](https://git-scm.com) 直接 clone):
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
  **要用收件箱认领(0.25.0)就把工作区根也追加进来**(如
  `...;${USERPROFILE}/Desktop;D:/设计工作区`)——工作区接入(workspace.json)
  与整理白名单是两份独立配置,不会互相打通,整理收件箱两边都要配。
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

### 5c. 文件工作区+图墙(可选,P5;不配则相关面板显示引导空态)

把工作台接到真实项目文件夹(目录结构约定 = docs/workspace-taxonomy.md):

1. 复制 `config\workspace.example.json` → `config\workspace.json`(不进 git,属于本机);
2. `root` 填工作区根(如 `D:\\设计工作区`,JSON 里反斜杠要双写)。**从 0.8.0 起
   一般到这就够了**:工作台自动读取 `root` 下的项目目录(`01项目`/`01-项目`/
   `01_项目`/`01 项目` 里第一个存在的;目录名不同就加一行 `"projectsDir": "相对路径"`,
   填 `"."` 表示项目夹直接摆在 root 下),里面的文件夹直接出现在左侧项目列表
   (未建档的带「未建档」标,文件区/图墙照用;在对话里建档后自动对上——档案 key
   的各段(按 `-` 拆)都出现在唯一一个文件夹名里即自动绑定);
   **项目先按年份/客户等分了一层文件夹**(如 `D:\G2 DESIGN GROUP\2026\0315 某项目`)
   → 再加一行 `"projectsDepth": 2`(必须是数字不带引号),所有分组下的项目一起
   出现在列表里、行尾带分组小标。也可以直接在对话里说"把我的项目文件夹接进来",
   助手会问清布局帮你配好;
3. `projects` 手工映射仍然可用且**优先**(自动绑定歧义/绑错时用它纠偏):
   每行 = 项目档案 key → 工作区内项目文件夹相对路径(用 `/` 分隔)。
   **0.16.0 起不用手改**:在对话里说「XX 文件夹就是 YY 项目」,助手会调
   `bind_project` 写好映射(项目列表里同名两行=没绑上,一句话合并);
4. 存盘即生效(每请求现读,不用重启)。刷新工作台:项目页右列出现类目计数+最近
   文件+「打开文件夹」;图片缩略点进图墙(参考图索引∪项目文件夹图片)。
   一切只读;唯一的"动作"是打开资源管理器,且只能打开工作区内已映射的目录。
5. **收件箱认领(0.25.0 起)**:工作区根下建一个 `00-收件箱` 文件夹,新文件都丢
   这里;再把工作区根加进 `DS_ORGANIZE_ROOTS`(见 §3)。之后在对话里说
   「整理收件箱」→ 助手报建议并暂存方案 → 工作台左列「收件箱」卡片核对预览、
   点「确认执行」,文件才真正归位(点按钮=批准本体,这类方案不用跑 ds-approve)。
6. **首次盘点存量(采纳现状,0.26.0 起)**:配好上面 1–3 后,在对话里说
   「**接管我的工作区**」(或「盘点一下工作区」)→ 助手只读盘出收件箱/项目根/
   归档/共享结构、每个项目夹的绑定状态和根层散文件,并逐个引导你 `bind_project`;
   对某个已绑定项目说「整理它根目录的散文件」→ 助手把资料/参考图暂存成方案上卡片,
   CAD/SU/MAX/PSD 只口头提示不自动动。纯盘点零改动,搬动仍走卡片「确认执行」。

## 6. 交代给机主的三句话(D2:不做专门文书)

1. 你的文件永远在这台机器上;AI 读过的内容会随对话经**你自己的** LLM 账号上云。
2. 整理文件永远先出方案,你批准后才会动(收件箱方案=工作台卡片点「确认执行」,
   其他目录=终端跑 `ds-approve`);删除功能没有。
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
  **例外(2026-08-03 起,只影响这次之前就装好的机器):MCP 入口换成了统一的
  `bin\ds_mcp.py <tools|organize|refs>`**,而入口路径写在
  `%USERPROFILE%\.nanobot\config.json` 里 —— 那个文件**不在仓库里,`git pull` 改不到它**。
  所以这一次拉更新后**必须重跑一次装机脚本**,否则助手会**一个工具都调不到**:

  ```powershell
  powershell -ExecutionPolicy Bypass -File <DS_ROOT>\bin\install.ps1
  ```

  (只想合配置也行:`python <DS_ROOT>\bin\ds_merge_config.py <DS_ROOT>\config\nanobot.config.windows.jsonc %USERPROFILE%\.nanobot\config.json`;
  会自动备份原 config,已完成的步骤自动跳过。)
  **怎么确认没漏做**:重启 gateway 后问一句"有什么待办",能返回 = 通了;
  忘了重跑的话,旧入口现在会**明确报错说"本文件不再是 MCP 入口"**并让你重跑本步骤
  (报错在 gateway 日志 `%USERPROFILE%\.openDesign\logs\gateway.log` 里)。
- **启动脚本读的配置**:`ds-nanobot.ps1` 用默认 `%USERPROFILE%\.nanobot\config.json`;
  排查"改了配置没生效"先确认改的是这个文件。key 在 `%USERPROFILE%\.openDesign\key.txt`。
