# Verify: opendesign-intake-simplify

- Date: 2026-07-25
- Verdict: **PASS**(ds-web 0.44.0;#4 标记 **UNTESTED on target**,待用户真机确认)

## Mechanical checks(全部主 agent 亲跑)

- [x] build passes:`npm run build` 绿
- [x] tests pass:`pytest tests/` 596 passed / 8 skipped(含新增 `test_ds_web_open_front.py` 19 例)、
      `node --test tests/*.mjs` 200/200、真 chromium e2e **16/16**(含新增 `intake_simplify.e2e.mjs`)
- [x] no secrets / unsafe ops:`_open_folder` 的九道闸逐条仍在(CT/体积/JSON/key 白名单+
      `_ws_proj`/rel·sub 互斥/`relpath_ok`/realpath+`within`/`isfile`/`_OPEN_EXTS`),
      置顶逻辑加在**闸后**的启动器内部;`DS_OPEN_CMD` 与非 Windows 分支一字未动
- [x] **亲自截图看**:建档表单只剩一个输入框、只填项目名建成后工作区正常;
      空业主在界面上零可见影响(核过:`owner` 字段前端根本没有消费者)

## Review

- lane: **full**(写路径 + PKB schema 触边)。实到 **3 条腿**:submimo(PASS,零 findings)、
  subkimi(PASS + 2 Low)、subdeepseek(chat 腿补跑,NEEDS_MORE_INFO + 1 HIGH/1 MEDIUM/2 LOW)。
  **subglm 缺席**:智谱账号触发 `SetLimitExceeded`(Safe Experience Mode 推理限额),
  非本单问题;subdeepseek 的 agent 腿也死了(默认模型名 `deepseek-chat` 已被端点下架,
  现在只认 `deepseek-v4-pro`/`deepseek-v4-flash`),我用正确模型名补跑了 chat 腿。
  两条工具链债已记 → 见文末。
- 规格自查(先于任何 employee 输出写下,全文
  `/root/aiwork/tasks/opendesign-intake-simplify-my-review.md`):
  1. **#4 的 oracle 证明不了真机效果** —— 断的全是"我的假 user32 被正确调用了";
     前台权规则/杀软/Explorer 复用窗口三种失败都在断言之外。
  2. **空业主是不是用户要的**:他说"去掉这个框";我译成"业主可空 + 空则不写链接"。
     若他其实想要"业主名自动等于文件夹名",这次就做错了 —— 但那是往 PKB 写假数据,不取。
  3. **放宽必填会不会让聊天大脑变懒**(编个业主名):docstring 已显式堵,只有真实对话能验。

### findings

主审(读 employee 输出前,实现过程中自查 + oracle 抓到):

1. **[已修] `_pick_folder_window` 在 Linux 上拆不开 Windows 路径**(原用 `os.path.basename`)
   → 判据恒不命中。**oracle 先红检救回的一条**:真机 `ntpath` 认反斜杠,反而看不出来。
2. **[已修] 子串匹配会认错窗口**(文件夹叫「图」→「施工图」「图片」全命中)→ 改边界对齐,
   补判据 p05b(先红检证明真会误伤)。
3. **[已修] 开单个文件也去追资源管理器窗口**(同一启动器还服务 rel 分支)→ 只对目录置顶,
   补判据 o01b。
4. **[已修] 注释事实不实**:写了"ds_web 是单线程 HTTP",实际是 `ThreadingHTTPServer`;
   理由改成真的那条(同步等 2 秒会把这次响应拖 2 秒)。
5. **[核过·无事] 下游读侧**:全仓 `grep 业主 bin/*.py` 只命中 `ds_tools`/`ds_web`(cockpit
   速览)/`ds_lint`;`ds_todo`/`ds_intake`/`ds_organize`/`ds_workspace`/`ds_model` 零引用。
6. **[已知·非本单引入] `[[{client}]]` 的 `]]` 提前闭合**:既有行为,`sanitize_field` 已挡
   伪造账本行(test_c09),本单不扩范围。

employee findings 逐条仲裁(每条给依据):

- **subkimi Low ①「docstring 承诺了不存在的补录路径」→ 接受,已修。**
  核过 `_upsert_header_field` 的调用方只有 `update_client`(业主档案字段)与 `set_stage`
  (阶段),`CLIENT_FIELDS` 也不含项目侧字段 ⇒ **项目档案头上那行 `- 业主:` 确实没有任何
  工具能改**。我原先写的"之后 update_client 随时补"是假承诺 —— 这条直接打在我
  **放宽必填的正当性理由**上,是本轮最有价值的发现。已把 `create_project` docstring 与
  MCP 工具 docstring 改成实话:业主信息可记在 clients/ 那侧,但项目档案那行补不了。
- **subkimi Low ②「workspace/AGENTS.md 工具表没同步」→ 接受,已修。**
  核过 `AGENTS.md:16` 仍写 `create_project(project, client, …)`,聊天大脑读它会继续追问
  业主名,与新 docstring 打架。已改成 `client?` 并写清留空的代价。
- **subdeepseek HIGH「下游读侧可能炸,文件没给所以不能保证」→ 拒收(盲评产物)。**
  它是 chat 腿,只看得到 diff,自己也写了 "Important context not available"。
  依据:仓内 `grep -rl 业主 bin/*.py` 只有三个文件(见主审 finding 5),subkimi(agent 腿,
  能自己读仓库)独立核了同一组读侧并明确"未发现漏掉的炸点"。**风险不成立,不是"未验证"。**
- **subdeepseek MEDIUM「同名不同盘会认错窗口」→ 接受,已修。**
  实测确凿:标题是完整路径 `E:\work` 时,原判据(以 `\work` 结尾)会把它当成 `D:\work`。
  改成:标题**整条等于目标路径**(分隔符/尾分隔符/大小写归一后)才算强命中;标题只有裸
  文件夹名时仍认(信息不足,且代价只是"提错一扇窗",不写不删)。补判据 p05c,先红检。
- **subdeepseek LOW「狂点会堆线程」→ 接受但不动作。**
  线程 daemon、封顶 20×0.1s=2s、无共享状态;subkimi 独立核为"非泄漏"。为一个尽力而为的
  体验项加线程池/去抖属过度工程,记为接受偏差。
- **subdeepseek LOW「吞 Exception 的粒度」→ 无需动作**,它自己也判定当前处理恰当
  (`KeyboardInterrupt` 属 `BaseException` 不被吞,核过属实)。
- **submimo:PASS 零 findings**,附一份 `_open_folder` 九道闸的逐条审计(与我的自查一致)。
  它没提 subkimi 那两条 docstring/文档失真 —— 沉默不是清白,以主审+subkimi 为准。

### arbitrated verdict(主裁)

**PASS**。三条腿无人对"空业主写空字段行、不写 `[[]]`"这个核心决定提出异议;
两条真 finding(docstring 假承诺、同名不同盘认错窗口)已修并各自补了先红检的判据。
**但 #4 的完成状态是"已实现 + 待真机确认",不是"做好了"** —— 见下。

## UNTESTED on target(deployment-target 铁律)

- **#4 置顶效果只能在 Windows 真机确认**。开发机是 Linux,连 `ctypes.WINFUNCTYPE` 都不存在,
  19 个判据证明的是**决策逻辑与失败姿态**(选对窗口/等窗口出现/失败不炸/不阻塞),
  不是"窗口真的到前面来了"。真机三种可能失败:①Windows 前台权规则拒绝后台进程抢焦点
  (最可能,表现为任务栏闪);②杀软拦截;③Explorer 复用已有窗口。
- 真机若仍不置顶:退路是前端点完给一句"已在任务栏打开",而不是更暴力的抢焦点脏招。
- #3 无此问题(纯核心 + 前端,已在真 chromium e2e 与截图验过)。

## Accepted deviations

- 空业主 = 项目档案里那行留空,不写占位文案、不自动补名(不往 PKB 写假数据);
  **且目前没有工具能事后补那一行** —— 已在两处 docstring + AGENTS.md 写实,
  并列入 follow-up(补一个对称的项目字段写口,新写口按规矩单独走四审)。
- 置顶不去重/不加线程池(狂点会临时多几条 2 秒即死的 daemon 线程)。
- 标题只有裸文件夹名时,同名不同盘无法区分(信息不足,代价仅"提错一扇窗")。
- 本单 full lane 实到 3 腿(subglm 因智谱账号限额缺席),已具名记录。

## 工具链债(本单暴露,记给下一轮)

1. **subdeepseek 默认模型名过时**:`deepseek-chat` 被端点拒(`The supported API model names
   are deepseek-v4-pro or deepseek-v4-flash`)。chat 腿默认值与 AGENTS.md 说明都要改;
   agent 腿(`subdeepseek-agent`)同样 rc=1,需一并复查。
2. **subglm 账号触发 `SetLimitExceeded`**(Safe Experience Mode 推理限额),需用户在智谱
   控制台调整才能恢复这条腿。
