# Verify: opendesign-todo-assistant

- Date: 2026-07-23 / 24
- Verdict: PASS

## Mechanical checks

- [x] build passes(`npx tsc -b` rc=0 · `npm run build` 成功 · dist 重建)
- [x] tests pass(全量 mjs **199/199** · **py 22/23**,唯一非 0 = `test_ws_protocol_smoke.py`
      rc=3 = **设计性 skip**(本机无 gateway;该文件本单未改动,非回归)·
      **e2e 九条全 ALL PASS**:`todo_assistant` / `todo_rail` / `todo_layout` /
      `todo_batch_space` / `duedate` / `frontend_p2_polish` / `frontend_p3_polish` /
      `cockpit` / `intake` —— 本单改了 App 路由,相邻 e2e 一条未跳)
- [x] no secrets / unsafe ops(零后端改动,唯一 Python 变更 = VERSION 0.37.0 → 0.38.0)

> ⚠️ **更正:前两单(todo-layout / todo-rail)verify.md 里写的「py 23/23」是虚的。**
> 当时的循环写成 `out=$(python3 … | tail -3); r=$?` —— 管道里 `$?` 取的是 `tail` 的退出码、
> 恒为 0,等于什么都没测。本单改用不带管道的写法才暴露。结论未变(那条 rc=3 是 gateway-off
> 的设计语义,且三单均未改动该文件),但**当时的证据强度被高估了**,在此更正。
> 与本会话其它几次是同一类错误:**验的是代理量,不是真东西。**

## 三硬闸

- **闸① oracle 逐字节 diff** → 整个 `tests/` 零改动;无符号链接。
  执行腿明确报告了它认为的 oracle bug 却**一个字节没动** —— 派活规矩执行到位。
- **闸② 亲跑** → 见上。
- **闸③ 逐行读 diff + 实机截图 + 定向探测** → 抓到四条,全部已修(`668c20a`)。

## Review

- lane: **full 四审**(路由改造是跨页面风险面;第三个 ChatPage 实例是本单最大未知)
- **实到 2 腿**:`subglm`(PASS)、`subdeepseek`(BLOCK);
  `subkimi` 会员额度用尽(403 usage limit)、`submimo` 23:18 后 45 分钟零字节静默死亡。
  按 AGENTS.md 单腿缺席不阻断,主审独立审到位。
  **工具教训**:判断某条腿"在思考"还是"已死",要看**日志最后修改时间**,不是看行数
  —— 本次两次误判、白等两轮。已记入 [[subkimi-moonshot-wrapper]]。

### 主审闸③ 抓到的(四条,两条到场的评审腿均未提)

- **[F1 · 实现真缺陷 · 截图才暴露 · 已修]** 原实现展开时一律隐藏 ask 区 → 未连接提交后
  整个右栏只剩一张连接卡,**用户刚打的字从画面上彻底消失**。执行腿辩护「字还在 DOM 里、
  收起一次能看到」**不成立:用户不知道要收起**。规则收敛为「ask 区只在已连接(聊天自己
  有输入框可用)时才让位」。
- **[F2 · 我的 oracle 是代理断言 · 已修]** 只验 `inputValue() === TEXT`,而它读隐藏元素
  照样返回值 → F1 那个缺陷能大摇大摆通过。已加 `isVisible()`。
- **[F3 · 我的 oracle 选择器缺限定 · 执行腿报出、我复现证实 · 已修]** 裸
  `[data-ui="connect-card"]` + `.first()` 恒定命中 home-pane 常驻的隐藏卡(定向探测实测
  页面上 2 张:home 隐藏 / rail 可见)。仓里 `frontend_p2_polish.e2e.mjs:113` 早有限定先例。
- **[F4 · 补线 · 已修]** 右栏 ChatPage 未接 `onTurnEnd` → 「记一下」后**同屏**待办列表不刷新
  (正是 hardening M5「聊完免 F5」治过的毛病,另两个实例都接了)。已接到既有 `onEdited`。

### panel findings 逐条裁决

- **[subglm MEDIUM · `connected` 单向置位]** → **拒(记为已知限制)**。依据:每个 ChatPage
  各自持有 `attempt` 并各自建 ws(`ChatPage.tsx:257` deps `[session, attempt, resume?.nonce]`),
  在别处登录不会让右栏自动连上;**但右栏会停在可见的 connect-card 上**,用户在那里连一次
  即可,**不存在"点发送毫无反馈"的静默失败**。掉线后 dispatch 进死连接时,`sendText` 返回
  false → ChatPage 把文本落回自己的 draft(`ChatPage.tsx:306-307`),**不丢字**。
  为此改 ChatPage 超范围且风险更高。
- **[subglm LOW · toast 定时器未受 active 门控]** → **采纳,已修(`352b4f3`)**。
- **[subglm LOW · 编辑态跨页存活]** → **采纳,已修(`352b4f3`)** + oracle 加断言钉住
  (开编辑框 → 切走 → 切回,编辑态已丢弃;而日期过滤这类纯展示态仍保留,两者刻意不同)。
- **[subglm LOW ·「展开对话 →」在展开态仍可见]** → **采纳,已修**(仅收起态渲染)。
- **[subglm LOW · 三实例 onTurnEnd 可能多次 bump dataEpoch]** → **接受,不改**。依据:
  取数 effect 有 `stale` 闭包守卫,结果正确;多一两次请求代价可忽略,加去抖会引入新时序面。
- **[subdeepseek BLOCK]** → **拒**。依据三条:①它列的两条 HIGH 在**自己的 Evidence 字段里**
  反复写着「无直接 bug」「符合设计」「当前实现正确」,结论与自身论据矛盾;②报告**退化**成
  同一条 LOW 的 18 份逐字复制(卡死);③它反复要求"需检查 `ChatPage.tsx` 中 dispatch 的
  消费实现"并**承认自己没读** —— 我读了:`ChatPage.tsx:304` 显式忽略 `nonce === 0`(初值安全)
  + 用 `dispatchedRef` 去重(不会重放),`:306-307` 发送失败把文本落回 draft(不丢字);
  它担心的三种情形均不成立。这是 [[panel-review-trust-calibration]] 已记录的
  "未读上下文上的自信误判"复发。

- arbitrated verdict(主裁):**PASS**。
  **本单四条真发现全部由主审闸③ + 截图 + 定向探测抓到,两条到场的腿一条未提**;
  而 subglm 补到三条我漏的行为对齐问题(toast / 编辑态 / 展开态按钮)——
  正是 panel 作为"盲点网"该有的价值,**不是通行证**。

## Accepted deviations

- **`connected` 单向置位**:见上裁决。已知限制;不静默失败、不丢字。
- **`variant="home"` 用在 320px 右栏**:执行腿理由成立(`column` 变体的登录卡藏在
  `ChatPage` 私有 `bannerOpen` state 后,外部够不着)。**已连接后**在窄栏里的对话流形态
  **无 gateway 测不到**,交装机看。
- **无 gateway 覆盖不到的三块**:真实发送/回复链路、「记一下」识别不出项目时是否追问
  (= agent 侧行为;前端只做到"不传项目前缀 + 文案提示带项目名")、`onTurnEnd` 刷新的
  端到端效果。**均交装机验收。**
- **panel 只到 2 腿**:kimi 额度用尽、submimo 静默死亡;主审独立审 + 截图 + 定向探测补位。
- **前两单 py 计数证据被高估**:见上方机械检查里的更正块。
