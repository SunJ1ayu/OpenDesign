// e2e 的 WebSocket 替身**底座**(2026-08-06 抽出来的)。
// 文件名带下划线开头 = 不是场景文件,run-all.sh 的 *.e2e.mjs 通配扫不到它。
//
// 为什么要有这一份:
//   `chat_reconnect.e2e.mjs` 与 `chat_image.e2e.mjs` 各手搓过一份 ws 替身,
//   同一段 readyState 常量抄了两遍 —— 然后**同一处漏了两遍**,08-05 隔 39 分钟
//   修了两次(6dd21cb / 4bc508a),占当天三次判据返工里的两次。
//   漏掉 `WebSocket.OPEN` 的后果不是"少个字段":实现里标准的
//   `ws.readyState !== WebSocket.OPEN` 会读到 `undefined` ⇒ 恒判"没连上" ⇒
//   一条消息都发不出去,红的是判据不是实现 —— 替身缺了它所替代的那个 API 的一部分,
//   等于在问一道现实里不存在的题。
//
// 治法:常量**不抄、派生**。e2e 跑在真 chromium 里,`window.WebSocket` 就是真的,
//   直接从它身上枚举出所有数值常量拷过来。这样"抄不齐"从"我要记得"变成结构上不可能。
//   ⚠️ 故意**不**写成"凡替身必须加一条照真 API 抄齐的断言":手列清单的强度只等于
//   我当时想得起来的字段,和 `--protect` 漏列一个就是那个洞,是同一个病。
//
// 用法(两步注入,顺序要紧):
//   import { WS_STUB_BASE } from "./_ws-stub.mjs";
//   await page.addInitScript(WS_STUB_BASE);   // 先装底座 -> window.__BaseStubWS
//   await page.addInitScript(STUB);           // 再装本场景的替身,extends 它
//
// 注:`addInitScript` 是把函数**源码**送进页面执行的,闭包变量带不过去 ——
//   所以底座只能通过 `window.__BaseStubWS` 交接,不能直接 import 进场景的 STUB 里。

/**
 * 页面初始化脚本:在真 WebSocket 之上派生出替身底座 `window.__BaseStubWS`。
 * 子类负责行为(连上、send、协议回包),底座只负责"长得像个 WebSocket"。
 */
export const WS_STUB_BASE = () => {
  const RealWS = window.WebSocket;
  if (typeof RealWS !== "function") {
    throw new Error("_ws-stub: 页面里没有真 WebSocket,底座没法派生常量");
  }

  // 真 WebSocket 的 readyState 常量既在**类上**也在**实例上**
  // (`WebSocket.OPEN` / `ws.OPEN`,都是 1);实例那份来自原型。
  // 挑法有两道过滤,都靠结构不靠列清单:
  //   ① 值是数字      —— `readyState` / `url` 这些在原型上是 getter(没有 value),自动出局;
  //   ② 可枚举        —— WebIDL 常量是 {value, writable:false, enumerable:true};
  //                      而函数自带的 `length`(元数,也是个数字!)是不可枚举的。
  //                      08-06 实测:漏了第②道,`Object.assign` 会去写 class 的只读
  //                      `length` 而当场抛 TypeError ⇒ 底座整个装不上。
  const numericOwn = (obj) => {
    const out = {};
    for (const k of Object.getOwnPropertyNames(obj)) {
      const d = Object.getOwnPropertyDescriptor(obj, k);
      if (d && typeof d.value === "number" && d.enumerable) out[k] = d.value;
    }
    return out;
  };
  const CLASS_CONSTS = numericOwn(RealWS);
  const PROTO_CONSTS = numericOwn(RealWS.prototype);

  // 派生要是派了个空(浏览器换了实现方式),必须当场炸,不许静默退回"什么都没有" ——
  // 静默的结果正是上面那条 08-05 的病:替身看着好好的,判据整份问错了题。
  if (!("OPEN" in CLASS_CONSTS) || !("OPEN" in PROTO_CONSTS)) {
    throw new Error("_ws-stub: 从真 WebSocket 派生 readyState 常量失败(类/原型上没找到 OPEN)");
  }

  class BaseStubWS {
    constructor(url) {
      this.url = url;
      Object.assign(this, PROTO_CONSTS);   // 实例上那份常量
      this.readyState = BaseStubWS.CONNECTING;
    }
    /** 把一个协议事件推给页面(等价于服务端发来一帧)。 */
    _emit(o) { this.onmessage?.({ data: JSON.stringify(o) }); }
    send() { /* 子类实现 */ }
    close() { this.readyState = BaseStubWS.CLOSED; }
  }
  Object.assign(BaseStubWS, CLASS_CONSTS);  // 类上那份常量

  window.__BaseStubWS = BaseStubWS;
  window.__wsStubConsts = { klass: CLASS_CONSTS, proto: PROTO_CONSTS };
};
