const { contextBridge, ipcRenderer } = require("electron");
contextBridge.exposeInMainWorld("probe", {
  wsPort: Number(process.argv.find((a) => a.startsWith("--ws-port="))?.split("=")[1] || 0),
  done: (r) => ipcRenderer.send("probe-done", r),
});
