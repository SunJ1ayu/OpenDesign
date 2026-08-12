# Verify: opendesign-windows-installer

- Date: 2026-08-12
- Verdict: <PASS | BLOCK | NEEDS_MORE_INFO>

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [x] 判据自己先跑通(Linux 台架,真起网关 + 真起 ds-web)
- [x] 红检:六条变异,靶子逐条指定
- [x] 组包后的结构检查
- [ ] **业主 Windows 真机跑一趟** —— 只有他能做,S0 的结论全压在这一趟上
- [x] no secrets:包里不含任何 key。`DS_LLM_KEY` 全程是占位符,探针自己用的是
      `sk-spike-not-a-real-key`;真 key 从头到尾没进过这个包。
- [x] unsafe ops:包只读、不装、不改机器 —— HOME/USERPROFILE 指向包内 fakehome,
      不写注册表、不进 PATH、不碰 `%USERPROFILE%\.nanobot`,删文件夹即消失。

**机器打印的**(不是我的转述)—— 判据用 `runlog` 跑,把它打印的收据行原样粘进来:

```
runlog -t opendesign-windows-installer -- <判据命令>
```

```
runlog: spike-redcheck rc=0 commit=8227223 dirty=yes at=2026-08-12T13:56:00Z file=tracks/opendesign-windows-installer/evidence/20260812T135600Z-01-spike-redcheck.txt
runlog: spike-on-linux-rig rc=1 commit=8227223 dirty=yes at=2026-08-12T14:00:29Z file=tracks/opendesign-windows-installer/evidence/20260812T140029Z-01-spike-on-linux-rig.txt
runlog: package-structure rc=0 commit=8227223 dirty=yes at=2026-08-12T14:01:11Z file=tracks/opendesign-windows-installer/evidence/20260812T140111Z-01-package-structure.txt
```

**那份 `rc=1` 不是藏起来的失败,是台架的真实差异**(5b:跑红的一份都不许藏):

- 红的两条是 `S0b`(sys.path 有包外条目)和 `S1`(版本 3.12.3 ≠ 3.12.10)。
- 台架是 Linux venv:标准库在 `/usr/lib` 与系统共享、解释器是系统的 3.12.3。
  **真包里这两样都在包内**(标准库 = 包里的 `python312.zip`,解释器 = 3.12.10)。
- 也就是说这两条红**正是判据咬对了**:它确实分得清"包里的"和"机器上的"。
  台架上其余 29 条全绿(含真起网关、3 个 MCP 全连上、ds-web 自报 0.85.0)。
- **别把台架的 29 绿当成 S0 通过** —— 台架跑的是普通 venv,而 S0 要问的恰恰是
  embeddable。台架只证明了**判据本身能用**,没证明结论。

## Review

- lane: **S0 = self;S1 = full**
  > **S0 判的是"探路包这份判据咬不咬得动"**,交付物是一个只读、不装、删掉即消失的 zip:
  > 不写注册表、不进 PATH、不碰 `%USERPROFILE%\.nanobot`(包内 fakehome 当 HOME),
  > 业主已有的安装一根头发都不碰。没有新写口、不碰权限/auth/钱/数据一致性 ⇒ self 站得住。
  > **self 不等于不干活**:闸③亲读 + 红检(拿故意坏掉的输入证明 spike.py 咬得动)+
  > 本机能验的结构检查,一样都不少。
  > **S1 必须 full,现在就写死在这儿,不许到时候降档**:安装器往业主机器上装东西、
  > 写 `%USERPROFILE%`、经手他的 LLM key ⇒ 同时命中**权限**和**auth**两条,
  > 「针孔再薄也不打折」。
  > **碰了新写口 / 权限 / auth / 钱 / 数据一致性 → full,针孔再薄也不打折**(硬规矩,别在这降档)。
  > fast = 主+1,中等风险;self = 主自审(闸③ + 截图 + 全量回归),
  > 限纯前端/纯观感、后端一字未动、只新增已过审针孔的调用方。
- 派给: **S0 = 主 agent 直接干**。
  逐档问过,不是"排除了 codex 就跳到我自己干"(07-31 那个洞我犯过四次,见
  [[self-narrated-fields-dont-guard]]):
  - **codex/gpt-5.5**:S0 的工作量**几乎全在 spike.py**,而 spike.py 就是 oracle ⇒
    按硬规矩不外包。刨掉它剩下的是组包(解 zip、改一行 `._pth`、拷 payload、写 bat、
    压回去,十来条命令)—— **任务书会比活本身长**,且没有探索空间。派它是负收益。
  - **Sonnet 腿(worktree)**:同上,且更不划算 —— 这单要动的是 **380MB 二进制/大文件**,
    隔离树的拷贝与合并成本远高于活本身。
  - **submimo fix**:窄口修复档,这单没有"一个坏了的窄口"要修。
  - ⇒ 真正值得重新评估分层的是 **S1 的 NSIS 脚本**(有真实工作量、纯文本、边界清楚),
    已写进 tasks.md,到那一步再判,**不拿这次的结论顶替下次的判断**。
  判卷不需要起服务(gateway 那一段在业主真机上跑,不在我这儿)。
- 规格自查(读任何 panel 输出之前先答):<如果规格本身就是错的,会错成什么样、我怎么发现?
  panel 只验"实现合不合规格",验不了"规格对不对" —— 四腿齐 PASS 不等于题是对的。>
- 腿的花名册: <把 `<日志前缀>.roster` 里那一行**原样粘过来**,别手写>
  > panel-review 收尾自己写这个文件(off / FAIL(rc) / 降级 都在里面)。
  > 08-06 立这条的理由:08-05 我在这里手写了"三条腿一致 PASS",而 Kimi 根本没出结论
  > (同一页第 90 行我自己还写着它没出报告)—— 手抄一份终端上的东西,抄错那次没人会发现。
- findings:
  - <...>
  > 只写发现。腿的身份/降级不在这儿抄第二遍:日志自带身份牌(降级横幅 + 视野边界),
  > 花名册在上一格,查工件不查自述。
- arbitrated verdict (主裁): <...>
  > **归档时这一条和顶部的 `Verdict:` 都不许还是占位符**,`track-guard` 规矩3 会挡;
  > 没归档但已经合并上线的,`track list` 会打 ⚠️(stage-timer 就这么漏了两个月)。

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>
