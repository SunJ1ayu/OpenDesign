# e2e(真 gateway)驱动

聊天链路的端到端验证,需要**活的 nanobot gateway + ds_web**,不进 `tests/*.mjs`
常规回归(glob 扫不到本目录,CI/无 gateway 环境不误红)。

## 跑法(Linux 开发机)

```bash
# 1. 临时开 WebSocket 通道(自动备份 ~/.nanobot/config.json -> .bak)
python3 bin/enable_webui.py e2etest

# 2. 起 gateway(MiMo key 从 mimocode auth.json 取)+ ds_web
bin/ds-nanobot gateway &            # 记 PID,勿 pkill -f(自杀坑,见记忆)
DS_WEB_PORT=8768 python3 bin/ds_web.py &

# 3. 跑场景(playwright-core 用 npx 缓存,chromium 用 ms-playwright 缓存)
E2E_BASE=http://127.0.0.1:8768 E2E_PASSWORD=e2etest \
  node tests/e2e/project-thread.e2e.mjs

# 4. 还原:kill 两个 PID;cp ~/.nanobot/config.json.bak ~/.nanobot/config.json
```

- `helpers.mjs`:找 chromium 可执行、登录、等待选择器等公共件(O1 工具债沉淀,
  新 e2e 场景 import 它,别再手搓)。
- 断言原则:断协议与 UI 事实(前缀/转录隔离/回放/localStorage),不断言 LLM 回复
  内容(不确定性)。
- 环境变量:`E2E_BASE`(ds_web 地址)、`E2E_PASSWORD`(enable_webui 设的口令)、
  `E2E_PW_MODULES`(可选,playwright-core 所在 node_modules,缺省用 npx 缓存)。
