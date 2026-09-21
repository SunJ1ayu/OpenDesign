# Tasks: opendesign-per-vendor-keys

- base-ref: 74ec75b384a541a1b7167b34412389534e433750

> 执行:主 agent 自己做(凭据面 + 跨模块契约,不外包)。oracle 先行、单独 commit、先红。

- [x] T0 方案检查:独立挑战(Cursor/Grok)+ 实验 p1(loader)/ p2(活网关)—— 见 design.md、evidence/
- [ ] T1 判据(先红):`tests/test_per_vendor_keys.py` v1~v12
- [ ] T2 判据(先红):`tests/test_per_vendor_live.py` 活网关真切换(断网、本机假服务器)
- [ ] T3 判据(先红):外壳接线增补(`build_env` → `prepare_gateway`,额外变量只进网关腿)
- [ ] T4 判据(先红):前端纯逻辑(分组菜单)+ e2e 两家场景
- [ ] T5 实现 `bin/ds_credential.py`:额外槽存储 / save(multi) / prepare_gateway / models_status / select_model / status.vendors
- [ ] T6 实现外壳接线:`bin/ds_shell.py` build_env、`bin/ds_shell_core.py` child_env/service_envs 的 extra_keys
- [ ] T7 实现 `bin/ds_web.py`:multi 判定、接口字段
- [ ] T8 实现前端:`LlmKeyCard.tsx` 每家一行、`chat/modelPicker.ts` + `ChatPage.tsx` 分组菜单
- [ ] T9 bump 0.98.9、build dist、全量 python 回归 + e2e 总跑
- [ ] T10 主 agent 自审(落盘)→ 两个不同家族外审 → 处置
- [ ] T11 归档;打安装包、发布;业主真机:存两家、菜单两组、切过去问一句「你是谁」、回显 0.98.9
