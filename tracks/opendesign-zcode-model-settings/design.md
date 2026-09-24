# Design: opendesign-zcode-model-settings

- Status: decided(4c 挑战后补定 D1~D4)

## Goal-to-design check

- 当前行为 → 拟改变的行为(事实见 proposal):
  - 设置 = 侧栏小弹层;「AI 模型 key」= 下拉选五家之一 + 填 key + 保存(`web/src/LlmKeyCard.tsx`)。
  - 模型 = 写死目录 `bin/ds_credential.py PROVIDERS[v]["models"]`(MiMo 从出货模板读);聊天框模型菜单 = 平铺、按厂商小标题、末行「换厂商 / 换 key…」(`web/src/chat/modelPicker.ts`)。
  - 拟改:设置整页(常规 / 模型设置);模型设置照 ZCode(左厂商列表 + 状态点;右详情:名称 + 启用开关、Base URL、API Key + 获取、模型列表 行内 测试/编辑/删除 + 添加模型);
    自定义供应商;聊天框两级弹框(厂商 → 模型,✓,底行「管理模型」)。
- 检查深度与触发事实:新增用户必经步骤 + 改跨模块契约(界面 ↔ ds-web ↔ ds_credential ↔ nanobot 配置)+ 钱 ⇒ 4c 第三行,做一次不同家族独立挑战(能读仓库的腿)。
- 关键前提(可证伪):
  - P1 nanobot 接受任意名字的额外厂商条目(`providers` 的 extra fields,`schema.py:191-252`),但只走 OpenAI 兼容 chat completions(`api_type` 仅 providers.openai 可设,`:256-265`)⇒ 自定义供应商只给这一种格式。
  - P2 kimi-glm 单的路由规矩(`_route_presets`:每份认得出主人的预设只发到主人那家;目录模型只以正式名挂自家槽;主人没 key/没格 ⇒ 删)只要「目录」是
    **内置 + 用户登记**,就对用户加的模型、自定义供应商同样成立 —— 不需要改规矩本身。
  - P3 用户登记放在 `<home>/.openDesign/models.json`(我们自己的文件,nanobot 不读);`<home>` 由配置路径 `<home>/.nanobot/config.json` 推出
    (与 key.txt / keys/ 同根)。登记是「用户意图」的唯一来源,nanobot 配置仍由现有写口派生。
  - P4(最危险)把 `PROVIDERS` 常量换成「每次调用按 home 现算的目录」会碰 31 处用法;漏一处 ⇒ 那一处仍按老目录判主人,用户加的模型会被当成「手写预设」删掉或留在错格。
  - P5 存 key 不换当前模型(照 ZCode;也顺带收掉 #60)。新存的 key 网关要重启才拿得到(`prepare_gateway` 起网关时注入);
    「测试」按钮由 ds-web 直接用 key 文件去请求厂商,不经网关,存完就能测。
- 完全实现仍可能失败:
  - 业主在小米那页加了 `mimo-v2.6-pro`,测试通过,聊天框却选不到 / 选了发到别家(路由没认它)。
  - 自定义供应商的 Base URL 恰好等于某家内置端点 ⇒ 两个「主人」认同一个端点(`_vendor_by_base`),账单串家。
  - 设置整页替换弹层后,「重启以更新」「检查更新」入口找不到了(cloud E4 按侧栏「设置」行上的按钮点)。
  - 没外壳(git-pull/Linux)装法只有一个 key 变量,新页面让人以为能配多家。
- 独立意见与核实(原文 evidence/20260924-design-challenge-grok.md,Grok 4.7 High / xai,没读本文件):
  - G1 手写预设不进目录 ⇒ 菜单看不见、`select_model` 拒、换主槽端点时被清扫删(`_preset_owner` 只认目录内模型;test_d3/d4/d8b)。**属实** ⇒ 正是 P2/P3:用户模型必须进目录。
  - G2 不在 PROVIDERS 的 `od_*` 每次起网关被删(`_synced_config`;test_d12)⇒ 自定义供应商活不过重启。**属实** ⇒ P4:所有清扫入口(含 ds_merge_config、set_model)都要用同一张目录。
  - G3 `api_type` 只有 providers.openai 可偏离 auto,写到别处 nanobot 拒载(`schema.py:256-265`)。**属实** ⇒ P1:不写 api_type,自定义供应商只给 OpenAI 兼容格式。
  - G4 老启动器只注入主槽变量;把主槽那家「禁用」或把唯一 key 挪出主槽 ⇒ 网关没 key。**属实,新发现** ⇒ D3。
  - G5 方向「只把 v2.6 加进模板、整页不做」:**不采纳** —— 业主已明示「不用分两步， 直接照zcode重做模型设置」,这是范围决定;G1~G4 的技术事实全部吸收进 D1~D4。
- 定下的规矩:
  - **D1** 目录 = 内置五家 ⊕ `<home>/.openDesign/models.json` 登记;由入口函数现算、显式传给所有路由/清扫助手;覆盖 save / select_model / prepare_gateway(_synced_config)/
    models_status / status / ds_merge_config / set_model.py。判据问「用户加的模型、自定义供应商走完 存 key → 起网关 → 选中 → 再起网关 → 合并更新」后 nanobot 真加载的端点与 key。
  - **D2** 自定义供应商只进额外槽(`od_c_<slug>`),永不进主槽;不写 api_type;Base URL 撞内置或别的自定义 ⇒ 拒收;没外壳的装法不开放添加。
  - **D3** 「禁用」= 只在换模型菜单里隐藏、不许选;路由与 key 不动;**正在用的那家不许禁用**(先换模型)。
  - **D4** 存 key 不写「想换过去」、不改当前模型;有外壳 ⇒ 存完经锁通道请外壳重启网关(`ds_shell.restart_gateway`),没外壳保持今天的单 key 行为。
- 未解决项:无能改变方向的;「测试」按钮直连厂商的请求形状(chat completions 最小一句)实现时用 MiMo 真 key 探一次。

## Approach(挑战前的方向)

后台:
- `catalog(home)` = 内置五家(现有 PROVIDERS,MiMo 目录补 v2.6-pro / v2.6-flash)⊕ `models.json` 登记
  (`extraModels[vendor]`、`customProviders[{id,label,apiBase,models}]`、`disabled[]`、`contextWindow[vendor/model]`)。
  入口函数(save / select_model / prepare_gateway / models_status / status / 合并)各算一次,显式传给路由助手;不改全局。
- ~~禁用的厂商在路由里等同「没 key」(预设删、当前回落)~~ **已被 D3 取代**(QA-设计 Grok 指出矛盾):禁用只在菜单里藏、不动路由;正在用的不许禁用。
- 自定义供应商 id = `c_<slug>`,槽 `od_c_<slug>`,key 在 `keys/c_<slug>.txt`,只进额外槽(不进主槽);Base URL 撞内置端点 ⇒ 拒收。
- 新接口:`GET /api/llm/providers`(列表 + 状态 + 模型)、存 key / 启用 / 加删改模型 / 增删自定义供应商、`POST /api/llm/test`(直连厂商测一句)。
  老接口 `/api/llm/credential`、`/api/llm/models`、`/api/llm/model` 保留(兼容与测试)。
- 存 key:不写「想换过去」标记、不改当前模型;若网关需要这把 key ⇒ 提示/触发重启网关(实现时核 ds_shell 能力)。

界面:
- 设置整页(`#/settings/...`),左栏目:常规(原弹层各项原样搬)/ 模型设置;「返回工作区」。侧栏「设置」行打开设置页;「重启以更新」按钮位置不动。
- 模型设置照 ZCode 结构(见 proposal);聊天框两级弹框照 `ModelConfigSelect.tsx`。视觉用现有主题变量。

## Key trade-offs / risks

- 不推倒 kimi-glm 的槽位模型(主槽 custom + 额外 od_*):那套规矩磨了 13 轮;换成「每家都进额外槽」理论更干净,但要迁移所有老安装、改没外壳启动器 —— 本单不做。
- P4 的漏改风险用判据兜:用户加的模型 / 自定义供应商走完 save → 起网关 → 选中 → nanobot 真加载,问真发出去的端点与 key。

## Alternatives considered

- 把用户模型直接写进 nanobot 配置当预设(不另立登记):现有清扫会把「目录外的手写预设」删掉(`_route_presets`),等于和规矩打架。
- 全局可变 PROVIDERS(入口处重载):测试与多 home 会互相污染。

## Test strategy (oracle)

先写判据(红):小米加 v2.6-pro → 起网关 → 选中 ⇒ nanobot 加载发往小米端点 + 小米 key;自定义供应商同理;禁用 ⇒ 当前回落、预设删;
自定义 Base URL 撞内置 ⇒ 拒;存 key 不改当前模型;老配置(0.98.11 五家 + 额外格 + 当前)升级后新接口列出原样;界面结构判据(设置整页栏目、两级弹框、管理模型)。
e2e 截图亲看对照 ZCode 截图。
