# 独立方案挑战:OpenDesign「每家厂商各存各的 key、随时切换」

你是独立的第二意见。仓库快照是 OpenDesign(室内设计师用的本地 AI 助手,Windows 桌面应用)。
请**先从用户目标推演失败场景,再挑战拟议的行为改变**。不要写代码,只读仓库。

## 用户是谁、原话

- 业主是室内设计师,不是程序员;在自己的 Windows 电脑上用装好的 OpenDesign(安装包形态)。
- 目前支持两家大模型厂商:MiMo(小米)和 DeepSeek。
- 对话记录:我问「你平时会在 MiMo 和 DeepSeek 之间来回换吗?」业主答:「会 先做换供应商这个吧」。
- 他看过一张对照页,对这一条的描述(**这是 agent 写的,不是业主原话**):
  「每家厂商各存各的,配好的都亮绿点,聊天框菜单里全列出来,点一下就换」。
- 业主从没说过「换的时候等多久可以接受」。

## 现在的行为(均已读代码核过,路径可查)

- key 只存一把:`<home>/.openDesign/key.txt`(`bin/ds_credential.py` 的 `save()`/`status()`)。
  换厂商 = 在「AI 模型 key」卡片(`web/src/LlmKeyCard.tsx`)选厂商 + 粘该厂商的 key + 保存;
  旧 key 被覆盖。配置 `~/.nanobot/config.json` 里只有 `providers.custom`,`apiKey` 永远是
  `${DS_LLM_KEY}` 这种引用(key 原文永不进配置),`apiBase` 被改成该厂商的地址。
- 后台大脑进程叫「网关」(nanobot 0.2.2,版本固定)。装好的应用由外壳 `bin/ds_shell.py` 启动网关,
  **启动时**从 key.txt 读 key 注入网关进程的环境变量(`build_env` / `bin/ds_shell_core.py` 的
  `service_envs`/`child_env`;key 只进网关那条腿)。保存 key 后,工作台 `bin/ds_web.py`
  通过外壳的单实例锁通道请外壳重启网关(`ds_shell_bridge_restart`);没有外壳时回 manual,界面让业主手动重启。
- 同一厂商内换模型(输入框里的模型按钮,`web/src/chat/modelPicker.ts`、`ChatPage.tsx`;
  后端 `ds_credential.select_model`)只改 `agents.defaults.modelPreset`,不重启:
  nanobot 每条消息前重读配置(`nanobot/agent/loop.py` `_refresh_provider_snapshot`)。
- 另有两种非主路径的启动器:`bin/ds-nanobot.ps1`(早期 git-pull 部署,只设 `DS_LLM_KEY`)、
  Linux 开发机的 `bin/ds-nanobot`(从别处读 key,配置里引用的是 `${MIMO_TP_KEY}`)。
- 装机时 `bin/ds_provision.py` → `bin/ds_merge_config.py` 生成配置;更新时不重新合并配置。

## 已做的最小实验(2026-09-21,主 agent 亲跑)

1. nanobot 0.2.2 一份配置里放两条 provider:`providers.custom`(`${DS_LLM_KEY}`)和一条自定义名
   `providers.od_deepseek`(`${DS_LLM_KEY_DEEPSEEK}`),两个预设分别 `provider: "custom"` / `"od_deepseek"`:
   `load_provider_snapshot` 按当前预设分别拿到对的地址和对的 key。
2. 配置里引用了一个环境里**没有**的变量 ⇒ 整份配置加载抛 `ValueError`(不管当前预设用不用它)。
   启动时 = 网关起不来;运行中每条消息前的重读 = 抛错被 `logger.exception` 吞掉,**保留旧 provider 继续用**。
3. 变量设为空串 ⇒ 加载通过,该 provider 的 key 是空串(调用时才会失败)。
4. Linux 开发机上网关从启动到 websocket 端口就绪约 2.3 秒(MCP 子进程是第一条消息时才连)。
   **业主 Windows 机器上重启网关要多久:没量过**;安装后首次冷启动曾见过接近 4 分钟。

## 硬约束

- key 原文永不写进配置文件、永不回显给浏览器、报错文本不带 key(见 `bin/ds_credential.py` 模块头)。
- 装好的应用(外壳形态)是主路径;git-pull 与 Linux 开发机那两种**不能被弄坏**(照旧单厂商能用即可)。
- 业主不是程序员:任何需要他理解「后台/环境变量/重启」的步骤都是成本。
- 界面显示的当前厂商/模型必须与真正在回答的一致;换不成功要明说。

## 拟改变的、用户看得见的行为

- 两家的 key 可以同时存着;填/换一家不影响另一家。
- 聊天框的模型按钮菜单列出所有已配 key 的厂商的模型(按厂商分组),点了就换;换过去再换回来不用再粘 key。
- 老用户升级后,原来那把 key 自动归到它本来属于的那一家,不用重填;全新装机第一次填 key 的流程照常。

## 请回答三件事(不必凑数,没有就说没有)

1. **完全按上面实现了,业主的目标仍会怎样落空?** 给具体场景(什么时候、他做了什么、看到什么、实际发生什么)。
2. **哪个前提如果是假的,整个方案就要重做?** 指出它,并说用什么最小实验能证伪。
3. **有没有更简单的方向?** 它牺牲什么;用什么最小实验在它和更复杂的方向之间分辨。

请给出你推荐的**一个**方向和它的取舍。引用仓库代码时给文件路径与函数名。
