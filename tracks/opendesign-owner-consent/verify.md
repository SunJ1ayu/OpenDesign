# Verify: opendesign-owner-consent

- Date: 2026-08-08(开工)/ 2026-08-10(实现与收口)/ 2026-08-11(四审与修复)
- Verdict: **PASS**(主裁;ds-web 0.82.0。**欠两台 Windows 真机验收** —— 见 T7)

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [x] build passes(`npm run build` 干净;总跑第③遍「dist 新鲜度」段绿)
- [x] tests pass(node 342 · python 981 · MCP 契约闸三条全绿 · e2e 34 PASS/0 FAIL)
- [x] no secrets / unsafe ops(未碰密钥/生产系统/依赖安装;全部改动在本地历史,未 push)

**机器打印的**(不是我的转述)—— 判据用 `runlog` 跑,收据行原样粘在这里:

```
runlog -t opendesign-owner-consent --repo . -- tests/run-all.sh
```

**跑了三遍,红的一遍都不藏**(规矩 5b):

**第①遍 —— 红的**。三段红,其中一条是**真 bug**:`ds_consent ↔ ds_tools` 循环依赖
(`test_no_import_cycles` 抓到,我人眼审 diff 没看出来 → findings F7);
MCP 契约闸跟着它一起红;dist 那段是产物没提交:
```
runlog: run-all rc=1 commit=bca62e9 dirty=yes at=2026-08-10T15:18:48Z file=tracks/opendesign-owner-consent/evidence/20260810T151848Z-01-run-all.txt
```

**第②遍 —— 还是红的**。循环依赖已修(python 981 / MCP 闸转绿、e2e 从 33 涨到 34
= 新增的同意卡那条),但 dist 那段仍红。**原因不是产物旧**:重新 build 出来的哈希
与暂存的逐字节相同,是那道闸查的 `git status --porcelain -- web/dist` 非空 ——
我的 dist 改动只暂存了、还没 commit。"入库"要求的是进库,暂存不算:
```
runlog: run-all rc=1 commit=bca62e9 dirty=yes at=2026-08-10T15:46:23Z file=tracks/opendesign-owner-consent/evidence/20260810T154623Z-01-run-all.txt
```

**第③遍(权威的一遍,覆盖真实 HEAD、工作树干净)** —— 五段全 PASS:
```
runlog: run-all rc=3 commit=b43109c dirty=no at=2026-08-10T16:00:46Z file=tracks/opendesign-owner-consent/evidence/20260810T160046Z-01-run-all.txt
```
> `rc=3` **不是判据红了**。五段全 `PASS`;`3` 来自总跑自己的口径:
> 「没有红的,但有 2 条没跑 —— 不算通过」。那 2 条(`new_chat` / `project-thread`)
> 要起活的 nanobot gateway,`tests/run-all.sh` 默认就不跑它们,与本单改动无关。
> **照抄不四舍五入。**

**第④遍(四审的四条修完之后,权威的一遍)** —— 五段全 PASS:
```
runlog: run-all rc=3 commit=873692e dirty=no at=2026-08-11T01:31:43Z file=tracks/opendesign-owner-consent/evidence/20260811T013143Z-01-run-all.txt
```
> `rc=3` 同上:五段全 `PASS`,3 来自那 2 条要起 gateway 的 e2e 没跑(与本单无关)。

汇总数字(以第④遍为准,供人眼核对,**权威仍是收据文件本身**):
node **345** 通过 / 0 跳过 · python **990 跑过 / 0 跳过**(死断言闸:0 条从未执行)·
MCP 契约闸三条全绿 · dist 与源码同步 · e2e **34 PASS / 0 FAIL / 2 SKIP**。
> 数字比第③遍多的 9 条 = 四审之后补的判据:O9 三条 + O10 三条(python)、
> O11 三条(python)、O12 三条(node)。python 981 → 990,node 342 → 345。

oracle-first commit:`74dbda6`(判据先行,`--stat` 只有 tests/,零实现文件)。
四审之后补的判据同样先行单独入库:`726e77b`(O9)、`6969c05`(O10)、
`d51a2d9`(O11+O12),修复在 `873692e` —— **三笔判据都在修复之前,git 里查得到**。

## Review

- lane: full
  > 新写口(两个 HTTP 针孔 + 一个新落盘文件)+ **权限面**(这一单本身就是授权闸)。
  > 硬规矩,不降档。
- 派给: **判据 = 主 agent 亲写(碰权限面,铁律);T2/T3/T5 后端 = `codex -m gpt-5.5`;
  T4 前端 = 主 agent 亲做。**
  > 后端派出去的理由:design 已经把形状钉死到"照抄针孔④ 的 posture"这一级,
  > 信息量足够一份独立任务书;而**考卷要开真 HTTP 端口,codex 沙箱跑不了** ——
  > 按 delegate 抽屉的两条路选了「主 agent 当测试机」(默认那条),不是换腿。
  > 前端留给自己的理由:这一单前端的价值几乎全在**文案说不说得清影响面**,
  > 那是判据接不住、只有人眼接得住的东西(0.68 那批真机反馈就是这么栽的)。
  > **返工 0 轮;执行腿自身错误 0 处**(它交回的三处问题逐条查下来根因都在我,见 findings)。
- 规格自查(读任何 panel 输出之前先答):

  这一单的核心赌注是:**「不落盘」比「弹窗」重要**。如果这条赌错了,最可能错成
  这样 —— 我把全部力气花在"待确认期间读不到新根"上,而真实的攻击者根本不走
  `set_workspace`:他让助手用**已经批准过的根**里的某个能力去够到别处
  (软链接、`..`、或者某个我没归类到"读工作区"的工具)。**canary 闸能照到的
  只有"新根"这一个方向。**

  我怎么发现:O7b 的 canary 只放在"新根"里。要证伪这条赌注,得在**工作区外的
  第三个位置**也放一份 canary,然后跑一遍全部工具 —— 那测的是"现有读面有没有
  别的洞",不是本单引入的洞,**超出本单范围**,记在这里留给以后。

  第二条赌注:**开关放 `config/consent.json` 且"任何 MCP 工具都写不了"**。
  这条我用"枚举 33 个工具真调一遍"验了,但它验的是**今天**的工具表;
  真正承重的是 O7a 那道"新工具必须回来分类"的闸。而 O7a 我已经实测过
  **它自己会分错**(第一版我分错 6 个)—— 所以承重的其实是 canary,
  分类表只是提醒器。这层区别值得四审替我再看一眼。

- 腿的花名册(原样粘,2026-08-11 00:22):
  ```
  submimo=PASS subdeepseek=PASS subglm=off subkimi=FAIL(rc=1)
  ```
  > `PASS` = 进程 rc=0,**不等于给了裁决**。实际拿到裁决的只有两条腿:
  > **submimo 判 PASS、subdeepseek 判 BLOCK**。
  > `subglm=off` 是**智谱欠费**(不是"通过");`subkimi` rc=1 挂在额度。
  > 所以这是一次 **2/4 腿**的 full 审 —— 比规矩要求的薄,记在这里不粉饰。
  > 而这一轮最值钱的东西恰恰来自那条孤腿(见 F9),又一次印证
  > 「孤腿 BLOCK 才是信号」;要是它也欠费,高危那条就漏网了。
- findings:

  **我自己先审出来的(写在读任何 panel 输出之前)**

  - **F1 `bind_project` 批准后会用"当时的工作区状态"重新解析 folder。**
    `_apply_bind_project` 走的是完整的 `_bind_project_impl`,folder→rel 的匹配
    发生在**批准那一刻**,而不是排队那一刻。如果两者之间工作区里新增/改名了
    文件夹,业主看到的卡片和最终写进映射的东西可能不是一回事。
    影响面小(bind 只在根内指路,不扩大根),但这是"确认后掉包"的一个真实变体,
    判据 O3b 只覆盖了 `set_workspace` 那一侧。**没修,记账。**
  - **F2 canary 闸有两个明账盲区**(`CANARY_BLIND_SPOTS`):`stage_intake_tool` /
    `stage_adoption_tool` 要非空数组参数才跑得动,参数猜测器造不出来。两者都读
    workspace 根。它们是写面且受 allowed_roots 二次限制,所以我判断风险有界 ——
    但这是**判据照不到的地方**,不是"验过没问题"。
  - **F3 这道闸挡不住业主自己点同意。** 卡片文案的清楚程度 = 这道闸的强度。
    我把影响面那句话写死进了 `describe()`,并在 e2e 里断言它真的在屏幕上
    (A2),就是为了防止以后有人把它简化成「助手请求权限 [同意]」。

  **收货三闸抓到的(执行腿交的活里)**

  - **F4 🔴 闸装错了门**:`/api/projects/bind` 是**业主在浏览器里点的**针孔,
    却也被同意闸拦住 —— 让业主确认业主自己,而且把项目列表的合并功能直接卡死
    (`test_ds_web_api` 那条红)。已改走 `_apply_bind_project`,并在注释里写明
    这个绕过依赖 design 的哪三条前提、哪条塌了就得回来重想。
    **根因是我的任务书没写清"闸拦的是模型不是业主"**,不是执行腿的错。
  - **F5 两处"为迎合判据而改产品行为" —— 根因也在我。**
    ① MCP 层把 `error` 键改名成 `status`(正好让我的下界闸把一次**失败**算成
    "跑起来了");② `create_pending` 加了"已有未决卡就不再排新的"(会让助手提的
    第二个请求被静默丢弃、却返回别人的编号)。
    **执行腿在报告里主动说明了这两处的原因,没有藏。** 查下来两处都是我判据写歪
    逼出来的(O5b 把"合法排队"也算违规;`_args_for` 的 rel 指向不存在的文件)。
    判据改对后**把两处全部退回,31 条仍然全绿** ⇒ 反证它们本来就不必要。
  - **F6 执行腿主动报告了"旧回归与新 oracle 冲突"**,没有偷偷改判卷。
    属实:默认档从"立即落盘"变成"要点头",`test_ds_documents` 35 条全红。
    已由主 agent 给三个测试文件的夹具加 `set_mode(ALLOW)` 显式声明"我不测那道闸"。

  **机械闸抓到、我人眼审 diff 没看出来的**

  - **F7 🔴 `ds_consent ↔ ds_tools` 循环依赖**(`test_no_import_cycles` 抓到)。
    我逐行读过那份 diff,没看出来。已把执行器改成由 ds_web 注入
    (`resolve_pending(..., apply_fn=ds_tools.apply_pending)`),依赖方向单向化,
    而且**更贴 design**(那里写的就是"ds_web 后端照 pending 里记的参数执行")。
    这正是那道闸的立身之本:结构问题肉眼不完备。
  - **F8 CSS 变量写错会静默失效。** 我在 app.css 里用了 `--ink-soft` / `--line`
    ——**两个都不存在**。tsc 全绿,而边框和次要文字颜色会悄悄丢掉。
    已改成 `--border-main` / `--ink-2` 并加了一遍机械核对(把该段用到的变量
    与 `:root` 定义求差集)。

  **判据自己的 bug(我写的,红检和收货时抓到)**

  - 一条**假绿断言**:`project_folders()` 回元组序,我拿字符串 `assertNotIn` —— 永远通过。
  - 一条**摆设闸**:O5a 在 `finally` 里就恢复了 `DS_ROOT`,而工具是在那之后才调的
    ⇒ 造一个真去写开关文件的恶意工具都咬不住它。
  - **8 条红得没意义**:直接 `[...]` 取 `pending_id`,假实现下全部 `KeyError`,
    红在前置塌了,真正要考的东西一条都没考到。
  - 一条**期望值写错**:bind 存的是带 `01-项目/` 前缀的 rel,我期望裸文件夹名。
  - 一条**规格错**:O5b 把"合法排队"判成违规(见 F5)。
  - **FastMCP 的 `call_tool` 回 `list[TextContent]` 不是 dict** —— 直接 json.dumps
    拿到对象 repr,"成功了没有"整个算错。
  - **判据自己的工具会互相拆台**:`delete_project_tool` 把夹具删了,后面的
    `bind_project_tool` 永远早退,覆盖面随 `list_tools()` 顺序静默缩水。

  **四审抓到的(2026-08-11,两条腿给了裁决)**

  - **F9 🔴 锁序成环 ⇒ 「业主点头」这条唯一人工通道可被 DoS**(subdeepseek 孤腿
    BLOCK,高危,**本轮唯一的高危发现**)。`bind_project` 在**持着 workspace 锁**时
    调 `create_pending` 去拿 pending 锁,而 `resolve_pending` 的顺序正相反
    (pending 锁 → apply → workspace 锁)—— 教科书式 AB-BA。Linux 的 flock 无限阻塞、
    resolve 又没有超时 ⇒ **永久挂死**,而且挂死的那条 ds_web 线程从此占死 pending 锁,
    之后所有待确认的创建与批准全卡住,只能重启。
    **不能按"罕见竞态"放过**:威胁模型里的助手是被注入控制的,它可以连续狂调
    `bind_project_tool` 去撞那个窗口。
    判据 O9(`726e77b`)钉的是**结构不变量**(`create_pending` 永不在持 workspace 锁时
    被调用),外加一条带 timeout 的并发行为闸兜底 —— 不去真造死锁,那会让判据自己挂住。
    已修(锁内只做决定,排队出了锁再排)。**我自己逐行读过那份 diff,没看出来。**
  - **F10 跨卡片的「显示≠执行」**(subdeepseek,中危)。design 硬性②说的是"执行时用
    pending 里记的参数",但 `bind_project` 的参数是**文件夹名**,名字要靠当时的根才
    解析得成路径。两张卡同时排队:先批 `set_workspace`(根换了)→ 再批 bind,
    bind 拿新根解析那个名字 ⇒ 绑到物理上另一个文件夹,而业主只看见过一个名字。
    **这正是 F1 记账的那个形状,只是发生在两张卡之间** —— F1 我当时判"影响面小、
    记账不修",四审把它推到了一个我没想到的、够得着的场景。已修(pending 记下排队时的
    根,批准时根变了就 `stale_pending`,判据 O10 `6969c05`)。
  - **F11 判据自己把生产形态屏蔽掉了**(subdeepseek Q1/Q3)。夹具把
    `DS_ORGANIZE_ROOTS` 设成 ds_root ⇒ `scan_dir_tool(新根)` 必然早退,canary 闸对
    organize 那三个工具**空转**;而真机白名单是 `Desktop;Downloads`,业主的项目夹
    十有八九就在里面。补了判据 O11 复现生产形态,结论是**边界要改口径**:
    正文一个字读不到(承重、o11b 钉住),**但文件名/大小/时间枚举得到** ——
    见 Accepted deviations 新增的那条。
  - **F12 「针孔绕过闸」的注释漏了第四条前提**(subdeepseek)+ **第五条**(submimo)。
    ④ 网页不许把助手内容当可执行 HTML 透传(否则请求从**业主自己的页面**发出,
    前三条全成立也白搭);⑤ 不许有别的进程把端口转发到外部(ngrok/frp)。
    两条都已写进 `ds_web.py` 那段注释 + design 的装包重验清单。
  - **两处文案**(两腿都提):bind 卡没说"同意后项目列表那两条重复条目会合并"
    (不是安全后果,但业主会困惑"我是不是批了别的事");多条待确认时标题不说数量。
    已改。

  **我修四审的东西时自己捅出来的(O12 抓到)**

  - **F13 新错误码没人翻译,业主会看到英文。** 修 F10 时后端新增 `stale_pending`,
    前端只认识 `already_resolved` ⇒ 屏幕上会出现 `没能提交:stale_pending`。
    业主不写代码,这就是这道闸"文案即强度"的反面。已补 `ERR_MSG` 码表,
    并加判据 O12:**码表从 `ds_consent.py` 现取、不手抄**,漏一个当场红。

- arbitrated verdict (主裁): **PASS**
  > 两条腿一 PASS 一 BLOCK,BLOCK 那条(F9)成立且已修,判据先行、红检留痕、
  > 第④遍收据五段全绿。四条发现全部落地为**会红的判据**(O9/O10/O11/O12),
  > 不是靠注释提醒下一个人。
  >
  > **主裁不降标准的两笔账,写在这里别被"全绿"盖过去:**
  > ① 这次实际只有 **2/4 腿**给了裁决(智谱欠费 + Kimi 额度),而高危那条恰好只有
  > 孤腿看见 —— 结论是"这一轮够了",不是"两腿够用了"。
  > ② F10 是 **F1 的升级版**:F1 是我自己审出来的、当时判"影响面小,记账不修"。
  > 四审把同一个形状放到一个我没想到的场景里,它就够得着了。
  > **"影响面小"这个判断本身要带上"我想不到的场景"这一项** —— 记进教训。

## Accepted deviations

- **有意偏离一条现有原则**(design 已写明,这里只记结论):本仓原则是"网页只批
  工作区内的事,工作区外的留给 CLI"。改工作区根是最"外"的动作,按原则该留给命令行。
  拍板允许网页批,代价是**这道闸挡不住"业主自己点了同意"** —— 它把"文档里藏一句话
  就能得手"降级成"得骗过业主眼皮底下的一张卡"。所以卡片文案是承重墙。
- **`/api/projects/bind` 针孔绕过同意闸**(F4)。安全性依赖 design 写死的三条:
  ① ds_web 只绑 127.0.0.1;② Host 白名单挡 DNS rebinding;③ 模型无 exec/网络能力。
  **装包引入新外壳/新端口时这三条要逐条重验**,否则这个绕过就变成洞。
- ~~**F1 未修**~~ —— **08-11 已修**。四审(F10)把同一个形状放进"两张卡同时排队"
  的场景,它就够得着了:根一换,卡上那个文件夹名指向的就是另一个地方。
  现在批准时根变过就回 `stale_pending`,让业主重新提。
- **`stale_pending` 是刻意的过度拒绝**:`set_workspace` 的参数是绝对路径,其实不受
  根变化影响,但这道闸不按动作分档 —— 两张换根卡同时排队时,批完第一张,第二张要
  重提一次。选宽的一边,理由是这张卡的既定哲学("拿不准就拒绝,重提成本很低"),
  而窄一档就要长一张"哪些动作的参数与根无关"的表,那种表会烂且烂法是静默的。
- 🔴 **口径要改**:「待确认期间新根**一个字**都读不到」的准确说法是
  「**正文**一个字都读不到」。organize 那条独立授权线(`DS_ORGANIZE_ROOTS`,
  真机白名单 `Desktop;Downloads`)在新根落进白名单时,`scan_dir_tool`
  **列得出文件名/大小/修改时间**。proposal 明写这一单不动 ds_organize,
  所以这是**接受的边界**,不是漏洞 —— 但判据 O11 现在把它钉成了明账:
  o11a 钉住"今天名字确实列得出来"(它红 = organize 也进闸了 = 好消息),
  o11b 钉住"正文一个字都不许"(承重那条)。
- **F2 两个 canary 盲区未补**:`stage_intake_tool` / `stage_adoption_tool`。
- **浏览器级测试只覆盖了"不许自动批准"这一条**(e2e B 组)。同意路径的
  端到端(点同意 → 根真的换了)由 python 判据 O3a/O7c 覆盖,没在浏览器里再走一遍。
