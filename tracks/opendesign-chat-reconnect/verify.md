# Verify: opendesign-chat-reconnect

- Date: 2026-08-04
- Verdict: **PASS(代码/判据面)—— 欠真机**。三份判据全绿(O1 15/15、O3+O4 36/36、
  O2 端到端 23/23),全量回归见下。**欠**:① 只有机主能做的真机冒烟(聊着天
  `start.ps1 stop` 再起,看它自己回来);② full lane 四审尚未跑(见下面 findings 末尾)。

> Panel hook — 软判断(correctness/security/edge/spec-drift)走 panel-review:
> 主 agent 先独立审并落 findings,再跑 panel-review 的全部评审腿,主 agent 主裁。
> build/test 跑通是机械检查。

## Mechanical checks

- [x] build passes —— `npm --prefix web run build` ✓,dist 已随提交入库(机主机器免 Node)。
      `npx tsc --noEmit` 无错。
- [x] tests pass ——
      - O1 `test_chat_reconnect.mjs` **15/15**;
      - O3+O4 `test_chat_transcript.mjs` **36/36**(含全部老用例,零退化);
      - O2 `tests/e2e/chat_reconnect.e2e.mjs` **23/23 ALL PASS**;
      - 协议冒烟 `test_ws_protocol_smoke.py`(活 gateway)**OK**,不是 SKIP;
      - **python 全量 `python3 -m unittest discover -s tests`:866 passed / 0 failed
        /14 skipped(199s,EXIT=0)**;
      - **e2e 总跑 `tests/e2e/run-all.sh`:32 PASS / 0 FAIL / 2 SKIP**
        (2 SKIP = 需要活 gateway 的那两条,脚本如实报数,**SKIP 不算通过**)。
      > ⚠️ 记一条工艺坑:`python3 -m unittest ... | tail -4` 会把汇总行冲掉
        (ds_web 的 HTTP 日志也走 stderr、排在汇总之后),而且**管道的退出码是 tail 的**,
        不是 unittest 的 —— 拿它当"全绿"依据是假绿。要整段落盘再 grep,并单独回显 `EXIT=`。
- [x] no secrets / unsafe ops —— 新增模块零 IO / 零依赖 / 零 DOM;前端只多了两个
      读接口调用(`/api/chat/sessions/<key>/thread`,**已过审的既有针孔**,本单没开新写口)。
      抓包存档里的工具返回**整段剔除**(仓库是 public,业主档案不进仓)。
      闸③ 亲读 diff:无符号链接、无 `create mode 120000`。

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
  - **返工记账(唯一账本就是这一格)**:执行腿**自身错误 0 处 / 返工 0 轮**。
    交货只有一个新文件、判卷零改动、三闸全过;它还主动答对了任务书里那道题
    (§4 里最容易做反的是"别把 ws 握手的 401 误判成口令失效"),
    并指出一处判据覆盖空隙(没验省略 `rand` 时用默认随机源)—— 属实,判为
    API 便利性而非行为规格,记账不补。
    **主 agent 事后改它的代码 0 行。**
- 规格自查(读任何 panel 输出之前答的):
  **本单规格已经被证伪过三次,而且三次都不是 panel 抓的** —— 这一格今天特别实在:
  1. 我写"从按下发送到出第一个字界面是死的" ⇒ **错**,三点动画早就有(connect-ux 做的)。
     我从"事件被忽略"推到"用户没反馈",中间隔着一个我没去看的渲染分支。
  2. 我写历史端点是 `/api/chat/thread/<id>` ⇒ **错**,真实是
     `/api/chat/sessions/<sessionKey>/thread`,而我自己的 e2e stub 模糊匹配把它盖住了。
  3. 我的 attach 断言**写反了**,正确实现会红、硬编码假 id 的错实现反而绿。
  **规格还可能错在哪(尚未证伪)**:对账时"哪条是本地独有"用的是**文本+角色**的启发式,
  不是身份匹配。它在"同一句话说两遍"和"服务端快照更早"两种情况下会判错。
  怎么发现:真机上重复发同一句话再断线,看有没有气泡消失或重复。
- findings(主 agent 独立审 + 亲跑判据;**执行腿自述一概不作数**):
  - **F1(已修)自愈重连会先把本地对话清空** —— effect 每次重跑都
    `setTranscript(emptyTranscript)`,于是断线瞬间发出、服务端没记上的那句先没了,
    后面的对账再也补不回来(它只存在于本地)。**判据 ⑧ 抓到的,不是我读代码读出来的。**
  - **F2(已修,判据自己的)e2e stub 时序错**:先 `emit(attached)` 再置
    `__threadReady`,而 emit 是同步的、客户端在里面同步发起拉历史 ⇒ 读到的还是 false。
    判据 ⑦ 因此红过一轮 —— **红的是夹具不是实现**,按规矩先查了才改。
  - **F3(已修,差点自己造假绿)**:我一开始让重连中也渲染 `.chat-meta`,
    而那正是 e2e 判"已连接"的标志 ⇒ 界面在撒谎说已连接,判据也会被我自己骗过。
    改成重连中不渲染它,并让重连与已连接**走同一条渲染路径** ——
    这样"断线前的气泡还在"是结构性的,不靠自觉。
  - **F4(记账不修)对账的身份判断是启发式**(文本+角色)。真身份要把信封的
    `turn_id` 存进本地 `ChatMessage`,那是另一单。见 design.md「判为成立但本单不做」。
  - **F5(记账不修)"气泡还在"不等于"消息送到了"** —— 本单不做自动补发(非目标),
    也不加"未送达"角标:服务端历史里没有**不能**证明没送达(快照可能更早),
    标错比不标更伤。**列进真机待验。**
  - ⚠️ **full lane 的四审(panel-review)尚未跑** —— 本单 lane 是 full,这一步是硬要求,
    不跑不算收口。**下一次接手先跑它**,并在这里如实记少了哪条腿
    (智谱余额未充,预计仍是三腿)。
  > 腿死了/降级了不用在这里再抄一遍:08-03 起每份评审日志**自带身份牌**
  > (降级横幅 + 视野边界),查日志不查自述。这里只写发现,别搞第二份手填拷贝。
- arbitrated verdict (主裁): <...>
  > **归档时这一条和顶部的 `Verdict:` 都不许还是占位符**,`track-guard` 规矩3 会挡;
  > 没归档但已经合并上线的,`track list` 会打 ⚠️(stage-timer 就这么漏了两个月)。

## Accepted deviations

- <接受的非关键偏差 + 原因 + 影响范围,或 None>
