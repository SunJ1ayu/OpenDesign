# Verify: opendesign-windows-installer

- Date: 2026-08-12
- Verdict: **S0 = PASS**(2026-08-12 业主真机第二跑全绿;S1 未开工)

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
runlog: package-structure-clean rc=0 commit=f555cd9 dirty=yes at=2026-08-12T14:22:53Z file=tracks/opendesign-windows-installer/evidence/20260812T142253Z-01-package-structure-clean.txt
```

**发布前抓到一个真泄漏(这条最值钱)**:第一版包里混进了 `config/workspace.json` ——
`.gitignore` 明确排除的**本机工作区配置**。而这个包是要往 **public 仓**发布的。
内容本身轻(Linux 路径 + 一个测试项目名,不是业主 Windows 上的真数据),但它属于
「业主数据不进仓」那一类,不该出现在公开发布物里。
- 根因:我拷的是 `bin/ config/ workspace/` **整个目录**,想当然认为"目录里的都是仓库里的"。
- 修法不是"下次记得":`check-package.sh` 加了一道机械闸 —— **ds/ 里每个文件都必须
  `git ls-files` 得到**。加完**先拿还没清理的包红检了一遍**(如期红在这条上),再清理、
  重验、重打包。
- 移掉之后 ds-web 照常起(`workspace.json` 缺失是"未配置"优雅降级),台架仍 29 PASS / 2 FAIL。

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
- 规格自查(读任何 panel 输出之前先答):
  S0 的规格是「免装 Python 能不能跑起这一整套」。它**可能错在哪**、以及实际结果:
  - **错法一:问得太窄,绿了也不说明能用。** 真机全绿只证明"进程起得来、工具连得上、
    版本报得出",**没证明能聊天** —— 全程用的是假 key,一次真的模型调用都没发生。
    这条我接受:S0 要答的是运行时形态,聊天链路在业主现有安装上早就跑着,不是本单的未知。
    **但不许把它说成"装完就能用"。**
  - **错法二:只在一台机器上绿。** 这次是 `C:\Users\PC`,**另一台没跑**。
    embeddable 的坑多半与机器无关(它自带运行时),但"多半"不是证据。
  - **错法三(真发生了):判据问不出没装的东西。** 第一跑炸在 `pywintypes`,而我的判据
    只在 S2-loc 里顺手撞见它 —— **不是我设计了一道"依赖完整性"的闸**。
    机械审计 `win-deps-audit.py` 是事后补的。若当初 mcp 恰好没在 S2-loc 名单里,
    这个洞会一路漏到 S5 才炸,甚至可能表现成别的症状。
    ⇒ **教训不是"判据不够",是"我按功能分关,没按依赖完整性分关"。** 已补成常驻闸。
- 腿的花名册: <把 `<日志前缀>.roster` 里那一行**原样粘过来**,别手写>
  > panel-review 收尾自己写这个文件(off / FAIL(rc) / 降级 都在里面)。
  > 08-06 立这条的理由:08-05 我在这里手写了"三条腿一致 PASS",而 Kimi 根本没出结论
  > (同一页第 90 行我自己还写着它没出报告)—— 手抄一份终端上的东西,抄错那次没人会发现。
- findings(S0,主 agent 自审;lane=self,无 panel):
  - 🔴 **F1(真机第一跑抓到,已修)**:`pip download --platform win_amd64` **只按标签挑轮子,
    `sys_platform=='win32'` 这类环境标记仍按本机(Linux)判** ⇒ 仅 Windows 需要的依赖
    被**静默丢掉且不报错**。机械审计扫出 4 个(colorama / pywin32 / tzdata / win32-setctime),
    **比真机炸出来的多 2 个** —— `tzdata` 要到起网关那步才炸,等于按"补炸出来的那两个"
    修会再废一趟真机。**打地鼠会输,机械扫描才赢。**
  - 🔴 **F2(我自己的闸自己坏了)**:`win-deps-audit.py` 第一版剥 `.dist-info` 后缀剥错
    (`rsplit('-',1)` 而 `.dist-info` 本身带连字符)⇒ "已装"集合全是坏名字、**任何包都判成缺失**。
    补完包之后它还在喊缺才露馅。**一个永远红的闸和永远绿的闸一样没用。**
    已修,并**双向验**(补齐后 0 缺 / 拿旧 payload 跑照样喊出那 4 个)。
  - **F3(判据自曝,台架阶段)**:`inside_root` 用 `resolve()` 跟穿软链接 ⇒ 会假红。
    Windows 上业主若把包解压在 OneDrive/映射盘那类带 junction 的路径下会踩到,
    **而假红会让我得出「免装 Python 不行」这个完全错误的结论**。已修。
  - **F4(发布前抓到)**:第一版包里混进 `.gitignore` 排除的 `config/workspace.json`,
    而这是要发到 **public 仓**的。已修 + 已上机械闸(ds/ 里每个文件必须 `git ls-files` 得到)。
  - **F5(接受,记账)**:`pywin32` 的三条路径我写死进了 `._pth`,而它本来靠 `.pth` 自挂。
    两套机制并存(重复但无害)。之所以不赌 `.pth`:embeddable 下会不会处理 `.pth`
    我在 Linux 上验不了,而赌输的代价是业主再废一趟真机。
- arbitrated verdict (主裁,S0): **PASS**。
  真机 31 PASS / 0 FAIL / 0 SKIP,**结论:免装 Python(embeddable 3.12.10)能跑起
  OpenDesign 这一整套**,含 3 个 MCP 子进程与 ds-web,运行中的进程自己报出了 0.85.0。
  ⇒ S1 的运行时形态**定为 embeddable**,PyInstaller/完整 Python 两条退路不必再走。
  **本轮最值钱的一件事**:S0 这一趟的价值几乎全在**第一跑那次红**上 ——
  它暴露的不是一个 bug,而是**我整条组包流水线的一个系统性盲区**(跨平台解析依赖时
  环境标记不跟着走)。要是当初图省事直接造安装器,这个洞会在业主装机时才炸,
  而且会被误读成"这方案不行"。**先做探路包这个决定,是这一单最赚的一笔。**
  > 只写发现。腿的身份/降级不在这儿抄第二遍:日志自带身份牌(降级横幅 + 视野边界),
  > 花名册在上一格,查工件不查自述。
- arbitrated verdict (主裁): <...>
  > **归档时这一条和顶部的 `Verdict:` 都不许还是占位符**,`track-guard` 规矩3 会挡;
  > 没归档但已经合并上线的,`track list` 会打 ⚠️(stage-timer 就这么漏了两个月)。

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>
