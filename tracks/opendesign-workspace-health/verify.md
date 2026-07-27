# Verify: opendesign-workspace-health

- Date: 2026-07-27
- Verdict: **阶段一 收货三闸 PASS,尚未过 full 评审、尚未 merge**

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 submimo/subdeepseek/subglm/subkimi,主 agent 主裁。
> build/test 跑通是机械检查。lane:full(主+3,高风险)/ fast(主+1,medium)/
> self(主自审,小改)。

## 阶段一(并发锁,commit `3e1a309`,分支 `wshealth-lock`)

执行腿:**GPT / codex `gpt-5.6-sol`(high effort)** —— 本机 GPT 执行腿首跑。
隔离:worktree `/root/aiwork/worktrees/wshealth-lock`,主仓零改动。

### Mechanical checks

- [x] 判卷一 `test_ds_workspace_config_lock.py` 17/17 绿(**unittest 复核过**,
      防 pytest subtests 顶层假绿;四审后补 t02e/t11/t12,故由 15 增至 17)
- [x] 全量回归 698 passed / 8 skipped / 0 failed(基线 679 + 判卷一 17 + 判卷二已绿的 2)
- [x] 判卷二按计划仍红(阶段二的活,`ds_web.py` 未被碰)
- [x] build:本阶段纯 Python,`web/` 零改动,不涉及前端构建
- [x] no secrets / unsafe ops:无新增依赖、无 push/merge、无删文件

### 收货三道硬闸(执行腿自述一概不作数)

- [x] **闸① oracle 逐字节 diff = 空**。哈希存档 `logs/wshealth-oracle-hashes.txt`,
      `sha256sum -c` 两份全 OK,`git diff 29dbea8 -- <两份判卷>` 输出为空。
- [x] **闸② 主 agent 亲跑**判卷 + 全量回归(上面的数字都是我自己跑出来的)。
      GPT 腿因沙箱禁 socket 跑不了 web 类测试,**它自己诚实声明了这一点、没有 overclaim**
      —— 但这正是闸②存在的理由:它的自述本来就不作数。
- [x] **闸③ 主 agent 亲读 diff**(106 insertions / 79 deletions,单文件)。
      无 `create mode 120000` 符号链接。`rename_project` 的 workspace 锁与
      步骤②的 `ds_common.locked_rw` **不嵌套**(缩进核过),无锁序死锁。

### 闸③ 顺出的真 bug(判卷全绿也没拦住)

**`locked_workspace_json` 会把字面量 `null` 写进 `workspace.json`。**
触发条件:调用方进了块、`raw` 保持 `None`(坏配置)、又忘了置 `write=False`。
实测落盘内容 = `b'null\n'` —— **用户手写的配置当场被毁**,而读侧对坏 JSON 的反应是
整份降级成 `None`,现象就是「我的项目全没了」。

四个既有写口目前各自都守住了(所以判卷全绿),但**阶段二的体检卡写口正是最容易
踩这一脚的地方**,而「别悄悄毁掉用户的配置」恰恰是本单的立身之本。
处理:安全网收进公共件(`raw` 不是 dict 就不落盘),补判据 `t02e`,先红后绿。

**这条记进方法论**:判卷是我写的,判卷全绿只证明「合乎我写的规格」,
不证明规格完整 —— 这次的洞就在我自己的规格里,是亲读 diff 捞回来的。
(同 [[panel-review-trust-calibration]]「真漏的根因反复是我自己的规格错」。)

## Accepted deviations

- **`workspace.json` 的权限位从 0644 变成 0600**(实测确认)。
  `tempfile.NamedTemporaryFile` 建的临时文件是 0600,`os.replace` 之后继承过去。
  判断:**接受**。方向是收紧不是放宽,不可能造成泄露;真机主要是 Windows(权限位无意义);
  本机是单用户单账号,MCP server 与 ds-web 同账号运行。
  **留痕理由**:这是修 tmp 名带来的**非预期副作用**,不是有意设计 ——
  哪天出现「两个账号跑同一份配置」的部署形态,这里就是第一个要看的地方。

## Review

- lane: **full(必须)** —— 规矩:新写口/权限/auth/钱/**数据一致性面**一律 full 全腿审。
  本阶段动的是「用户整个工作区配置」的并发一致性,四个既有写口全被改过,**不打折**。
- **status: 尚未执行。merge 进 main 之前必须先过。**
- 规格自查(读任何 panel 输出之前先答):
  - **如果规格本身就是错的,会错成什么样?** 我的判卷全部在打「并发下不丢/不坏」,
    但**没有一条打「加了锁之后会不会卡住」** —— 锁是阻塞式的(`LOCK_EX` 无超时),
    真机上 MCP server 与 ds-web 抢同一把锁,若某个写口在锁内做了慢活(比如
    `bind_project` 在锁内调 `ds_workspace.project_folders()` **扫盘**),
    另一个进程就得干等。工作区文件夹多、或放在慢速外接盘/网络盘上时会被放大。
    **这是我写判卷时完全没想到的一面,panel 要专门盯。**
  - 另一个可能的规格错:`set_workspace` 的 `.bak` 备份条件被顺手扩大了
    (原来只在 JSON 解析失败时备份,现在顶层非 dict 也备份)。方向是更保守,
    但**这是我没要求的行为改动**,要确认没有别的地方依赖旧行为。
- findings(主 agent 独立审,先落再看 panel):
  - **[已修]** `null` 写入毁配置(见上,判据 `t02e`)
  - **[已接受]** 权限位 0644→0600(见 Accepted deviations)
  - **[待 panel 盯]** 阻塞锁 + 锁内扫盘导致的相互等待(见规格自查)
  - **[待 panel 盯]** `.bak` 备份条件被扩大
### 四审结果(2026-07-27,日志 `logs/panel-wshealth-lock-review-20260727-003645.*`)

派发纪律:oracle 先跑(`rc=0` 记录在案)→ 自审先落盘(仓外
`tasks/wshealth-lock-review-my-review.md`)→ 才派发。**评审树刻意用了不含我 findings
的那一版**(另开 detached worktree 到 `3e1a309`,verify.md 在那棵树里还是空模板)
—— 我此前已经把带结论的 verify.md commit 进分支了,那正是 07-21 踩过的反锚定坑。

| 腿 | 裁决 | 价值 |
|---|---|---|
| submimo | PASS + 3 测试缺口 + 2 风格 | 中。顺出 `ds_organize.py:237` 已有同款旁路锁先例 |
| subdeepseek | **BLOCK**(权限)+ 3 warning | **高**。W1 重入死锁是真的 |
| subglm | PASS(六项全 PASS) | **低**。基本是把我的设计意图复述回来,且断言"无死锁风险"= **错** |
| subkimi | PASS + M1/M2 | **最高**。分析最细,且诚实声明 harness 挡了 pytest、不代测试结论 |

**再次印证 [[panel-review-trust-calibration]]**:全票不是信号,**孤腿 BLOCK 才是**;
而最值钱的两条来自"裁决为 PASS"的那条腿的正文,不在裁决词里。

### 逐条对账(每条都自己核过代码/发过探针)

- **[采纳·已修] 重入自死锁**(subdeepseek W1 + subkimi M1,**两腿独立命中,我漏了**)
  **发探针证实**:同线程嵌套进入 → `timeout 8` 退出码 **124**,永久挂起、无超时、
  无报错。真机=ds-web 那条线程整个挂死,用户点按钮永远转圈。
  而它已被定为「阶段二网页写口要接的公共件」,网页写口最容易在锁内间接调到
  另一个接了锁的入口。**修法:嵌套当场抛 RuntimeError,不做成可重入**
  —— 可重入会让「锁内再调另一个写口」这种真正错的写法悄悄合法化。判据 `t11`。
- **[采纳·已修·但下调严重级] 权限位收紧**(subdeepseek BLOCK-1 + subkimi L2)
  DeepSeek 判 BLOCK 的理由是「两进程若不同 uid 会读不回」—— **这个场景在本部署不成立**
  (单账号;真机主要是 Windows,POSIX 权限位基本无意义)。**采纳 subkimi 的 L2 定级。**
  但仍然修:写文件顺手改掉它的权限本就不该发生,且修法只是"存在就保留原位、
  新建用 0644"。判据 `t12`。**我原先把它列为"接受的偏差"是偷懒了** —— 修它比论证它无害更便宜。
- **[采纳·已修] `t07` 没验证子进程真的写成功**(submimo #3 + subkimi)
  原来只断言"被挡住 + 退出码 0",一个既被挡住又静默写失败的实现照样能变绿。已补断言。
- **[采纳·仅文档] Windows 语义**(subdeepseek W3 + subkimi M2)——**Linux 上无法证实,不硬修**
  - 空锁文件能否加锁:**这是仓内既有做法,非本次引入** —— `ds_organize.py:239`
    的 `.apply.lock` 同样是空文件加锁,注释还专门写了「"a" 不截断」。若真在 Windows
    上不成立,那是既有面的问题,不该由本单背;**但要进真机核查清单**。
  - 同进程跨线程是否互斥 + `msvcrt.locking` 约 10 次重试后**抛 OSError**(不是无限等):
    后者是 `ds_lock.py:10-12` 自己写明的,**确定**。四个写口都不捕获 → 长争用时
    炸给调用方。**已写进 docstring**。**ds-web 是 `ThreadingHTTPServer`(已核 `ds_web.py:1952`),
    所以阶段二的网页写口正好落在这个不确定区** —— 列为阶段二上线前的硬前置。
- **[驳回·仅记注释] `bind_project` 锁内二次读**(subdeepseek W2 + submimo #4)
  两次读都在**同一把锁内**,内容必然一致;subkimi 独立判断"不算缺陷",与我一致。
  DeepSeek 说的是"将来 load_config 若合并外部文件才会出问题" —— 那是未来的假设,
  为它现在重构 `bind_project` 的解析路径,引入的风险大于消除的风险。**不改**。
- **[驳回] subglm「没有死锁风险」** —— 探针实测 124,**事实错误**。
- **[采纳·流程]** subkimi 指出 `t02e` 与其修复同一个 commit 落地,
  **git 历史里没有「红→绿」的证据链**。属实。我确实红检过(会话内实测 `b'null\n'`),
  但仓库证明不了。`t11` 同样:我先发探针拿到 124 才动手。**记在这里当证据。**
  另:我的评审任务书写了「判卷未被改动」,subkimi 指出字面不成立(`t02e` 就在 diff 里)
  —— 我的本意是"执行腿没改",**任务书措辞是我写糙了**。

### 仍然存在、明确不修的缺口(记账,不装作没有)

- `rename_project` / `delete_project` 的**并发终态一致性**无专测(submimo #2 + subkimi)。
  现有覆盖:`t04` 证明这两个口确实走了锁,`t05` 证明锁能防丢更新。判断:够用,不补。
- `set_workspace` 的 `.bak` 备份路径挪进锁内后零覆盖(subkimi)。
- Windows 分支整面零覆盖(本机是 Linux,跑不了)。

- arbitrated verdict (主裁): **PASS** —— 两条真缺陷已修并有判据,其余或驳回或记账。
  **但附一条硬前置**:见下方「阶段二上线前必须先做的事」。

## 阶段二上线前必须先做的事(四审的硬前置)

**`ds-web` 是 `ThreadingHTTPServer`(`ds_web.py:1952`)** —— 阶段二的网页写口意味着
**同一个进程内的多个线程**会争这把锁(用户双击保存、开两个标签页就够了)。
而真机是 Windows,`msvcrt.locking` 在这一场景下的两条语义本机验不了:

- [ ] **同进程跨线程是否真的互斥**(Windows 字节范围锁的所有权语义)。
      若不互斥,`t03/t04/t05` 在 Windows 上根本跑不绿,阶段二的并发保护也是假的。
- [ ] **约 10 次重试后抛 `OSError`** 而不是排队等(`ds_lock.py:10-12` 自述,**确定**)。
      四个写口都不捕获。`bind_project` 锁内要扫整棵项目树 ——
      工作区在慢速外接盘/网络盘时,另一进程可能直接吃到异常。
- [ ] **空锁文件在 Windows 上能否加锁**(既有面:`ds_organize.py:239` 同款)。

做法:在用户机器上跑一次判卷一(`python -m pytest tests/test_ds_workspace_config_lock.py`)。
**这是唯一能把这三个"未知"打成"已知"的办法**,在 Linux 上再审多少遍都没用。

## 阶段二(体检卡**后端**)—— 2026-07-27,lane = full

前端卡片(T8)**不在本轮**:无判卷覆盖 + 需前端构建,单独一单,也让本轮的安全面
(网页写口)能被闸③单独读清楚。

### Mechanical checks(主 agent 亲跑)

- [x] 判卷二 30/30 绿(含四审后补的 v20/v21);判卷一 17/17 仍绿
- [x] 全量回归 **726 passed / 8 skipped / 0 failed**
- [x] build:本轮纯 Python,`web/` 零改动
- [x] no secrets / unsafe ops:无新增依赖、无 push/merge、无删文件

### 收货三闸

- [x] 闸① 两份判卷对 `4578afd` 逐字节 diff = 空;哈希与存档一致
- [x] 闸② 亲跑判卷 + 回归(见上)
- [x] 闸③ 亲读 diff 逐行;`create mode 120000` 零命中

### 执行腿

`codex -m gpt-5.5`(首次按 07-27 新分层派活)。**沙箱禁网 → 它跑不了这份判卷**
(判卷要起 `127.0.0.1` HTTP server),**判卷全部由主 agent 代跑**。
它如实声明未跑、拒绝宣称全绿,并自写不启 HTTP 的函数级探针自查。
**一次过,零返工轮**:交付即判卷 28/28 绿 + 回归 724 全绿。

### 四审裁决:主 agent 仲裁 = PASS(修复轮后)

`logs/panel-wshealth-card-20260727-205846.*`。submimo PASS / subdeepseek PASS /
subglm NEEDS_MORE_INFO(驳回,见下)/ subkimi 超时未交卷(rc=1)。

**存活的发现(已修,`d3d2299`)**

1. **写口请求体上限是借来的**(subkimi 算出约 110 个中文长目录名即爆,
   subdeepseek 独立指出该口与写针孔⑨共用 `OPEN_BODY_MAX` 而请求体与目录数线性相关)。
   该口语义是「一次存整份清单」,已声明的名字每次保存都要原样重报 → 用户存不进去,
   且只拿到一句无差别的 400。改为该口专属的两条闸:64KiB + 500 个名字。
   **根因在主 agent 的规格**:design.md:39 明写「数量与请求体上限」两条,
   判卷 v04c 只测了「超限被拒」,没测「正常大小存得下」,也没测数量闸。
2. **读口那把锁去掉**(主 agent 判定比 subdeepseek 的「观察」重一级)——
   它买不到防撕裂(阶段一原子替换已保证),目录快照本就不受该锁保护,
   而 `ds_lock` 在 Windows 上争用**抛 OSError 而非排队**(阶段一四审记录),
   读口持锁扫目录会抬高并发保存直接失败的概率。**真机就是 Windows。**
   *这条单看任何一腿都出不来,是拼上阶段一的记录才成立的。*
3. 写口错误路径改为出锁再发响应;`_dir_entries` 跨模块私有依赖两侧加互指注释。

**驳回 subglm 的 HIGH**:它自己在报告里写明「`bin/ds_web.py` 的具体实现内容不可得」,
findings 是把评审任务书里的问题原样复述回来。**但根因不在模型,在派发**:
它的 agent 腿失败回落成 chat 腿,而 chat 腿只吃增量 diff —— 我**先 commit 再派发**,
工作区是干净的,于是它拿到的实现代码是空的(`PANEL_INCLUDE` 我只给了判卷文件)。
**这正是 agent 腿当初要根治的「空 diff 盲评」,回落时复发了。**
→ 待办已记入 [[review-tooling-debt-queue]]:回落到 chat 腿时,应自动把
`git diff <base>..HEAD` 的改动文件并进 `PANEL_INCLUDE`,而不是只喂工作区未提交改动。

**subkimi 又一次 900s 超时(rc=1),而本轮最值钱的发现在它的思考日志正文里** ——
第三次印证「失败腿的日志一定要读」。

### 仍然欠着的真机验收(接口全绿 ≠ 做对了)

- [ ] 判卷一必须在**用户的 Windows 机器**上跑一次(三条锁语义 Linux 验不了)
- [ ] 真机肉眼:拿真实工作区开卡片,确认没声明过的真项目出现在「显示」侧
      —— 判卷承认自己接不住「下发集合算漏一个」这一面

## 真机验收(两条都没做,**接口全绿 ≠ 做对了**)

- [ ] 版本回显:用户机器 `git pull` → `bin\start.ps1` stop/start → Ctrl+F5 →
      `/api/health` version 对得上(盘上和运行时对不上 = BLOCK,不是警告)
- [ ] 肉眼:真实工作区(含中文名 + 一个没声明过的真项目文件夹)开卡片,
      确认那个真项目出现在「显示」侧
