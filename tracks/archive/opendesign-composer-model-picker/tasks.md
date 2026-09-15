# Tasks: opendesign-composer-model-picker

- base-ref: 84db5209dc49373a8ed7c60175e46ae77a986132

- [x] 判据先行:`tests/test_ds_llm_model.py`(lm1~lm8)、`tests/test_model_picker.mjs`(mp)、`tests/e2e/model_picker.e2e.mjs`;e2e 里 `.chat-meta` 20 处改认 `[data-ui="chat-model"]`(单独一笔说明理由)
- [x] 后端:`ds_credential.PROVIDERS` 加 models(MiMo 读模板);`ds_web` GET /api/llm/models、POST /api/llm/model
- [x] 前端:`web/src/chat/modelPicker.ts`(纯逻辑)、ChatPage 输入卡模型按钮 + 向上菜单、删 .chat-meta 与退出登录、App 传 onOpenLlmKey;重建 dist
- [x] 红检(变异咬住 lm/mp/e2e 关键断言)
- [x] 全仓总跑
- [x] panel-review(impact high ⇒ 预算 2)→ 仲裁
- [ ] 截图给业主看改后的真界面;bump / 发版问业主
