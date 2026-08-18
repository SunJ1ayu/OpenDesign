# Design: e2e-gateway-dependency

- Change: e2e-gateway-dependency
- Status: draft

- 规划双出: **不适用** —— 不是新写面。改的是两条 e2e 的前置条件,方向唯一
  (仓里已有先例:`chat_image.e2e.mjs` 就是 stub 掉 ws/bootstrap 的那条)。

## Approach

两条 e2e 在 `page.goto()` **之前**各加一段:

```js
// 让 bootstrap 回 401 ⇒ connection.ts:93 抛 PasswordRejected
// ⇒ reconnect.ts:88 判定 kind:"login" ⇒ ChatPage:753 渲染连接卡。
// 这正是这两条 e2e 一直想要的状态,此前它们靠"机器上恰好有个会拒口令的 gateway"白拿。
await page.route("**/api/chat/bootstrap", (route) =>
  route.fulfill({ status: 401, contentType: "application/json", body: "{}" }));
```

**为什么拦 bootstrap 而不是 stub WebSocket**:连接卡的触发条件是 `PasswordRejected`,
而它**唯一**的来源就是 bootstrap 的 401(`connection.ts:93`)。stub WebSocket 要多造一个
假 ws 底座(`_ws-stub.mjs` 那一套),而且 ws 根本不在这条因果链上 —— 拦 bootstrap 是
**正对着因果**的最小干预。

## Key trade-offs / risks

- **风险一:改完可能"永远绿"**(判据失去咬合力)。这是改判据最该怕的事。
  ⇒ 必收的红检:把连接卡的 `data-ui` 改名(变异),两条 e2e 必须当场红;还原后回绿。
- **风险二:有 gateway 的机器上会不会反而坏**。`page.route` 拦在浏览器侧,
  优先于真实网络 ⇒ 有没有 gateway 都走同一条路。**要跑两遍证明**(无 gateway / 有 gateway)。
- **取舍:不改产品**。未连接态的产品行为已探针实测正确(见 proposal)。
  本单只让判据问对问题,不动被判的东西。
- **文件头那句话必须一起改**。两条 e2e 的头都写着「无 gateway」,那句话是这次因果被
  误读五天的源头之一(我自己今天也被它带偏过一次,先判成了产品 bug)。
  **改了行为不同步改描述它的注释 = 08-18 已经栽过一次的老坑。**
