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

test("没有口令就动手 → PasswordRejected 且零网络请求", async () => {
  const { s, fetchFn } = makeSession({});
  await assert.rejects(() => s.apiFetch("/api/chat/sessions"), PasswordRejected);
  await assert.rejects(() => s.openSocket(), PasswordRejected);
  assert.equal(fetchFn.calls.length, 0);
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
