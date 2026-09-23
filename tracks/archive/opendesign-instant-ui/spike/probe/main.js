"use strict";
// 探针:app:// 自定义协议能不能扛住工作台的全部用法(track opendesign-instant-ui)。
// 跑两次:--mode=write(写 localStorage + 各种请求)→ 退出 → --mode=read(读回 localStorage)。
const { app, BrowserWindow, protocol, net, session, ipcMain } = require("electron");
const fs = require("node:fs");
const path = require("node:path");

const arg = (k) => process.argv.find((a) => a.startsWith(`--${k}=`))?.split("=")[1];
const mode = arg("mode"), httpPort = Number(arg("http-port")), wsPort = Number(arg("ws-port")), out = arg("out");
app.setPath("userData", path.join(arg("udata"), "ud"));

protocol.registerSchemesAsPrivileged([{ scheme: "app",
  privileges: { standard: true, secure: true, supportFetchAPI: true, stream: true, corsEnabled: true } }]);

let resolveReady; const ready = new Promise((r) => { resolveReady = r; });
const seen = [];

app.whenReady().then(async () => {
  // 模拟业主机器上配了系统代理:代理指向一个不存在的端口。回环请求若走代理就会失败。
  await session.defaultSession.setProxy({ proxyRules: "http://127.0.0.1:9" });
  protocol.handle("app", async (req) => {
    const u = new URL(req.url);
    seen.push(`${req.method} ${u.pathname}`);
    if (u.pathname.startsWith("/api/")) {
      await ready;                                   // 就绪前挂起
      const headers = new Headers(req.headers);
      for (const h of ["origin", "referer", "sec-fetch-site", "sec-fetch-mode", "sec-fetch-dest"]) headers.delete(h);
      const init = { method: req.method, headers, bypassCustomProtocolHandlers: true };
      if (!["GET", "HEAD"].includes(req.method)) { init.body = req.body; init.duplex = "half"; }
      return net.fetch(`http://127.0.0.1:${httpPort}${u.pathname}${u.search}`, init);
    }
    const file = u.pathname === "/" || !path.extname(u.pathname) ? "page.html" : u.pathname.slice(1);
    return net.fetch("file://" + path.join(__dirname, file).replace(/\\/g, "/"));
  });
  const win = new BrowserWindow({ show: true, webPreferences: {
    preload: path.join(__dirname, "preload.js"), contextIsolation: true, sandbox: false,
    additionalArguments: [`--ws-port=${wsPort}`] } });
  const t0 = Date.now();
  setTimeout(() => resolveReady(), mode === "write" ? 3000 : 0);   // 后台 3 秒后「就绪」
  ipcMain.on("probe-done", (_e, r) => {
    r.mode = mode; r.firstPaintVsReady = "ready@3000ms"; r.wallMs = Date.now() - t0; r.handlerSaw = seen;
    fs.writeFileSync(out, JSON.stringify(r, null, 2));
    setTimeout(() => app.quit(), 300);
  });
  win.webContents.on("console-message", (_e, l, m) => console.log("[page]", m));
  setTimeout(() => { fs.writeFileSync(out, JSON.stringify({ mode, error: "timeout 40s", seen })); app.exit(2); }, 40000);
  win.loadURL(`app://opendesign/?shell=1&mode=${mode}`);
});
