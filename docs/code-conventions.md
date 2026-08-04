# 本仓代码约定(派活任务书直接引用这一份)

> **这份文件的读者主要是执行腿**(codex / sub-Claude)。它们看不到本机的
> `/root/CLAUDE.md`,**风格约定不写进任务书就等于不存在**。
>
> **每一条都必须是从真实退货里长出来的**,不许凭"业界最佳实践"往里加。
> 每条后面的「出处」就是它的准入证明;出处失效即候删。
>
> 派活时的用法:任务书里写一句「遵守 `docs/code-conventions.md`」,不必抄条文。

## 1. 注释与 docstring 一律中文

模块头、函数 docstring、行内注释都写中文。全仓 23 个 `bin/*.py` 只有一个例外
(`ds_openfolder.py`,已是待修的残留,见第 2 条出处)。

- **出处**:track `opendesign-structure-debt` F2 —— 执行腿给新拆出的
  `bin/ds_taxonomy.py` 写了英文 docstring,全仓其余模块都是中文。当时判定
  「又一次是任务书的洞,不是它的错」。

## 2. 模块头 docstring 要写「为什么」,不只写「是什么」

一句话概括不够。模块头至少要交代:这个模块为什么单独存在、边界在哪(它**不**管什么)、
出自哪个 track。改动会波及已装机器的文件,还要把后果写在文件头。

- **出处**:track `opendesign-mcp-registry` F1 —— 新文件只有一句话 docstring。
  `ds_mcp.py` 尤其不能这样:**它是全项目唯一被用户 config 钉死的文件**,
  改它的路径/参数会让所有已装机器的助手失效,而机主不是程序员、自己修不好。
- **同一批的残留(2026-08-04 查这份约定时才发现)**:`ds_taxonomy.py` 和
  `ds_openfolder.py` 是同一个 commit(`4078c45`)拆出来的两刀,F2 只修了前者,
  **后者的英文一句话 docstring 一直留到今天**。教训:退货是按"找到的那一处"修的,
  同批产物要一起扫。

## 3. 搬运/拆分单:不许出现原文件没有的行

纯搬运(把代码从 A 挪到 B、0 行为改动)的单子,产物里多出来的任何一行都算夹带,
哪怕无害也要记账 —— 因为「逐字节比对」是这类单唯一的低成本验收手段,一旦允许夹带,
这个手段就没了。

- **出处**:track `opendesign-structure-debt` F3 —— 两个新模块都加了
  `from __future__ import annotations`,原文件没有。零行为影响,仍记账。
- ⚠️ **别把它读成「不许用 `from __future__ import annotations`」**:全仓 23 个
  `bin/*.py` 里 15 个都有这行,它在本仓是常规写法。**这条约束的是"搬运单"这个场景,
  不是这一行本身。**

## 4. 类型注解里的名字必须能解析

如果注解用到的类型模块层没有 import(常见于故意不在运行期 import 重依赖),
放进 `if TYPE_CHECKING:` 块,别靠 `from __future__ import annotations` 让它悬空。

- **出处**:track `opendesign-mcp-registry` F2 —— `-> FastMCP` 是悬空注解,
  模块层没 import `FastMCP`。修成 `TYPE_CHECKING` 块后,运行期仍不 import `mcp`
  (那是承重墙:不装 mcp 也得能跑),但注解不再指向不存在的名字。

## 5. 判卷文件(`tests/`、`e2e/`、各 `*_eval`)执行腿一律不许动

任务书会把它们逐个列进 `--protect`。这条写在这里只是为了让执行腿知道
**为什么**:判据由主 agent 写,弱模型最省力的过关方式是改考卷
(删断言 / 写死期望值 / 加 skip),所以「没动判卷」是收货的第一道闸。

- **出处**:`/root/CLAUDE.md` 的随身规矩,不是本仓特有。
