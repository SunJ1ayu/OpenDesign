# Proposal: e2e-gateway-dependency

- Date: 2026-08-18
- Status: open

## Goal

让 `frontend_p2_polish.e2e.mjs` 与 `todo_assistant.e2e.mjs` **不再依赖这台机器上有没有活 gateway**:
用 `page.route()` 把 `/api/chat/bootstrap` 拦成 401,页面就走到它们真正要测的登录态。

## Motivation

这两条 e2e **在默认总跑里长期红**,而红的原因与它们要测的东西无关。
今天(08-18)把因果彻底查清了,证据链如下:

| 条件 | 结果 | 收据 |
|---|---|---|
| 无 gateway | **2 FAIL**(等 `[data-ui="connect-card"]` 超时 10s) | 本 track `redcheck-A` |
| 有 gateway | **2 PASS** | 08-18 手跑,见 verify |

**因果**(读代码 + 探针实测,不是推断):
- 连接卡只在 `view.kind === "login"` 时渲染(`ChatPage.tsx:753`);
- 而进入 `login` 的**唯一**路径是 `reduceReconnect` 收到 `PasswordRejected`
  (`reconnect.ts:88`),其余失败一律 `scheduleRetry` 无限重连;
- `PasswordRejected` 只在 `/api/chat/bootstrap` **回 401** 时抛(`connection.ts:93`)。
⇒ **gateway 在跑但没口令 = 401 = 出连接卡;gateway 根本没起 = 连不上 = 一直重连,连接卡永不出现。**

所以这两条 e2e 的文件头写着「无 gateway——未连接态本身就是被测对象」是**错的**:
它们要的不是"没有 gateway",是"**有一个会拒绝口令的 gateway**"。

## 真问题(第一性)

- 用户原话:「你先继续把两条红和跳过的判据修了」。
- 真正要解决的是:**判据的绿不该取决于跑它的机器上恰好有没有起某个服务**。
  这两条一直红,人就会习惯"那两条本来就红",于是它们真正守的东西(连接卡的形状与交互)
  **失去了报警能力** —— 和没有这两条判据没区别。
- 我在这中间翻译了什么:**我一度把它翻译成"产品 bug"并向用户提了产品方案,那是错的。**
  探针实测显示未连接态的产品行为**完全正确**(8s 后出「连接不上,gateway 可能没在跑」
  + 「立即重试」按钮,`ChatPage.tsx:878`)。错的是判据的期望,不是产品。
  **这次转译差点让我去改一个没坏的东西。**

## Scope

- in: 两条 e2e 各加一段 `page.route("**/api/chat/bootstrap", 401)`,并改正文件头那句话。
- in: 证明改完之后**有无 gateway 都绿**,且**判据仍咬得动**(变异红检)。

## Non-goals

- **不改产品代码一个字**。未连接态的行为已经是对的,今天用探针看过了。
- **不塞进 `NEEDS_GATEWAY` 名单**。那等于默认少测两条,是把报警器关掉而不是修好。
- 不动 `reconnect.ts` / `connection.ts`:它们是断线自愈的核心,本单没有任何理由碰。
