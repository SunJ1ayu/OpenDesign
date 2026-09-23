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
- 完全实现仍可能失败:模型名/大小写不对(见 2);GLM 套餐 key 被服务端限定只给编程工具(官方未写死,ZCode 自己就是编程工具)。
- 未解决项:无能改方向的;真 key 验证留业主。

## Approach
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
