# Proposal: opendesign-kimi-glm-vendors

## 业主原话(09-23)
- 排期:「可以先做kimi和glm自定义放在最后加吧」;「可以把kimi和glm一起做完再发」(与 quiet-start-icons 一起出 0.98.11)。
- 问 ZCode 怎么做 → 我读 ZCode `config/provider/zcode-builtin.json`:Kimi 一项(按量,platform.kimi.com)、GLM 两项(BigModel Coding Plan / BigModel API),各带 key 管理页链接。
- 「kimi的套餐不加吗」→ 我核官方文档(只给编程工具教程、禁改 User-Agent,可能拒陌生客户端)→「没关系 那就先加kimi的按量和glm吧」。
- 「发图片收不到的字就不需要加了 太笨了有点」—— 看图提示不做(模型自己会说:实测 deepseek-v4-pro 答「看不到图片」)。

## 做什么
1. 厂商表加三家:`kimi`(Kimi 按量)、`glm_plan`(GLM 套餐)、`glm`(GLM 按量)。
2. 每家(含 MiMo / DeepSeek)带「获取 API Key」链接,key 卡片里在输入框旁边显示。

## 不做
- Kimi 会员(Kimi Code)、自定义厂商(排最后)、看图标记与报错翻译、测试按钮。
- 没有真 key:Kimi/GLM 模型名按 ZCode 目录 + 官方文档,**未经真 key 验证**,发版说明写明。
