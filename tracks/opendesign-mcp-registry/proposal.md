# Proposal: opendesign-mcp-registry

- Date: 2026-08-02
- Status: open(**方向未定,先 panel-explore**)

## Goal

把 29 个 MCP 工具的**注册层**从三个业务模块里分出来,消掉全仓 4 个循环依赖里的 3 个。
**方向尚未选定** —— 见 design.md:一条硬约束把方案空间整个改写了。

## Motivation

`opendesign-structure-debt`(第①②刀)的判据首跑证实:全仓 **4 个循环依赖**
(主 agent 人肉只看出 2 个),其中 **3 个同根因**:

| 环(归一化) | 反向边在哪 |
|---|---|
| `ds_adopt ⇄ ds_organize` | `ds_organize:365`,MCP 工具登记处 |
| `ds_intake ⇄ ds_organize` | `ds_organize:346`,MCP 工具登记处 |
| `ds_lint ⇄ ds_tools` | `ds_tools:1369`,`_run_mcp()` 内 |

成因一致:`ds_organize` / `ds_tools` / `ds_refs` 三个**干活的模块**同时兼职当
**工具登记处**(分别 7 / 17 / 5 个 `@server.tool()`),登记处要反向 import 别的业务模块
→ 成环,只能靠"把 import 藏进函数里"绕开。

顺带收益:`ds_tools.py` 1537 行里约 170 行是登记壳,分出去能瘦一大截。

## ⚠️ 硬约束(开工前查出来的,它改写了方案空间)

**这三个不是普通模块,是三个独立进程的入口。**
`~/.nanobot/config.json` 里写死:

```jsonc
"design-studio":          { "args": ["${DS_ROOT}/bin/ds_tools.py"] },
"design-studio-organize": { "args": ["${DS_ROOT}/bin/ds_organize.py"] },
"design-studio-refs":     { "args": ["${DS_ROOT}/bin/ds_refs.py"] },
```

而**那份 config 在用户的 `%USERPROFILE%\.nanobot\` 下,`git pull` 更新不到**
(装机时拷过一次)。`bin/start.ps1:77` 已经为同一类问题写过告诫:
「AGENTS.md/SOUL.md/skills **只有装机时拷过一次**……改了契约不重装,
运行中的助手看到的还是老版本」。

⇒ **只要 `bin/ds_tools.py` 不再是可直接运行的 MCP 入口,用户机上的助手工具就全废,
而且 `git pull` 修不好。** 这正是「盘上和运行时对不上」那类事故(一周内栽过两次:
GLM 抢购脚本、gateway 6.8/6.10)。

**这条约束不是"注意事项",是选型的第一位输入。**

## 真问题(第一性)

- 用户原话:「我们现在每一个模块是不是解耦的 每一块代码会不会很大 适不适合做全局的一个review」
  (08-02,与第①②刀同源)。第①②刀交付并真机验收后,他说「继续」。
- 真正要解决的是:**以后改这几块时会不会牵一发动全身**。不是审美。
- 我在这中间翻译了什么:把"解耦"翻译成"消掉循环依赖 + 让胖文件瘦下来"。
  **这个转译可能是错的** —— 环本身不影响运行(它们现在跑得好好的),
  真正的成本是"改动时的心智负担",而那东西没有直接度量。
  ⇒ **值不值得做,本身就是 panel-explore 要问的问题之一;
  「不做」必须是台面上的候选,不能只当礼貌性陪衬。**

## Scope(待 panel-explore 后定稿)

- in: 消掉 3 个登记处造成的环
- in: **保住入口契约**,或者证明"改 config + 两台 Windows 重装"这条路代价可接受
- in: 判据必须能证明"三个 MCP server 仍起得来、29 个工具一个不少、名字/参数一字不差"

## Non-goals

- 不改任何工具的**行为、名字、参数、docstring** —— 助手的行为面一个字不动。
  (docstring 是喂给模型的规格,改它等于改产品行为,不是重构。)
- 不合并三个 server 成一个(那会动 config 里的 server 名,是更大的一单)。
- 不动第①②刀拆好的 `ds_taxonomy` / `ds_openfolder`。
