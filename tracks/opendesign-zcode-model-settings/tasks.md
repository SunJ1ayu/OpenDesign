# Tasks: opendesign-zcode-model-settings

> 接手先读:proposal(业主原话)、design(D1~D4)、本文件「接手须知」。ZCode 源码克隆在
> /tmp/claude-0/-root/21304192-cb7b-484a-b81f-0a79c7cff119/scratchpad/zcode [仓外不承重](没了就 `git clone --depth 1 https://github.com/zai-org/ZCode`);
> 设置页在 packages/ui/src/settings/model-provider-section/,换模型弹框在 packages/ui/src/ModelConfigSelect.tsx;
> 真截图:https://doc.dmxapi.cn/zcode.html(Zcode7/10/14/15.png)。

- [x] T1 方案 + 4c 挑战(Grok)→ D1~D4(`a2222b5`)
- [x] T2 后台判据 z1~z12(`218f0af`,`eb51281` 修键名)→ 实现(`05db6c4`):目录 = 内置 ⊕ `<home>/.openDesign/models.json`,
      `catalog_scope`/`_scoped` 包所有入口 + 合并器 + set_model;新 API:providers_view / add_model / remove_model / set_context_window /
      set_enabled / add_custom_provider / remove_custom_provider / test_model;save(switch=False);MiMo 模板补 v2.6-pro/flash;lm1 前提更新(`1575924`)
- [x] T3 ds-web 接口判据 w1~w7(`7ba8802`)→ 实现(同 `05db6c4`):GET /api/llm/providers;POST /api/llm/providers/{key,enabled,models,custom}、/api/llm/test
- [ ] T3b **试点:测试员角色**(业主 09-24 同意,见 evidence/qa-pilot.md):QA-设计两家 16:15 派出
      (日志前缀在 scratchpad prefix_qa;/root/aiwork/logs/explore-zcode-qa-design-*)→ 主裁合并成 evidence/acceptance-cases.md → 据此写 T4 判据; [仓外不承重]
      界面建好后 QA-执行(真操作 + 截图)→ 缺陷分级 → 再做代码评审(1 轮为主)。
- [x] T3b QA-设计完成 → evidence/acceptance-cases.md(A1~A29 + 需求空白主裁定 Q1~Q9,`3b19d75`);Q8 后台补 update_custom_provider(判据 z13 `df32ac2` → 实现 `36c5529`)
- [x] T4 界面(09-24):判据移植批 `7000f41`(+ 判据修 `ae7d599` `980c73f`、w9/ms9 `5d214d4`、settings_fvis `ea99d37`)
      → 实现 `6a8d320`(设置整页 / ModelSettings / 两级弹框 ModelMenu / App 路由与首启 / 删旧卡片)→ 红检脚本改锚点 `ca53484`。
      node 514/514;e2e llm_key 32 问、per_vendor 29、model_picker ⑦a~⑦c、model_settings 66、settings_fvis、desktop_update 各自全绿(逐个跑)。
      **下一步**:整套 e2e + 两个红检脚本(后台在跑)→ QA-执行(两家模型照 acceptance-cases 真操作 + 截图)→ 缺陷分级 → T5。
- [ ] T4(原计划细节,保留)界面判据先行(node 纯逻辑 + e2e),再实现界面:
      - 设置整页:点侧栏「设置」(data-ui=settings-toggle)⇒ 整个侧栏换成设置栏目(返回工作区 / 常规 / 模型设置);
        「返回工作区」接替 settings-toggle(同 data-ui、aria-expanded=true);常规页放原弹层各项,**更新相关钩子原样沿用**
        (update-status / update-check / update-retry;update-restart 与 update-badge 留在侧栏设置行)⇒ 云 E4(.github/scripts/electron-e2e/e4-drive.mjs)
        与 tests/e2e/desktop_update.e2e.mjs 不用改。
      - 模型设置照 ZCode:标题「模型设置」+ 说明 + 刷新 + 添加供应商;卡片左栏(内置供应商五家 / 自定义供应商 + 添加供应商,状态点 ready/unavailable/disabled),
        右详情(名称 + 启用/禁用、Base URL(内置只读)、API Key + 获取 API Key、模型列表 行内 上下文长度 + 测试/编辑/删除、添加模型弹窗:模型 ID + 上下文窗口);
        添加供应商表单(名称、Base URL、API Key、API 格式只读「Chat Completions」、至少一个模型)。
      - 聊天框两级弹框:沿用 chat-model / chat-model-menu;每家一行(当前 ✓),悬停/点开向右弹出这家模型(当前 ✓),底行「管理模型」直达设置页该厂商;
        没 key 首次打开 ⇒ 直接进设置页模型设置(接替旧 LlmKeyCard 的 A1/A7)。
      - 旧 LlmKeyCard 与 tests/e2e/llm_key.e2e.mjs、per_vendor_keys.e2e.mjs、model_picker.e2e.mjs、tests/test_model_picker.mjs、test_kimi_glm_ui.mjs
        要**逐条移植**到新界面(判据改动单独 commit,verify.md 写「旧条目 → 新条目」对照表;泄漏扫描 C 组、env 遮蔽只读 H1、没外壳 manual D、
        重启外壳 B5/B6、只列有 key 的厂商 A1/A2、✓ 只在(厂商,模型)都对上时 pv3 —— 一条不许丢)。
- [ ] T5 build(web/dist)+ run-all + 截图亲看对照 ZCode 截图 + 云 Windows 整跑
- [ ] T6 两家族评审(impact high,预算 2 轮;锤子砸墙类照报不算阻断;分裂按 split_resolutions 裁)→ 归档 → 发 0.98.12(另开发版单,当天归档)
