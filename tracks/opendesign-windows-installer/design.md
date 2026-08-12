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
