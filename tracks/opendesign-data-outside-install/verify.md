# Verify: opendesign-data-outside-install

- Date: 2026-08-15
- Verdict: **代码面 PASS**(四审三腿 + 主裁,2026-08-15);**欠业主真机装一趟才算完**

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [ ] build passes
- [ ] tests pass
- [ ] no secrets / unsafe ops

**机器打印的**(不是我的转述)—— 判据用 `runlog` 跑,把它打印的收据行原样粘进来:

```
runlog -t opendesign-data-outside-install -- <判据命令>
```

```
<粘收据行,逐字节,别改数。**每次提交**都会跟 evidence/ 里的收据逐字节比对(5a);
 **归档时**还要求:最后跑的那一遍必须在这儿、跑红的那几遍一份都不许藏(5b)、
 收据得进 git(5d)。一份收据都没有的话,写一行
 「- 无机器证据:<理由>」认账 —— 沉默不算理由(5c)。>
```

## Review

- lane: **full**。命中两条硬规矩:**数据一致性**(业主的图库/档案换落点,搬错=他的东西
  在卸载时消失)+ **新写面语义**(所有写口的落点变了)。不降档。
  > **碰了新写口 / 权限 / auth / 钱 / 数据一致性 → full,针孔再薄也不打折**(硬规矩,别在这降档)。
  > fast = 主+1,中等风险;self = 主自审(闸③ + 截图 + 全量回归),
  > 限纯前端/纯观感、后端一字未动、只新增已过审针孔的调用方。
- 派给: **codex 腿 `-m gpt-5.6-sol`**(实现),oracle 与仲裁留在主 agent。
  **逐档问了一遍**(上一单 S1c 我在这一格写着"到那一步再判"然后直接自己开写、
  没留任何判断记录 —— 那笔账记在 opendesign-windows-installer/verify.md 里,这次不重犯):
  - **主 agent 直接干**:活的大头是 ~25 个调用点按"数据 / 代码"逐个分类改写 ——
    有真实工作量、纯文本、边界清楚,正是抽屉里写的"PR 级实现"形状。**派它省下的是我的额度,
    而这单最贵的东西(oracle 与仲裁)本来就外包不出去。** ⇒ 不自己干。
  - **submimo fix(微档)**:限 1-3 文件的窄口,这单跨 7 个文件。⇒ 不合档。
  - **Sonnet 腿(worktree)**:后备档,没有非用不可的理由(这单不需要开端口的考卷,
    见下)。⇒ 不用。
  - **codex `gpt-5.5` 还是 `gpt-5.6-sol`**:跨模块 + 判的是"哪些东西算业主的数据"这种
    语义边界,不是照着规格填空 ⇒ **升 5.6-sol**。
  - **判卷要不要起服务**:不要。不变量闸跑的是工具层写口(建项目/加参考图/set_workspace/
    整理计划),不起 gateway、不开端口 ⇒ **腿自己跑得了这份考卷**,不必主 agent 当测试机。
    (全量回归里那 36 条 e2e 要端口,但那是闸②我亲跑的事,不进任务书。)
- 规格自查(读任何 panel 输出之前先答):
  本单的规格是「**安装目录在运行时是只读的**」。它可能错在哪:
  - **错法一(最像真的):我把"数据"这个集合圈错了。** 圈的依据是机械实扫
    (`join(ds_root,…)` 47 处全是数据)+ 读口补扫,但**只读的用户数据不出现在任何写口里**
    —— refs/ 里的真图片就是靠规划双出 B 卷点出来的,不是我扫出来的。**再漏一类,它就
    静静躺在会被删的地方。** 发现方式:g3/g4 的 canary(没认识的东西必须被报出来且不被淹)。
  - **错法二:落点选错(不是代码错)。** B 卷第 6 问答得比我狠 —— 业主可能觉得档案是
    **他的文档**,该看得见、能备份、能同步,那正确落点就不是 LocalAppData。
    触发条件已写死在 design 里:他一提"我想自己看/同步这些档案",落点就改。
  - **错法三:Linux 上全绿 ≠ Windows 上删的是那些东西。** `RMDir /r` 到底删了什么
    只有真机能答 ⇒ 真机清单里那条"建个项目 → 卸载 → 档案还在不在"是这一单的**唯一**终审。
- 规格自查(原模板问法保留):<如果规格本身就是错的,会错成什么样、我怎么发现?
  panel 只验"实现合不合规格",验不了"规格对不对" —— 四腿齐 PASS 不等于题是对的。>
- 腿的花名册:
  ```
  submimo=PASS subdeepseek=PASS subglm=off subkimi=PASS
  ```
  **subglm 连续第五轮 off(智谱欠费)⇒ 本单的 full 实际只有 3 条腿。off 不许读成通过。**
- 腿的花名册(模板原句): <把 `<日志前缀>.roster` 里那一行**原样粘过来**,别手写>
  > panel-review 收尾自己写这个文件(off / FAIL(rc) / 降级 都在里面)。
  > 08-06 立这条的理由:08-05 我在这里手写了"三条腿一致 PASS",而 Kimi 根本没出结论
  > (同一页第 90 行我自己还写着它没出报告)—— 手抄一份终端上的东西,抄错那次没人会发现。
- findings(主 agent 自审,**落盘于跑 panel 之前**):
  - 🔴 **F1(已修,`6a19c7d`)迁移只挂在 ds-web 上,而外壳里网关先起。**
    装了旧数据的机器上,网关和三个 MCP 会先读到一个空数据根;业主那一刻问"我有哪些项目",
    助手回"一个都没有",甚至可能在新根里建一个重名的。
    **附带一笔更值钱的**:我第一版的修法是**假的** —— 外壳只给子进程设 env、自己那个
    进程里没有 ⇒ `data_root()` 返回 ds_root、目标==来源、迁移空转。
    **h3 那种静态接线判据完全看不见**(调用在、位置也对、全绿,而什么都没搬)。
    判据 d3 问真行为才钉住。⇒ **"接线测试"证明不了"接上了"。**
  - **F2(接受,写清理由)两处"安装目录"的算法不一样**:`_deletable_roots()` 认标志
    (OpenDesign.exe / python\pythonw.exe),`_workspace_location_error()` 直接把上一级
    当安装目录。看起来是漂移,但**方向是对的**:数据根算宽了会 fail closed 把业主挡在门外
    (08-15 实测把两条真联跑打红过),而工作区算宽了只是让他"换个文件夹" ——
    **两边的错误代价不对称,所以规则也不该一样**。已在代码里互相指注释。
  - **F3(记账)`data_root()` 每次调用都 realpath + makedirs**,一个请求里几十次。
    功能上无害(exist_ok),但属于"每次都做一遍本可以只做一次的事";
    真要出问题是在慢盘/网络盘上。不在本单改(改它要动缓存失效语义)。
  - **F4(记账)迁移的 `skipped`(同名不覆盖)没有出口** —— `failed` 会让启动停下来并
    念给业主听,而 `skipped` 只进返回值。真发生同名冲突时业主不会知道有一份没搬过去。
    ⇒ 记 backlog:同名冲突要和 unknown 一样有一条能被人看见的出口。
  > 只写发现。腿的身份/降级不在这儿抄第二遍:日志自带身份牌(降级横幅 + 视野边界),
  > 花名册在上一格,查工件不查自述。
- panel findings 与处置(逐条):
  - 🔴 **subdeepseek [HIGH/BLOCK]:装出来之后项目列表恒空。**
    `ds_web._projects` 里 `root = self.server.ds_root` 是 **Attribute 别名**,
    我的 AST 静态闸只认 `Name` ⇒ 看不见。数据没丢,但业主看到的是"我的项目没了" ——
    **正是本单要消灭的那个症状**。已修(判据 d9e63cd 先行,实现 55e242b)。
  - 🔴 **subkimi [BLOCKER]:三个 MCP 子进程拿不到 `DS_DATA_ROOT`。**
    它们不是外壳起的,是网关按配置 `env` 块起的,那几块只列 `DS_ROOT`;MCP SDK 的
    stdio 客户端只继承一份白名单。⇒ **聊天侧 47 处改动全部等于没改**:助手建的档案
    仍落在会被卸载删掉的树里,而工作台读数据根 —— 两个世界,重启时迁移再把它搬走。
    已修(patch_config 给三个 MCP 注入绝对路径的数据根)。
    🔴 **这一条我自己的 design 里就写着该问**("三个 MCP 与 ds-web 四份 env 都要问到"),
    D 组只问了 child_env 一份 —— **我把它写进了规格,却没写进判据。**
  - **subdeepseek [MEDIUM] 跨卷装机砖机**:`os.rename` 抛 EXDEV ⇒ failed ⇒ 外壳和
    ds-web 都拒绝启动 ⇒ 装在别的盘的机器升级后**永久打不开**(数据安全,人被锁在门外)。
    已修:退化成"拷过去、确认在、再删原件"。判据 g5 用 monkeypatch 造出 EXDEV 咬住。
  - **两腿同时点名:迁移报告没有出口**(`unknown`/`skipped` 只进返回值,生产路径只查
    `failed`)⇒ canary 那张网**没接电**。已修:搬完在数据根写一份 `迁移记录.txt`。
    design 3b 自己写着这一行,之前没实现 —— **写进设计不等于做了**,同上一条一个病。
  - **subdeepseek [MEDIUM] 标志漏判则防线静默失效** / **装进 `%LOCALAPPDATA%\OpenDesign`
    会被自己判危险且无出路**:两条都成立,**接受并记账**(见 Accepted deviations)。
- **机器打印的收据行**(逐字节粘的):

  ```
  runlog: redcheck-15 rc=0 commit=55e242b dirty=yes at=2026-08-15T11:39:43Z file=tracks/opendesign-data-outside-install/evidence/20260815T113943Z-01-redcheck-15.txt
  runlog: regression-final rc=1 commit=55e242b dirty=yes at=2026-08-15T11:39:51Z file=tracks/opendesign-data-outside-install/evidence/20260815T113951Z-01-regression-final.txt
  ```

  内容:判据 35/35;红检 **15 条定点变异 15 咬住 0 漏网**(跨 6 个实现文件),
  跑前跑后比 `~/.nanobot/config.json` 哈希:真家零改动。
  总跑四段里三段全绿(node 350 / python 1171 **0 跳过 0 死断言** / MCP 三闸 / dist 新鲜度),
  **e2e 35 PASS 1 FAIL** —— 那一条(`project-thread`)**不是本单造成的**:
  拿基线代码 `d10535f` 配真数据跑同一对,红得一模一样(一天复现 4 次,只有单跑才绿)。
  已记 `docs/backlog.md`,写清了下一个人该查哪两处。
- arbitrated verdict (主裁,代码面): **PASS**。
  三腿全部给出 BLOCK,**两条 BLOCK 都是真的、都已修、都先补了判据再动实现**;
  其余四条两修两记账。判据从 20 条长到 35 条,期间**三轮攻题**
  (我自攻 5 条 → 攻题腿 9 条 → 四审 6 条)总共把 20 条"全绿但业主照样丢东西"的路线补掉。
  **但代码面 PASS 离交付还差一趟真机** —— Windows 上 `RMDir /r` 到底删了什么、
  迁移在真盘上搬得动搬不动,只有业主装那一趟能答。**在他答之前本 track 不归档。**
  > **归档时这一条和顶部的 `Verdict:` 都不许还是占位符**,`track-guard` 规矩3 会挡;
  > 没归档但已经合并上线的,`track list` 会打 ⚠️(stage-timer 就这么漏了两个月)。

## Accepted deviations

- **标志漏判则防线静默失效**(subdeepseek):`_INSTALL_MARKERS` 是两个硬编码文件名
  (`OpenDesign.exe` / `python\pythonw.exe`)。布局漂移 + 手工设 env 时,`$INSTDIR\Data`
  会被放行、卸载静默删光。**接受**:当前被成品闸(build-installer.sh 查这两件必须在)
  与外壳写死的 `%LOCALAPPDATA%` 两头夹住;真要根治得让安装器写一个显式哨兵文件,
  那是安装器那一单的事。
- **装进 `%LOCALAPPDATA%\OpenDesign` 会被自己判成危险且没有出路**(subdeepseek):
  真发生时业主看到"数据目录不可用…请重新运行安装程序",而重装解不开。**接受**:
  安装器默认路径是 `%LOCALAPPDATA%\Programs\OpenDesign`,要撞上得业主手工改到那个
  特定目录;而 fail closed 的方向是对的(那里确实会被删)。已记 backlog。
- **`data_root()` 每次调用都 realpath + makedirs**(F3):一个请求几十次。功能无害,
  慢盘/网络盘上才可能显形。不在本单改(要动缓存失效语义)。
- **迁移的 `skipped` 只写进 `迁移记录.txt`,不打断启动**(F4 的收口):同名冲突时
  旧的那份留在原处、业主能在记录里看到,但没有主动弹窗。**接受** —— 打断启动的
  代价比这个大。
- **subglm 连续第五轮 off(智谱欠费)** ⇒ 本单 full 实际 3 腿。不当作通过。
