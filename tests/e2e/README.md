# e2e(真 gateway)驱动

聊天链路的端到端验证,需要**活的 nanobot gateway + ds_web**,不进 `tests/*.mjs`
常规回归(glob 扫不到本目录,CI/无 gateway 环境不误红)。

> **收货前请跑仓库级总跑 `tests/run-all.sh`**(node 单测 + python 全量 + MCP 闸 + 本目录 e2e,
> 四段一条命令)。本文件说的是其中第四段;单独调试 e2e 时才直接用下面的 `tests/e2e/run-all.sh`。

## ⭐ 先看这个:总跑开关 `run-all.sh`

```bash
tests/e2e/run-all.sh                  # 全部可无人值守的场景(约 2.5 分钟)
tests/e2e/run-all.sh --with-gateway   # 连下面那两条需要活 gateway 的也跑
tests/e2e/run-all.sh todo focus_ring  # 只跑名字含这些子串的
```

**改完东西请跑一遍。**本目录 30 个 e2e 谁都不归 `unittest discover` 管
(文件名不匹配 `test_*.py`),2026-08-02 之前全靠人记得手跑 —— 结果
`adoption.e2e.py`(`38da0ac` 之后)和 `frontend_p2_polish.e2e.mjs`(`549472d` 之后)
**各自红了好几天没人发现**,两次都是"实现刻意改了、判据漏改"。
开关第一次跑就把后者揪出来了。`SKIP` 单独列、**永不算作 PASS**。

## 跑法(Linux 开发机)

```bash
# 1. WebSocket 通道:配置里 channels.websocket.token 非空就已经开着,**别再跑
#    enable_webui.py** —— 它会改 ~/.nanobot/config.json,而改坏真机 gateway 口令
#    这件事已经害人查了一整天(见记忆 judging-must-have-no-egress)。先只读地查:
python3 -c 'import json,pathlib;print(bool((json.loads((pathlib.Path.home()/".nanobot"/"config.json").read_text()).get("channels",{}).get("websocket",{}) or {}).get("token")))'

# 2. 起 gateway(MiMo key 从 mimocode auth.json 取)
bin/ds-nanobot gateway &            # 记 PID,勿 pkill -f(自杀坑,见记忆)

# 3. 起 ds_web —— **家目录要隔离,而且必须显式指回真配置**(2026-08-16):
#    · HOME 隔离 + 放一把假 key.txt ⇒ 否则 T4 的 key 卡片会自动弹出来,
#      遮罩吃掉所有点击(29 条 e2e 一起红就是这么来的);
#    · DS_NANOBOT_CONFIG 指回真配置 ⇒ ds_web 要从那儿读口令替前端代签,
#      HOME 一隔离它就找不着了。两个需求指向不同目录,所以要分开给。
H=$(mktemp -d); mkdir -p "$H/.openDesign"; echo sk-e2e-fixture > "$H/.openDesign/key.txt"
env HOME="$H" USERPROFILE="$H" DS_NANOBOT_CONFIG="$HOME/.nanobot/config.json" \
  DS_WEB_PORT=8768 python3 bin/ds_web.py &

# 4. 跑场景(playwright-core 用 npx 缓存,chromium 用 ms-playwright 缓存)
#    **不用给口令**:T2 起 ds-web 替前端代签,给了也没人读。
E2E_BASE=http://127.0.0.1:8768 node tests/e2e/project-thread.e2e.mjs

# 5. 还原:kill 两个 PID;rm -rf "$H"。配置一个字都没动过,不需要还原。
```

- `helpers.mjs`:找 chromium 可执行、登录、等待选择器等公共件(O1 工具债沉淀,
  新 e2e 场景 import 它,别再手搓)。
- 断言原则:断协议与 UI 事实(前缀/转录隔离/回放/localStorage),不断言 LLM 回复
  内容(不确定性)。
- 环境变量:`E2E_BASE`(ds_web 地址;口令不用给 —— 见 `helpers.waitConnected`)、
  `E2E_PW_MODULES`(可选,playwright-core 所在 node_modules,缺省用 npx 缓存)。

## 不需要 gateway 的场景(自起 ds_web,直接 `node <file>`)

- `image_upload.e2e.mjs`(8808)、`chat_image.e2e.mjs`(8810)。
- `chat_image` 需要聊天已连接,但**不用真 gateway**:`page.addInitScript` 里 stub 掉
  `window.WebSocket` + `/api/chat/bootstrap`,于是能直接断"`ws.send()` 的信封里
  media 形状对不对"。代价:证明不了 nanobot 会收下 —— 那条靠对真 gateway 的手工冒烟
  兜(见该 track 的 verify.md),两者缺一不可。
