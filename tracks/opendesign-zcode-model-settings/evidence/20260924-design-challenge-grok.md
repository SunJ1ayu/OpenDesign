# 4c 方案挑战原文:Grok 4.7 High(经 Cursor,family=xai)

- 派发 09-24 15:50,`panel-explore --members subcursor@grok-4.7-high`,题面 = 同目录 20260924-design-challenge-brief.md

```
我先核对仓库里模型目录、预设路由和设置页的真实实现，再判断「照 ZCode 重做」会在哪一步让业主目标落空。
Direction: 只把 `mimo-v2.6-pro` 和 `mimo-v2.6-flash` 写进 `config/nanobot.config.windows.jsonc` 的 `model_presets`（`provider: custom`），让现有菜单和 `select_model` 放出它们。ZCode 整页、手填模型、改 Base URL、启用/禁用、自定义供应商先不要做。

Core bet: 填完 key 仍选不了 v2.6，是因为 MiMo 目录只有模板里那两行。`_template_models()` 从 `config/nanobot.config.windows.jsonc` 里 `provider == "custom"` 的预设取模型名，模板里只有 `mimo-v2.5` 和 `mimo-v2.5-pro`。`models_status` 只按 `PROVIDERS` 列菜单，`select_model` 在模型不在该家 `models` 里时直接拒绝。ZCode 那种「每家一张可增删的模型表」在这份配置里没有落点：用户新写的预设会被 `_preset_owner` 当成手写（模型必须已在 `PROVIDERS[v]["models"]` 里，且名字等于 `preset_name`），随后被清扫删掉，或留在不带厂商身份的 `custom` 上。

How it works: 模板多两条 MiMo 预设后，`_template_models()` 会把它们带进 `PROVIDERS["mimo"]["models"]`。有小米 key 的机器上，聊天菜单按这家目录列出；点选时 `select_model` 按现有规则补预设，名字就是模型 id（v2.6 不与别家重名，不会变成 `模型@厂商`）。槽位仍是主槽 `providers.custom` 加 `providers.od_<五家之一>`，key 仍是 `key.txt` / `keys/<厂商>.txt`。`save`、`prepare_gateway`、`ds_merge_config` 继续走 `_route_presets`：目录里的模型只挂在主人那一格。已装机器再合并时，`ds_merge_config` 只并入预设清单，已有的 `modelPreset` 还在就不会被模板默认盖掉。

Best at: 业主填完小米 key 后，右下角能选 v2.6-pro / v2.6-flash，请求仍发到小米套餐端点 `https://token-plan-cn.xiaomimimo.com/v1`，用的是这把 key。只装了一家、走老启动器（只认 `providers.custom` 和它引用的那一个变量）的机器，配置形状不变，只是菜单多两项。同名模型各家一份、套餐和按量分开记账的规矩不用再开一扇门。

Sacrifices: 没有 ZCode 的左栏厂商卡、悬停二级菜单和「管理模型」。下一款新模型 id 还是要改模板再发一版。Base URL、API 格式、上下文窗口、启用/禁用、自定义供应商都维持现状。

Blind spots in the brief: 完全照那张页面做，三件事业主目标仍会落空。

用上新模型。ZCode 不拉厂商 `/models`，内置只带少量模型，新 id 靠手填。本仓库就算把 v2.6 补进内置清单，页面上的「添加模型」写出来的行，菜单和 `select_model` 仍然看不见：列表来自目录，不来自盘上的 `model_presets`。手填的 id 只有再写进 `PROVIDERS` 才进菜单。填 key 本身（`save`）不扩大清单。所以「填完 key 为什么不能选小米最新的」在下一款型号上会原样再出现。

账单跟选中那家走。主槽预设的 `provider` 只写 `"custom"`，厂商是靠 `apiBase` 反查的。用户在某一家卡片下加的模型，若落成 `custom`，扣的是当前主槽那家，不是卡片上那一行。模型 id 若撞上目录里别家的名字（例如在小米主槽上加 `glm-5.3`），`_route_presets` 发现这一格的厂商没有这个模型，就把预设删掉，当前选择回落到这一格的默认模型（`test_d7` / `test_d8` 钉的就是这件事：裸名 `glm-5.3` 挂在 Kimi 主槽上会被删，不许改指到 `od_glm`，以免套餐的账记到按量）。用户改的 Base URL 也会被盖回去：`save` 和 `_synced_config` 都把 `apiBase` 写成 `PROVIDERS` 里的值。

已装好的机器照常。外壳每次起网关都跑 `prepare_gateway` → `_synced_config`。凡是 `od_` 开头、后缀不在 `PROVIDERS` 里或没有对应 `keys/<厂商>.txt` 的条目会被删掉；指着消失槽位的预设，包括手写的，一并删掉（`test_d12`）。自定义供应商因此活不过一次重启。`api_type` 只有 `providers.openai` 能偏离 `"auto"`（`nanobot/config/schema.py` 的 `_validate_api_type_scope`），在 `custom` 或额外厂商上写入 ZCode 的「API 格式」会让 nanobot 拒绝加载，机器起不来。老启动器只注入主槽那一个变量；把唯一一把 key 移出 `providers.custom`，或把主槽标成禁用，这些机器的网关就没有 key。

哪个前提为假就要重做：已经为真，所以整页方案要重做。前提是「用户新加的模型可以当作手写预设留在他选的那一家上」。代码里不是这样。`_preset_owner` 认不出目录外的模型。目录外、挂在 `custom`、且这次 `save` 换了主槽端点：删（`_route_presets` 里 `endpoint_changed` 分支；`test_d3`）。同一家只换 key、端点没变：留着（`test_d4`、`test_d8b` 的 `my-own-model`），但 `provider` 仍是 `custom`，账单跟着主槽走。id 已经在全局目录里、这一格的厂商却没有它：立刻删，不改挂到另一家。不在五家之内的 `od_*`：下次起网关删槽再删预设。若为了让手填模型活下来而放宽「换端点时删掉 custom 上的手写预设」，就会回到上一单磨了 13 轮才收住的缝：主槽换人后，旧预设跟着新端点扣钱。

Smallest first step: 用现有测试夹具做两下盘上推演，不必做页面，也不必打真 key。第一份：主槽已是 MiMo，另写一条 `model_presets["mimo-v2.6-pro"] = {provider: custom, model: mimo-v2.6-pro}`，不改 `PROVIDERS`。看 `models_status` 的 `groups` 里没有它，`select_model(..., "mimo-v2.6-pro", provider="mimo")` 拒绝。再 `save(..., provider="deepseek")` 让主槽换端点，看这条手写预设被删掉。第二份：同一主槽上写 `{provider: custom, model: glm-5.3}`，跑一次 `prepare_gateway`，看预设被删、当前模型回落到 `mimo-v2.5`，快照的 `api_base` / `api_key` 仍是小米。两下都成立，就说明 v2.6 只能进模板目录；手填行和自定义供应商会被这套清扫拆掉。
```
