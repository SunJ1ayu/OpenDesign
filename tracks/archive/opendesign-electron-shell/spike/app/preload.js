// 探路版 preload(track opendesign-electron-shell U2)。
// 为了让**现在这份前端一行不改**就能跑,这里暂时冒充 pywebview 的 api 形状
// (WindowChrome.tsx / startupReport.ts 认的就是 window.pywebview.api)。
// preload 在页面脚本之前就位 ⇒ 没有「对象在了、方法还没挂上」那一瞬。
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("pywebview", {
  api: {
    minimize: () => ipcRenderer.invoke("od:minimize"),
    toggle_maximize: () => ipcRenderer.invoke("od:toggle-maximize"),
    close_window: () => ipcRenderer.invoke("od:close"),
    window_state: () => ipcRenderer.invoke("od:window-state"),
    // 拖动与改大小交给 Electron:拖动带用 CSS app-region,缩放边是系统的。
    begin_drag: () => Promise.resolve(null),
    begin_resize: () => Promise.resolve(null),
    report_startup: (event, detail) =>
      ipcRenderer.invoke("od:report", String(event), detail == null ? "" : String(detail)),
  },
});
