# Verify: opendesign-workbench-p1

- Date: 2026-07-08(开单) / 2026-08-04(归档结论)
- Verdict: **ARCHIVED-SUPERSEDED —— 部分交付后路线被取代,不是验收通过**

> ⚠️ 这条结论是 08-04 补写的,补写时距最后一次动它(07-10)已 25 天。
> **它不是「PASS」**:本 track 的成功标准(见 proposal「成功标准」)从没被完整验过,
> 也不该再去验 —— 那份标准描述的产品形态在 07-10 就被用户否掉了。

## 为什么归档而不是继续做

07-10 用户在 Windows 真机看过 T4+T5前半 的聊天后,判定**聊天占 C 位与
「项目工作区,聊天只是输入入口」的定调不符**(原话记在 tasks.md「用户真机反馈」段),
拿 brief 去 Claude Design 出前端设计图,本 track 当场挂起。
此后 0.51 → 0.72 的前端是**照新图另起 track 重走的**,不是接着这条线做的。
挂起 25 天没有任何人回来捡 = 事实上已被取代;继续挂在 active 只是让
`track list` 每次都报一个假的「在做」。

## 交付了什么(已进主线,不随归档回退)

T0 协议基线快照 / T1+T2 ds_web 代理(9 条 oracle)/ T3 nanobot token 皮肤 + IA 重排 /
T4 聊天登录连接流(14 条 oracle + e2e 7/7)/ T5前半 聊天核心(17 条 oracle + e2e 6/6)。
逐条的 oracle 条数、red-check 结果、e2e 实跑记录都在 tasks.md 里,当时都跑绿过。

## 没做、且随归档转为独立欠账的

- **T6 断线自愈** —— 现状:`web/src/chat/ChatPage.tsx` 的 `ws.onclose` 直接落
  「连接已断开」+ 手动「重试」按钮;**没有指数退避自动重连,重连后也不 refetch
  补断线期间的缺口**。08-04 核过磁盘属实。
- **T5b** —— tool_hint / progress 事件降级显示(现为忽略,见 `transcript.ts` 顶部注释)、
  代码块高亮子集、链接 target。

已被别的 track 覆盖、**不再是欠账**的(08-04 逐条核过磁盘):
T7 会话列表 → 被「项目线程」(`chat/projectThread.ts` + 项目列自愈)取代,形态不同但需求已覆盖;
T8 Windows 物料 → `bin/start.ps1` 已顺手拉起 ds-web 8766;
T9/T10 dist+截图+全量回归 → 后续每个 track 反复做过。

## Mechanical checks

- [x] build passes —— **不适用于本次归档**:归档 commit 只移动 tracks/ 下的 markdown,
      零代码改动。已交付部分的 build/test 记录在 tasks.md 各条,且这批代码在此后的
      多轮全量回归里持续跑绿。**本次没有重跑,不谎称重跑过。**
- [x] tests pass —— 同上。
- [x] no secrets / unsafe ops —— 归档 commit 为纯文件移动,已 `git status --porcelain` 确认。

## Review

- lane: **self**(归档决定本身:零代码改动、零新写口、零权限/钱/数据一致性面。
  按 CLAUDE.md 硬触发器,不触发 full)
- 派给: **主 agent 亲自**(未外包。核「哪些欠账还成立」是逐条读磁盘代码,
  正是执行腿最容易靠自述糊弄的一类,不派)
- findings:
  - 主 agent 自审 08-04:**原 tasks.md 的剩余清单已过期**,直接照它捡活会重做
    三件已经做掉的事(T7/T8/T9)。⇒ 已在上面按「磁盘实测」重新分类,不照抄旧清单。
  - 主 agent 自审 08-04:归档不能默认「剩下的都不要了」。T6 是用户会真碰上的
    (合盖/断网后聊天卡在断开态要手点)。⇒ 已单独列为欠账,归档时口头交底给用户。
- arbitrated verdict (主裁): **ARCHIVED-SUPERSEDED**。归档 track,保留 T6 + T5b 两条欠账
  到下一个小 track;**不追认本 track 的 proposal 成功标准为已达成**。

## Accepted deviations

- **一份从未收口的 track 以「取代」结案**,而非 PASS/BLOCK。原因:它的验收标准
  随产品方向作废,强行套用只会产出一个假的 PASS 或一个误导性的 BLOCK。
  影响范围:仅本 track 的历史记录;已交付代码在主线上,不受此结论影响。
- 归档结论比最后一次动工晚 25 天,**中间那段时间 `track list` 一直把它显示成 active**。
  这是 08-04 新加的 ⚠️ 提示照出来的第一单,也是本条结论存在的原因。
