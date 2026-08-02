# Verify: opendesign-mcp-registry

- Date: 2026-08-02
- Verdict: <PASS | BLOCK | NEEDS_MORE_INFO>

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [ ] build passes
- [ ] tests pass
- [ ] no secrets / unsafe ops

## Review

- lane: **full,不打折**
  > 硬触发器直接命中:动的是**助手能力的全部来源**(三个 MCP server 的 29 个工具),
  > 且牵连**部署面**(用户 `~/.nanobot/config.json` 里写死的入口路径,`git pull` 修不到)。
  > 搞砸的表现不是"某个功能不好用",是**用户下次用的时候助手什么都不会做了**。
  > 这一条在方向定稿前就能确定,不必等 explore。
  > **碰了新写口 / 权限 / auth / 钱 / 数据一致性 → full,针孔再薄也不打折**(硬规矩,别在这降档)。
  > fast = 主+1,中等风险;self = 主自审(闸③ + 截图 + 全量回归),
  > 限纯前端/纯观感、后端一字未动、只新增已过审针孔的调用方。
- 派给: **待方向定稿后确认;当前预判 = `codex -m gpt-5.6-sol`(升档,不用默认的 5.5)**
  > 理由:delegate 分档表里"架构敏感 / 跨模块判断"就该升 `gpt-5.6-sol`,而本单
  > 三个方向(M 反转入口 / R 改 config / S 重分配归属)差别正在架构判断上。
  > 轴(判卷要不要起服务):工具表快照与入口可运行闸**不需要开网络端口**,可外包;
  > 但若方向选 R,验收要碰 config/装机,那部分**主 agent 自己做,不外包**
  > (外部执行腿一律不许碰部署面)。
  > ⚠️ 正式派活前重开 `delegate` 抽屉,不许凭这行预判直接调参数。
- 规格自查(读任何 panel 输出之前先答):<如果规格本身就是错的,会错成什么样、我怎么发现?
  panel 只验"实现合不合规格",验不了"规格对不对" —— 四腿齐 PASS 不等于题是对的。>
- findings(**主 agent 独立审,读任何 panel 输出之前落盘;2026-08-03 凌晨**):
  - **F1(已修)新文件模块说明太薄** —— 一句话 docstring,全仓惯例是把"为什么"写进去。
    `ds_mcp.py` 尤其不能这样:**它是全项目唯一被用户 config 钉死的文件**,
    改它的路径/参数会让所有已装机器的助手失效,而用户不是程序员、自己修不好。
    已把警告写进文件头(含"为什么不让业务模块自己当入口" —— 那会留下
    「入口 ⇄ 自己的 server」自环,我实测验证过)。**根因又是我的任务书没写。**
  - **F2(已修)`-> FastMCP` 是悬空注解**(模块层没 import FastMCP,靠
    `from __future__ import annotations` 不求值)。改成 `TYPE_CHECKING` 块,
    运行期仍不 import mcp(承重墙),但注解不再指向不存在的名字。
  - **零 BLOCK**:闸①逐字节空;闸③无符号链接、config 模板只动该动的 3 行×2、
    **29 个包装函数完整源码(含函数体)逐字节相同**(这一条是我判据的盲区,
    快照只比 name+schema+description,单独机械核的)。
  - **我自己知道这套判据挡不住什么**:仓库全绿 ≠ 用户机上那份已生成的 config 已更新。
    **判据在仓库里,风险在仓库外。** 只能靠真机验收(见 tasks.md 第 3 步)。
- arbitrated verdict (主裁): <...>

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>
