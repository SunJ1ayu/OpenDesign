# Verify: opendesign-chat-reconnect

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

- lane: **full**(开工前填)。**看着像纯前端,但硬触发器的 auth 那一格被碰到了**:
  本单要改的正是「什么时候认定口令失效、什么时候清 localStorage 里的口令、
  什么时候把用户踹回登录框」这套判定 —— design.md C 段那条红字说的就是它
  (ws 握手 401 与 bootstrap 401 长得一样,判错的后果是每次正常重连都当口令失效)。
  另外 `markdown.ts` 是 XSS 铁律焊死的地方,本单要往那里加 `components.a`。
  **两条都够 full,针孔再薄也不打折。**
- 派给: **拆两半(开工前填)**——
  - **纯逻辑层 `reconnect.ts` = `codex -m gpt-5.6-sol`**(分层还账**第 7 单**;
    序号按交付版本号排,前六单见 [[model-tiering-trial]] 08-04 那节)。
    轴 = 判卷要不要起服务:O1 是 `node --test` 纯函数判据,**不起服务** ⇒ 可外包。
    升档理由:这是**策略判断**(退避/放弃/两种 401 的分界),不是机械搬运。
  - **接线层 `ChatPage` + O2 e2e = 主 agent 亲自**。判卷要真起 ds_web + chromium
    (codex 沙箱禁网跑不了),且这一半正好是 auth 判定所在,不外包。
  - 判据全部主 agent 亲写、先单独 commit;`--protect` 清单见 tasks.md。
  - **返工记账(本单交付时填,别再欠着)**:自身错误 ___ 处 / 返工 ___ 轮。
- 规格自查(读任何 panel 输出之前先答):<如果规格本身就是错的,会错成什么样、我怎么发现?
  panel 只验"实现合不合规格",验不了"规格对不对" —— 四腿齐 PASS 不等于题是对的。>
- findings:
  - <...>
  > 腿死了/降级了不用在这里再抄一遍:08-03 起每份评审日志**自带身份牌**
  > (降级横幅 + 视野边界),查日志不查自述。这里只写发现,别搞第二份手填拷贝。
- arbitrated verdict (主裁): <...>
  > **归档时这一条和顶部的 `Verdict:` 都不许还是占位符**,`track-guard` 规矩3 会挡;
  > 没归档但已经合并上线的,`track list` 会打 ⚠️(stage-timer 就这么漏了两个月)。

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>
