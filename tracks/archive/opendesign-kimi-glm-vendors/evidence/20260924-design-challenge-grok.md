我先读评审 diff 和仓库里真正改配置、选模型的代码，核对“扣错家的钱”还剩哪些路径。
diff 是空的，我改去读配置写入、模型路由和安装脚本，核对主槽 `custom` 到底被谁改。
业主要的是「账单跟选中的那一家走」。现在扣错钱,是因为 `provider: custom` 是一根会换主人的指针,而裸名 `glm-5.3` 没有主人。安装脚本少问两句,治不住已经写在盘上的这种形状。

Direction: 主槽一旦能认出是目录里的哪一家,就把「指向 custom、模型名在目录里、预设名却不是这家的 `preset_name`」的预设删掉,当前模型悬空就回落到这家自己的默认预设。两家都有的名字(两家 GLM 的 `glm-5.3`)只许删,不许改指到另一格。这条规矩写进已经存在的 `_route_presets`(`bin/ds_credential.py` 里 `save`、`prepare_gateway`、以及 `bin/ds_merge_config.py` 合并结束都会调它)。老启动器 `bin/ds-nanobot.ps1` 今天只把 `key.txt` 灌进 `DS_LLM_KEY` 就 exec,从不调用它,所以要在 exec 前用同一次调用补上,失败则跳过、照旧启动。`install.ps1` 不再问端点/模型,只是别再造出新的裸名。

Core bet: key 继续走主槽的 `key.txt` / `${DS_LLM_KEY}`(老启动器只认这个,见 `ds-nanobot.ps1` 第 26–31 行和 `ds_credential.py` 模块头)。要拆开的是「预设属于谁」,不是「key 放哪」。裸名在端点已经错了的时候不会再变一次,等「端点变更那一刻」才扫,存量永远留着。按「主人另有槽」把裸名改指走,对同名模型就是把套餐的账改记到按量。

How it works: `_preset_owner` 只认「模型在那家目录里,且名字正好是 `preset_name(那家, 模型)`」。`glm-5.3` 两家都有,所以合格名字是 `glm-5.3@glm_plan` / `glm-5.3@glm`,裸名主人是 `None`,`_route_presets` 直接 `continue`。因此下面这份配置,主槽已经是 Kimi、之后没人再改 `apiBase`,提案的清扫不会发生,下一句仍走 Moonshot、带 `key.txt` 里的 Kimi key:

```json
{
  "providers": {
    "custom": {"apiKey": "${DS_LLM_KEY}", "apiBase": "https://api.moonshot.cn/v1"}
  },
  "model_presets": {
    "glm-5.3": {"provider": "custom", "model": "glm-5.3"}
  },
  "agents": {"defaults": {"modelPreset": "glm-5.3"}}
}
```

改完后的规则只在 `_current_provider` 认得出时动手:这种裸名删掉,`_fallback_if_dangling` 把 `modelPreset` 落到 `kimi-k3`(主槽默认,并带上 Kimi 的 `temperature: 1.0`)。账单跟主槽那把 key 走。另一份更危险的形状是主槽已是 GLM 套餐、旁边又有 `od_glm`:

```json
{
  "providers": {
    "custom": {"apiKey": "${DS_LLM_KEY}", "apiBase": "https://open.bigmodel.cn/api/coding/paas/v4"},
    "od_glm": {"apiKey": "${DS_LLM_KEY_GLM}", "apiBase": "https://open.bigmodel.cn/api/paas/v4"}
  },
  "model_presets": {
    "glm-5.3": {"provider": "custom", "model": "glm-5.3"}
  },
  "agents": {"defaults": {"modelPreset": "glm-5.3"}}
}
```

「主人另有槽就改指」会把这条裸名指到 `od_glm`,下一句用按量 key 打按量端点,模型名又合法,钱记到另一家。正确动作是删掉裸名,回落到已经指向 `custom` 的 `glm-5.3@glm_plan`。模型名不在任何一家目录里的手写预设(例如 `我的@kimi` / `my-own-model`)继续不碰;主槽端点认不出(自配代理)时,指向 `custom` 的预设也不碰。

方案落地后仍会「连不上」的形状,清扫碰不到:

- Linux `bin/ds-nanobot` 从 `auth.json` 导出 `MIMO_TP_KEY` 给子进程,不读 `key.txt`。界面 `save` 把 `custom.apiBase` 改成 Kimi 并写下 `key.txt` 之后,网关仍拿 MiMo 的 key 去打 Kimi。这是 `ds_credential.py` 模块头写明不修的边界。
- 环境里已经有 `DS_LLM_KEY`,而 `key.txt` 是另一家的。`save` 会拒绝(约第 600 行),`ds-nanobot.ps1` 又是环境变量优先。端点跟着配置走、key 跟着环境走,请求 401。
- 只有主槽、没有第二家 key 的 Kimi 预设若缺 `temperature: 1.0`,早退路径只跑 `_route_presets`、不跑 `_apply_params`。Kimi 拒收小于 1 的 temperature,句句失败。回落预设必须走 `_custom_preset`,才会把参数补上。

Best at: 已经装好、主槽端点认得出、盘上留着裸名或「名模不一致」预设的机器。不用等业主再换一次厂商。正式外壳走 `prepare_gateway`,老 PowerShell 启动器补上同一次调用后,两条启动链用同一条规矩。

Sacrifices: 业主若故意把目录里的模型名(尤其 `glm-5.3`)挂在自配代理上,且主槽端点又能被认成某一家,这份预设会被删掉,聊天改走主槽默认模型。自配端点只要 `_vendor_by_base` 认不出,就仍然保留。没有外壳时界面保存仍是整槽覆盖(`ds_web.py` 里 `multi=_has_shell()`),第二家 key 不会并存;这跟启动器只注入一个变量是同一件事,这次不动。

Blind spots in the brief: 「主槽不能迁进 `od_*`」只约束 key 注入,不约束预设的 `provider` 字段;拿它当理由留下可移动的 `custom` 指针,存量裸名还在。`custom.apiBase` 的写入口不止界面: `save` 第 606 行,以及 `ds_merge_config.py` 的 `--api-base`(第 112 行)。出货安装 `ds_provision.merge_template` 本来就不传这个参数;手填端点只活在 `install.ps1` 第 127–134 行。删掉参数会断掉测试里那种自配代理(`https://my-own-proxy.example/v1`),那些机器要继续靠「端点认不出就不碰」。`check-package.sh` 的 `NEED` 清单确实没有 `ds_credential.py` / `ds_model.py`(约第 149–154 行),但 `build-package.sh` 是 `cp bin/*.py`,包里一般仍在;清单漏了不等于运行时一定缺文件。本仓库没有 nanobot 自己的 `/model` 实现;若会话中途它照着当前预设抄出一个新的裸名,要等下次启动前的那次 `_route_presets` 才删得掉。

Smallest first step: 加两份只读夹具,主槽 `apiBase` 先写好、调用期间不许改。第一份是上面的 Kimi + 裸名 `glm-5.3`,再加一个带 key 的 `od_glm`。走 `prepare_gateway`(以及直接调 `_route_presets`)之后,用现有测试里那种 nanobot 快照断言:这条预设不再打到 `api.moonshot.cn`,也没有被改指到 `open.bigmodel.cn/api/paas/v4`;`modelPreset` 落到 `kimi-k3`。第二份是主槽 GLM 套餐 + 裸名 `glm-5.3` + 已有 `od_glm`,断言没有改指到 `od_glm`,而是落到 `glm-5.3@glm_plan` 且端点仍是 coding plan。这两条有一条不成立,「等端点变了再扫 / 主人有槽就改指」就仍然会扣到另一家。
