# e2e(真 gateway)驱动

聊天链路的端到端验证,需要**活的 nanobot gateway + ds_web**,不进 `tests/*.mjs`
常规回归(glob 扫不到本目录,CI/无 gateway 环境不误红)。

> **收货前请跑仓库级总跑 `tests/run-all.sh`**(泄漏闸自测 + node 单测 + python 全量 +
> MCP 闸 + dist 新鲜度 + 本目录 e2e,一条命令)。本文件说的是其中 **e2e 那一段**;
> 单独调试 e2e 时才直接用下面的 `tests/e2e/run-all.sh`。
>
> ⚠️ 这里**故意不写第几段、也不写总共几段**:原来写的是「四段…其中第四段」,
> 总跑插进新段之后就成了假话(2026-08-18 四审 submimo 抓到)。按名字指,插多少段都不会漂。
> **2026-08-24 补**:那次只把序号改掉,却在同一句里留了「六段」—— **总数和序号一样会漂**,
> 现已一并去掉。上面那串按名字列举的清单才是可靠的指法。

## ⭐ 先看这个:总跑开关 `run-all.sh`

```bash
tests/e2e/run-all.sh                  # 全部可无人值守的场景(约 2.5 分钟)
tests/e2e/run-all.sh --with-gateway   # 连下面那两条需要活 gateway 的也跑
tests/e2e/run-all.sh todo focus_ring  # 只跑名字含这些子串的
```

**开跑之前它会先过一道产物新鲜度闸**(`check-dist-fresh.sh`,约 3 秒 ——
所以你会看到一段 build 输出,那是正常的):把当前前端源码 build 到**仓外**临时目录,
与 `web/dist` **逐字节**比对。对不上就中止,因为那种情形下跑出来的绿是假的 ——
**e2e 跑的是 `web/dist`,不是 `web/src`**,两者对不上时"你以为验了你改的代码,其实没有"。
它**只报告不修复**,`web/dist` 一个字节都不碰(「你欠一次 build」这个信号要留在工作树上)。

> 2026-08-24 换的做法。此前这道闸比的是 **mtime**、而且只装在 `llm_key.e2e.mjs`
> **一个**场景里 —— 改一行注释就误报,src 真改了而 dist 的 mtime 因无关动作变新则**漏报**,
> 另外 36 个场景全无人看。track `opendesign-dist-freshness-gate`。

**改完东西请跑一遍。**本目录 30 个 e2e 谁都不归 `unittest discover` 管
(文件名不匹配 `test_*.py`),2026-08-02 之前全靠人记得手跑 —— 结果
`adoption.e2e.py`(`38da0ac` 之后)和 `frontend_p2_polish.e2e.mjs`(`549472d` 之后)
**各自红了好几天没人发现**,两次都是"实现刻意改了、判据漏改"。
开关第一次跑就把后者揪出来了。`SKIP` 单独列、**永不算作 PASS**。

## 无出口守卫:e2e 进程没有外网(导入即生效)

**不变量只有一句:跑判据的进程不许有外网出口**(08-10 一条判据真去调模型、一上午烧光额度;
09-15 e2e 打开页面会真去问 GitHub 查更新,跟业主抢同一份免登录额度)。

- **导入即生效**:`.e2e.mjs` 导入 `helpers.mjs`、`.e2e.py` 顶部 `import _no_egress`,进程就把自己
  搬进一个**只有回环**的网络命名空间(`unshare -n`)再跑。单跑、总跑都一样,不靠 run-all 记得套。
- **前提:root + 内核支持 `unshare -n`**。做不到就**拒跑**,退出码 **78**,stderr 以
  `🔴 无出口守卫:` 开头并说清原因(找不到 unshare / 没权限 / 回环没起来 / 进去了却仍连得出去)。
  看到 78 不是场景红了,是守卫在说环境不对 —— **别去查产品**。
- **豁免只有两条**:`new_chat.e2e.mjs`、`project-thread.e2e.mjs`(要连主命名空间里的活 gateway)。
  名单唯一一份在 `helpers.mjs` 的 `NEEDS_LIVE_GATEWAY`,`run-all.sh` 的 `NEEDS_GATEWAY` 由判据钉成逐项相同。
  **想加第三条豁免时先问"这条 e2e 为什么需要外网"**,不是"怎么让它过"。
- **浏览器临时目录归测试自己收**:`helpers.launchBrowser` 给 Chromium 一个自己建的 TMPDIR,进程退出时收掉;
  浏览器没走正常关闭时,除了收掉还**点名**:stderr 一行 + 往 `E2E_BROWSER_NOTES` 指的文件记 `<脚本名>: …`。
  单跑 `run-all.sh` 时点名簿在它自己的日志目录里、汇总后打印;仓库级总跑 `tests/run-all.sh` 会给它一个
  外层自己的路径,把「浏览器收容 N 次:哪几条」直接写进汇总表那一行(外层绿了会删日志,名字只能留在那儿)。
  ⚠️ 手工调试时 shell 里 export 过 `E2E_BROWSER_NOTES` 的话,`run-all.sh` 会沿用它 —— 用完 `unset`。
- 强度:挡手滑,不挡蓄意(root 一行 `nsenter` 就出去)。判据在 `tests/test_e2e_harness_guard.mjs`。

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

# 3b. 🔴 **`project-thread.e2e.mjs` 的夹具是 ds_root 里那两个项目,而它们没进仓。**
#     它和别的场景不一样:别的自己起 ds_web、自己造夹具;它连的是**外面这一个**,
#     只知道 HTTP 地址、够不着人家的 DS_ROOT ⇒ 夹具只能在起 ds_web 之前先摆好。
#     · 上面这条命令**没给 DS_ROOT** ⇒ ds_root 落在 `DEFAULT_DS_ROOT` = 仓库根
#       (`bin/ds_web.py:838`),夹具就是仓库根的 `projects/翡翠湾-1801.md` 与
#       `projects/星河名邸-2302.md`。**本机有,但 git 里 `projects/` 只提交了
#       `.gitkeep`** ⇒ 换一台机器新克隆,这两个文件不存在。
#     · 表现是:第 2 步在 `.proj-row` 上干等 30 秒 → TimeoutError,
#       错误信息里没有半个字提到"你少了夹具"(2026-09-08 收 opendesign-in-app-update
#       时真撞上:那次是 ds_web 被起在一个空的 DS_ROOT 上。那两条要 gateway 的 e2e
#       长年 SKIP,这个洞因此从来没露过头)。
#     ⇒ 给 DS_ROOT 指别处、或换机器时,先把夹具造出来:
mkdir -p "$DS_ROOT/projects"   # 不给 DS_ROOT 就是仓库根,本机已经有了
for P in 翡翠湾-1801 星河名邸-2302; do
  printf '# %s\n\n- 阶段: 施工跟进\n\n## 变更记录\n\n## 变更历史\n\n## 沟通日志\n' "$P" \
    > "$DS_ROOT/projects/$P.md"
done
#     (`curl -s http://127.0.0.1:8768/api/projects` 列得出这两个才算摆好了。
#      正解是让这条 e2e 自己用 `/api/projects/create` 造夹具、别靠机器上碰巧有什么 ——
#      那要单独一单,记在 track `opendesign-in-app-update-install` 的 backlog 里。)

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
