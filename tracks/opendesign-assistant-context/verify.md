# Verify: opendesign-assistant-context

- Date: 2026-08-04
- Verdict: <PASS | BLOCK | NEEDS_MORE_INFO>

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [ ] build passes
- [ ] tests pass
- [ ] no secrets / unsafe ops

## Review

- lane: **self**(开工前填)
  > 硬触发器逐条对过:**没有**新写口(`append_change`/`set_due_date`/`set_change_status`
  > 签名与语义一字不动)、没有权限/auth/钱面、不动档案格式 ⇒ 不触发 full。
  > 改的全部是 `workspace/AGENTS.md` 里的**自然语言职责说明**。
  > 先例:T6 在 due-picker 里就预判成 self(「改的是工具 docstring/文案,不是写口本身」);
  > due-writer 那单同形状,也是 self。
  > ⚠️ **但 self 在这单比平时弱**:没有代码断言能焊住"说明书改了会不会把别的行为带跑",
  > 唯一的护栏是既有考卷的基线成绩 —— 所以基线成绩必须**跑满、逐题对**,不许只看总数。
- 派给: **主 agent 亲自**(开工前填)—— 本单的产出是**两段中文规格**(契约措辞)和
  **两份考卷**,两样都是不可外包的那一类:oracle 铁律禁止外包;而契约措辞就是规格本身,
  外包等于让执行腿定规格。判卷要不要起服务:**不要**,但要网络 + MiMo key(考卷真调 LLM),
  这也是 codex 腿跑不了的形状(沙箱禁网)。
- 规格自查(读任何 panel 输出之前先答):
  **如果我的规格本身错了,会错成什么样?** 两处最可能:
  ① **时间锚点的"问一句"门槛定错**——我定的是「有相对期限 **且** 有迹象不是刚发生的」
  才问。要是门槛太松,助手每次贴记录都追问一句,机主天天被烦;太紧则该问的不问,
  继续静默错一周。**考卷两题都接不住这个**(问了之后照样能答对日期,判绿)⇒
  只能靠真机观感,已列进下面真机待验。
  ② **"冲突"的定义是我编的**——我按「指同一处东西、要求不一样」定义。真实场景里
  业主常常是**补充**而不是推翻(「大理石用蓝色」+「蓝色要哑光」),我这条定义会不会
  把补充也判成打架?考卷里只有"明确反了"和"完全无关"两个极端,**中间地带没考**。
  ⇒ 已知缺口,写进 accepted deviations,靠真机反馈补题。
- findings:
  - <...>
  > 腿死了/降级了不用在这里再抄一遍:08-03 起每份评审日志**自带身份牌**
  > (降级横幅 + 视野边界),查日志不查自述。这里只写发现,别搞第二份手填拷贝。
- arbitrated verdict (主裁): <...>
  > **归档时这一条和顶部的 `Verdict:` 都不许还是占位符**,`track-guard` 规矩3 会挡;
  > 没归档但已经合并上线的,`track list` 会打 ⚠️(stage-timer 就这么漏了两个月)。

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>
