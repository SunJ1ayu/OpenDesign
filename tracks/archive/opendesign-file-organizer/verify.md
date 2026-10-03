# Verify: opendesign-file-organizer

- Date: 2026-07-02
- Verdict: **PASS**(panel 修复后复测 18/18 绿 + 回归 13/13)

## Mechanical checks

- [x] tests pass: test_ds_organize.py 15/15(venv,含 MCP 表面测试)/ 14+1skip(系统 py,无 mcp)
- [x] regression: test_ds_tools.py 13/13 仍绿
- [x] no secrets / unsafe ops:纯标准库,无网络,无硬编码 key;delete 原语不存在

## Review

- lane: full(权限/确认闸敏感 → 主 + MiMo/SenseNova/GLM)

### 主 agent 独立 findings(落于读 panel 输出之前,2026-07-02)

结论倾向 PASS,核心闸验证过硬:

1. **硬闸成立(核对代码+test_15)**:MCP 表面恰好 scan/stage/apply 三工具,无任何
   工具能写 `.approved`;apply 在 flock 下检 marker;plan_id 强正则(`^\d{8}-\d{6}-[0-9a-f]{6}$`)
   → plan_id 无法用于路径注入;ds_tools 的写面被锁死在 projects/*.md(强制 .md 后缀),
   够不到 organize/ 下的 plan/marker → 模型经由两个 MCP server 都造不出批准标记。
2. **已知残余(设计已接受,列为 deviation)**:
   a. 执行中途 os.rename 失败(如权限)会部分执行——先整体复验把概率压到极低,
      audit.log 可追溯;设计文档已声明接受。
   b. 目录漂移检测弱:目录内文件"内容"变化不改目录 mtime/size,移动目录时检不出;
      文件级漂移检测是可靠的。
   c. src 是"指向 root 内目标"的符号链接时,realpath 后移动的是目标而非链接本身
      (语义小坑,非安全问题;指向 root 外的链接会被 path_escape 拒)。
   d. 若用户把 DS_ORGANIZE_ROOTS 配成包含 DS_ROOT 自身,批准过的 plan 可以挪动
      plans/ 下的文件——这是部署配置问题,config 注释已引导填"要整理的目录"。
   e. stage 的 plan 文件用 "x" 独占创建,同秒+3字节随机撞名概率可忽略,撞了 = 异常
      冒泡成工具错误,无数据风险。
3. **复验顺序核对**:applied → marker → root 白名单 → 逐 op(存在/realpath 未变/
   快照/不覆盖)全过才动第一条 —— 零执行保证成立(test_09/10 覆盖)。
4. **scan 不跟符号链接**(os.walk 默认 followlinks=False)→ 无经 symlink 目录逃逸读取。
5. **conflict 检查含祖先重叠**(动目录又动其内部/往被动目录里塞)→ 挡住了"复验全过
   但执行中互踩"的一类中途失败。

### panel findings + 仲裁(logs: panel-opendesign-organize-0702-2032.*)

MiMo=BLOCK / SenseNova=PASS / GLM=BLOCK。逐条对代码仲裁(基准=修复前版本):

1. **TOCTOU:复验↔rename 窗口(MiMo HIGH + GLM HIGH + SenseNova MEDIUM)→ 部分接受,已修**。
   外部进程竞态不在威胁模型内(单用户机,对手=模型失误);但**模型可达的变体成立**:
   两个"都被人批准"的 plan 并发 apply(FastMCP 同步工具可进线程池),dst 复验互相打穿,
   POSIX rename 静默覆盖。修复:`organize/.apply.lock` 全局排他锁串行化全部 apply +
   rename 前最后一验(lexists dst + makedirs 后 parent realpath 落 root 内)。
2. **部分执行(三家都提;MiMo/GLM MEDIUM,SenseNova HIGH)→ 维持设计已接受的 deviation,
   加便宜缓解**:exec 循环捕 OSError,结构化返回 `executed` 已执行清单,audit 逐条 flush;
   rollback/resume 方案拒——回滚自身可失败(反向 rename 同样会撞),复杂度不换安全增益。
3. **makedirs 撞"父组件是文件"(GLM LOW)→ 接受,真 bug,主 agent 首审漏掉(panel 价值点)**:
   dst 中间组件若已存在为文件,stage 放行、apply 中途 FileExistsError 炸出部分执行。
   修复:`_dst_parent_blocked`(最近已存在祖先必须是目录)进 stage 校验 + apply 复验;
   test_17 红→绿验证。
4. **dst == root_real 检查冗余(MiMo MEDIUM)→ 拒,不改**:核对 `_resolve_in_root`+lexists
   确实重叠,但显式意图零成本,留着。
5. **plan_id 24-bit 熵可爆破(MiMo LOW)→ 拒**:apply 仍需该 plan 自己的 `.approved`,
   猜中 id 只能执行"人已批准的 plan"=本来就允许的操作,加熵无安全增益。
6. **测试缺口 → 择收**:采纳 symlink-外指拒绝(test_16)、dst 父组件为文件(test_17)、
   approve 幂等(test_18);拒并发 apply 线程测试(全局锁已使其确定,线程测试易 flaky)、
   拒 marker-deleted/truncation 用例(代码路径平凡,肉眼核过 scan 截断三行逻辑)。

修复后:`test_ds_organize.py` **18/18 绿**(venv),`test_ds_tools.py` 13/13 回归绿。

## Accepted deviations

- 执行中途 OSError 部分执行不回滚(概率被 stage+apply 双重整体复验压极低;executed 清单
  + audit.log 可手工恢复;回滚方案拒,理由见仲裁 2)。
- 目录级漂移检测弱(目录内文件内容变化不改目录 mtime/size);文件级可靠。
- src 为"指向 root 内目标"的符号链接时移动的是目标不是链接(语义小坑,非安全问题;
  外指链接被 path_escape 拒,test_16)。
- DS_ORGANIZE_ROOTS 若被用户配成含 DS_ROOT 自身,批准过的 plan 可动 plans/ 下文件
  ——部署配置问题,config 注释已引导。
- plan 文件同秒撞名 = "x" 模式异常冒泡,无数据风险。
