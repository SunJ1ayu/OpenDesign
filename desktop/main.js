"use strict";

const { app, BrowserWindow, Tray, Menu, ipcMain, shell, dialog } = require("electron");
const { autoUpdater } = require("electron-updater");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const { createController } = require("./lib/controller");
const { trayMenuTemplate, contextMenuTemplate } = require("./lib/menus");
const { windowOpenDecision } = require("./lib/navPolicy");
const { encodeCommand } = require("./lib/hostProtocol");
const { shutdownHost } = require("./lib/lifecycle");

const resources = app.isPackaged ? process.resourcesPath : path.join(__dirname, "pkg");
const localData = process.env.LOCALAPPDATA || app.getPath("appData");
const logPath = path.join(localData, "OpenDesign", "Logs", "electron.log");
app.setPath("userData", path.join(localData, "OpenDesign", "Electron"));

function log(message) {
  try {
    fs.mkdirSync(path.dirname(logPath), { recursive: true });
    fs.appendFileSync(logPath, `${new Date().toISOString()} ${message}\n`, "utf8");
  } catch {
    // 诊断层不能拖垮启动。
  }
}

let win = null;
let tray = null;
let host = null;
let quitting = false;

function showWindow() {
  if (!win || win.isDestroyed()) return;
  if (win.isMinimized()) win.restore();
  win.show();
  win.focus();
}

function sendHost(command) {
  if (!host || host.exitCode !== null || !host.stdin.writable) return;
  try { host.stdin.write(encodeCommand(command), "utf8"); } catch (error) { log(`[管家 stdin] ${error}`); }
}

const ctl = createController({
  appVersion: app.getVersion(),
  loadWorkbench: (url) => win && win.loadURL(url),
  showWindow,
  showError: (message) => dialog.showErrorBox("OpenDesign", message),
  revealFile: (file) => shell.showItemInFolder(file),
  openExternal: (url) => { void shell.openExternal(url).catch((error) => log(`[外链] ${error}`)); },
  log,
  updater: autoUpdater,
  pushUpdateState: (state) => {
    if (win && !win.isDestroyed()) win.webContents.send("od:update-state-changed", state);
  },
  setTimeout,
  clearTimeout,
  relaunch: () => { app.relaunch(); app.exit(0); },
  graceMs: 15000,
});

function sendWindowState() {
  if (win && !win.isDestroyed()) {
    win.webContents.send("od:window-state-changed", { maximized: win.isMaximized() });
  }
}

function createWindow() {
  win = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 960,
    minHeight: 640,
    title: "OpenDesign",
    icon: path.join(resources, "opendesign.ico"),
    show: false,
    frame: false,
    backgroundColor: "#f7f5f0",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
    },
  });
  void win.loadFile(path.join(__dirname, "loading.html"));
  win.once("ready-to-show", showWindow);

  win.on("close", (event) => {
    if (quitting) return;
    event.preventDefault();
    win.hide();
  });
  win.on("maximize", sendWindowState);
  win.on("unmaximize", sendWindowState);

  let repaintTimer = null;
  const repaint = () => {
    if (!win || win.isDestroyed()) return;
    win.webContents.invalidate();
    clearTimeout(repaintTimer);
    repaintTimer = setTimeout(() => {
      if (win && !win.isDestroyed()) win.webContents.invalidate();
    }, 32);
  };
  win.on("resized", repaint);
  win.on("show", () => {
    repaint();
    sendHost({ cmd: "window-shown" });
  });

  win.webContents.on("will-navigate", (event, url) => {
    if (ctl.navigate(url)) event.preventDefault();
  });
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (windowOpenDecision(url) === "external") void shell.openExternal(url).catch((error) => log(`[外链] ${error}`));
    return { action: "deny" };
  });
  win.webContents.on("context-menu", (_event, params) => {
    const template = contextMenuTemplate(params);
    if (template.length) Menu.buildFromTemplate(template).popup({ window: win });
  });
  win.webContents.on("render-process-gone", (_event, details) => log(`[窗口] 渲染进程退出：${details.reason}`));
}

function startHost() {
  const python = path.join(resources, "python", "python.exe");
  const script = path.join(resources, "ds", "bin", "ds_host.py");
  host = spawn(python, ["-u", script], {
    cwd: path.join(resources, "ds"),
    stdio: ["pipe", "pipe", "pipe"],
    windowsHide: true,
  });
  host.stdout.on("data", (chunk) => ctl.hostStdout(chunk));
  host.stderr.setEncoding("utf8");
  host.stderr.on("data", (chunk) => log(`[管家 stderr] ${chunk.trimEnd()}`));
  host.on("close", (code) => ctl.hostExit(code));
}

async function quitAll() {
  if (quitting) return;
  quitting = true;
  ctl.setQuitting();
  await shutdownHost(host, { graceMs: 15000 });
  app.exit(0);
}

function createTray() {
  tray = new Tray(path.join(resources, "opendesign.ico"));
  tray.setToolTip("OpenDesign");
  tray.setContextMenu(Menu.buildFromTemplate(trayMenuTemplate({
    onOpen: () => showWindow(),
    onExport: () => sendHost({ cmd: "export-diagnostics" }),
    onQuit: () => { ctl.setQuitting(); void quitAll(); },
  })));
  tray.on("click", showWindow);
}

ipcMain.handle("od:minimize", () => { win.minimize(); return true; });
ipcMain.handle("od:toggle-maximize", () => {
  if (win.isMaximized()) win.unmaximize(); else win.maximize();
  return { maximized: win.isMaximized() };
});
ipcMain.handle("od:close", () => { win.close(); return true; });
ipcMain.handle("od:window-state", () => ({ maximized: !!win && win.isMaximized() }));
ipcMain.on("od:report", (_event, event, detail) => sendHost({ cmd: "report", event, detail }));
ipcMain.handle("od:update-check", () => ctl.checkNow());
ipcMain.handle("od:update-state", () => ctl.updateState());
ipcMain.handle("od:update-install", async () => {
  // 放行 electron-updater 自己发出的 app.quit；失败时控制器会立即 relaunch。
  quitting = true;
  const installed = await ctl.installUpdate(host);
  if (!installed) quitting = false;
  return installed;
});

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", showWindow);
  app.on("before-quit", (event) => {
    if (quitting) return;
    event.preventDefault();
    void quitAll();
  });
  app.on("window-all-closed", () => {});
  app.whenReady().then(() => {
    log(`==== OpenDesign(Electron ${process.versions.electron}) 启动 ====`);
    createWindow();
    createTray();
    startHost();
    ctl.startUpdates();
  }).catch((error) => {
    log(`[启动失败] ${error && error.stack ? error.stack : error}`);
    dialog.showErrorBox("OpenDesign", "桌面程序启动失败，请重新打开。");
    app.exit(1);
  });
}
