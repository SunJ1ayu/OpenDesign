# Verify: config-merge-keeps-brain

- Date: 2026-08-06
- Verdict: PASS(代码面;真机验收欠机主)

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [x] build passes(纯 python/PowerShell,无构建)
- [x] tests pass(仓库级总跑全绿;本单判据 9 条)
- [x] no secrets / unsafe ops(合并前照旧备份 TARGET.bak-<时间戳>)

## Review

- lane: full
  > 理由:这段代码**写的是机主自己机器上的 nanobot 配置**,而且跑在装机/更新那条路上 ——
  > 同一个文件 07-13 就崩过一次真机装机(模板结构与脚本脱节)。我在 Linux 上验不了
  > Windows 真机,判据只能证明逻辑对;失败形态是"他的助手起不来",代价由他承担。
  > 改动本身是把行为**收紧**(不再覆盖已有配置),但收紧写口也是写口。
  > **碰了新写口 / 权限 / auth / 钱 / 数据一致性 → full,针孔再薄也不打折**(硬规矩,别在这降档)。
  > fast = 主+1,中等风险;self = 主自审(闸③ + 截图 + 全量回归),
  > 限纯前端/纯观感、后端一字未动、只新增已过审针孔的调用方。
- 派给: 主 agent 直接干 —— 改动约 20 行、判据已存在且我刚扩过,切碎外包比自己写贵。
- 规格自查(读腿之前落盘,全文在 scratchpad 的 my-review):
  最可能出事的地方是**"全新装机"的判定靠字段缺失** —— 如果 onboard 预写占位符,
  我会把占位符当成机主的选择保留下来,装完直接起不来。我当时没核实 onboard 的输出形状,
  如实写在了自审里。另一条:坏配置(端点已下线)现在会被一路保留,更新本来有机会修好它。
- 腿的花名册: `submimo=PASS subdeepseek=PASS subglm=off subkimi=PASS`
  (原样粘自 `logs/panel-config-merge.roster`;**进程 rc 不等于裁决** ——
  实际裁决是 submimo PASS / subkimi PASS / **subdeepseek NEEDS_MORE_INFO**。)
  > panel-review 收尾自己写这个文件(off / FAIL(rc) / 降级 都在里面)。
  > 08-06 立这条的理由:08-05 我在这里手写了"三条腿一致 PASS",而 Kimi 根本没出结论
  > (同一页第 90 行我自己还写着它没出报告)—— 手抄一份终端上的东西,抄错那次没人会发现。
- findings:
  - **subdeepseek 给的是 NEEDS_MORE_INFO**,卡在一个它无法证实的事实:
    「nanobot onboard 会不会写非空占位符」。**subkimi 去读了 nanobot 0.2.2 的源码**
    (onboard.py / loader.py / schema.py)把它解决了,**我逐条复核过源码,一致**:
    base URL 强制非空、未设字段落 `null` 而非 `""`、`modelPreset` 指向不存在的预设
    会让 gateway **直接拒绝加载** —— 最后一条正是我那层兜底存在的理由。
  - **subdeepseek 另两条是真的、已修**:① 回落逻辑**一条断言都没有**(删掉照样全绿)⇒
    补了 3 条(空串/null/悬空预设);② 悬空预设只回落模板默认会产出
    「模板的模型 @ 机主的端点」自相矛盾态 ⇒ 改成**优先用机主自己的预设**。
  - **subdeepseek LOW**:`install.ps1` 那句「直接回车 = 用 MiMo 默认」在新语义下撒谎 ⇒ 已改。
  - submimo/subkimi 另指出 docstring 过时 ⇒ 已改。
  - **我自审就写下的那条最可能出事的地方**(占位符),正是三腿分歧的焦点 ——
    自审提前把它标出来,让这一轮的争论有个明确落点。
  > 只写发现。腿的身份/降级不在这儿抄第二遍:日志自带身份牌(降级横幅 + 视野边界),
  > 花名册在上一格,查工件不查自述。
- arbitrated verdict (主裁): **PASS(代码面)**。两腿 PASS、一腿 NEEDS_MORE_INFO,
  而它卡住的那个事实我已亲自读源码证实(不是采信另一条腿的转述)。
  它提的两条实质问题已修并补了判据(修复前 1 处红)。**欠真机**:
  Windows 上重跑一次合配置,回车不填 ⇒ 大脑仍是机主自己选的那个。
  > **归档时这一条和顶部的 `Verdict:` 都不许还是占位符**,`track-guard` 规矩3 会挡;
  > 没归档但已经合并上线的,`track list` 会打 ⚠️(stage-timer 就这么漏了两个月)。

## Accepted deviations

- **不探活端点**:端点已下线时配置会被一路保留(更新本来有机会"修好"它)。
  离线脚本探活要联网,而且"好心覆盖端点"正是这一单要治的病。端点坏了 nanobot 在聊天时
  会报可见错误 —— 机主看得到、会反馈,和"静默变笨"不是一回事。
- **`apiKey` 仍一律写成 `${DS_LLM_KEY}`**(既有行为,非本单引入):机主若把字面 key
  直接写进 config(流程外),重合并会静默改成环境变量引用。记着。
- **判据全在 Linux 上跑**,这段代码只在 Windows 装机/更新时执行;PowerShell 侧的
  传参/路径/编码只有真机能验。同一文件 07-13 崩过一次真机装机 —— 所以这单的真机验收不是形式。

---

## 归档说明(2026-08-10)

- 无机器证据:本单完工于 `runlog` 收据机制上线(2026-08-08)之前,判据结果是我手工转述进
  上面正文的。**不补跑也不追认** —— 今天补跑出来的收据对应今天的代码,证明不了当时那一遍。
- **归档时真机验收仍未做**,已移交 `docs/accept-0.81.0.md` **D 组**(重装不会把选的大脑冲掉)。
  归档 = 「我这边判完了」,**不等于**「已在机主机器上验过」。
