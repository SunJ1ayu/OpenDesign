"use strict";

// 工作台在 Electron 里的源站:app://opendesign(track opendesign-instant-ui)。
// 窗口一创建就加载 APP_URL —— 界面文件从包里的 resources/ds/web/dist 直接给,不等后台;
// /api/* 挂起到后台就绪,再转给 http://127.0.0.1:<web_port>(ds-web)。
// 云探针 run 35820084450:挂起 / 5MB 上传 / 图片 / ws 直连 / 系统代理 / localStorage 跨重启都在真 Windows 上过了。
//
// 静态规则照抄 ds-web `_static`(bin/ds_web.py):反斜杠与 NUL 直接拒、realpath 不出 dist、
// 入口页不缓存(否则更新后跑旧界面)、带哈希资源长缓存、不回落首页(工作台是 #/ 路由)。
// **不许 require("electron")**:判据在没装 node_modules 的 Linux 上跑(tests/test_desktop_instant.mjs)。

const path = require("node:path");
const { SHELL_MARK } = require("./navPolicy");

const APP_SCHEME = "app";
const APP_HOST = "opendesign";
const APP_ORIGIN = `${APP_SCHEME}://${APP_HOST}`;
const APP_URL = `${APP_ORIGIN}/?${SHELL_MARK}`;

const CTYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".map": "application/json; charset=utf-8",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".woff2": "font/woff2",
};

// 页面的身份头不带去 ds-web:它的同站检查只认 http://127.0.0.1:<端口> 或「没有 Origin」,
// app://opendesign 带过去就是 403。去掉之后 ds-web 把这次调用看成本机非浏览器调用 —— 与 curl 同待遇;
// 而能走到这里的只有我们自己窗口里的页面(冒名主机在上面就 404 了)。
const STRIP = ["origin", "referer", "sec-fetch-site", "sec-fetch-mode", "sec-fetch-dest", "sec-fetch-user"];

function json(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "X-Content-Type-Options": "nosniff" },
  });
}

function isOurHost(url) {
  return url.protocol === `${APP_SCHEME}:` && url.hostname === APP_HOST && !url.port
    && !url.username && !url.password;
}

function createAppHandler({ distRoot, readFile, backendPort, fetch, log }) {
  const root = path.resolve(distRoot);
  const within = (p) => p === root || p.startsWith(root + path.sep);

  async function serveFile(pathname) {
    let raw;
    try {
      raw = decodeURIComponent(pathname);
    } catch {
      return json(400, { error: "bad path" });
    }
    if (raw.includes("\\") || raw.includes("\0")) return json(400, { error: "bad path" });
    const rel = raw.replace(/^\/+/, "") || "index.html";
    if (path.isAbsolute(rel) || /^[a-zA-Z]:/.test(rel)) return json(404, { error: "not found" });
    const target = path.resolve(root, rel);
    if (!within(target) || target === root) return json(404, { error: "not found" });
    let body;
    try {
      body = await readFile(target);
    } catch (error) {
      if (error && error.code !== "ENOENT" && error.code !== "EISDIR") log(`[界面文件] ${target}:${error}`);
      return json(404, { error: "not found" });
    }
    const ctype = CTYPES[path.extname(target).toLowerCase()] || "application/octet-stream";
    const cache = path.basename(target) === "index.html" ? "no-cache" : "public, max-age=31536000, immutable";
    return new Response(body, {
      status: 200,
      headers: { "Content-Type": ctype, "Cache-Control": cache, "X-Content-Type-Options": "nosniff" },
    });
  }

  async function forward(request, url) {
    // 后台没好就挂在这里:页面拿到的是「晚到」,不是「失败」。
    // 🔴 端口只取一次:依赖「ds-web 在一次运行里不换端口」(重启网关只动网关,ds_shell.restart_gateway)。
    //    将来要让 ds-web 自己重启/换端口的人,必须把这里改成每次现取。
    const port = await backendPort();
    const headers = new Headers(request.headers);
    for (const h of STRIP) headers.delete(h);
    const init = { method: request.method, headers };
    if (request.method !== "GET" && request.method !== "HEAD" && request.body) {
      init.body = request.body;
      init.duplex = "half";
    }
    try {
      return await fetch(`http://127.0.0.1:${port}${url.pathname}${url.search}`, init);
    } catch (error) {
      log(`[后台转发] ${request.method} ${url.pathname}:${error && (error.stack || error.message) ? (error.stack || error.message) : error}`);
      return json(502, { error: "backend unreachable" });
    }
  }

  return async function handle(request) {
    let url;
    try {
      url = new URL(request.url);
    } catch {
      return json(400, { error: "bad url" });
    }
    if (!isOurHost(url)) return json(404, { error: "not found" });
    if (url.pathname.startsWith("/api/")) return forward(request, url);
    return serveFile(url.pathname);
  };
}

module.exports = { APP_SCHEME, APP_HOST, APP_ORIGIN, APP_URL, createAppHandler };
