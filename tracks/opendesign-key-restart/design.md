# Design: opendesign-key-restart

- Change: opendesign-key-restart
- Status: settled(2026-09-25 上午,4c 挑战核实后)

## Goal-to-design check

- 当前行为 → 拟改变的行为:业主在设置页存任意一家的 key ⇒ 外壳杀掉网关、起新网关;Windows 上新网关卡死
  (进程在、300s 没进 Python),聊天一直「连接不上」、右下角换模型按钮消失,只能退出重开(proposal 原话)。
  改成:**网关在跑 ⇒ 存 key 不动它**,下一句起网关自己读到新 key(照 ZCode,业主拍板「那就直接改成zcode那样」);
  **网关没在跑(全新装机没 key)⇒ 存 key 时把它起起来**;外壳起的子进程不再共用管家的输入管道。
- 检查深度与触发事实:改变默认自动动作(存 key 不再重启)+ 跨模块契约(key 从「起网关时注入 env」变成「网关用时现读文件」)
  + 钩 nanobot 私有函数 ⇒ 4c 第三行:一次不同家族方案挑战 + 关键未知先实验。三样都做了,见下。
- 关键前提与证据:
  - P0(Windows 卡死的根因)= 新网关继承了管家主线程正同步 readline 的 stdin 管道。
    证据:probe-3 两组(聊天连着 / 没连)都复现「网关.log 新增 0B、240s 没起来」;probe-4 对照组照样卡,
    只让子进程 stdin=DEVNULL 的两组 1.5s / 1.6s 起来(`evidence/20260925-windows-probe-3.txt`、`-probe-4.txt`)。
    与业主真机日志同形(网关.log 00:24:47→00:42:25 零行)。机制细节(Windows 同步管道 I/O 串行化)是推断,对照实验是事实。
  - P1(网关每句重读配置、重解析 `${VAR}`,签名含解析后的 key)= 成立:nanobot 0.2.2 `agent/loop.py:1255`
    `_process_message` 先 `_refresh_provider_snapshot()`;`providers/factory.py` `provider_signature` 含 `get_api_key`;
    子代理 / 压缩(`_apply_provider_snapshot` 同步 `subagents` / `consolidator`)、cron(`cli/commands.py:1017` 现取 `agent.provider`)都跟着换。
    真网关实验(上一会话 scratchpad/livekey,[仓外不承重]):K1→换 K2→新加 DeepSeek K3→切回 K2,不重启,「Failed to refresh」0 次。本单判据 L 组把它钉进仓库。
  - P2(钩 `nanobot.config.loader._env_replace` 能覆盖所有解析路径)= `_resolve_in_place` / `_resolve_env_vars` 按模块全局名查
    `_env_replace` ⇒ 换模块属性即全生效。启动器开跑前断言这个符号在;判据 G 组钉住。
  - P3(配置引用一个读不到 key 的变量 ⇒ 每句重读都抛、被吞、悄悄留旧厂商)= 已知形状(per-vendor-keys 实验 p2)。
    ⇒ 顺序硬规定:**先写 key 文件、再写配置条目**(prepare_gateway 只为有 key 文件的厂商写条目);钩子读文件失败才落回 env。
- 完全实现仍可能失败:① 全新装机没 key ⇒ 没有网关可「不重启」(Grok 抓到,已纳入:没在跑就起)。
  ② 起网关那一下 Windows 仍卡(若 P0 推断错)⇒ 云 Windows 真管家探针用**修好的包**走一遍首次存 key + 聊着存 key(QA 执行)。
  ③ 业主找「换模型」找到设置页列表上(那里只有测试/编辑)—— ZCode 也只在输入框工具栏换(`V4ComposerToolbar.tsx`),
  列表不加切换;修好连接后按钮回来,真机清单里让业主确认。
- 独立意见与核实:Grok 4.7 high(xai,能读仓库)`evidence/20260925-design-challenge-grok.md`,结论「需改」:
  - 「没 key 冷启动后只存不起 ⇒ 仍连不上」—— **成立**(`bin/ds_shell_core.py:1128` startup_plan 无 key 不起网关;今天靠重启请求顺带起)⇒ 纳入。
  - 「设置页列表每行只有测试/编辑,业主没地方点换」—— 核实:ZCode 设置页也不能换,换模型在输入框;业主看到的是连接断了按钮消失 ⇒ **不改列表**,真机确认。
  - 「更稳:只把 key 文件写进 os.environ,不替换私有函数」—— **不采纳**:它也得有一个「每次解析前」的钩点,
    而 `resolve_config_env_vars` 被 `webui/mcp_presets_api.py:21` 在模块顶层 `from … import` 走(包它的模块属性覆盖不全),
    `_env_replace` 是 loader 内按全局名查的唯一出口(`config/loader.py:102/135`);
    另外往 os.environ 写新 key 会进网关所有子进程(MCP / exec)的环境,比现在多一处扩散。私有符号改名的风险由启动器断言 + 判据 G 接住。
  - 「前提在所有路径都成立?」—— 已核(P1)。
- 未解决项:无能改变方向的。Linux 上 `port_free` 被 TIME_WAIT 骗(Linux 整链复现的那条)不在本单:
  Linux 没有外壳产品,且本单后存 key 不再走重启 ⇒ 延期,记在 verify。

## Approach

1. **子进程不共用管家的输入**:`Supervisor._spawn` 一律 `stdin=DEVNULL`(网关、工作台都不读 stdin)。
2. **网关由我们的启动器起**:`bin/ds_gateway.py` 在 nanobot 读配置前换掉 `nanobot.config.loader._env_replace`:
   主槽变量(配置 `providers.custom.apiKey` 引用的那个)→ `.openDesign/key.txt`;`DS_LLM_KEY_<V>` → `keys/<v>.txt`(含自定义供应商);
   **每次解析现读**;读不到才落回进程环境;两边都没有 ⇒ 照 nanobot 原样抛。映射只在 `ds_credential.live_key()` 一处。
   argv 由 `ds_shell_core.gateway_argv()` 给(外壳与判据同一来源)。
3. **存 key 当场对齐配置**:`ds_credential.save(multi=True)` 额外厂商那支、`add_custom_provider(key=…)` 写完 key 文件后调 `prepare_gateway`
   (额外条目仍只由它写;「想换过去」标记当场兑现)。
4. **工作台按网关在不在决定**:`ds_web` 存 key 后 —— 没外壳 ⇒ `manual`;网关端口在听 ⇒ `live`,**不发任何帧**;
   不在听 ⇒ 发原来那个锁帧 ⇒ `requested` / `manual`。
5. **外壳收到那个帧 = 确保网关在跑**:`Supervisor.ensure()` —— 同名腿活着就不碰;没有 / 死了才起。(帧名沿用 `RESTART-BACKEND`,线上兼容;语义与注释改成 ensure。)
6. **界面**:`live` ⇒ 改的是正在用的那家:「已保存,下一句对话起就用新的 key」;存别家:「已保存,马上可用:在聊天框右下角就能换到这家的模型」
   (QA 设计两家同指:存 key 不换当前模型,笼统说「下一句就用它」会被读成下一句改走新那家);
   `requested` 改口成「正在准备聊天服务」(不再是重启;也不沿用业主让删的启动横幅原话,q1)。

## Key trade-offs / risks

- 钩私有符号:nanobot 升级改名 ⇒ 启动器开跑前断言,缺了就让网关带一句人话退出(外壳弹框),不静默退回「只认 env」。
- 配置里 key 仍只以 `${VAR}` 出现(「原文永不进配置」契约不变)。
- 存 key 不再重启 ⇒ 0.98.12 的「重启完改口」那套轮询在额外厂商这支不再触发(条目当场在,`pending`=false)。

## Alternatives considered

- **只修重启(stdin=DEVNULL),存 key 仍重启**:一行修复。没选:业主已拍板照 ZCode;且重启会掐断正在回的那句、断开重连有空窗,
  业主真机冷启动见过近 4 分钟(3 个 MCP)。stdin 修复仍要做(首次存 key 起网关要走它)。
- **key 原文写进配置(ZCode 形状)**:违反「原文永不进配置」(配置会进日志、截图、收据),不选。
- **只写 os.environ(Grok 的方向)**:见上「独立意见」。

## Test strategy (oracle)

- **L(真网关,判据的核心)**:用 `gateway_argv()` 起**真 nanobot**(外壳会给的那份 env),两台本机假厂商记 Authorization:
  L1 主槽换 key → 下一句带新 key;L2 存第二家 key(设置页那条:`switch=False`)→ 菜单切过去 → 带它的 key;
  全程网关 **pid 不变、没重启**,日志无「Failed to refresh」。
- **S(外壳)**:S1 子进程 stdin 是空设备(真起子进程让它自己报);S2 `ensure` 对活着的腿不碰(pid 不变)、对没有的腿起起来。
- **W(工作台)**:W1 网关在听 ⇒ `live` 且锁端口**一个帧都没收到**;W2 不在听 ⇒ 帧送到 ⇒ `requested`;W3 没外壳 ⇒ `manual`。
- **K(key 文件)**:K1 存第二家 ⇒ 配置当场有 `od_<v>` 条目(只含 `${VAR}`)、行 `live`、不 `pending`;K2 `switch=True` ⇒ 当场换过去;
  K3 自定义供应商带 key 同理。旧判据 v1(「额外厂商存 key 配置一个字节不动」)的理由是「此刻网关拿不到这把 key」,本单让网关现读 key 文件,
  该理由失效 ⇒ 改写为 K1,并由 L2 在真网关上问「真的用上了没有」(更强)。
- **G(启动器)**:G1 钩上后 `${DS_LLM_KEY}` 解析成文件里的 key(env 里放另一把);G2 文件没了落回 env;G3 两边都没有照样抛;G4 符号不在 ⇒ 启动器拒绝开跑。

**这个 oracle 能被什么骗过?**

- 全绿但 Windows 上首次存 key 起网关仍卡:Linux 判据问不出 Windows 管道行为 ⇒ **云 Windows 探针用修好的包**真跑(QA 执行,收据进 evidence)。
- 全绿但业主界面上「换模型」按钮不回来 / 提示说假话:只有真界面看得出 ⇒ QA 执行在隔离台面录真界面 + 业主真机清单。
- L 组用的 env 若是判据自己拼的,外壳那一跳坏了照样绿 ⇒ env 与 argv 都从外壳自己的函数取(沿用 per-vendor-live G4 的做法)。
