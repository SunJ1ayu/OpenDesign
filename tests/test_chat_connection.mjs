// T4 oracle:聊天登录/连接流(web/src/chat/connection.ts,纯逻辑层)
// 跑法:node --test tests/test_chat_connection.mjs(Node 22+,原生 strip-types)
// 依据 = docs/nanobot-ws-protocol.md(T0 实抓)+ design.md D-C2:
//   口令→localStorage;每次开 ws 前 bootstrap 新签一次性 token;
//   HTTP 401 透明重签一次;重签仍 401 = 口令失效弹回登录;
//   ws 地址用 ws_path+已知端口自拼,ws_url 只作参考。
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  ChatSession,
  PasswordRejected,
  PASSWORD_KEY,
} from "../web/src/chat/connection.ts";

// ---- 测试替身 ----------------------------------------------------------

function memStorage() {
  const m = new Map();
  return {
    getItem: (k) => (m.has(k) ? m.get(k) : null),
    setItem: (k, v) => m.set(k, String(v)),
    removeItem: (k) => m.delete(k),
  };
}

const jsonRes = (status, body = {}) => ({
  status,
  ok: status >= 200 && status < 300,
  json: async () => body,
});

// 记录型 fetch:handler(url, init, n) 按第 n 次调用出剧本
function recFetch(handler) {
  const calls = [];
  const fn = async (url, init = {}) => {
    calls.push({ url: String(url), init });
    return handler(String(url), init, calls.length);
  };
  fn.calls = calls;
  return fn;
}

class FakeWs {
  constructor(url) {
    this.url = url;
  }
}

const boot = (token, extra = {}) => ({
  token,
  ws_path: "/",
  // 故意给个"错误参考":自拼正确的话绝不会连到这里
  ws_url: "ws://evil.example:9999/",
  expires_in: 300,
  model_name: "mimo-v2.5",
  ...extra,
});

function makeSession({ handler, storage = memStorage(), port } = {}) {
  const fetchFn = recFetch(handler ?? (() => jsonRes(200, boot("nbwt_1"))));
  const opened = [];
  const s = new ChatSession({
    fetchFn,
    storage,
    wsFactory: (url) => {
      const w = new FakeWs(url);
      opened.push(w);
      return w;
    },
    randomId: () => "cid-fixed",
    ...(port ? { nanobotPort: port } : {}),
  });
  return { s, fetchFn, opened, storage };
}

const authHeader = (call) =>
  (call.init.headers ?? {})["Authorization"] ?? null;

// ---- 口令持久化 --------------------------------------------------------

test("口令一次:setPassword 落 localStorage,新实例(=新标签页)直接可用", () => {
  const storage = memStorage();
  const { s } = makeSession({ storage });
  assert.equal(s.hasPassword(), false);
  s.setPassword("秘密口令");
  assert.equal(storage.getItem(PASSWORD_KEY), "秘密口令");
  const { s: s2 } = makeSession({ storage });
  assert.equal(s2.hasPassword(), true);
  s2.clearPassword();
  assert.equal(storage.getItem(PASSWORD_KEY), null);
  assert.equal(s2.hasPassword(), false);
});

// ---- bootstrap ---------------------------------------------------------

test("bootstrap:GET /api/chat/bootstrap + Bearer 口令,返回 info", async () => {
  const { s, fetchFn } = makeSession({
    handler: () => jsonRes(200, boot("nbwt_1")),
  });
  s.setPassword("pw1");
  const info = await s.bootstrap();
  assert.equal(info.token, "nbwt_1");
  assert.equal(fetchFn.calls.length, 1);
  assert.equal(fetchFn.calls[0].url, "/api/chat/bootstrap");
  assert.equal(authHeader(fetchFn.calls[0]), "Bearer pw1");
});

test("bootstrap 401 = 口令错 → PasswordRejected", async () => {
  const { s } = makeSession({ handler: () => jsonRes(401) });
  s.setPassword("bad-pw");
  await assert.rejects(() => s.bootstrap(), PasswordRejected);
});

test("中文口令 → PasswordRejected 明确提示且零网络(fetch header 只收 Latin-1)", async () => {
  const { s, fetchFn } = makeSession({});
  s.setPassword("中文口令");
  await assert.rejects(
    () => s.bootstrap(),
    (e) => e instanceof PasswordRejected && /中文|字符/.test(e.message),
  );
  assert.equal(fetchFn.calls.length, 0);
});

// ---- 没口令 = 主路(track opendesign-key-onboarding T4)-------------------
//
// 🔴 **题面 2026-08-16 改过,原断言是「没有口令 → 零网络请求」。**
//    改的理由不是它红了,是它**结构上已经问不出该问的事**:ds-web 现在会替前端签
//    (bin/ds_web.py `_proxy`,判据 j1 咬着),业主从此不必手输口令 ⇒
//    "没有口令"从异常路变成了**主路**,再断言"零网络"等于禁止主路发生。
//    断言没有删,是搬到问得出的地方,而且问得更细:没口令时**不许自己瞎编一个
//    Authorization**(那会把一个假 Bearer 送到上游)、只发一次、被拒了才回登录框。
//    ——「改题面前必须说清这份考卷问不出这件事,并把断言搬到问得出的地方」。

test("没口令 = 代签主路:照发 bootstrap,但**一个 Authorization 都不许带**", async () => {
  const { s, fetchFn } = makeSession({ handler: () => jsonRes(200, boot("nbwt_signed")) });
  assert.equal(s.hasPassword(), false);
  const info = await s.bootstrap();
  assert.equal(info.token, "nbwt_signed");
  assert.equal(fetchFn.calls.length, 1, "没口令时该发且只发一次");
  assert.equal(fetchFn.calls[0].url, "/api/chat/bootstrap");
  // 关键:头必须**缺席**。带一个空的 / "Bearer null" / "Bearer undefined" 都算漏 ——
  // 上游会拿它当口令去比,而我们等的是"ds-web 认出没带、替我签"这条路。
  assert.equal(authHeader(fetchFn.calls[0]), null,
               `没口令却带了 Authorization:${authHeader(fetchFn.calls[0])}`);
});

test("没口令时 apiFetch / openSocket 都能走通(代签路是主路,不是兜底)", async () => {
  const { s, fetchFn, opened } = makeSession({
    handler: (url) => (url === "/api/chat/bootstrap"
      ? jsonRes(200, boot("nbwt_signed"))
      : jsonRes(200, { ok: true })),
  });
  const r = await s.apiFetch("/api/chat/sessions");
  assert.equal(r.status, 200);
  await s.openSocket();
  assert.equal(opened.length, 1);
  for (const c of fetchFn.calls.filter((c) => c.url === "/api/chat/bootstrap")) {
    assert.equal(authHeader(c), null, "代签路上不许出现 Authorization");
  }
});

test("没口令且服务端也拒(401)→ PasswordRejected 弹回登录,且不重试", async () => {
  // 代签失败(配置里没口令 / 口令错)时,手输那条兜底路必须还在 —— 这正是
  // design 里「保留手输为兜底,删了就没有退路」那一条。
  const { s, fetchFn } = makeSession({ handler: () => jsonRes(401) });
  await assert.rejects(() => s.bootstrap(), PasswordRejected);
  // 消息双向写:0 和 2 是**两种病**,写死一种会把人引去查没发生的事
  // (同类教训:判据里"红是对的但理由是假的")。
  assert.equal(fetchFn.calls.length, 1,
               `bootstrap 该恰好发一次:0 = 根本没走代签路(还在要口令),>1 = 被拒了还反复签`);
});

test("有口令时仍用它签:兜底路没被拿掉", async () => {
  const { s, fetchFn } = makeSession({ handler: () => jsonRes(200, boot("nbwt_pw")) });
  s.setPassword("pw1");
  await s.bootstrap();
  assert.equal(authHeader(fetchFn.calls[0]), "Bearer pw1");
});

test("gateway 不可达(bootstrap 502)≠ 口令错:抛错但不是 PasswordRejected", async () => {
  const { s } = makeSession({ handler: () => jsonRes(502, { error: "上游不可达" }) });
  s.setPassword("pw1");
  await assert.rejects(
    () => s.bootstrap(),
    (e) => !(e instanceof PasswordRejected) && e instanceof Error,
  );
});

// ---- apiFetch:401 透明重签 -------------------------------------------

test("apiFetch:无缓存 token 先 bootstrap,再带 Bearer token 调目标", async () => {
  const { s, fetchFn } = makeSession({
    handler: (url) =>
      url === "/api/chat/bootstrap"
        ? jsonRes(200, boot("nbwt_1"))
        : jsonRes(200, { sessions: [] }),
  });
  s.setPassword("pw1");
  const res = await s.apiFetch("/api/chat/sessions");
  assert.equal(res.status, 200);
  assert.deepEqual(
    fetchFn.calls.map((c) => c.url),
    ["/api/chat/bootstrap", "/api/chat/sessions"],
  );
  assert.equal(authHeader(fetchFn.calls[1]), "Bearer nbwt_1");
});

// p7:init(method/headers/body)透传,且调用方 headers 覆盖不了 Authorization
test("apiFetch init 透传:method/body/CT 到线,Authorization 不可被覆盖", async () => {
  const { s, fetchFn } = makeSession({
    handler: (url) =>
      url === "/api/chat/bootstrap"
        ? jsonRes(200, boot("nbwt_1"))
        : jsonRes(200, { deleted: true }),
  });
  s.setPassword("pw1");
  const res = await s.apiFetch("/api/chat/sessions/websocket:x/delete", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: "Bearer 伪造" },
    body: "{}",
  });
  assert.equal(res.status, 200);
  const call = fetchFn.calls[1];
  assert.equal(call.init.method, "POST");
  assert.equal(call.init.body, "{}");
  assert.equal(call.init.headers["Content-Type"], "application/json");
  assert.equal(call.init.headers.Authorization, "Bearer nbwt_1");
});

test("apiFetch 401 → 透明重 bootstrap 一次 → 新 token 重试成功", async () => {
  let issued = 0;
  const { s, fetchFn } = makeSession({
    handler: (url, init) => {
      if (url === "/api/chat/bootstrap") return jsonRes(200, boot(`nbwt_${++issued}`));
      // 旧 token 401,新 token 200
      return authHeader({ init }) === "Bearer nbwt_2"
        ? jsonRes(200, { sessions: [] })
        : jsonRes(401);
    },
  });
  s.setPassword("pw1");
  const res = await s.apiFetch("/api/chat/sessions");
  assert.equal(res.status, 200);
  assert.deepEqual(
    fetchFn.calls.map((c) => c.url),
    [
      "/api/chat/bootstrap", // 首签 nbwt_1
      "/api/chat/sessions", // 401
      "/api/chat/bootstrap", // 透明重签 nbwt_2
      "/api/chat/sessions", // 200
    ],
  );
  assert.equal(authHeader(fetchFn.calls[3]), "Bearer nbwt_2");
});

test("401 后重 bootstrap 也 401 = 口令失效 → PasswordRejected(弹回登录)", async () => {
  let bootN = 0;
  const { s } = makeSession({
    handler: (url) => {
      if (url === "/api/chat/bootstrap")
        return ++bootN === 1 ? jsonRes(200, boot("nbwt_1")) : jsonRes(401);
      return jsonRes(401);
    },
  });
  s.setPassword("expired-pw");
  await assert.rejects(() => s.apiFetch("/api/chat/sessions"), PasswordRejected);
});

test("重签后重试仍 401 → PasswordRejected 且只重试一次(不无限循环)", async () => {
  const { s, fetchFn } = makeSession({
    handler: (url, init, n) =>
      url === "/api/chat/bootstrap" ? jsonRes(200, boot(`nbwt_${n}`)) : jsonRes(401),
  });
  s.setPassword("pw1");
  await assert.rejects(() => s.apiFetch("/api/chat/sessions"), PasswordRejected);
  // 有界:首签→目标 401→重签→目标 401,到此为止
  assert.deepEqual(
    fetchFn.calls.map((c) => c.url),
    [
      "/api/chat/bootstrap",
      "/api/chat/sessions",
      "/api/chat/bootstrap",
      "/api/chat/sessions",
    ],
  );
});

// ---- openSocket:一次性 token,每连必新签 -----------------------------

test("openSocket 每次都新 bootstrap:两次开连 = 两次签发,token 各自独立", async () => {
  let issued = 0;
  const { s, fetchFn, opened } = makeSession({
    handler: () => jsonRes(200, boot(`nbwt_${++issued}`)),
  });
  s.setPassword("pw1");
  const a = await s.openSocket();
  const b = await s.openSocket();
  assert.equal(
    fetchFn.calls.filter((c) => c.url === "/api/chat/bootstrap").length,
    2,
  );
  assert.equal(opened.length, 2);
  assert.match(opened[0].url, /token=nbwt_1/);
  assert.match(opened[1].url, /token=nbwt_2/);
  assert.equal(a.info.model_name, "mimo-v2.5");
  assert.ok(b.socket instanceof FakeWs);
});

test("ws 地址 = ws_path + 已知端口自拼,绝不信 ws_url 的 host", async () => {
  const { s, opened } = makeSession({
    handler: () => jsonRes(200, boot("nbwt_1", { ws_path: "/ws" })),
  });
  s.setPassword("pw1");
  await s.openSocket();
  const u = new URL(opened[0].url);
  assert.equal(u.protocol, "ws:");
  assert.equal(u.hostname, "127.0.0.1");
  assert.equal(u.port, "8765");
  assert.equal(u.pathname, "/ws");
  assert.equal(u.searchParams.get("client_id"), "cid-fixed");
  assert.equal(u.searchParams.get("token"), "nbwt_1");
});

test("nanobotPort 可覆盖(对应 DS_NANOBOT_PORT 部署形状)", async () => {
  const { s, opened } = makeSession({ port: 9765 });
  s.setPassword("pw1");
  await s.openSocket();
  assert.equal(new URL(opened[0].url).port, "9765");
});

test("openSocket 顺手刷新 api token:随后 apiFetch 不再额外签发", async () => {
  const { s, fetchFn } = makeSession({
    handler: (url) =>
      url === "/api/chat/bootstrap"
        ? jsonRes(200, boot("nbwt_ws"))
        : jsonRes(200, { sessions: [] }),
  });
  s.setPassword("pw1");
  await s.openSocket();
  const res = await s.apiFetch("/api/chat/sessions");
  assert.equal(res.status, 200);
  assert.equal(
    fetchFn.calls.filter((c) => c.url === "/api/chat/bootstrap").length,
    1,
  );
  const last = fetchFn.calls[fetchFn.calls.length - 1];
  assert.equal(authHeader(last), "Bearer nbwt_ws");
});
