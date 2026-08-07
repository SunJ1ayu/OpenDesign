# Verify: dead-assertion-gate

- Date: 2026-08-07
- Verdict: PASS(代码面;这一单没有真机面 —— 它不改产品行为)

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [x] build passes
- [x] tests pass
- [x] no secrets / unsafe ops

**粘机器输出,不是我打字**(08-06 的教训:两次把"发出命令"当成"事情发生了"):

① 总跑 `tests/run-all.sh`(解释器 = venv,不是系统 python3):

```
  PASS  node 单测(tests/*.mjs)           342 通过 / 0 跳过 / 0 todo
  PASS  python 全量 + 死断言闸(/root/.venvs/design-studio/bin/python) 888 跑过 / 0 跳过
  PASS  MCP 契约闸                      三条闸全绿
  PASS  dist 新鲜度(重新 build 后 git 应无差异) 与源码同步
  PASS  e2e 总跑                         32 PASS / 0 FAIL / 2 SKIP

没有红的,但有 2 条没跑 —— 不算通过。
```

exit 3 = 那两条要活 gateway 的 e2e,是默认状态,不是本单引入的。
**build 那一段就是 `dist 新鲜度`**(重新 `npm run build` 后 git 对 web/dist 无话可说)。

② 本单 oracle `python3 -m unittest tests.test_dead_assertions -v`:

```
Ran 9 tests in 0.660s

OK
```

③ 这道闸在**真仓库**上的报告(用系统 python3 跑,好让 skip 那条路径真被走到 ——
venv 里 mcp 装齐了,888/0 跳过,⏭️ 分支一次都没执行):

```
Ran 888 tests in 267.692s
OK (skipped=14)
=== 死断言检查(断言在那儿、却从没被执行过)===
  扫了 37 个判据文件、2200 条断言;放行清单 2 条
  ⏭️ 35 条断言在**被跳过的判据**里 —— 这台机器上没条件问,不算死断言
  ✅ 没有从没跑过的断言。
EXIT=0
```

2200 条真断言、0 误报 —— 这是"它会不会变成噪音发生器"的实测答案。

## Review

- lane: fast
  > 它**不改任何产品行为**,只新增一个只读的检查器 + 一段总跑。
  > 但它动的是判卷防线本身,所以不走 self:主 + 1 条腿。
  > **碰了新写口 / 权限 / auth / 钱 / 数据一致性 → full,针孔再薄也不打折**(硬规矩,别在这降档)。
  > fast = 主+1,中等风险;self = 主自审(闸③ + 截图 + 全量回归),
  > 限纯前端/纯观感、后端一字未动、只新增已过审针孔的调用方。
- 派给: 主 agent 直接干 —— "判据没被执行"这件事的定义本身就是我要立的规格,
  外包等于让别人替我定义什么叫"问出口了"。
  ⇒ **三道闸里的闸① 不适用**(没有执行腿、没有 worktree);闸②③照走,见上/见下。
- 规格自查(读任何 panel 输出之前先答):
  规格 = **"断言被问出口" ≙ "断言所在的那一行被执行过"**。它会错成这样:
  行粒度接不住"一行里既有守卫又有断言",以及"整个方法被 skip"——
  前者是**假绿**(闸对它瞎了还说干净),后者是**假红**(把没条件问说成没问)。
  我怎么发现:光靠夹具发现不了(夹具的形状都是我造的),
  只能靠 ①在真仓库上跑一遍看误报 ②别人来攻题。
  **两条都做了,而两个洞都是第二条抓出来的** —— 见 F1/F2。
- 腿的花名册:

```
# panel-review 花名册(2026-08-07 09:45:16)task=dead-assertion-gate
# PASS = 进程 rc=0,**不等于给了裁决**;off = 这条腿压根没派(不许读成通过)。
# 日志:/root/aiwork/logs/panel-dead-assert.*.log
submimo=PASS subdeepseek=PASS subglm=off subkimi=off
```

  > lane=fast 要的是"主 + 1 条腿",实到 2 条。subglm 是智谱没充值(全局关着,不是本单降级)。
  > 派发时引擎报了 anchor leak(verify.md 未跟踪 ⇒ 可能进腿的 prompt):
  > 当时 verify.md **通篇是模板占位符**,没有我的任何结论,所以这次泄漏无内容可锚定。

- findings:
  - **F1(DeepSeek,HIGH,成立,已修 `d407160`)—— 跳过被算成了死断言。**
    没起 gateway 的机器上 `test_ws_protocol_smoke.py` 整类被 skip,18 条断言全不执行,
    这道闸会报 ~16 条"死断言"并让总跑 py-full 段**从 exit 3 变成 exit 1**。
    它当场把行号点全了。这是我 08-06 立的规矩("SKIP 不是 PASS,但它是 exit 3")
    被我自己新写的闸推翻 —— 我没看见。
    修法:闸自己认 skip(`skipped_method_ranges`),归 ⏭️ 一档,印出来但不算红。
  - **F2(DeepSeek,HIGH,成立,已修 `d407160`)—— 同一个事故写成一行就躲过整道闸。**
    `if got: self.assertIn(...)`:LINE 事件在这一行的第一条字节码就触发,
    这一行"执行过"了,断言一次没跑。**08-06 那个事故换个换行位置就免疫**。
    修法:一行上起了 >1 条语句且其中有断言 ⇒ 当场报"这道闸对它是瞎的",逼它拆行;
    `with self.assertRaises(...)` 不在此列(本仓库现有 7 处,一条都不许误报)。
  - **F3(我自己,收口时发现)—— 报告里"放行清单 N 条"会撒谎。**
    `load_allow()` 原来对 `ROOT` 和 `HERE` 两个基准都登记,同一条例外记两遍:
    清单 2 条印成 4 条。一个会撒谎的机器输出,恰恰长在"别信自述、信机器打印的"
    这道闸身上。已改成只登记真实存在的那一个。
  - **F4(MiMo,LOW,接受)—— `run-all.sh` 解析依赖中文文案。**
    `_dead` 靠 grep "条断言一次都没执行过";文案一改,汇总行就不显示死断言数。
    不修,理由见 Accepted deviations。
  - **F5(DeepSeek,LOW-MED,接受)—— `except` 豁免是结构性后门。**
    把死断言包进 `try/except` 就照不到。接受,理由在 design 的 trade-off:
    不豁免则误报,而误报的闸活不过一周。
  - **F6/F7(DeepSeek,LOW,接受)—— `top_level_dir` 回退的非确定性、
    扫描用 `test_*` 而 unittest discover 用 `test*`。** 当前仓库无此形状的文件,
    是潜在错配不是现存缺陷。
  - **F8(MiMo,建议,已落地)—— 判据没问 skip 相关场景。** 成立:F1/F2 的根都在这儿。
    已补 4 条判据(`46f39e0`,**修复前 2 处红**),其中一条是防新后门的:
    `test_skip_does_not_hide_a_real_dead_assertion` —— 同一份判据里既有 skip 又有真死断言,
    真死的那条照样要红,否则"整份 skip 掉"就是关闸的万能钥匙。
  - **闸③(我亲读 diff):** `git log 954c823..HEAD --stat` 里**无 `create mode 120000`**
    (符号链接);`git status --porcelain -- tests/` 空(无未跟踪文件塞进判卷目录);
    改动全在 `tests/` 和 `tracks/`,产品代码一字未动。
- arbitrated verdict (主裁): **PASS**。
  两条 HIGH 都成立、都已修,且**都是先补判据红检、再修**(`46f39e0` → `d407160`),
  git 历史里证明得了"红过"。剩下 4 条低危按 Accepted deviations 记账。
  **最值钱的一条**:两条 HIGH 全来自评审腿,而我自审时给自己打的分是"机制扎实"——
  我在这一单里同时是出题人和答题人,**规格错的地方我自己一处也没找到**。

## Accepted deviations

- **`run-all.sh` 的死断言计数靠中文文案 grep(F4)**:文案改了汇总行就少印一个数字。
  不修的理由:那一段**红不红不取决于它**(rc 直接来自 `dead_assertions.py` 的退出码,
  FAIL 标记和日志路径照常印),它只影响汇总行的措辞。影响范围 = 一行提示文字。
- **`except` 豁免(F5)与 skip 豁免**:两条都是"想关这道闸的人有办法关"。
  接受的前提是**关它的动作是看得见的**:skip 数进总跑的 `n_skip` → exit 3;
  `except` 包裹会出现在闸③亲读的 diff 里。无痕的关法目前没有。
- **放行清单按行号锚定(F4-DeepSeek)**:编辑后条目失效方向是"重新报红",安全的一侧。
  内容锚(存断言源码片段)更稳,但当前清单只有 2 条,不值得。留作以后条目变多再说。
