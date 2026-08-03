# Verify: opendesign-mcp-registry

- Date: 2026-08-02(判据)/ 2026-08-03(实现 + panel + 修复)
- Verdict: **PASS(代码面)—— 但整单未完:欠机主两台 Windows 各重跑一次装机脚本 + 真调一次工具**

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [x] build passes —— `python bin/ds_mcp.py <key> --selftest` 三个 key 子进程真跑通过
      (`test_mcp_entry_contract` 里跑的,不是我口头说的)
- [x] tests pass —— 全部在 `3da58f7`(修复 commit)上亲跑:
  - `tests/mcp-gate.sh` **全绿**(装了 mcp 的解释器;29 个工具的 name/inputSchema/docstring
    逐字节 == `mcp_surface_baseline.json`;无环闸 `KNOWN_REMAINING` 空集)
  - `pytest tests/` → **844 passed / 14 skipped / 136 subtests**
  - `tests/e2e/run-all.sh` → **31 PASS / 0 FAIL / 2 SKIP**(两条需活 gateway)
  - ⚠️ 记账:`pytest` 用的 `python3` 没装 mcp ⇒ 工具表快照闸在它下面**整块 SKIP**,
    而汇总只印一行 "844 passed"。**"pytest 全绿"这句话不包含本单最重要的那条闸** ——
    必须另跑 `tests/mcp-gate.sh`(它没装 mcp 就直接红,不给静默跳过留门)。
- [x] no secrets / unsafe ops —— 闸③ 亲读全 diff:无符号链接(`git diff --summary` 无
      `mode 120000`)、无夹带、config 模板只动该动的行

## Review

- lane: **full,不打折**
  > 硬触发器直接命中:动的是**助手能力的全部来源**(三个 MCP server 的 29 个工具),
  > 且牵连**部署面**(用户 `~/.nanobot/config.json` 里写死的入口路径,`git pull` 修不到)。
  > 搞砸的表现不是"某个功能不好用",是**用户下次用的时候助手什么都不会做了**。
  > 这一条在方向定稿前就能确定,不必等 explore。
  > **碰了新写口 / 权限 / auth / 钱 / 数据一致性 → full,针孔再薄也不打折**(硬规矩,别在这降档)。
  > fast = 主+1,中等风险;self = 主自审(闸③ + 截图 + 全量回归),
  > 限纯前端/纯观感、后端一字未动、只新增已过审针孔的调用方。

- 派给: **实现 = `codex -m gpt-5.6-sol`(升档,分层还账第 5 单);判据与修复 = 主 agent 亲写**
  > 派活前重开了 `delegate` 抽屉,没凭预判直接调参数。
  > 轴(判卷要不要起服务):工具表快照与入口可运行闸不需要开网络端口 ⇒ 实现可外包。
  > **部署面(config / 装机文档 / 报错桩)主 agent 自己做,没外包** —— 外部执行腿一律不许碰部署面。
  > 返工账:执行腿自身错误 **2 处**(F1 模块头说明太薄、F2 悬空类型注解),
  > 两处根因都在**我的任务书没写风格约定**,已在前一轮修完;交付的搬运本体逐字节正确。
- 规格自查(读任何 panel 输出之前答的,原文在 `/root/aiwork/tasks/mcpreg-review-my-review.md`):
  > 我的规格 = 「工具表一个字不变 + 新入口能跑 + 仓库里两份模板已指向新入口」。
  > 它整块漏掉的是**存量机器上那份已生成的 `~/.nanobot/config.json`** —— 判据在仓库里,
  > 风险在仓库外。**规格全绿而用户机上助手全废,是本单唯一"能过审还是错"的形态。**
  > 怎么发现:只能靠机主两台 Windows 各跑一次装机脚本后让助手真调一次工具。
  > 这不是能补测试的,是流程上必须有人做的一步。
  > —— 事后看,这条自查是对的:panel 三腿命中的最重的一条正落在这个面上。
- panel-review(2026-08-03 19:57–20:09,日志 `/root/aiwork/logs/panel-mcpreg-20260803.*`):
  - `subdeepseek` **PASS** + 3 findings(其中 test_05 漏查 args 的 key 是它独有的孤发现)
  - `subkimi` **PASS** + 6 findings(最完整的一腿:install-windows.md 那条、eval 退化、
    闸的扫描名单漏掉 server 层与地基四模块,都是它)
  - `submimo` **2 BLOCK**(两份 eval 静默退化)+ 1 WARN
  - `subglm` **死于额度**(后端返回"余额不足或无可用资源包")—— 失败腿的日志已读,
    确认是环境问题不是评审结论
- findings(合议后的最终账,五条全部已修并转绿于 `3da58f7`):
  - **F1 旧入口静默死亡(最重;三腿 + 我独立同时命中)** —— `__main__` 整块删掉后,
    旧 config 拉起 `python bin/ds_tools.py` 会**退出 0、零输出**,nanobot 只表现成
    "工具没了"。本单风险最高的路径却是**最不可诊断**的失败形态。
    修法:三个业务模块末尾各留一个报错桩(`SystemExit` + 人话 + 重跑装机脚本的命令),
    不 import mcp、不 import 登记层。实测三条命令各 rc=1 且打印原话。
  - **F2 `docs/install-windows.md`「更新的生效边界」对本单已是谎话(subkimi 孤发现)** ——
    它写着"git pull 后重启 gateway 即生效",而这次入口路径变了、config 在仓库外。
    它是**存量机器唯一会读的耐用文档**;机主不会去看 `ds_mcp.py` 的 docstring。已补。
  - **F3 `docs/spec.md` §9 那段 config 骨架照抄即装坏(我 + subkimi)** —— 那段的存在理由
    就是给人抄。已改成三条 server 各带 key 的新入口。
  - **F4 两份 eval 静默退化(submimo BLOCK + subkimi;我漏了)** —— 从 AST 抽工具表、
    自称"与真部署同源",搬家后抽到的是**空表**,而它们不进 pytest ⇒ 不会让任何测试变红。
    已改扫 `bin/ds_*_server.py`(29 / 17 已由新闸钉死)。
  - **F5 我自己判据的三个洞(自审 + subdeepseek + subkimi 各补一个)** ——
    ① 快照闸在没装 mcp 的解释器下整块 SKIP 而汇总印"全绿"(→ 新增 `tests/mcp-gate.sh`,
    没装 mcp 直接红);② 模板判据只查"文本里有 ds_mcp.py",**漏掉 key 照样绿**
    (→ test_07 逐条比 args);③ 登记层自己没有任何测试无条件 import 它 ⇒ 它若在模块层
    import mcp,装了 mcp 的机器永远绿、没装的永远 skip(→ 扫描名单扩到 server 层 + 地基四模块)。
  - **实现面零 BLOCK**:29 个包装函数的**完整源码(含函数体)**逐字节相同(快照闸只比
    name+schema+description,函数体是它的盲区,我单独机械核过);`build()` 从环境变量取值
    与旧 `_run_mcp()` 一字不差(含 `DS_ORGANIZE_ROOTS` 用 `os.pathsep` 切分的 Windows 语义)。
- arbitrated verdict (主裁): **PASS(代码面),但本单不因此算完。**
  > 依据:搬运本体经逐字节核对无行为变化;五条闸先红后绿、红检有据;三道硬闸全走
  > (闸① `git diff 59ec15b -- <六份判卷文件>` = 空;闸② 亲跑三套;闸③ 亲读 diff)。
  > **保留的孤判断**:三腿有两腿给 PASS、只有 submimo 给 BLOCK,但 submimo 那两条
  > (eval 退化)是真的,我采纳了 —— **全票 PASS 不降低我自己的标准,孤腿 BLOCK 才是信号**。
  > **不算完的理由**:本单唯一"能过审还是错"的形态(存量机器 config 没更新)在仓库外,
  > 任何判据都够不到。见下面的验收断点。

## 验收断点(未完成,必须有人做)

1. 机主两台 Windows(公司 `F:\AI\OpenDesign` / 家里 `D:\AI\OpenDesign`)各:
   `git pull` → **重跑 `bin\install.ps1`**(或只跑 `bin\ds_merge_config.py` 合配置)→ 重启 gateway。
2. 在对话里问一句"有什么待办" —— **能返回 = 29 个工具真的通了**;
   这是「在使用现场验证」那条规矩要的"运行中的目标自己回显",盘上文件对不算数。
3. 万一忘了第 1 步:助手会一个工具都调不到,但 gateway 日志里现在会有报错桩的原话
   指向"重跑装机脚本"(这正是 F1 修的东西)。

## 收货第 1 轮:panel 之前那一轮的两条(08-03 凌晨,均已修)

> 合并时从 main 侧的存档版本保留下来的完整理由 —— 上面 `派给:` 那格只写了
> 「自身错误 2 处」,把**为什么**压没了,而这两条的理由本身有复用价值。

  - **F1(已修)新文件模块说明太薄** —— 一句话 docstring,全仓惯例是把"为什么"写进去。
    `ds_mcp.py` 尤其不能这样:**它是全项目唯一被用户 config 钉死的文件**,
    改它的路径/参数会让所有已装机器的助手失效,而用户不是程序员、自己修不好。
    已把警告写进文件头(含"为什么不让业务模块自己当入口" —— 那会留下
    「入口 ⇄ 自己的 server」自环,我实测验证过)。**根因又是我的任务书没写。**
  - **F2(已修)`-> FastMCP` 是悬空注解**(模块层没 import FastMCP,靠
    `from __future__ import annotations` 不求值)。改成 `TYPE_CHECKING` 块,
    运行期仍不 import mcp(承重墙),但注解不再指向不存在的名字。


## Accepted deviations

- **`_find_cycles` 是 DFS 单遍枚举**,理论上可能漏报某些非树环。它是上一单留下的工具,
  本单没动它 —— 但"环归零"这个结论的强度以它为上限。记在账上,不在本单修。
- **`subglm` 腿没跑成**(额度),full lane 实际是三腿而非四腿。已读其日志确认是环境问题;
  另外三腿覆盖面(尤其 subkimi 的六条)足够,不为此重跑。
