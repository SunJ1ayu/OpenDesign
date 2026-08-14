# Design: opendesign-windows-installer

- Change: opendesign-windows-installer
- Status: draft —— **本文只定 S0(探路包)。完整安装器设计(S1)等 S0 真机结果再写。**

- 规划双出: **不适用(S0)** —— S0 不定架构,它是一个只回答"能/不能"的风险探针,
  方向谱为空(要么 embeddable Python 跑得动,要么跑不动)。
  **S1 正式设计必须跑双出**:那时才是真·开放方向(运行时形态 / 更新机制 / key 录入位置
  三处都有多个站得住的选项),且这单我自己干 ⇒ 命中触发条件。**这条不许在 S1 里省掉。**

## 为什么先做 S0 而不是直接造安装器

整个方案压在一个我验不了的假设上:**免装 Python(embeddable)能跑起这一整套**。
它与正常 Python 的差别是结构性的 —— `sys.path` 由 `python312._pth` 写死、默认**不**加载
`site-packages`、不带 pip/venv。119 个包里 25 个是 native 扩展,还有 3 个 MCP server 要
**以子进程方式**被 nanobot 拉起(子进程的解释器路径、工作目录、环境变量全得对)。

这些我在 Linux 上一个都验不了。所以 S0 = 用最小的东西把这个假设**测量到证伪或成立**,
而不是推理它。(CLAUDE.md:**假设要被测量证伪** —— 08-10 那次 346s 撞 300s cron 就是
推理代替测量的账。)

## Approach(S0 探路包)

一个 zip,业主解开、双击 `跑一下.bat`,它自己跑完自己打印收据。**只读、不装、不改机器**:

- 全部落在解压出来的那个文件夹里,不写注册表、不进 PATH、不碰 `%USERPROFILE%\.nanobot`
  (用文件夹内的 `fakehome` 当 HOME/USERPROFILE)。
- 删掉文件夹 = 完全消失。业主已有的 OpenDesign 安装**一根头发都不碰**。

包内容:

| 件 | 来源 | 大小 |
|---|---|---|
| `python\` | 官方 embeddable 3.12.10 解开 + `._pth` 放开 site-packages | ~22MB |
| `python\Lib\site-packages\` | 今晚离线装配好的 payload(119 个包) | ~355MB |
| `ds\` | 本仓 `bin/*.py` + `config/nanobot.config.windows.jsonc` + `workspace/` | ~小 |
| `跑一下.bat` | 唯一入口,调 `python\python.exe spike.py`,**不接管道** | — |
| `spike.py` | 判据本体(我写,见下) | — |

zip 压缩后估计 100–150MB。

> **`._pth` 这一步是全包最脆的一环**:embeddable 版默认注释掉 `import site`,不放开
> 就加载不到 site-packages。放开的写法有两种(改 `._pth` / 设 `PYTHONPATH`),
> S0 用 `._pth` 那种(装机后不依赖环境变量,更接近成品形态)。**它红了不代表方案死**,
> 只代表要换成带完整 Python —— 所以 spike 要能把"到底哪一步断的"打印清楚。

## S0 顺手挖出来的、S1 必须处理的两件(别到时候重新发现)

1. **MCP 启动命令写死了 venv 路径**:`config/nanobot.config.windows.jsonc:60` 是
   `${USERPROFILE}/.venvs/design-studio/Scripts/python.exe`。安装器**必须改写这三处**
   指向包内 python,否则三个工具服务一个都起不来。spike 的 S4d 测的就是这个真机制
   (不是为了让判据过而打的补丁)。
2. **`._pth` 会忽略 `PYTHONPATH`**,而 ds 的模块之间是平级 import
   (`ds_web.py` 直接 `import ds_common`)⇒ `ds/bin` 必须**写死进 `._pth`**,
   靠环境变量注入是无效的。已写进 `check-package.sh` 当机械检查。

## 体积构成(量出来的,不是估的)

包 251MB / zip 79MB。`site-packages` 228MB,其中 **93MB(41%)是 OpenDesign 一个都不用的东西**:

| 白带的 | 大小 | 是什么 |
|---|---|---|
| lark_oapi | 45MB | 飞书 |
| botocore + boto3 + s3transfer + jmespath | 32MB | AWS |
| anthropic | 7MB | 另一家 LLM 客户端(我们走 openai 兼容口连 MiMo) |
| telegram / slack_sdk / botpy / dingtalk_stream / slackify_markdown | 9MB | Telegram / Slack / QQ / 钉钉 |

都是 nanobot 自带的聊天平台接口,而 OpenDesign 只开 websocket 一条通道
(模板里飞书那段本来就写死 `enabled: false`)。

**实测可砍**:台架上把这 11 个卸掉后 spike 仍 29 PASS(网关照起、3 个 MCP 照连、
ds-web 照报 0.85.0)⇒ 不是启动期强依赖。S1 砍掉大约能到 **160MB / zip 50MB 上下**。
⚠️ 这是在 Linux 上量的**导入关系**,Windows 上要再验一次;S0 探路包**故意不砍** ——
先动依赖会把结论搅浑,红了分不清是 embeddable 的问题还是我删坏了。

## 依赖必须锁精确版本(还原台架时踩出来的)

出货包里是 `lark_oapi==1.5.5`。不带版本重装会拿到 **1.7.2,它要求 `websockets<16`,
而 nanobot 要 `>=16`** —— 直接互斥。也就是说**同一份 requirements 在不同日期装出来的
东西可能根本起不来**。

⇒ S1 的安装器必须携带**精确版本的离线 payload**(本单 `pip download` 出来的那 119 个
就是一个已解析好的自洽集合),不许在用户机器上现场解析。
**这反过来是离线方案的一个额外优点**,不只是"装机不联网"那么简单。
(若 S1 砍掉 lark-oapi,这个特定冲突自然消失,但"锁版本"这条不因此作废。)

## 业主已拍板的(08-12 夜)

1. **成品是正经安装器四件套**:安装器 exe(选路径 / 桌面图标 / 开机自启勾选框)+
   主程序 `OpenDesign.exe` + 卸载条目 + (签名待定,要花钱)。工具倾向 **Inno Setup**
   (VS Code 同款)。
2. **桌面外壳,不是弹浏览器**:自己的窗口 / 自己的任务栏图标 / 没有地址栏。**界面不重做**。
3. **常驻式**:关窗口 ≠ 退出,后台继续;**右下角托盘**里才是真退出。理由是业主原话
   ——「类似 openclaw 的常驻式软件……后期可以和 QQ 微信链接」。
4. **开机自启做成选项**(业主:「软件工程一般都会有的思维」),不替他决定。
5. **心跳默认关**,除非用户自己去设置里开。
   **"整理记忆"(dream)保持开着** —— 业主看过它是什么之后决定留;
   它只在有新对话时才跑,不干烧。SOUL.md 那个撞车记 backlog,本单不动。
7. **更新方式 = 行业主流的第 ②**:软件启动时查一次有没有新版 → 提示业主 →
   他点一下 → 自己下载安装 → 提示重启。**不做后台静默更新**,理由是更新有时会改
   助手的行为规则,那种变化他应该知道,而不是某天发现助手脾气变了。
   - **更新源 = 现在这个 GitHub Releases**(不另搭服务器,已在用)。
   - **分两层下**:OpenDesign 自己的代码 **1.1MB**(常改)vs 运行时 **269MB**(几乎不变)
     ⇒ 平时只下 1.1MB;运行时变了才需要完整安装包,那种情况明说"要重装"。
   - **更新失败要能退回旧版**,不许把业主卡在一个打不开的软件上。
   - **数据全程不碰**:记忆 / 对话历史 / 工作区配置(已按 start.ps1:79-94 核准过口径)。
8. **key + 登录口令:装完第一次打开时问**,不在安装过程里问。
   ⇒ 安装器不经手 key ⇒ 安装阶段不碰凭据,口子更小。
6. ⇒ **聊天平台那 9MB 全留**(QQ 就在里面,才 1MB),只砍确定用不上的 AWS 32MB。
   **原先"砍 93MB"的方案作废** —— 差点把业主明说的后路砍掉。

## 🔴 查出来的live问题:dream 一直开着,而且它有权改助手契约

`config/nanobot.config.windows.jsonc` **一个字都没提 dream / heartbeat** ⇒ 两个都在跑
底座默认值(dream 每 2h、heartbeat 每 30min)。**业主两台机器上现在就是这样。**

dream 干的事(`templates/agent/dream.md` + `agent/memory.py:482`):读最近 20 条还没处理过的
对话,让模型把值得长期记的事实**写进 `SOUL.md` / `USER.md` / `memory/MEMORY.md` /
`skills/*/SKILL.md`**,带 Write/Edit/ApplyPatch 工具,而且 prompt 里明写
"ruthless about pruning"—— **会主动删它认为过时的内容**。

后果(**已按 `bin/start.ps1:79-94` 逐行核准,不是推测**):

- 每次启动只覆盖三样:`AGENTS.md`、`SOUL.md`、`skills\*`;脚本注释明写
  **「运行目录里的 memory/sessions/cron/config.json 一个不碰」**。
  ⇒ **记忆不会被更新覆盖**(`USER.md`、`memory/MEMORY.md`、对话历史全都安全)。
  > ⚠️ 我第一版在这儿写成了"dream 写的东西无声消失",**说重了**。撞车只发生在
  > `SOUL.md` 这一个文件上。范围小得多。
- 唯一的撞车:**`SOUL.md` 两个写入方**(dream 会往里写"助手行为规则";start.ps1 每次
  启动用仓库版覆盖)⇒ dream 写进 SOUL.md 的内容每次重启被清掉,而且没人被告知。
- 只有**有新对话**时才触发(没有新记录直接返回、不调模型),不是干烧。

**定性:是个小缺陷,但覆盖的方向是对的那一边** —— 被清掉的正是"助手自己改自己的行为规则",
而那本来就该由我们掌握(08-02 加这条覆盖,就是因为运行目录里的 AGENTS.md 比仓库旧了三周
没人发现)。⇒ **真正该修的不是覆盖,是 dream 不该有权写 `SOUL.md`**。
不急、不影响用,记进 backlog;**别在安装器这一单里顺手动它**(那是他助手的脑子)。

⇒ **这不是安装器引入的问题,是本来就有的**,只是"常驻 + 开机自启"会把它放大到 24 小时。
**S1 开工前要单独跟业主确认**:dream 要不要关 / 要不要限制它能改哪几个文件。
**别顺手在安装器里替他决定** —— 那是他助手的脑子。

## Key trade-offs / risks

- **355MB 解压体积**换"用户不装 Python"。可接受:一次性,且业主机器上装的 3D 软件
  哪个都比这大。
- **没有代码签名** ⇒ SmartScreen 会拦。S0 是 zip + bat,不触发安装器那套告警,但成品会。
  已列 non-goal,业主拍板。
- **S0 绿了不等于安装器就绿**:它证明的是"运行时能跑",没证明"装/卸/开始菜单/更新"。
  别把 S0 的绿当成整单的绿。

## Alternatives considered

- **直接造安装器,红了再说** —— 否。150MB 的成品造完才发现运行时不行,方案形状要重来。
- **PyInstaller / Nuitka 打成单个 exe** —— 否(至少不是现在)。nanobot 要**拉起 3 个
  MCP 子进程**,onefile 模式下子进程解释器路径和临时解包目录是出了名的坑;而
  embeddable 方案里 `python\python.exe` 是一个货真价实、路径稳定的解释器。
  留作 S0 红了以后的退路之一。
- **让安装器联网 pip install** —— 否。业主机器在公司,装机时网络不可控,而且一旦
  PyPI 抽风装机就卡死;离线装配今晚已验证 rc=0。

## Test strategy (oracle)

**判据是我写的,不外包。** 业主只做一件事:双击,然后把屏幕上的字发给我。

六问,全部必须绿(`spike.py` 逐条打印 PASS/FAIL,最后打印总判和收据文件路径):

1. **S1 免装 Python 起得来** —— 打印 `sys.version` == 3.12.10。
2. **S2 25 个 native 扩展真能用**(不是只 import 成功):
   `cryptography` 真做一次加解密、`lxml` 真解析一段 XML、`PIL` 真开一张图、
   `pydantic_core` 真校验一个模型。
3. **S3 anydoc 真转一份文件** —— 直接搬 `install.ps1:76` 那条(CSV → markdown,
   断言 `45天` 在结果里)。**它从来没在 Windows 上真跑过。**
4. **S4 脚本化配置生成成立** —— 原样跑 `enable_webui.py` + `ds_merge_config.py`,
   再用 nanobot 自己的 loader 读回来,含**今晚补强过的那两问**
   (设了 key 解析出真值 / 没设当场 fail closed)。
5. **S5 网关 + ds-web 真起来了,而且是我们这一份** —— **这是"在使用现场验证"那条规矩的
   落点:运行中的目标自己打印身份,不是"文件躺在盘上"。**
   - 5a nanobot gateway:从**我们自己子进程的管道**里读到它的开机横幅
     (`Starting nanobot gateway version 0.2.2 on port 18795`)+ 3 个 ds MCP server
     全部 `connected` + `Agent loop started`;`GET /health` 回 `{"status":"ok"}`。
   - 5b ds-web:`GET /api/health` 回 `version` == 仓库里的 `VERSION`(0.85.0)
     且 `doc_reader.available` 为真 —— **运行中的进程自己报版本**。

   > ⚠️ **写这条判据时当场纠正了我自己的规格**:design 初稿写的是"`/health` 回显 version
   > 且 pid == 子进程 pid"。查了 `cli/commands.py:1111` —— nanobot 的 `/health`
   > **只回 `{"status": "ok"}`,既没有 version 也没有 pid**。断言写在不存在的字段上,
   > 跑起来会红在 KeyError 上,那等于**没红检过**(08-02 栽过同款)。
   > 身份改由上面两个真实存在的出口来证。
   > 另:`doc_reader` 走的是 `importlib.metadata`,**只证明包的元数据在,不证明它能用** ⇒
   > 它是弱证人,真证人是 S3 那次真转换。两个都留,别混为一谈。
6. **S6 能干净关掉** —— 收到停止信号后进程退出,端口释放。

### 这个 oracle 能被什么骗过?

逐条焊死,**每一条都对应 spike.py 里的一个具体动作**:

- **骗法1:业主机器上本来就装着 Python,`python` 命令走了 PATH 上那个** ⇒ 假绿。
  焊:`.bat` 只用**绝对路径**调包内 `python\python.exe`;`spike.py` 第一件事就打印
  `sys.executable` 和 `sys.prefix`,并**断言它们在本文件夹内**,不在就当场红。
- **骗法2:包导入的是业主机器上已有的 site-packages** ⇒ 假绿。
  焊:打印每个关键模块的 `__file__` 并**断言路径在本文件夹内**;同时打印完整 `sys.path`。
- **骗法3:应答的是别的进程**(业主自己那份 OpenDesign 正开着,占着 8765/8766)⇒ 假绿。
  焊三层:① 用**非常规端口**(gateway 18795 / ds-web 18796);② **起之前先探一次**,
  端口已被占就**当场红并说清楚**(而不是把别人的应答当成我们的绿);③ 开机横幅与版本号
  从**我们自己子进程的 stdout 管道**里读 —— 别的进程再怎么应答也进不了这根管子;
  ④ 关掉之后再探一次,必须不再应答。
- **骗法4:管道吃掉退出码**(我 08-11 一天犯两次,坏收据都还留在 evidence 里)。
  焊:`.bat` 和 `spike.py` 里**任何命令后面都不接管道**;子进程一律
  `subprocess.run(...)` 后显式判 `returncode`;总判由累计的 `failures` 列表算出,
  不由任何一行输出的字面文字决定。
- **骗法5:import 成功 ≠ native 扩展真能用**(有些是 lazy 加载,import 时不碰 DLL)。
  焊:S2 每个都**真做一次运算**,不是 `import x; print("ok")`。
- **骗法6:我事后手打收据**(规矩5:verify.md 的结果必须是机器写的收据行)。
  焊:`spike.py` 自己把全文写进 `收据.txt`,业主发我这个文件 / 或截屏;
  归档时进 `evidence/`。
- **骗法7:红了但看不出哪一步断的** ⇒ 拿到红也推进不了。
  焊:每条 FAIL 都带上"断在哪一句 + 原始报错前 20 行",最后按"哪一关最先红"给出
  一句人话结论。

**这个 oracle 答不了的**(明账,别当它答了):装/卸/开始菜单/更新路径/SmartScreen/
第二台机器的差异。那些是 S1 的事。

---

# S1 设计:安装器 + 桌面外壳 + 应用内更新

## 规划双出 · A 卷(主 agent)—— **落盘于读 B 卷之前**

> 双出规矩:我先独立出方案并 commit,再让 `gpt-5.6-sol` 在隔离目录对同一份**中立需求书**
> 独立出 B 卷,然后逐条对差异。B 卷是证据不是决定。

### A1. 桌面外壳选型 —— 选 **pywebview + pystray**(留在现有 Python 运行时里)

业主要的是:自己的窗口 / 自己的任务栏图标 / 没有地址栏 / 关窗不退出 / 托盘才是真退出,
**且界面不重做**(ds-web 已经在 8766 上跑着)。

| 选项 | 判 |
|---|---|
| **pywebview + pystray** ✅ | 复用包内 Python,不引第二套运行时/工具链;Win10/11 自带 Edge ⇒ WebView2 基本都在 |
| Electron | +150MB 和一整套 Node 工具链 —— 我们正在为砍 32MB 费劲,方向相反 |
| Tauri | 成品只有几 MB,但要 Rust 工具链且从 Linux 交叉编译到 Windows 很痛 |
| C# + WebView2 | exe 极小(Win 自带 .NET Framework),但引入第二种语言和第二条构建链 |
| 浏览器 `--app=` 模式 | **业主明确否掉**(「不是弹浏览器」),且任务栏图标是 Edge 的 |

**代价说清楚**:pywebview 在 Windows 上要 `pythonnet`(native cp312 轮子)+ WebView2 运行时。
这是**新的仅 Windows 依赖**,tasks.md 已写死「必须先进探路包再跑一趟真机」。
⇒ **S1a = 外壳探路包**,不是直接写安装器。WebView2 若缺,安装器带官方 Evergreen 引导程序兜底。

### A2. 装到哪 —— **每用户安装 `%LOCALAPPDATA%\Programs\OpenDesign`,不要 Program Files**

这条是 S1 最硬的一个岔路,理由链:

1. 业主要**应用内一键更新**。装进 `Program Files` ⇒ 写自己的目录要管理员权限
   ⇒ 每次更新弹 UAC,或者干脆写不进去。
2. 每用户安装 ⇒ Inno Setup `PrivilegesRequired=lowest`,**装的时候就不需要管理员**,
   更新时也不需要。开机自启写 `HKCU\...\Run`,同样不需要管理员。
3. 代价:不出现在"为所有用户安装"的语义里。这台机器是单人用,**代价为零**。

⇒ **数据与代码同树但分目录**:`app\`(会被更新替换)、`data\`(更新一个字节都不碰)。
`data\` 放:记忆 / 对话历史 / 工作区配置 / key 与口令。
> S0 已按 `bin/start.ps1:79-94` 核准过"更新只覆盖 AGENTS.md / SOUL.md / skills\*"的口径,
> 这里把它升级成**目录级隔离**,而不是继续靠一份"哪些文件能覆盖"的清单 ——
> 清单会漏,目录边界不会。

### A3. 更新:两层 + 清单 + 可回滚

- **层一 `code`(~1.1MB,常改)**:`ds\bin\*.py`、config 模板、ds-web dist、skills、AGENTS.md/SOUL.md。
- **层二 `runtime`(~269MB,几乎不动)**:`python\` + `site-packages\`。
- **GitHub Releases 里放一份 `manifest.json`**:
  `{code_version, runtime_version, min_runtime, code_url, sha256}`。
- 启动时查一次:
  - `runtime_version > 本机 runtime` ⇒ **不自动下**,明说"这次要重装完整包"并给链接(业主已拍板)。
  - 否则只下那 1.1MB,校验 sha256,解到 `app.new\`,**下次启动时原子换名**:
    `app` → `app.old`,`app.new` → `app`。
- **回滚**:换完之后跑一次冒烟自检(能起 ds-web 且 `/api/health` 报出预期版本);
  失败就把 `app.old` 换回来并告诉业主。`app.old` 保留一份。
- **数据不碰**:更新只动 `app\`,`data\` 在另一个目录 ⇒ 由 A2 的目录边界机械保证。

### A4. 进程模型 —— 外壳当爹

`OpenDesign.exe`(= 包内 python 跑 `shell.py`)负责:
1. **单实例**:命名互斥体;第二次双击 ⇒ 把已有窗口叫到前台,不再起一份。
2. 拉起两个子进程:nanobot 网关、ds-web。**它们的生命周期挂在外壳上**,托盘退出时一起收。
3. **端口冲突**:8766 被占 ⇒ 探测后换端口,并把真实端口传给 webview,不要硬写死。
4. 关窗口 = 隐藏到托盘;托盘菜单里"退出"才是真退出(业主明确要的常驻式)。

### A5. 顺序(每一步都能单独交付,不做大爆炸)

- **S1a 外壳探路包**:pywebview + pythonnet + pystray 塞进 embeddable Python,真机跑一趟。
  **这是 S1 唯一"可能推翻方案形状"的未知**,和 S0 同一个道理,先测量。
- S1b Inno Setup 脚本 + 在本机构建 `.exe`(每用户装、图标、卸载、开机自启勾选)。
- S1c 首次启动向导(key + 口令,写进 `data\`)。
- S1d 应用内更新(manifest + 换名 + 冒烟回滚)。
- S1e 砍 AWS 32MB —— **在 Windows 上重验一次导入关系**(Linux 上量的不算数)。

### A6. 我自己看得见的风险(写下来,别等 B 卷来提)

1. **pythonnet 在 embeddable Python 里可能装不起来** —— 它要找 .NET 运行时,而 `._pth`
   写死 sys.path 的环境下行为未验证。这就是 S1a 存在的理由。
2. **WebView2 不在的老机器**:Win10 早期版本可能没有。安装器要带 Evergreen 引导程序。
3. **杀软**:自制未签名 exe + 后台常驻 + 开机自启,很容易被 Defender/360 拦。
   签名要花钱(业主已知"签名待定")。**这条我控制不了,但要在交付说明里写清楚**。
4. **换名更新在 Windows 上会被文件占用打败**:`app\` 里的 .pyd 正被自己加载着 ⇒
   换名可能失败。所以**换名必须发生在启动早期、加载 app 之前**,不能在运行中做。
5. **开机自启 + 常驻**会把 design.md 上面记的 dream 问题放大到 24 小时。
   业主已拍板"dream 留着、SOUL.md 撞车记 backlog、本单不动" ⇒ 本单不动,但
   **交付说明里要提一句**,别让它变成没人知道的事。

## 规划双出 · 对差异(A=主 agent,B=gpt-5.6-sol;**B 是证据不是决定**)

证据:`evidence/S1-dualplan/B-requirement.md`(发给它的中立需求书,不含我的方案)
+ `evidence/S1-dualplan/B-plan-full.log`(它的完整输出)。

### 采纳(B 命中、我漏了或做得更差)—— 5 条

1. 🔴 **回滚 ≠ 数据还打得开**(B 自评"最容易被低估的一步",我判它对)。
   我的 A3 只做到"换回旧代码 + 冒烟自检"。B 指出:新版启动后可能已经改了数据库 schema /
   配置格式 / 索引,**那时候换回旧 exe,旧版打不开新数据** —— 回滚形同虚设。
   ⇒ 补一条**硬政策**:普通更新**不许做破坏性原地迁移**;N 与 N-1 必须双向读得动;
   真要改格式,单独走一条"数据升级"流程,不许伪装成普通更新。
2. 🔴 **版本化组件目录 + 指针切换**,取代我的"改名替换"。
   我的 A6 风险 #4 已经点出"Windows 会锁住正在用的 .pyd,改名可能失败",
   但我的设计**没解决它**,只是把改名挪到启动早期。B 的解法更干净:
   `components\app\<版本>\` 各自独立,永不覆盖正在跑的目录,靠 `state\active.json`
   一个指针切换,回滚 = 把指针指回 `previous.json`。**这条同时把回滚变成 O(1) 且无锁风险。**
3. 🔴 **`._pth` 里只登记一个稳定的引导目录**,由引导程序读 `active.json` 再把
   `components\app\<版本>` 加进 `sys.path`。
   我的方案会**每次更新都重写 `._pth`** —— 而 S0 的教训正是「`._pth` 忽略 PYTHONPATH,
   `ds/bin` 必须写死进 `._pth`」。两条撞在一起 = 每次更新都要改运行时里那个最脆的文件。
   B 这一层间接把"运行时"和"应用代码"真正解耦了。
4. **用户数据放到安装根目录之外**(`%LOCALAPPDATA%\OpenDesign\UserData\`),
   而不是我的"同树下分目录"。理由:卸载/更新逻辑不必再为"树里那个特殊目录"开例外,
   边界从**约定**变成**路径**。同时 B 补了一条我没写的:**卸载默认保留数据**,
   删数据必须是卸载器里单独的、默认不勾的选项。
5. **Job Object(kill-on-close)管进程树**,而不是我笼统的"外壳当爹"。
   我们这套底下还有 **3 个 MCP 子进程**是 nanobot 拉起来的 —— 孙子进程。
   外壳崩了之后靠"我去收子进程"收不干净,Job Object 是 Windows 上真正管得住整棵树的机制。

### 部分采纳 / 降档

6. **Ed25519 签名清单**(B 主张:只校验 SHA-256 不够,能替换 Release 的人也能替换哈希)。
   **理由成立**(仓库是 public,更新路径是在业主机器上执行代码),**但排到 S1d 再做**,
   不阻塞前面几步。诚实边界:它保护不了**第一次安装**(那要花钱买代码签名证书)。
7. **动态端口**:B 主张 supervisor 分配空闲端口再传给外壳。采纳,但保留 8766 为首选
   (业主的书签/习惯),占用时才换。**B 有一条我没想到、必须抄**:发现 8766 被占时,
   **绝不自动杀进程** —— 先核对 PID / 可执行文件路径 / 用户 / 本次启动的随机令牌,
   确认是自己的残留才处理;别人的就明确报错让人处理。

### 不采纳(我判 B 错或不适用)—— 1 条,但要说清理由

8. **外壳选 Electron —— 我判"未定",不是"否"。**
   > **✅ 08-13 已由 S1a 真机结案:轻方案跑通,不采纳 Electron。** 详见文末「外壳选型定稿」。
   B 的理由是可靠性(窗口/托盘/单实例/进程管理成熟、Linux 出 Windows 包链路成熟),
   代价它自己也写了:"压缩包增加数十 MB、安装后增加上百 MB"。
   我的 A1 选 pywebview 的理由是**不引第二套运行时**(我们正在为砍 32MB 费劲)。
   **两边都站得住,而它们的分歧点是一个可测量的事实**:
   `pywebview + pythonnet` 在 **embeddable Python + `._pth`** 下到底跑不跑得起来。
   ⇒ 不靠嘴仗定,**用 S1a 探路包一次真机跑答掉**(与 S0 同一套办法)。
   - 跑通 ⇒ 省下 ~150MB 和一整条 Node 工具链。
   - 跑不通 ⇒ **直接落 B 卷的 Electron 方案**(它已经设计完了,不浪费)。
   > 这不是骑墙:S0 的全部价值就是"用一次便宜的测量替掉一个昂贵的猜"。
   > 这里的猜价值 150MB + 一条工具链,而测量的成本是业主双击一次 bat。

### B 卷没有、只有 A 卷有的(因为它看不到我们的现场)

- **MCP 启动命令写死了 venv 路径**(`nanobot.config.windows.jsonc:60`),安装器必须改写三处。
- **dream 会写 `SOUL.md`,而"常驻 + 开机自启"把它放大到 24 小时**;业主已拍板本单不动,
  但交付说明里要提一句。
- 首选端口 8766 是业主已有的习惯。

### 结论:S1 架构定稿(A∪B)

程序结构照 B:
```
InstallRoot\(%LOCALAPPDATA%\Programs\OpenDesign)
  OpenDesignLauncher.exe
  components\{shell,python-runtime,app}\<版本>\
  state\{active.json,previous.json}
  staging\
用户数据(安装根之外):%LOCALAPPDATA%\OpenDesign\{UserData,Logs,Cache}\
```
外壳选型**已由 S1a 真机答掉(见下)**;其余全部按上面的对差异结论执行。

### 🔒 外壳选型定稿(2026-08-13,S1a 真机 11 PASS / 0 FAIL / 0 SKIP)

**选 `pywebview + pystray`,留在包内那套 Python 里。Electron 方案封存不走**
(它设计完整、没浪费:真出事可以直接取用)。

收据在 `evidence/20260813T153846-真机-S1a外壳-收据-全绿.txt`,机器是
`C:\Users\msi`(**第二台机器,此前没跑过 S0**)。上面第 8 条那个"可测量的分歧点"
——`pywebview + pythonnet` 在 embeddable + `._pth` 下跑不跑得起来 —— 答案是**跑得起来**:
四个组件全导得进、pythonnet 挂上了 CLR、`webview.start()` 真起了窗口并正常退出、
pystray 报 visible=True。⇒ 省下 ~150MB 与一整条 Node 工具链。

**但这张收据只覆盖"运行时可行性",下面几件它没证明,S1b 必须自己解决**
(判读全文在收据文件末尾):

- **WebView2 只证明了那台机器有**(151.0.4129.78)。考卷注释自己写了"通常自带但不保证"。
  ⇒ **安装器必须带微软官方 WebView2 Bootstrapper,装机时检测并补装** —— 不许赌。
  `.NET` 同理:这台挂得上不代表老机器,首启动要给可读错误而不是抛 CLR 栈。
- **窗口里没加载过 ds-web**。考卷故意只喂自带 HTML(不把"窗口起不起得来"和"后端行不行"
  混进一问,这个取舍是对的)⇒ **"外壳 + 真实后端"这个组合仍未跑过**。
- **"常驻"和"关窗不退出"没验**,只验了"图标能创建并显示 2 秒"。属 S1b 实现时的事。
- 🔴 **"无地址栏"那四个字,考卷其实没验**:`create_window()` 没传 `frameless=True`,
  也没有任何检查。pywebview 不是浏览器、本来就没有地址栏,所以事实大概率对,
  但**断言名比它问的强 —— 这是我自己写的考卷的一处 overclaim,记在账上**。
  结论不受影响(外观是参数问题,不是运行时可行性问题),措辞已收窄。

---

# S1c 设计:安装器本体(2026-08-14)

三块探路(S0 运行时 / S1a 外壳选型 / S1b 外壳真跑)全绿 ⇒ 方案风险出清,这一单造成品。
**S1c 只做一件事:把 S1b 真机验过的那棵树,变成业主双击一次就装好的 .exe。**
下面两个决策都是对上文定稿的**修正**,理由写在这里,不许日后当成"忘了照做"。

## 🔧 决策一:安装器工具 Inno Setup → **NSIS**(理由是可重复构建,不是偏好)

上文 A1/成品四件套写的是"倾向 Inno Setup(VS Code 同款);NSIS 备选"。**换成 NSIS。**

- **测量而不是推理**:Inno Setup 的编译器 `ISCC.exe` 只有 Windows 版,在 Linux 上要靠
  wine。本机 wine 9.0 **建不起 prefix**(`wineboot` 死在 `user32.dll.CreateDialogParamW`
  unimplemented → `could not load kernel32.dll`)。根因是这台机器上**几百个 deb 处在
  "解包了但没配置完"的状态**(`dpkg --audit`:连 curl、fonts-wine、libwine 都在里面),
  wine 是其中之一。修它=对系统跑一次全量 `dpkg --configure -a`,那是**为了工具偏好去动
  业主的机器**,不划算,也不该我一个人拍。
- **NSIS 的 `makensis` 是原生 Linux 程序**,把 Ubuntu 的两个 .deb 解到构建缓存目录即可用,
  **零系统改动**。探针已编出一个真的 PE 安装器:`Unicode true` + 简体中文界面 +
  `RequestExecutionLevel user` + LZMA solid 全部通过。
- **判据侧的代价要认**:Inno 的 `/VERYSILENT` 自测在 wine 下本来也跑不了 ⇒ 两条路
  在 Linux 上**都只能静态验 + 真机跑**。所以换工具**没有降低可验证性**,
  这一条是我特意核过才换的,不是拿"反正都验不了"当借口。
- 代价:NSIS 脚本比 .iss 更容易写出脚枪(经典的是卸载时 `RMDir /r` 把数据一起删)。
  ⇒ **这些脚枪逐条变成静态闸**(见 tasks.md 的 S1c-1),而不是靠我写的时候小心。

## 🔧 决策二:本单装**扁平树**,版本化组件 + 指针切换**随 S1d 更新机制一起落地**

上文「结论:S1 架构定稿(A∪B)」写的是 `components\{shell,python-runtime,app}\<版本>\`
+ `state\active.json` 的版本化布局。**S1c 不做它**,装的树与 S1b 真机跑绿的那份**结构一致**
(`<根>\python\` + `<根>\ds\`,数据在安装根之外的 `%LOCALAPPDATA%\OpenDesign\`)。

理由三条,按重量排:

1. **那套结构唯一的消费者是 S1d 的应用内更新,而 S1d 还不存在。** 先把没人用的结构装上,
   等真写更新时多半会发现形状不对 —— 本机为这个形状记过账:
   读侧按"像不像"挑字段、写侧没人维护,字段在界面上当了两个月摆设。
   **有写侧的时候再造读侧。**
2. **代价是零,不是"欠一笔"。** 想象中的代价是"业主将来要重装一次"——可 S1c 装的这一版
   **本来就没有应用内更新**,升到 S1d 那一版无论如何都得重装一次(下一个 .exe 双击)。
   ⇒ 现在做和那时做,业主的动作数一模一样。
3. **B 卷第 2 条(版本化目录躲开文件锁)解的是我们大概率没有的问题**,这一条要说清楚,
   免得日后被当成"偷懒删掉了一条采纳项":锁只发生在 `.pyd`/`.dll` 上,而
   **代码层(1.1MB)是纯 `.py` + web dist + 配置模板,运行时层(269MB)按业主已拍的板
   根本不做应用内更新(要动就重装整包)**。⇒ 到 S1d 再按当时的真实需求裁,
   `._pth` 那条耦合(B 卷第 3 条)也一并在那时解,**别现在为它改动全包最脆的那个文件**。

**保留不动的**:数据在安装根之外(A∪B 第 4 条)、卸载默认保留数据、每用户安装不要管理员
——这三条本单就要兑现,它们与版本化布局无关。

## 装完之后盘上长什么样

```
%LOCALAPPDATA%\Programs\OpenDesign\        ← 安装根(卸载时整棵删)
  OpenDesign.exe        启动器 stub(自有图标;Exec 后台的 pythonw + ds_shell.py)
  python\               免装 Python 3.12.10 + 全部依赖(S0/S1a/S1b 已验)
  ds\bin\ ds\config\ ds\web\ ds\workspace\  应用代码(= 仓库里那份)
  ds\图标.png           托盘图标(ds_shell.tray_image() 已经在找它)
  卸载.exe
%LOCALAPPDATA%\OpenDesign\                 ← 业主数据(卸载默认**不**碰)
  UserData\  Logs\  Cache\
```

`ds_shell.py:install_root()` = `HERE.parent.parent`,即 `<安装根>`——**与 S1b 包里一致**,
所以外壳一行不用改。这正是"沿用已验证的树"要买的东西。

## 这一单我自己看得见的、判据接不住的风险

1. **任务栏/窗口图标仍是 Python 的**。启动器 stub 有自己的图标(开始菜单/桌面看到的是它),
   但窗口一起来,任务栏显示的是 `pythonw.exe` 的图标 —— 要改得在 Windows 上用
   `WM_SETICON`/winforms 设窗口图标,**那层在 Linux 上一条考卷都跑不了**。
   ⇒ 本单**不做**,写进真机清单让业主用眼睛答一次"图标对不对",按他的反应再决定值不值。
   (S1a 的账教过一次:别把没验的事写进断言名。)
2. **没有代码签名 ⇒ SmartScreen 会拦**"未知发布者"。业主已知"签名待定"。
   ⇒ 真机清单里要**先告诉他会看见什么、该点哪里**,否则他会以为装坏了。
3. **WebView2 兜底只在缺失时才走**,而两台机器上它都在 ⇒ **这条兜底路径真机上大概率不会被走到**,
   收据只能证明"检测逻辑没炸",证明不了"补装真的成功"。**别把它当验过。**
