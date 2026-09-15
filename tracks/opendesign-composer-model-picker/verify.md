# Verify: opendesign-composer-model-picker

- Date: 2026-09-15

> 机器消费的 impact / uncertainty / execution plan / outcome 只写在同目录
> `decision.json`；这里保留检查、理由、发现与主 Agent 仲裁说明，不复制枚举。

## Mechanical checks

- [x] build passes —— 最终总跑「dist 新鲜度 + 类型检查」段(收据 `final-run-all-with-gateway-r3`)
- [x] tests pass —— **判据 0 红,但总跑 rc=1 —— 这不叫全绿**(收据 `final-run-all-with-gateway-r3`,`dirty=no`、`source-stable: yes`):
      泄漏闸自测 14 全过、node 422 / 0 跳过、python 1639 跑过 / 1 跳过、MCP 三闸全绿、dist 与源码同步、**e2e 42 PASS / 0 FAIL / 0 SKIP**;
      红的只有 e2e 段外面那道**临时目录泄漏闸**:台面剩 1 个、前缀为空。跳过的 1 条是档案原子写单的 `aw12b`(Windows 专属,已由 windows-atomic-probe 真跑,见那单 verify)。
      泄漏闸这一条的归属与根因见下「红的那几份」,**不是本单代码**,也没有去放行清单里加前缀。
- [x] no secrets / unsafe ops —— 新写口 `POST /api/llm/model` 走 do_POST 入口既有 Host 白名单 + 同站闸(lm7 + 红检 a7),只收当前厂商目录里的 id,配置读不出不建文件(lm6);不碰 key.txt(lm2 字节比对);无新外呼

**机器打印的**(不是我的转述)—— 判据一律用 `runlog` 跑,下面每一行都是它写的:

```
runlog: red-lm-mp-e2e-oracle rc=1 commit=f9c97cf dirty=yes at=2026-09-15T04:52:34Z file=tracks/opendesign-composer-model-picker/evidence/20260915T045234Z-01-red-lm-mp-e2e-oracle.txt
runlog: redcheck-model-picker rc=1 commit=3f2a8bc dirty=yes at=2026-09-15T06:51:08Z file=tracks/opendesign-composer-model-picker/evidence/20260915T065108Z-01-redcheck-model-picker.txt
runlog: redcheck-model-picker-v2 rc=0 commit=3f2a8bc dirty=yes at=2026-09-15T06:53:13Z file=tracks/opendesign-composer-model-picker/evidence/20260915T065313Z-01-redcheck-model-picker-v2.txt
runlog: green-lm-mp-e2e-impl rc=1 commit=3f2a8bc dirty=yes at=2026-09-15T06:54:56Z file=tracks/opendesign-composer-model-picker/evidence/20260915T065456Z-01-green-lm-mp-e2e-impl.txt
runlog: green-lm-mp-e2e-impl-v2 rc=0 commit=3f2a8bc dirty=yes at=2026-09-15T06:58:24Z file=tracks/opendesign-composer-model-picker/evidence/20260915T065824Z-01-green-lm-mp-e2e-impl-v2.txt
runlog: final-run-all-with-gateway rc=1 commit=07afda8 dirty=yes final=yes at=2026-09-15T09:56:23Z file=tracks/opendesign-composer-model-picker/evidence/20260915T095623Z-01-final-run-all-with-gateway.txt
runlog: final-run-all-with-gateway-r3 rc=1 commit=c6a4b62 dirty=no final=yes at=2026-09-15T12:30:54Z file=tracks/opendesign-composer-model-picker/evidence/20260915T123054Z-01-final-run-all-with-gateway-r3.txt
```

- **红的那几份各自红在哪(一份不藏)**:
  - `red-lm-mp-e2e-oracle` rc=1:判据先行,实现前 lm/mp/e2e 该红(lm7 实现前就绿,见 Review 条目)—— 该红。
  - `redcheck-model-picker` rc=1:咬住 18 / 漏网 2 —— a6、a7 **不是漏网,是没打上**(锚点在文件里出现 2 次,脚本拒绝打)⇒ 修锚点唯一后 `-v2` 20/0。
  - `green-lm-mp-e2e-impl` rc=1:lm 8 OK、mp 6/6、model_picker e2e ALL PASS,**chat_reconnect `locator.click: Timeout`** —— 命令继承了真实 HOME,
    本机没有 key ⇒ 「AI 模型 key」卡片的遮罩拦住点击。量具病不是产品病:`-v2` 改用隔离 HOME + 假 key(同 `tests/e2e/run-all.sh:135-154`)后两份 e2e 全过。
  - `final-run-all-with-gateway` rc=1(07afda8):六段五 PASS,python 段 1637 跑过 / 1 跳过、**`test_t35b` 红 `'busy' != 'handoff'`** + 连带 1 条死断言(t35b 第 429 行,因上一行断言失败而没执行)。
    同一份产品代码在 8a4e327 那遍是绿的。**我没有把它归成抖动**:探针让回包之后的线程慢 0.3 秒 ⇒ t31b / t35b 两条稳定变红 ⇒
    失败回包在持锁时写出、放锁在后,满载时紧跟的第二次撞上还没放的锁。属 in-app-update 单(已随 0.98.4 发出):
    判据 `d838c71`(t41a/b 2 红)→ 修 `d3148fb`(先放锁再回话)→ 红检 `f8fc405` 15 咬 0 漏,收据在 `tracks/opendesign-in-app-update-install/evidence/`。
    对业主几乎碰不到(人手再点远慢于那个窗口),但它让判据时红时绿,是真顺序错。
  - `final-run-all-with-gateway-r3` rc=1(c6a4b62,dirty=no):除泄漏闸外全绿(见 Mechanical checks)。泄漏闸剩 1 个、前缀为空(名字里没有 `-`/`_`)。
    **先问是不是真 bug**:是 —— 判据确实漏了东西,但不是产品、也不是本单:同形状 09-15 02:17Z 在 in-app-update 的总跑(eaec8f0,本单还不存在)就出现过一次,那时探针 0 残留、没追下去。
    这次追到了机制(探针,不进仓):Playwright 起的 Chromium 在 TMPDIR 里建 `org.chromium.Chromium.XXXXXX`,正常关闭会删;**浏览器进程被 SIGKILL 一次就留一个**(5 次 → 5 个,与「剩 1 个、空前缀」同形)。e2e 单跑 4 遍 42/0/0 全部 0 残留;「close 之后立刻 process.exit」与「等进程退出」各 15 次都是 0 ⇒ 不是退出太快。即:漏的那几遍里,约 40 次浏览器启动中有 1 次没走正常关闭、而该条 e2e 照样判过。**是哪一条、为什么没走正常关闭,没钉住。**
    跟进(不在本单):让 e2e 的 Chromium 用测试自己拥有的临时目录并在退出时收掉,判据 = SIGKILL 浏览器后外层 TMPDIR 剩 0;归 `opendesign-e2e-orphan-generation`(同属「e2e 生成遗留物」)。**不往泄漏闸放行清单加前缀。**
    顺带:我第一版抓残留的量具把 TMPDIR 建在很长的路径下 ⇒ Chromium 起不来、38/42 红、还生出一个 ds_web 遗孤(stage_timer 的 spawn 在 try 之前,正是那单写的形状);已杀掉、目录已删。

## Review

- 规格自查(读任何 panel 输出之前先答,沿用派发前的自审 `/root/aiwork/tasks/opendesign-composer-model-picker-review-my-review.md`):
  规格若错,最可能错在「写配置 = 下一句换模型」—— 那是读 nanobot 源码推出来的跨组件契约,本机没有 LLM key 真跑不了。
  lm3 用 nanobot 自己的 `load_provider_snapshot` 问,但问不到网关内存态;评审把这条的两处边界都照出来了(构造参数前提、`/model` 粘性会话预设),
  已写进 design「⚠️ 前提 / ⚠️ 例外」。最终只能真机答:换到 pro 后问一句,看回复与网关日志(真机清单)。
- 腿的花名册(四次派发,**原样粘的**;r2 派出 1 分钟我发现漏了业主要的 GLM,撤掉重派,花名册用 panel-roster 从盘上重建):

```
r1  panel-opendesign-composer-model-picker-review-20260915-174641(subject head 07afda8)
submimo=off subdeepseek=PASS(verdict=PASS) subglm=PASS(verdict=PASS) subkimi=off subgemini=off subgrok=PASS(verdict=PASS)
r2 (撤销) panel-opendesign-composer-model-picker-review-r2-20260915-200240(subject head 51d2b35)
submimo=未收尾(无 state:被砍或仍在跑) subdeepseek=off subglm=SKIP(rotation) subkimi=未收尾(无 state:被砍或仍在跑) subgemini=off subgrok=off
r2b panel-opendesign-composer-model-picker-review-r2b-20260915-200422(subject head 51d2b35)
submimo=off subdeepseek=off subglm=FAIL(rc=1,降级:回落聊天腿也没成) subkimi=PASS(verdict=PASS) subgemini=off subgrok=PASS(verdict=NEEDS_MORE_INFO)
r3  panel-opendesign-composer-model-picker-review-r3-20260915-202423(subject head 6953cd3)
submimo=PASS(verdict=PASS) subdeepseek=PASS(verdict=PASS) subglm=PASS(verdict=PASS) subkimi=off subgemini=off subgrok=off
```

- 为什么要四次:r1 三腿 PASS 之后,为修 t41 与收 r1 发现改了仓库 ⇒ 交付绑定作废、必须重审。
  r2b 让腿重审全部(5 题全量 + 1 题增量),GLM 底座腿到步数上限无结论(回落聊天腿也没成)、Grok 到步数上限判 NEEDS_MORE_INFO,只有 Kimi 审完。
  r3 把问法收窄到 07afda8 之后的增量 —— **问法收窄,不是标准放宽**:全量内容的实审证据在 r1(DeepSeek 171 轮实跑往返 + GLM),r2b Kimi 又独立全量审过一遍;增量证据在 r3。
- findings(逐条对代码 / 源码核过;自审正本 r1 / r3 两份在 `/root/aiwork/tasks/` 仓外):
  - r1 DeepSeek【低】`tests/e2e/helpers.mjs` 注释「重连中按钮照样在」理由错 —— **成立,已改**(`51d2b35`;核 ChatPage 渲染闸 `view.kind === "connected"`)。
  - r1 DeepSeek【低】「下一句生效」依赖网关构造时传 loader + signature —— **成立,已写进 design**(核 venv `cli/commands.py:844-854`、出货 `ds_shell.py:323`)。
  - r2b Kimi【中】聊天里打过 `/model X` 之后,按钮选配置里已有的默认不生效(粘性会话预设)—— **机制成立**(核 loop.py:441-456、474-479);
    需有人打过 `/model`,选别的再选回来或重启网关即恢复;旧头部同样读配置,非回归 ⇒ 对业主定低,**design「⚠️ 例外」记账不修**
    (ds 这侧没有合法手段清网关内存态)。附带:出货模板第 29 行注释仍在教 `/model`、说「不需前端按钮」,已过时;模板一动会触发 /UPDATE 不跑 provisioning 那笔账,本单不碰。
  - r1 DeepSeek【低】apiBase 带尾斜杠 ⇒ 绿点 + 菜单只剩「换厂商」(r2b Kimi 疑问同)—— 成立,安全降级不误写,记账。
  - r1 DeepSeek【低】lm5 断言的 preset `apiBase` 是 nanobot 忽略的字段 —— 成立(判据账);端点保证靠 lm2 整份逐值比对。
  - r2b Kimi【低】select_model 不校正同名 preset 的 apiBase ⇒ 发错地址 —— **驳回**:nanobot `ModelPresetConfig`(config/schema.py:96-105)没有 api_base 字段,端点只来自 `providers.custom.apiBase`。
  - 判据缺口(r1 DeepSeek 疑问 a、r2b Kimi):三实例 `ds-model-changed` 同步、菜单 esc/外点关闭、lm3 问不到 loop 内存态 —— 成立,记账(代码两腿静态读过)。
  - r1 GLM【低】key 卡换厂商不广播 —— 成立但窄:自动重启成功时视图 connected→reconnecting→connected 触发 `loadModels()` 重拉;只有自动重启不可用时字旧到下次打开菜单。记账。
  - r1 GLM【低】畸形 `agents`/`model_presets` 非 dict ⇒ 500 而非 400;lm6 放行 409 略松;补建 preset 缺 maxTokens(与既有 save() 同形)—— 成立,记账。
  - r1 DeepSeek 疑问 b/c(`/model` 覆盖后按钮不一致、error 视图只剩「重试」)—— 旧界面同样,非回归,记账。
  - 我自审的 GET/POST 乱序(r1 GLM 疑问同)、`_atomic_write` 无 Windows 重试、写口间无锁 —— 记账。
  - r2b Grok NEEDS_MORE_INFO 的三条「HIGH」—— **驳回**:全是"没来得及用工具验证"的问题复述,不是发现(例:"残留 DeepSeek preset 仍列在 MiMo 菜单" 被 lm5 与 r1 DeepSeek 实跑否定)。
  - r3 DeepSeek【低】红检 n13 / n14 变异体逐字节相同,「咬住 15」实为 14 个不同变异体、t41a 没有被独立咬过 —— **成立**;数字已在这里更正,in-app-update 那单 tasks.md 的「15 咬 0 漏」与脚本改法在那单里收(改那边的文件会动本单交付绑定,本单归档后做)。
  - r3 DeepSeek + GLM【低】`tests/e2e/helpers.mjs` 注释「草稿为空」应为「草稿为空**且没有附件**」—— **成立**,记账(同上理由,下一次动 helpers 时改)。
  - r3 DeepSeek【说明】t41 成因写成「写 socket 让出 GIL」偏窄:多核上回包可读而 release 未被调度本身就够 —— 接受,修法对两种情形都成立。
  - r3 DeepSeek【说明】t41 重构顺带修掉改前一个边角:shell / started 两支若写回包时 socket 断,改前 keep 停在 False ⇒ 接力脚本在跑却放锁;现在 keep 先绑定、写回包在锁外 —— 核 `git show d3148fb` 属实。
  - r3 MiMo【低】异常路径「理论上可能写出 null 回包」—— **驳回**:异常穿过 try/finally 直接上抛,`self._json(200, reply)` 不可达;DeepSeek、GLM 两腿各自在副本里让 `check_cached` 抛异常实跑坐实(RemoteDisconnected、锁已放)。
  - r3 三腿:t41 五条出路回包与锁去留逐条对 07afda8 一致;DeepSeek 手打 n11~n14、GLM 手打 n11~n13 全部红在靶子上。
- 反锚定:每轮派发都报 anchor leak(`tracks/opendesign-composer-model-picker/verify.md` 与已归档的另一单 verify)。本单 verify.md 派发时是**未填的模板**,仲裁一句都没在树上;另一单那份与本单无关。
- arbitrated verdict (主裁): **PASS**。模型按钮全量内容由 r1 DeepSeek(171 轮、实跑 MiMo↔DeepSeek 往返)+ GLM 实审,r2b Kimi 独立全量再审一遍,均 PASS;07afda8 之后的 5 个提交由 r3 GLM-5.3 + DeepSeek + MiMo 三家实审 PASS(subject 6953cd3;其后只有 r3 观测这一个收口件提交)。成立的中/低发现要么已修(两条注释级)、要么记账并写明理由(`/model` 粘性会话预设等),没有阻断项。总跑判据全绿;唯一的红是泄漏闸,已核为本单之前就出现过的 e2e 卫生问题(Chromium 非正常退出留 1 个目录),不放宽闸、单独跟进。**真机仍欠**:「换了下一句真的用新模型」只有带 key 的真网关答得了。

## Accepted deviations

- 真机才答得了的:「换了之后下一句真的用新模型」—— 真机清单:换到 pro 后问一句「你是哪个模型」,对网关日志。
- bump 版本号 / 发版:问业主(0.98.4 已发;档案原子写那单同样待定,可一版一起发)。
- 上面「记账」的各条不在本单修。
