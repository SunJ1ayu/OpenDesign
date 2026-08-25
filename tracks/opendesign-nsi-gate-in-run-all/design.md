# Design: opendesign-nsi-gate-in-run-all

- Change: opendesign-nsi-gate-in-run-all
- Status: draft

> Panel hook — 仅当这是真·开放架构分叉(多个站得住的方向、风险=隧道视野)时,
> 先跑 `panel-explore`,把方向谱折叠进这里。否则直接写方向就行。
> 主 agent 在读任何 panel 输出之前,先落自己的方向(反锚定)。

- 规划双出: <日志路径 | 不适用:____>
  > **只剩一个触发条件:新写面 / 开放方向且这单我自己干**(动档案格式、写口语义扩张、
  > 新增参数……即 `decision.json` 的 `impact.factors` 会含 `new_write_surface` 的同一批面)。
  > **"要外包给执行腿"那半句 08-06 退场** —— 它升级成了 `delegate-codex --attack-log`:
  > 派活时给不出攻题记录就发不出去,不再靠我在这一格里自评(08-05 我就是在这格里
  > 用一句括号把它绕过去的)。
  > 做法:主 agent **先落盘**,再让 `gpt-5.6-sol` 对**同一份需求**独立出一版
  > (明令不许读本 track 的工件),然后对差异。抓的是**"我以为理所当然"的地方** ——
  > 那正是"我出方案、它来审"照不到的死角(审查只会在我的框子里挑毛病)。
  > 史料:08-02 due-writer 单它点破了我判卷题的一个洞(`fef253c`);
  > 08-06 delegate-entry 单它点破三处(攻题记录会过期 / 闸①没给闸③底账 /
  > 红检没区分"红在 build 上")—— 两次都是**结构性的洞,不是措辞**。

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
