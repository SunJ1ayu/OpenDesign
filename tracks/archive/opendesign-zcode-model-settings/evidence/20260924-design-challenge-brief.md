# 方案挑战(4c):OpenDesign 照 ZCode 重做模型设置

仓库:当前目录(design-studio,本地桌面 AI 助手:Electron 外壳 + Python 后台 ds-web + nanobot 网关)。
**不要读** `tracks/opendesign-zcode-model-settings/design.md`、`/root/aiwork/tasks/` 与任何 `*my-review*`(那是主裁的方案与自审)。
可读:`bin/ds_credential.py`、`bin/ds_web.py`、`bin/ds_merge_config.py`、`bin/ds_shell.py`、`web/src/LlmKeyCard.tsx`、`web/src/chat/modelPicker.ts`、
`web/src/chat/ChatPage.tsx`、`web/src/workspace/Sidebar.tsx`、`tests/test_vendor_one_door.py`、`tests/test_kimi_glm_vendors.py`、
`tracks/archive/opendesign-kimi-glm-vendors/`(上一单:13 轮评审才磨稳「账单跟选中那家走」)、nanobot 源码(`/root/.venvs/design-studio/lib/python3.12/site-packages/nanobot/config/schema.py`)。

## 业主原话(09-24)
- 「问题还是很多啊，比如我填完api key为什么不能选择模型比如小米最新的v2，6呢」
- 「zcode是怎么做的 你能不能好好看一下啊」「包括他们的前端设置页面排版」
- 「不用分两步， 直接照zcode重做模型设置」
- 「严格按照zcode做，包括我们第一个开始聊天的页面，右下角点换模型之后弹出来的框的样式」

## 现状(事实)
- 模型目录写死在 `bin/ds_credential.py` 的 `PROVIDERS`(五家:MiMo / DeepSeek / Kimi 按量 / GLM 套餐 / GLM 按量),MiMo 只有 v2.5、v2.5-pro;
  小米服务端 `/v1/models` 09-24 实查已有 mimo-v2.6-pro、mimo-v2.6-flash。
- 配置槽位:主槽 `providers.custom`(key 变量 DS_LLM_KEY,老启动器只认它)+ 额外槽 `providers.od_<厂商>`(key 在 `keys/<厂商>.txt`,由外壳起网关时注入);
  预设 `model_presets` 由 `_route_presets` 等规矩保证「每份预设只发到它主人那家」。
- 设置 = 侧栏小弹层;「AI 模型 key」卡 = 下拉选一家 + 填 key。聊天框模型菜单平铺按厂商分组。

## ZCode 3.14.3 的做法(源码 + 教程截图核过)
- 设置整页:左栏目(常规 / 模型设置 / …),模型设置里一张大卡片:左 224px 厂商列表(内置组 / 自定义供应商组 + 添加供应商,每行图标 + 名称 + 状态点),
  右详情:名称 + 已启用/禁用、Base URL、API 格式、API Key(获取 API Key)、模型列表(每行模型 ID + 上下文长度 + 测试 / 编辑 / 删除)+「添加模型」弹窗(模型 ID、上下文窗口)。
- 内置厂商只带少量内置模型;新模型靠用户「添加模型」手填 ID。不从厂商 /models 自动拉取。
- 聊天框换模型:下拉里每家一行(当前那家 ✓),悬停向右弹出这家模型(当前 ✓),底部固定「管理模型」跳设置页。

## 拟改变的行为
- 设置从弹层改整页(常规 = 原弹层各项;模型设置照上面);内置五家 + 可加自定义供应商(只支持 OpenAI 兼容格式,nanobot 额外厂商只支持这一种);
  每家模型列表可加 / 删(内置不可删)/ 测(直接用 key 请求厂商一次)/ 改上下文窗口;厂商可启用 / 禁用;
- 存 key 不改当前模型;聊天框两级弹框 + 管理模型;内置清单补小米 v2.6-pro / v2.6-flash。

## 请回答(不必凑问题)
1. 完全照这样实现,业主的目标(用上新模型、账单跟选中那家走、已装好的机器照常)仍会怎样落空?
2. 哪个前提若为假就要重做?请到代码里核实最可疑的那个(例如:用户新加的模型会不会被现有清扫规矩当成「手写预设」删掉或留在错格)。
3. 有没有更简单的方向?用什么最小实验能分辨?
