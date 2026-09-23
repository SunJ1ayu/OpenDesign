# Design: opendesign-kimi-glm-vendors

- Status: approved(业主 09-23 定范围)

## Goal-to-design check
- 当前 → 拟:key 卡片下拉只有 MiMo/DeepSeek ⇒ 多 Kimi / GLM 套餐 / GLM 按量;每家有「获取 API Key」链接。
- 检查深度:**直接验证**。沿用 per-vendor-keys 已验证的契约(额外槽 `keys/<id>.txt` + `providers.od_<id>` 只由 prepare_gateway 写),
  只往 PROVIDERS 表加行 + 加一个只读的链接字段;不改存储/注入/切换代码路径。
- 关键前提(可证伪)与证据:
  1. 端点存在且是 OpenAI 兼容:09-23 无 key 探测 `GET <base>/models` —— `api.moonshot.cn/v1` 401 incorrect_api_key、
     `open.bigmodel.cn/api/paas/v4` 401、`open.bigmodel.cn/api/coding/paas/v4` 401(都是「缺/错 key」不是 404)。
     ZCode 目录把 `open.bigmodel.cn/api/paas/v4` 标 `openai-chat-completions`;GLM 官方文档给 Coding Plan OpenAI 兼容地址 `…/api/coding/paas/v4`。
     Kimi 在 ZCode 走 anthropic 端点,OpenAI 兼容 `/v1` 是 Moonshot 官方长期形态(探测 401 佐证存在)。
  2. 模型名:ZCode 目录 builtinModelIds —— Kimi `kimi-k3 / kimi-k2.7-code / kimi-k2.6`;GLM 套餐 `GLM-5.3 / GLM-5.3-Flash`;
     GLM 按量另有 `GLM-5V-Turbo / GLM-5.1` 等。GLM 官方文档示例用小写 `glm-5.2` ⇒ 我们用小写。**未用真 key 验证 = 已知未知**,
     业主没有 key;错了的表现是那家聊天报「模型不存在」,修法是改表一行,不影响其他厂商。
  3. 两家 GLM 有同名模型:前端打勾已按「厂商+模型」判(pv3);后端预设按模型名存,select_model 对已存在预设按厂商所在槽纠正 provider
     ⇒ 切来切去应路由正确。**这条由判据 k4 用 nanobot 自己的加载器验**,不靠读代码。
- **实现中自审推翻了前提 3 的一半**(判据 k4 只验了「选完就对」,没验「重启之后还对」):
  prepare_gateway 每次起网关都把目录里每个模型的预设重指到「最后处理的那家」⇒ 两家 GLM 都有 key 时,
  业主选的套餐 glm-5.3 重启一次就改走按量(或反之),**扣另一份钱**。修法:起网关时,预设现在指着的那家若仍有 key
  且目录里也有这个模型,就不替业主改(k4b);唯一例外是「存了新一家的 key、想换过去」的标记,兑现时把该预设指到新那家(k4c)。
- **自审发现的第二条**:Kimi K2.5+ 拒收 temperature<1.0。nanobot 只在它内置的 moonshot 规格里覆盖(registry.py model_overrides),
  我们走 custom/od_kimi 通道吃不到,预设默认 0.1 ⇒ 每句被拒。修法:厂商表加 `presetParams`,Kimi 的每个预设写 temperature=1.0;
  判据 k7/k7b 问 nanobot `_build_kwargs` 真发出去的参数。kimi-k3 不在 nanobot 的覆盖名单里,按同一家规则一并给 1.0(未经真 key 验证)。
- 完全实现仍可能失败:模型名/大小写不对(见 2);GLM 套餐 key 被服务端限定只给编程工具(官方未写死,ZCode 自己就是编程工具)。
- 未解决项:无能改方向的;真 key 验证留业主。

## Approach

> **第 3 轮评审后改了方向(同名模型的存法)**:原来同名模型共用一份以模型名为键的预设,靠「起网关时别替业主改归属 /
> 想换过去时改指 / 不带厂商时优先当前 / 丢 key 时回落」四层补丁守住不串家,连打五次补丁仍被评审找到缝。
> 现在改成 **同名模型按厂商各存一份预设**(`preset_name`:`glm-5.3@glm_plan` / `glm-5.3@glm`;不重名的仍用模型名,老配置零变化),
> 再加一条不变量:带 `@厂商` 的预设只许指向名字里那一家(主槽 ⇒ custom、有 key 的额外槽 ⇒ od_<厂商>、否则删)。
> keeps_owner、removed 两层补丁随之删除。未发版 ⇒ 没有要迁移的旧配置。
>
> **第 4 轮两家 BLOCK 后找到的真根因(业主拍板「从第一性原理修」)**:共享的不是模型名,而是主槽 `custom` ——
> 它的厂商会变,指向它的预设却不带厂商。改名只拆开了同名这一种症状。现在只留一条不变量 `_route_presets`:
> **每份认得出主人的预设(名字带 `@厂商`,或模型只在一家目录里)只许发到主人那家**:主人是主槽 ⇒ custom;
> 主人有额外槽 ⇒ od_<主人>;主人没 key ⇒ 删。在槽的厂商会变的每一处都跑:save 写主槽时、起网关时(含只有一把 key 的老家快路径,
> 本来就对齐的配置字节不变 v12/v12b)。认不出主人的(业主手写、自配端点)一律不碰。顺带收掉已发版本就有的 #16
> (换过 DeepSeek 的老家里 mimo-* 发到 DeepSeek),`set_model.py` 也改用带厂商的名字(#17)。
- `bin/ds_credential.py` PROVIDERS 加三行 + 每行 `keyUrl`;`/api/llm/credential` 的 providers 带出 `keyUrl`。
- `web/src/llmKey.ts` asProvider 读可选 keyUrl(只收 https);`LlmKeyCard.tsx` 在 API key 输入框下显示「获取 {label} 的 API Key ›」外链(新窗口/外部浏览器)。
- 链接:MiMo `https://platform.xiaomimimo.com/token-plan`(我们接的是套餐端点,不能照 ZCode 链平台首页);DeepSeek `https://platform.deepseek.com/api_keys`;
  Kimi `https://platform.kimi.com/console/api-keys`;GLM 套餐 `https://bigmodel.cn/coding-plan/personal/overview`;GLM 按量 `https://bigmodel.cn/usercenter/proj-mgmt/apikeys`(后四个与 ZCode 目录逐字一致)。

## Test strategy (oracle)
新 `tests/test_kimi_glm_vendors.py` + `tests/test_kimi_glm_ui.mjs`:
- k1 三家在表里,端点/默认模型/模型列表钉死(会过期的事实,标日期)。
- k2 每家有 https keyUrl,值钉死;MiMo 必须指套餐页。
- k3 厂商 id 可安全落文件名/变量名,变量名两两不同。
- k4 🔴 两家 GLM 都存 key 后:选「GLM 按量 glm-5.3」→ nanobot 加载器拿到按量端点+按量 key;再选「GLM 套餐 glm-5.3」→ 套餐端点+套餐 key(同名模型不串家)。
- k5 Kimi 作第二家:存→prepare_gateway→菜单出现→选中后 nanobot 拿到 Kimi 端点与 key。
- k6 `/api/llm/credential` providers 带 keyUrl。
- ku1~ku3(node):asProvider 收 keyUrl、非 https 丢弃;卡片按选中厂商渲染外链(target=_blank、rel=noreferrer)。

**这个 oracle 能被什么骗过?** 全绿但真 key 连不上(模型名/大小写/端点形态错)—— 只有真 key 接得住,业主没有;
链接在 Electron 里点了没反应 —— 靠 navPolicy 既有判据(外链交系统浏览器)+ 发版单云 e2e 截图。
