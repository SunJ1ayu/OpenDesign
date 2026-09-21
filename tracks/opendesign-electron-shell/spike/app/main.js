// OpenDesign 桌面外壳 —— Electron 探路版(track opendesign-electron-shell,U2 的 E2/E3)。
// **不是产品代码**:它只回答「这条路在真 Windows 上走不走得通」,判据在 spike/probe/。
//
// 分工(照 ZCode:窗口进程 + 单独的后台管家进程):
//   这里 = 窗口、三按钮、托盘、单实例、外链、收摊顺序;
//   host/spike_host.py = 现有外壳的后台那一半(挑端口、改配置、起网关与工作台、Job、锁通道)。
// 两边只走 stdin/stdout:管家一行一个 JSON 事件;我这边关掉它的 stdin = 「收摊」,
// 我被杀掉时管道也会断 ⇒ 管家读到 EOF 自己收摊(E2 要量的正是这一条)。
const { app, BrowserWindow, Tray, Menu, ipcMain, shell, dialog } = require("electron");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const readline = require("node:readline");

const RES = app.isPackaged ? process.resourcesPath : path.join(__dirname, "res-dev");
const LOCAL = process.env.LOCALAPPDATA || app.getPath("appData");
const LOG = path.join(LOCAL, "OpenDesign", "Logs", "electron.log");

function log(msg) {
  try {
    fs.mkdirSync(path.dirname(LOG), { recursive: true });
    fs.appendFileSync(LOG, `${new Date().toISOString()} ${msg}\n`);
  } catch {
    /* 日志写不了不许把外壳带崩 */
  }
}

// Chromium 的档案放进我们自己的数据根,不去 Roaming 另开一处。
// 必须在单实例锁之前:锁按 userData 目录区分实例。
app.setPath("userData", path.join(LOCAL, "OpenDesign", "Electron"));

// 现在这份前端的窗口栏靠 pywebview 的 begin_drag/begin_resize;这里改由 Chromium 自己认拖动区,
// 八个缩放把手隐藏(它们会压在系统缩放边上,挑战腿 DeepSeek #10)。
const DRAG_CSS = `
  .win-bar { -webkit-app-region: drag; }
  .win-btns, .win-btns * { -webkit-app-region: no-drag; }
  .win-grip { display: none !important; }
`;

let win = null;
let tray = null;
let host = null;
let quitting = false;
let webUrl = null;

function showWindow() {
  if (!win) return;
  if (win.isMinimized()) win.restore();
  win.show();
  win.focus();
}

function sendState() {
  if (win && !win.isDestroyed()) win.webContents.send("od:window-state", { maximized: win.isMaximized() });
}

function createWindow() {
  win = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 960,
    minHeight: 640,
    title: "OpenDesign",
    icon: path.join(RES, "opendesign.ico"),
    // 照 ZCode:Windows 上 frame:false 且不关 thickFrame ⇒ 系统缩放边/贴边/最小化动画由 Electron 保住。
    frame: false,
    backgroundColor: "#f7f5f0",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
    },
  });
  win.loadFile(path.join(__dirname, "loading.html"));

  // 关窗 = 收进托盘;只有托盘「退出」才真的收摊。
  win.on("close", (e) => {
    if (quitting) return;
    e.preventDefault();
    win.hide();
    log("[窗口] 关窗 → 收进托盘");
  });
  win.on("maximize", sendState);
  win.on("unmaximize", sendState);

  // 照 ZCode attachWindowsWindowRepaint:拉伸结束 / 从托盘 show 之后补两次重绘,
  // 它遇到过「窗口只剩宿主底色」(挑战腿 Cursor #17)。
  let timer = null;
  const repaint = () => {
    if (win.isDestroyed()) return;
    win.webContents.invalidate();
    clearTimeout(timer);
    timer = setTimeout(() => !win.isDestroyed() && win.webContents.invalidate(), 32);
  };
  win.on("resized", repaint);
  win.on("show", repaint);

  // 外链一律交给系统浏览器;窗口里只许留在我们自己的工作台上。
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//i.test(url)) shell.openExternal(url);
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (e, url) => {
    if (webUrl && url.startsWith(new URL(webUrl).origin)) return;
    e.preventDefault();
    if (/^https?:\/\//i.test(url)) shell.openExternal(url);
  });
  win.webContents.on("did-finish-load", () => {
    if (webUrl) win.webContents.insertCSS(DRAG_CSS);
  });
  win.webContents.on("render-process-gone", (_e, d) => log(`[窗口] 渲染进程没了:${d.reason}`));
}

function createTray() {
  tray = new Tray(path.join(RES, "opendesign.ico"));
  tray.setToolTip("OpenDesign");
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: "打开 OpenDesign", click: showWindow },
      { label: "退出", click: quitAll },
    ]),
  );
  tray.on("click", showWindow);
}

function startHost() {
  const py = path.join(RES, "python", "python.exe");
  const script = path.join(RES, "host", "spike_host.py");
  log(`[管家] 起:${py} ${script}`);
  host = spawn(py, ["-u", script], { cwd: RES, stdio: ["pipe", "pipe", "pipe"], windowsHide: true });
  readline.createInterface({ input: host.stdout }).on("line", onHostLine);
  host.stderr.on("data", (d) => log(`[管家 stderr] ${String(d).trimEnd()}`));
  host.on("exit", (code) => {
    log(`[管家] 退出 code=${code}`);
    if (!quitting) {
      dialog.showErrorBox("OpenDesign", `后台意外退出了(退出码 ${code})。\n\n请从右下角托盘退出后重新打开。`);
    }
  });
}

function onHostLine(line) {
  let m;
  try {
    m = JSON.parse(line);
  } catch {
    log(`[管家] ${line}`);
    return;
  }
  log(`[管家→] ${line}`);
  if (m.event === "ready") {
    webUrl = `http://127.0.0.1:${m.web_port}/?shell=1`;
    win.loadURL(webUrl);
  } else if (m.event === "show") {
    showWindow();
  } else if (m.event === "quit") {
    quitAll();
  }
}

// 收摊顺序:先让管家把后台收干净(它关 Job,整棵子孙树一起走),再退 Electron。
// 反过来的话,安装/更新时 Python 还攥着安装目录里的文件(挑战腿 #1 #16)。
function quitAll() {
  if (quitting) return;
  quitting = true;
  log("[收摊] 开始");
  const done = () => {
    log("[收摊] 结束");
    app.exit(0);
  };
  if (!host || host.exitCode !== null) return done();
  host.once("exit", done);
  try {
    host.stdin.end();
  } catch {
    /* 已经断了 */
  }
  setTimeout(() => {
    log("[收摊] 管家 15 秒没走完,强杀");
    try {
      host.kill();
    } catch {
      /* ignore */
    }
    done();
  }, 15000);
}

ipcMain.handle("od:minimize", () => {
  win.minimize();
  return true;
});
ipcMain.handle("od:toggle-maximize", () => {
  if (win.isMaximized()) win.unmaximize();
  else win.maximize();
  return { maximized: win.isMaximized() };
});
ipcMain.handle("od:close", () => {
  win.close();
  return true;
});
ipcMain.handle("od:window-state", () => ({ maximized: win.isMaximized() }));
ipcMain.handle("od:report", (_e, event, detail) => {
  log(`[前端] ${event} ${detail}`);
  return true;
});

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    log("[单实例] 第二次打开 → 叫出窗口");
    showWindow();
  });
  app.on("before-quit", (e) => {
    if (quitting) return;
    e.preventDefault();
    quitAll();
  });
  app.on("window-all-closed", () => {
    /* 窗口只会被藏起来;真退出只走 quitAll */
  });
  app.whenReady().then(() => {
    log(`==== OpenDesign(Electron ${process.versions.electron})启动 ====`);
    createWindow();
    createTray();
    startHost();
  });
}
