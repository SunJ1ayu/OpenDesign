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

- [x] 判卷一 `test_ds_workspace_config_lock.py` 15/15 绿(**unittest 复核过**,
      防 pytest subtests 顶层假绿)
- [x] 全量回归 694 passed / 8 skipped / 0 failed(基线 679 + 新增 15)
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
- arbitrated verdict (主裁): 待 panel 后填

## 阶段二(体检卡本体)

未开始。判卷二 `test_ds_web_folder_visibility.py` 28/28 红,等实现。

## 真机验收(两条都没做,**接口全绿 ≠ 做对了**)

- [ ] 版本回显:用户机器 `git pull` → `bin\start.ps1` stop/start → Ctrl+F5 →
      `/api/health` version 对得上(盘上和运行时对不上 = BLOCK,不是警告)
- [ ] 肉眼:真实工作区(含中文名 + 一个没声明过的真项目文件夹)开卡片,
      确认那个真项目出现在「显示」侧
