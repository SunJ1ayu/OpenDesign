# Design: opendesign-per-vendor-keys

- Change: opendesign-per-vendor-keys
- Status: decided(2026-09-21,独立挑战 + 两个实验之后)

## Goal-to-design check

- **当前行为 → 拟改变的行为**:业主原话「会 先做换供应商这个吧」(对「你会在 MiMo 和 DeepSeek 之间来回换吗」)。
  事实:现在只存一把 key(`ds_credential.save` → `key.txt`),换厂商 = 重粘另一家 key、旧的被覆盖、再重启网关。
  拟改:两家 key 同时存着;聊天框模型菜单列出所有「后台已拿到 key」的厂商的模型,点了下一句生效,不重粘、不重启。
  「点一下就换 / 不用等」是**我**在对照页写的描述,业主只确认了「会来回换」。
- **检查深度与触发事实**:改变数据/凭据存储与跨模块契约(ds_credential ↔ 外壳注入 env ↔ nanobot 配置 ↔ 前端),
  选错要迁移业主机器上的配置才能撤回 ⇒ 4c 第三行:不同家族独立方案挑战 + 关键未知先实验。
  主 agent 方向先封存:`evidence/20260921-c0-my-direction-sealed.md`(派发时在仓外,不在腿的快照里)。
- **关键前提与证据**:
  1. nanobot 0.2.2 同一份配置里能挂多条 provider、各用各的 `${VAR}`,预设 `provider` 字段强制路由 ——
     **已证**(`evidence/20260921-p1-*`,loader 层)。
  2. **运行中的网关**只改 `modelPreset`,下一句就换到另一家的地址和 key,不重启 —— **已证**(真网关 + 两台本机假服务器,
     `evidence/20260921-p2-live-gateway-switch.*`:A→B→A 三句各自命中对的服务器、对的 Authorization)。
     这是挑战腿指出我原实验**没证到**的那一层(只问了 loader,没问活进程)。
  3. 配置里引用了网关进程 env 里没有的变量 ⇒ 启动时网关起不来;运行中每句前的重读抛错被吞、**保留旧 provider**
     —— **已证**(p1 + p2 第四句:配置要 deepseek,实际仍打到 A)。这是本单最大的「界面撒谎」源头,设计必须从结构上排除。
  4. 空串变量能通过加载,调用时才 401 —— 已证(p1)。⇒ 设计里**不用空串兜底**(那会把「没 key」伪装成「key 错」)。
  5. 业主 Windows 上重启网关要多久 —— **未知**(Linux ~2.3s 到 ws 就绪;S0 首次冷启动见过近 4 分钟)。
     选定方向下「切换」不重启,只有「第一次填/换某家 key」重启 —— 与今天完全相同,不因这个未知变坏。
- **完全实现仍可能失败(用户目标落空的场景)**,及本设计的对策:
  - F1 菜单列出了后台还没拿到 key 的厂商 → 点了显示换了、实际没换(前提 3)。**对策**:只有外壳在「起网关的那一刻」
    才往配置里写额外厂商的 provider 条目,并在同一处把对应 key 注入网关 env ⇒ 配置里的额外厂商 ⊆ 网关手里的 key,**结构上成立**;
    菜单按配置列,所以菜单里的厂商就是活的。ds_web / 保存 key 的那一下**从不**往配置里加额外厂商条目。
  - F2 刚存了 DeepSeek 的 key、重启还没完成就去点 → 菜单里此刻还没有 DeepSeek(配置里没有条目),不会撒谎;
    卡片上写「已保存,后台重启后就能用」。
  - F3 git-pull / Linux 启动器不认识额外变量 → 起不来。**对策**:没有外壳时(`DS_SHELL_LOCK_PORT` 不在)保存走**今天的单把语义**,
    配置里永远不出现额外条目;这两种形态行为逐字节不变。
  - F4 老用户升级后被要求重填。**对策**:不迁移 —— `providers.custom` + `key.txt` + 原变量**原地不动**,继续表示「最早配的那一家」;
    新加的厂商是**另起**的 `providers.od_<厂商>` + `keys/<厂商>.txt`。老 key 天然还在它原来的厂商名下。
  - F5 厂商认不出(`custom.apiBase` 带尾斜杠 / 手改过)→ 不列、要重粘。**对策**:认厂商时对 apiBase 去尾斜杠;
    仍认不出就按今天的行为处理(不猜)。
  - F6 正在回答的那一句还是旧厂商(切换在下一句生效)—— 与今天同厂商换模型一样,按钮提示「下一句起生效」已存在。**接受**。
  - F7 今天「填 DeepSeek 的 key、保存」的结果是**换到了 DeepSeek**;新版若只存不换,业主会以为没生效。
    **对策**:保存另一家 key 时留一个「想换到这家」的标记(不含 key),外壳在注入了这家 key 的那次起网关时把当前模型切过去并清掉标记。
- **独立意见与核实**:Cursor 腿(模型 Grok 4.6 High,`evidence/20260921-c1-*`,只读快照)。逐条:
  - 「实验 1 只问了 loader,没问活网关」—— **成立**,已补实验 p2 并证实前提 2。
  - 「菜单只能列后台已拿到 key 的厂商,不能按文件在不在列」—— **成立**,是 F1 对策的来源。
  - 「`ModelPresetConfig` 没有 apiBase 字段,端点来自 provider;写 `provider:"custom"` 会把 DeepSeek 模型发到 MiMo 端点」
    —— **成立**(核 `nanobot/config/schema.py:96`;我们现在预设里写的 `apiBase` 是 nanobot 不认的多余字段)。
    ⇒ 额外厂商的预设必须 `provider: od_<厂商>`;同步时由外壳统一改写目录内模型预设的 `provider` 字段。
  - 「空串兜底会把没 key 变成 401」—— **成立**,不采用(我封存的方向里原本写了空串兜底,被这条推翻)。
  - 「MiMo 留在 custom、DeepSeek 另起一条;不动 ds-nanobot.ps1 / 模板」—— **采纳并改写**:不是「MiMo 留 custom」,
    而是「**现在 custom 里是谁就留谁**」(业主机器上 custom 可能已经是 DeepSeek)。
  - 「重启切换那条简单路线」—— 不选,理由见 Alternatives。
- **未解决项**:无能改变方向的未知。Windows 重启耗时仍未知,但只影响「第一次填某家 key」这一步,与今天相同。

## Approach

**一句话**:最早那一家原地不动;新加的厂商另起一条;额外厂商的配置条目只由外壳在起网关时、与注入 key **同一处**写入;
切换只改当前预设。

### 存储(`bin/ds_credential.py`)

- 「主槽」= `providers.custom` + 它引用的变量(`env_var_name`,Windows `DS_LLM_KEY`)+ `<home>/.openDesign/key.txt`。**格式与语义不变。**
  主槽厂商 = 按 `custom.apiBase`(去尾斜杠)在 `PROVIDERS` 里认。
- 「额外槽」= `<home>/.openDesign/keys/<厂商id>.txt`,一行,原子写,与 key.txt 同一套不变量。
  对应配置条目 `providers.od_<厂商id>` = `{"apiKey": "${DS_LLM_KEY_<厂商ID大写>}", "apiBase": <该厂商端点>}`。
- 「想换过去」标记 = `<home>/.openDesign/keys/switch-to`(一行厂商 id,不含 key)。

### 保存 key:`save(home, cfg_path, provider, key, *, multi)`

- `multi=False`(没有外壳):**与今天完全相同**(主槽覆盖、改 apiBase/预设/modelPreset、写 key.txt)。
- `multi=True`(有外壳):
  1. 主槽还没有 key(key.txt 没有、env 也没有)⇒ 同今天(这家进主槽)。
  2. 主槽厂商 == 这家 ⇒ 只换 key.txt,并把 modelPreset 切到这家(当前已是这家的模型就不动)。
  3. 否则 ⇒ 写 `keys/<这家>.txt` + 标记 `switch-to`;**配置一个字节不动**。
  所有分支之后照旧请外壳重启网关。env 遮蔽(主槽变量被业主手工设过)的拒绝规则不变,只管主槽。

### 起网关(外壳 `build_env`,启动与重启同一条路)

新增 `ds_credential.prepare_gateway(home, cfg_path) -> {变量名: key}`(纯逻辑,Linux 可测),外壳 `build_env` 调它:
1. 对每个 `keys/<V>.txt` 非空且 V ≠ 主槽厂商:确保 `providers.od_V` 条目;V 目录里每个模型的预设
   `{"label": m, "provider": "od_V", "model": m}`(已有预设只改写 `provider`,保留其余字段)。
2. 配置里 `od_*` 条目没有对应 key 文件 ⇒ 删条目,并把指向它的预设删掉。
3. 主槽厂商目录里模型的预设 `provider` 统一成 `custom`(修掉「custom 换过厂商后留下的错指预设」)。
4. `switch-to` 标记指向的厂商此刻有 key 且活 ⇒ modelPreset 切到它的默认模型,删标记;否则留着。
5. modelPreset 悬空(指向被删的预设)⇒ 回落到主槽厂商的默认模型。
6. 有改动才原子写配置;返回额外变量 → key 的映射(主槽 key 仍由现有 `read_key` 那条路注入)。
7. 任何一步出错:记日志、**不写配置、不返回额外变量**(退回今天的单厂商),不许 `die()`。

`child_env` 增加 `extra_keys: dict[str,str]`,只进网关那条腿(与主槽 key 同一条不变量)。

### 读状态 / 换模型

- `models_status(cfg_path)`:按配置列出**活的厂商组** —— 主槽厂商(有 key 时)+ 配置里每个 `od_*` 条目;
  每组 `{provider, label, models}`;`current` = 当前预设的模型;`provider` = 当前预设的 `provider` 字段对应的厂商。
  旧字段 `provider/label/current/models` 保留(= 当前厂商那一组),前端旧代码不炸。
- `select_model(cfg_path, model, provider=None)`:只接受活厂商组里的模型;`provider` 缺省按目录反查(模型名两家不重名);
  写 modelPreset(预设缺就按该厂商的槽建)。**不重启。**
- `status(home, cfg_path)`:旧字段不变;新增 `vendors: [{id,label,configured,hint,live,active,pending}]`。

### 界面

- 「AI 模型 key」卡片:每家一行 —— 名字、状态(在用 / 已配置 末四位 / 已保存·后台重启后能用 / 没配置)、
  「填 key / 换 key」展开输入框 + 保存。只有一家也照常。
- 聊天框模型菜单:按厂商分组列活厂商的模型;底部入口改名「管理 key…」。

## Key trade-offs / risks

- **两种存法并存**(主槽在 key.txt、额外槽在 keys/)。代价是读的人要知道两处;换来的是老用户零迁移、老启动器零改动。
- **外壳改配置**:外壳本来就在启动时 `patch_config`(端口);这里加第二处写。写入与注入在同一函数里,是保证 F1 的关键,不能拆开。
- 重启中的极窄窗口:外壳写完配置到旧网关被杀之间,旧网关若恰好收到一句,会因缺变量保留旧厂商作答 —— 它正在被替换,可接受。
- 目录外的预设(业主手写的)一概不碰。
- Linux 开发机本机的真网关不受影响(无外壳 ⇒ 单把语义;配置里不会出现 od_ 条目)。

## Alternatives considered

- **B「只存多把,切换时重启」**(挑战腿推荐的简单族):启动器/配置形状零改动。**没选**:每次换厂商都断开对话等重启,
  Windows 上耗时未知(冷启动见过 4 分钟),而断线时界面文案是「连接不上,gateway 可能没在跑」;
  前提 2 已被真网关证实,不重启的收益拿得到。
- **全部搬进 keys/,custom 改名**(我封存方向里的原案):老用户要迁移、老启动器要改,撤回代价大。被挑战腿「现在是谁就留谁」替代。
- **额外变量注入空串兜底**(我封存方向里的原案):把「没 key」伪装成「key 错(401)」。推翻。
- **由 ds_web 在保存时就写额外条目**:与今天 save 的形状最像,但会立刻产生「配置引用 ⊆ 网关 env」不成立的窗口(前提 3),
  没外壳的形态还会直接起不来。不选。

## Test strategy (oracle)

主 agent 亲写,先红后绿,单独 commit。

**Python(`tests/test_per_vendor_keys.py`,新文件,v 组)**
- v1 有外壳时存第二家:`keys/deepseek.txt` 有且仅一行;`key.txt` 原样;**配置逐字节不变**;标记写了。
- v2 有外壳时 key 只出现在它自己的 key 文件里(整树扫描,沿用 a1 的 sweep 思路);状态/返回值不含原文。
- v3 没外壳时存第二家 ⇒ 与今天完全相同(主槽被覆盖、配置里没有任何 `od_` 条目、没有 keys/ 目录)。
- v4 `prepare_gateway`:返回的额外变量集合 == 配置里 `od_*` 条目引用的变量集合(**逐一对上**);
  且把配置交给 nanobot 自己的 `resolve_config_env_vars`,在「主槽变量 + 返回的额外变量」这份 env 下**加载不抛**。
- v5 没有 key 文件的 `od_*` 条目被删、指向它的预设被删、悬空 modelPreset 回落到主槽默认模型;nanobot 能加载。
- v6 标记:有 key ⇒ 切过去并删标记;没 key ⇒ 不切、标记留着。
- v7 `models_status` 只列活厂商组;没有 `od_` 条目时只有主槽一组;字段向后兼容。
- v8 `select_model` 能跨厂商切(写对 modelPreset,预设 `provider` 指向对的槽);不活的厂商 / 目录外模型 ⇒ 拒绝且配置不动。
- v9 主槽里原本是 DeepSeek(业主以前存过)再加 MiMo:MiMo 进额外槽;原有 `mimo-*` 预设(provider=custom,错指 DeepSeek 端点)
  被改写成 `od_mimo`;用 nanobot 自己的 `load_provider_snapshot` 验证选 `mimo-v2.5` 时拿到的是 MiMo 端点和 MiMo 的变量。
- v10 `prepare_gateway` 遇到坏配置 / 读不了的 key 文件:不抛、不写配置、返回空。
- v11 状态里的 `vendors`:在用 / 已配置 / 待重启 / 没配置 四种都对;不含原文。
- v12 老数据零迁移:只有 key.txt 的老家 ⇒ status 报主槽厂商已配置,prepare_gateway 不写任何东西。

**活网关判据(`tests/test_per_vendor_live.py`,断网跑)**:把实验 p2 固化成判据 —— 用 `prepare_gateway` 产出的配置与 env
起真 nanobot 网关 + 两台本机假服务器,`select_model` 切过去、下一句命中另一台、Authorization 是另一把;切回来同理。
**这是整单唯一直接问「真的换了没有」的判据。**

**外壳接线(`tests/test_ds_shell_wiring.py` 增补)**:`build_env` 调 `prepare_gateway`,额外变量只进网关腿(`service_envs`)。

**前端**:`tests/test_model_picker.mjs` 增补分组菜单纯逻辑;`tests/e2e/model_picker.e2e.mjs`/`llm_key.e2e.mjs` 增补两家场景
(卡片两行、存第二家不动第一家、菜单分组、跨厂商点选后配置文件真的变了)。

**这个 oracle 能被什么骗过?**
- 全部判据绿,而业主机器上**外壳没调 prepare_gateway**(ds_shell.py 在 Linux 跑不起来)⇒ 额外厂商永远不出现。
  接线判据只能读源码;真正接得住的是**云 Windows 机器装包跑一次**或业主真机:存两家、菜单出现两组、切过去问一句「你是谁」。
- 判据绿而**真实 DeepSeek/MiMo 的回答**不对(端点/模型名过期)—— 判据全用本机假服务器,答不了;只有真机一问。
- 菜单分组画出来了、点了也写了配置,但**聊天那一句仍是旧厂商**:活网关判据接得住逻辑层;
  前端到后端这一跳由 e2e 接(断言配置文件真的变了);「下一句真是那家」最终靠真机。
