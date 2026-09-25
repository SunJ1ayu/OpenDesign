# subdeepseek-agent explore log
time: 2026-09-25T10:20:13+08:00
mode: explore (agent base: claude-code headless -> deepseek)
base_url: https://api.deepseek.com/anthropic
model: deepseek-flash
repo: /root/.openclaw/workspace/projects/design-studio
task: /root/aiwork/logs/explore-keyrestart-qa-exec-20260925-102012.task.md
视野: 底座腿 —— 自己读仓库(Read/Glob/Grep)+ 只读 git(自己跑 git diff/log/show)。

  → Bash ls -la /root/.openclaw/workspace/projects/design-studio/ 2>&1 | head -40; echo "---"; ls -la /root/.openclaw/workspace/projects/design-studio/tracks/ 2>&1 | head -40

  → Bash ls -la /root/.openclaw/workspace/projects/design-studio/tracks/opendesign-key-restart/evidence/ 2>&1

  → Read /root/.openclaw/workspace/projects/design-studio/tracks/opendesign-key-restart/evidence/20260925-qa-design-subdeepseek.md

  → Read /root/.openclaw/workspace/projects/design-studio/tracks/opendesign-key-restart/evidence/20260925-qa-design-subcursor.grok-4.7-high.md

  → Read /root/.openclaw/workspace/projects/design-studio/tracks/opendesign-key-restart/evidence/20260925-windows-probe-5.txt

  → Read /root/.openclaw/workspace/projects/design-studio/tracks/opendesign-key-restart/evidence/20260925-windows-probe-3.txt

  → Read /root/.openclaw/workspace/projects/design-studio/tracks/opendesign-key-restart/evidence/20260925-windows-probe-4.txt

  → Read /root/.openclaw/workspace/projects/design-studio/tracks/opendesign-key-restart/evidence/20260925T014105Z-01-run-all.txt

  → Bash wc -l tests/e2e/model_settings.e2e.mjs tests/e2e/per_vendor_keys.e2e.mjs 2>&1; echo "---"; ls tests/e2e/ | head -50

  → Bash grep -n 'check(' tests/e2e/model_settings.e2e.mjs | head -80

  → Read /root/.openclaw/workspace/projects/design-studio/tests/e2e/model_settings.e2e.mjs

  → Read /root/.openclaw/workspace/projects/design-studio/tests/e2e/per_vendor_keys.e2e.mjs

  → Bash grep -rn "手动重启\|正在准备聊天服务\|下一句对话起就用\|右下角就能换" --include=*.py --include=*.mjs --include=*.ts --include=*.tsx --include=*.svelte --include=*.js tests/ web/src bin/ 2>/dev/null | head -40

  → Bash ls tests/*.py | head -40; echo "---key_live---"; ls -la tests/test_key_live.py tests/test_per_vendor_live.py 2>&1

  → Bash grep -n "def \|skip\|pytest.mark" tests/test_key_live.py | head -60

  → Bash grep -rn "gateway\|SKIP\|skip" tests/run-all.sh | head -40

  → Read /root/.openclaw/workspace/projects/design-studio/tests/test_key_live.py

  → Read /root/.openclaw/workspace/projects/design-studio/tracks/opendesign-key-restart/evidence/20260925T013738Z-01-mutation-key-restart.txt

  → Bash grep -n "FAIL\|ok  " tracks/opendesign-key-restart/evidence/20260925T011650Z-01-e2e-model-settings-rewrite-red.txt | head -40; echo "=== per_vendor red on old ==="; grep -n "FAIL\|ok  " tracks/opendesign-key-restart/evidence/20260925T013952Z-01-e2e-per-vendor-rewrite-red-on-old.txt | head -40

  → Bash grep -rn "立即重试" --include=*.mjs --include=*.py --include=*.ts --include=*.svelte tests/ web/src bin/ 2>/dev/null | head -20; echo "=== 401 ==="; grep -rln "401" tests/*.py tests/e2e/*.mjs 2>/dev/null | head -20

  → Bash head -30 tests/e2e/chat_reconnect.e2e.mjs; echo "=== run-all e2e list ==="; grep -n "\.mjs\|\.py\|SKIP\|skip" tests/e2e/run-all.sh | head -60

  → Bash grep -rn "连接不上" --include=*.mjs --include=*.ts --include=*.svelte tests/ web/src 2>/dev/null | head -20; echo "=== probe files ==="; ls -la probe/ 2>/dev/null; find . -path ./node_modules -prune -o -name "*probe*" -print 2>/dev/null | grep -v node_modules | head -30

  → Bash ls -la .github/scripts/restart-probe/ && wc -l .github/scripts/restart-probe/*

  → Read /root/.openclaw/workspace/projects/design-studio/.github/scripts/restart-probe/drive5.py

  → Bash sed -n '195,245p' tests/test_llm_key.mjs

  → Read /root/.openclaw/workspace/projects/design-studio/tracks/opendesign-key-restart/evidence/20260925-qa-design.roster

  → Bash sed -n '95,160p' tests/run-all.sh

  → Bash sed -n '1,80p' tests/dead_assertions.py

  → Bash grep -n "401" tests/test_ds_web_credential.py | head -10; echo "=== test_key_live in allow ==="; grep -n "key_live" tests/dead_assertions.allow | head; echo "=== desktop_update scope ==="; grep -n "key\|模型\|model" tests/e2e/desktop_update.e2e.mjs | head -20

  → Bash ls -la tracks/opendesign-key-restart/ && git log --oneline -20

  → Bash grep -n "401\|invalid\|鉴权\|错的 key\|错key" tests/test_per_vendor_live.py tests/test_ws_protocol_smoke.py tests/test_ds_web_proxy.py 2>/dev/null | head -20

  → Bash grep -n "ms-model\"\]\.click\|modelRow(.*)\.click\|当前模型不变\|不换当前" tests/e2e/*.mjs | head -20; echo "=== 定时任务/model ==="; grep -rln "cron\|定时任务" tests/*.py tests/*.mjs tests/e2e/*.mjs 2>/dev/null | head -15

  → Bash ls -la tracks/opendesign-key-restart/observations/ && head -40 tracks/opendesign-key-restart/observations/* 2>/dev/null | head -80

  → Bash for f in 20260925T013952Z-01-e2e-per-vendor-rewrite-red-on-old.txt 20260925T014014Z-01-e2e-per-vendor-rewrite-red-on-25011a3.txt 20260925T011136Z-01-rewritten-oracles-red-on-old.txt 20260925T011306Z-01-oracle-d5-red.txt; do echo "### $f"; grep -n "FAIL\|红\|条红" tracks/opendesign-key-restart/evidence/$f | head -12; done

  → Grep FAIL|条红|红检

  → Bash git diff --stat c25ffb3 HEAD | tail -20

读完仓库里的原始记录(两份设计、probe-5/3/4、run-all 收据、两份 e2e 判据、`tests/test_key_live.py`、红检与 mutation 记录、`.github/scripts/restart-probe/drive5.py`)。以下按要求的标签输出。

**Direction:** 以「真机收据优先、按'有没有一句话能回答它'分档」对账 23 条 P0 —— 机制层已被两条独立记录钉死,界面层与失败路径整片空白

**Core bet:** 我赌这一单真正的结论不是「42 PASS / 0 FAIL」,而是「绿的都集中在'存了就用、不重启、不扣错家'这一条主轴上,而业主原话里的界面症状(按钮没了)和全部 P0 失败路径,在真机上零证据」。把这两件事分开说,比再补一条 e2e 有用。

**How it works:**

### 1. 用例对账表(两份设计里的 P0,共 23 条)

证据代号:`P5`=`evidence/20260925-windows-probe-5.txt`;`MS`=`tests/e2e/model_settings.e2e.mjs`;`PV`=`tests/e2e/per_vendor_keys.e2e.mjs`;`KL`=`tests/test_key_live.py:165`(真网关、假厂商、走外壳自己的 `gateway_argv`/`service_envs`);`RA`=`evidence/20260925T014105Z-01-run-all.txt`。
**假设(已核)**:`KL` 在 python 全量里真跑过 —— `RA:27` 是「1553 跑过 / 1 跳过 / 无死断言」,而死断言闸跑的是 `unittest discover -s tests`;`RA:35-36` 显示树与 `HEAD` 一致(只多了收据文件)。

| 编号 | 判定 | 证据 |
|---|---|---|
| T01 存别家不断线/按钮在/下一句走它 | 已执行·通过 | P5:11-12「切到 DeepSeek 之后」只打到 DeepSeek、带 `…6789ab`;P5:17 全程同一条 websocket 没断;P5:18 网关进程没换;PV:258-263 菜单两家、勾仍在 MiMo;MS:354-361 一帧都没发给外壳 |
| T02 保存后立刻发就用新 key | 已执行·通过 | KL:174-176「主槽换了 key 之后」同一网关下一句带 K2;P5:13-16 K1→K2 后仍带 `…543210`(真机上这两条都夹了一次模型切换) |
| T03 换模型按钮选 B | 已执行·通过 | P5:10-12 只打 `deepseek-v4-pro`;PV:276-280 配置里当前模型真的变了、按钮字变 |
| T04 全新装机第一把 key 自己连上 | 已执行·通过 | P5:21-30 存第一把 ⇒ `restart=requested` ⇒ 网关 `@+5.8s` 起来 ⇒ ws 连上 ⇒ 第一句只打 MiMo 带 `…456789`;MS:506-514 提示「正在准备聊天服务」+ 请外壳起 |
| T05 存完第一把**马上**发送 | 没执行到 | 缺「网关还没起来就发送」这一支:P5 fresh 是等到 ws 连上才发(P5:27-28);浏览器 e2e 的聊天是替身(MS:78、PV:84 `send() { }`),发不出真一句 |
| T08 错 key 明确报错、旧 key 不继续用 | 没执行到 | 缺「错 key 的下一句」。KL 三台假厂商只认对的 key,判据里无 401 分支;MS 的「测试」按纪律只点本机假厂商的自定义供应商(MS:7-8 注释:内置厂商的测试按钮只问在不在,不点) |
| T09 保存动作本身失败 | 没执行到 | 缺一次「保存失败」注入。现有失败类断言只有空 key(MS:388-392)与表单校验(MS:299-305、418-428) |
| T11 起服务失败给出路 | 没执行到 | MS G1 只问回包与提示原文,假外壳那一步照做(MS:116-125);P5 只有成功路径 |
| TC-01 存别家后不换模型再发仍是小米 | 已执行·通过 | KL:179-181「存了 DeepSeek 但还没切」那一句仍打 MiMo 带 K2;PV:261-263 勾仍在 MiMo;MS:362 当前模型不变 |
| TC-02 菜单选 DeepSeek 后下一句走它 | 已执行·通过 | 同 T03 |
| TC-03 改当前那家 key 后立刻发 | 已执行·通过 | KL:174-176;P5:13-16 |
| TC-04 错 key 那一句失败、按钮不变 | 没执行到 | 同 T08 |
| TC-05 首装第一把 key 自己连上 | 已执行·通过 | 同 T04 |
| TC-06 设置页点模型行**不**换当前模型(负向) | 没执行到 | 全仓没有一条判据点设置页模型行后断言当前模型不变;MS 只有 A6「正在用的模型删不掉」(MS:332-334)。正向(pickInMenu)已覆盖 |
| TC-07 错 key 点「测试」给可读失败 | 没执行到 | 内置厂商的测试不点;自定义供应商那条(MS:446-454「模型 ID 不对…404」且不含 key)是近似,但问的是模型 ID 不是 key |
| TC-08 保存失败不说「已保存」 | 没执行到 | 同 T09 |
| TC-09 首装超时后「立即重试」+ 退出重开 | 没执行到 | 条件未触发(P5:26 是 5.8s 就连上),且无「起不来」注入器;现有提示里也没有它期望的「立即重试」 |
| TC-10 流式中途存 key、半句不断 | 没执行到 | 没有工件;P5 三句都是发完才动设置页 |
| TC-11 全新装机、只有自定义供应商 | 没执行到 | MS 加自定义供应商是在**已有 MiMo** 的台面上(MS:83-97);已验的只是「不等重启就能测」(MS:446-457)与「菜单里选得到」(MS:459) |
| TC-12 错 key 家切过去失败、再切回 | 没执行到 | 同 T08/TC-04 |
| TC-13 改 key 后不停留立刻发 | 已执行·通过 | KL:174-176(同一网关、同一 ws、就是新 key);MS:395-403 提示说下一句、没找外壳 |
| TC-14 自动更新后 key/模型还在 | 没执行到 | 本单无判据;`tests/e2e/desktop_update.e2e.mjs` 无 key/模型断言 |
| TC-15 定时任务仍走原模型 | 没执行到 | 没有「定时任务 × 模型」的判据 |

**合计:通过 9 / 不通过 0 / 没执行到 14。**
「不通过 0」是真的 —— 中途红过两条(死断言 + e2e 41 PASS/1 FAIL,见 `evidence/20260925T012405Z-01-run-all.txt:27,30`),已由 `c25ffb3` 修掉,`c25ffb3..HEAD` 对代码/判据零差异(`git diff --stat` 只有收据与 verify.md)。

### 2. 缺陷

**① 全新装机起不来时,提示把用户推回「退出重开」——正好是本单要消掉的那个动作。**
触发:全新装机(网关没在跑)→ 存第一把 key → 几秒内没连上。
用户看到:「已保存,正在准备聊天服务,稍等片刻即可开始对话;**若稍后仍连不上,请退出 OpenDesign 再打开。**」
证据:brief 提示表第 3 行原文;唯一出处 `web/src/settings/modelSettings.ts:262`;红检记录里这句兜底在改造前就存在 —— `evidence/20260925T014014Z-01-e2e-per-vendor-rewrite-red-on-25011a3.txt:35` 是旧版「…一直没好就退出 OpenDesign 再打开」,改文案时被原样带过来了。MS:511 只断言 `/正在准备聊天服务/` 且 `!/重启/`,**没有一条断言问过这半句**。两份设计都点过它(deepseek T11/Q1、grok TC-09 期望的是「连接不上 + 立即重试」,聊天页本来就有这个按钮却没人指)。
严重度:中低。命中概率低(P5 fresh 5.8s 就好),但一旦命中,用户做的就是这个 track 立单要删掉的动作。

**② 「保存失败」这条状态没有任何一句话、也没有任何工件能证明它对。**(框定为缺陷而非已证伪)
触发:点保存时后台写失败。用户看到什么:记录里查不到 —— brief 的提示表只有 4 行,没有这一行。
证据:失败类断言只有空 key `「API key 是空的」`(MS:389-392)与表单校验;没有一条判据能让保存**本身**失败。deepseek Q3 与 grok TC-08 都把它列成 P0。用户会分不清「该重填」还是「该等」——这正是 deepseek Q3 的原话。

**③ 存别家 key 时说「下一句对话起就用它」(已在本单修掉,留档)。**
证据:`evidence/20260925T011650Z-01-e2e-model-settings-rewrite-red.txt:31` `FAIL - A3 …(「已保存,下一句对话起就用它。」)`;`5f2cf3d` 拆成两种说法,`MUT` 的 M14 咬住。现状表第 2 行已正确。

### 3. 请业主在真机上亲自走的 5 步(按要紧程度)

1. **先看界面(最要紧)。** 装好这版,聊着天去设置页存**另一家**的 key,全程别把眼睛移开:聊天框右下角那个换模型按钮**一直在吗**?存完的提示**原文照下来**。然后**不换模型**,直接再发一句 —— 回复还是原来那家吗?
   (业主 09-25 的原话是「新对话一直显示链接不上 gateway」+ 按钮没了;`drive5.py` 全程走 HTTP/ws,**没有浏览器**,所以真机上界面长什么样,今天一条记录都没有。)
2. **错 key 那一趟。** 把当前这家的 key 改成一个明显错的,存完马上发一句:它给的是**看得懂的失败**吗?右下角**仍然停在原来这家**吗?有没有别家的正常回复顶上来?再把 key 改回来,是不是立刻就能聊。
3. **半句被打断那一趟。** 发一句要求写很久的,趁它还在写,去设置页存另一家的 key:正在写的那半句断没断?写完了吗?按钮还在吗?
4. **起不来那一趟(第 5 步用不上时做)。** 全新装一次,断着网存第一把 key,掐表等 1 分钟:界面是一直「正在准备聊天服务」,还是自己变成「连接不上,gateway 可能没在跑」+「立即重试」?除了退出重开,还有别的路能走出去吗?
5. **更新之后那一趟。** 从旧版走自动更新装到这版,打开:key 掩码还在吗?当前模型还是原来那个吗?不用重填就能直接发一句吗?

**Best at:** 把「绿得可信」和「根本没问」分开。业主最初的那句症状是界面层的,而这个 track 的全部收据(probe-5、L1、42 条 e2e)加在一起,只证明了**机制层**:同一网关/同一条 ws、下一句带刚存的那把 key、只有对的那家收到请求。这一层证据是硬的(真 Windows 一条 + Linux 真网关一条,互为独立),而且 mutation 15/15 咬住,不是空绿。

**Sacrifices:** 我按「有没有工件能回答」判,不按「代码看起来对不对」判,于是 14 条 P0 直接记「没执行到」而不给「大概没问题」——短期看这份对账比「42 PASS」难看,而且我明确把 2 条真机人工步骤放在了机器证据之前。代价是:如果业主不想动手,这份对账就停在「9 通过 / 14 未知」,我给不出更紧的结论。**方向错在哪**:如果团队本来就只打算验「存了就用」这一条主轴、界面文案另走一轮,那我这份 P0 清单里的一多半是越界的。

**Blind spots in the brief:**
- **把「真机跑过」读成了「界面验过」。** `drive5.py:109-119` 的 `call()` 直接打 `/api/llm/…`,`ws` 是 `websockets.sync` 直连 —— 真 Windows 上**没有浏览器在环里**。业主的症状却是界面的(按钮没了、显示连接不上)。今天真机上界面层的证据是 0,这条缺口 brief 没提。
- **e2e 的聊天是替身,扣谁的钱在浏览器层根本问不出来。** `MS:78`、`PV:84` 的 `send() { }` 是空的,那 42 条 PASS 里没有一条能回答「谁答的话」。brief 把 e2e 说成「浏览器端到端」,会让人以为钱那条路在浏览器里问过了。
- **提示表第 4 行(源码老装法)没有任何执行证据。** 只有 `tests/test_llm_key.mjs` 的单测问「四句话互不相同、不撒谎」,grok 的 TC-16/S7(H2「重启后新的那家才进菜单」)没人跑。brief 把四种状态并列成一张表,读起来像四种都验过。
- **「对照」是旧包上的旧病,不是同一维度的对照。** probe-3/4 的 idle 组 240s 起不来,而 probe-4 的 `idle-devnull` 对照组 +6.3s 就起来了(`-probe-4.txt:10-14`)—— 病因是子进程继承了管家 stdin,不是「没改之前都不行」。这一层 brief 摘要里被压成了一句「对照」。
- **5 条 P0 路径完全零证据,却被总数掩盖。** 错 key、保存失败、流式中途存 key、自动更新后 key/模型还在、定时任务仍走原模型 —— brief 用「42 通过 / 0 失败」收尾,这五个连一条断言都没有。
- **「存 key 不换当前模型」的真机上那一支没孤立验过。** P5 每一步都夹了一次切模型 API;真正「存完不切换直接发」只在 Linux 的 `KL` 里问过。

**Smallest first step:** 拿一台装了修好包的 Windows,**只做上面第 1 步** —— 在聊天页存另一家的 key,全程录屏右下角换模型按钮 + 提示原文,存完不换模型再发一句。这是业主最初那句「按钮没了」唯一没有任何工件回答的地方;半天内能给出结论,而且它不过,后面第 2、3 步都不用展开。

------------------------------------------------------------
turns: 62 / 上限 200
(原始 stream-json:/root/aiwork/logs/explore-keyrestart-qa-exec-20260925-102012.subdeepseek.stream.jsonl)
