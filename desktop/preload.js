"use strict";

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("odShell", {
  minimize: () => ipcRenderer.invoke("od:minimize"),
  toggleMaximize: () => ipcRenderer.invoke("od:toggle-maximize"),
  close: () => ipcRenderer.invoke("od:close"),
  windowState: () => ipcRenderer.invoke("od:window-state"),
  onWindowState: (callback) => {
    const listener = (_event, state) => callback(state);
    ipcRenderer.on("od:window-state-changed", listener);
    return () => ipcRenderer.removeListener("od:window-state-changed", listener);
  },
  reportStartup: (event, detail) => ipcRenderer.send("od:report", String(event), detail == null ? "" : String(detail)),
  backend: {
    state: () => ipcRenderer.invoke("od:backend-state"),
    onState: (callback) => {
      const listener = (_event, state) => callback(state);
      ipcRenderer.on("od:backend-state-changed", listener);
      return () => ipcRenderer.removeListener("od:backend-state-changed", listener);
    },
  },
  update: {
    check: () => ipcRenderer.invoke("od:update-check"),
    install: () => ipcRenderer.invoke("od:update-install"),
    state: () => ipcRenderer.invoke("od:update-state"),
    onState: (callback) => {
      const listener = (_event, state) => callback(state);
      ipcRenderer.on("od:update-state-changed", listener);
      return () => ipcRenderer.removeListener("od:update-state-changed", listener);
    },
  },
});
