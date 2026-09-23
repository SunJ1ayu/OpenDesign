# Design: opendesign-release-09810

- Change: opendesign-release-09810
- Status: draft

> 实施前按 panel skill **4c** 检查目标到方案的翻译。只有一种方案、自报 low、Jev 低分都不免检;
> 新增关键行为/改变契约/难撤回的方案先做不同家族挑战,关键未知先实验,方向分叉才扩大探索。
> 主 agent 先落自己的方向,但独立腿不读本轮自审或同伴报告。局部可逆、契约已验证的修改可简写。

## Goal-to-design check

- 当前行为 → 拟改变的行为:<引用 proposal 用户原话,区分事实与我的推导;用户得到什么、付出什么>
- 检查深度与触发事实:<直接验证 / 最小实验 / 独立挑战 / 多方向探索;理由指向行为、契约与撤回代价,不是重复 low/high>
- 关键前提:<可证伪的主张 → 已有证据或最小实验;未知就写未知>
- 完全实现仍可能失败:<用户目标落空的具体场景,不只列实现漏洞>
- 独立意见与核实:<原始记录/实际家族、反例、核实、取舍;不适用时可省略>
- 未解决项:<能改变方向的未知先解决或改方案,不能只归入 accepted risk 后开工>

> 检查实际完成后,机器字段只写 decision.json 的 premise_attack.status/evidence;
> low 可以配 done,轻量路径仍可 not_required。文件存在不等于前提成立。

## Approach

<选定的技术方向>

## Key trade-offs / risks

- <关键取舍与风险>

## Alternatives considered

- <考虑过但没选的方向 + 为什么没选>

## Test strategy (oracle)

<怎么证明它对 —— 这是后面 verify 的判据,主 agent 拥有>

**这个 oracle 能被什么骗过?**

<不问"断言写没写",问"用户眼里的成功长什么样,我的断言离它差了什么"。
写下:断言全绿但结果仍然错,会错成什么样;以及那种错要靠什么才接得住
(真截图/真机/真返回)。史料:07-24 `columnCount==="3"` 全绿,实际正文被压成竖排。>
