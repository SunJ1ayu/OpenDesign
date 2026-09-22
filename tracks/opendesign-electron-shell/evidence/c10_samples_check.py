#!/usr/bin/env python3
"""判据的判据:c10~c10e(main.js 接线静态闸)对一份**写对的** main.js 必须全绿,对每种**故意写错**的必须在
对应那一条上红。主 agent 亲写(track opendesign-electron-shell,派活前复核之后)。
跑法:/root/.venvs/design-studio/bin/python tracks/opendesign-electron-shell/evidence/c10_samples_check.py
退出码:有一例不符预期 ⇒ 1。样例 main.js 只是量具,不是实现参考(实现照 design.md 接缝表写)。"""
import importlib.util, io, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GOOD = r'''const { app, BrowserWindow, Tray, Menu, dialog, shell, ipcMain } = require("electron");
const { spawn } = require("node:child_process");
const { autoUpdater } = require("electron-updater");
const { createController } = require("./lib/controller");
const { trayMenuTemplate, contextMenuTemplate } = require("./lib/menus");
const { windowOpenDecision } = require("./lib/navPolicy");
const { encodeCommand } = require("./lib/hostProtocol");
let win, host, ctl;
if (!app.requestSingleInstanceLock()) app.quit();
function startHost() {
  host = spawn(py, [hostPy], { windowsHide: true, stdio: ["pipe", "pipe", "pipe"] });
  host.stdout.on("data", (chunk) => ctl.hostStdout(chunk));
  host.on("close", (code) => ctl.hostExit(code));
}
app.whenReady().then(() => {
  win = new BrowserWindow({ webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true, preload } });
  ctl = createController({
    appVersion: app.getVersion(),
    loadWorkbench: (u) => win.loadURL(u),
    showWindow: () => { win.show(); win.focus(); },
    showError: (m) => dialog.showErrorBox("OpenDesign", m),
    revealFile: (p) => shell.showItemInFolder(p),
    openExternal: (u) => shell.openExternal(u),
    log, updater: autoUpdater,
    pushUpdateState: (s) => win.webContents.send("update:state", s),
    setTimeout, clearTimeout,
    relaunch: () => { app.relaunch(); app.exit(0); },
  });
  win.webContents.on("will-navigate", (e, url) => { if (ctl.navigate(url)) e.preventDefault(); });
  win.webContents.setWindowOpenHandler(({ url }) => windowOpenDecision(url, origin));
  win.webContents.on("context-menu", (e, params) => Menu.buildFromTemplate(contextMenuTemplate(params)).popup());
  const tray = new Tray(icon);
  tray.setContextMenu(Menu.buildFromTemplate(trayMenuTemplate({
    onOpen: () => ctl && win.show(),
    onExport: () => host.stdin.write(encodeCommand({ cmd: "export-diagnostics" })),
    onQuit: () => { ctl.setQuitting(); app.quit(); },
  })));
  ipcMain.handle("update:get", () => ctl.updateState());
  ipcMain.on("update:retry", () => ctl.checkNow());
  ipcMain.handle("update:install", () => ctl.installUpdate(host));
  startHost();
  ctl.startUpdates();
});
'''

# 变异名 → (把哪一段换成什么, 必须红的那一条)
MUTANTS = {
    "main 自己查一次更新、不开调度": ("ctl.startUpdates();", "autoUpdater.checkForUpdates();", "test_c10b_updates_only_go_through_the_controller"),
    "按钮直接 quitAndInstall": ("() => ctl.installUpdate(host)", "() => autoUpdater.quitAndInstall()", "test_c10b_updates_only_go_through_the_controller"),
    "在 exit 上叫 hostExit": ('host.on("close"', 'host.on("exit"', "test_c10c_host_exit_is_read_after_the_pipe_drains"),
    "逐块 toString": ("ctl.hostStdout(chunk)", "ctl.hostStdout(chunk.toString())", "test_c10c_host_exit_is_read_after_the_pipe_drains"),
    "只 relaunch 不 exit": ("app.relaunch(); app.exit(0);", "app.relaunch();", "test_c10d_relaunch_really_leaves"),
    "托盘导出是空函数": ('onExport: () => host.stdin.write(encodeCommand({ cmd: "export-diagnostics" })),', "onExport: () => {},", "test_c10e_tray_callbacks_do_something"),
    "托盘退出是空函数": ("onQuit: () => { ctl.setQuitting(); app.quit(); },", "onQuit: () => {},", "test_c10e_tray_callbacks_do_something"),
    "托盘回调不在调用处": ("trayMenuTemplate({", "trayMenuTemplate(handlers, {", "test_c10e_tray_callbacks_do_something"),
    "外链 deps 是空函数": ("shell.openExternal(u)", "void u", "test_c10_main_uses_the_tested_pieces"),
    "诊断包 deps 是空函数": ("shell.showItemInFolder(p)", "void p", "test_c10_main_uses_the_tested_pieces"),
    "没拦新窗口": ("win.webContents.setWindowOpenHandler(({ url }) => windowOpenDecision(url, origin));", "", "test_c10_main_uses_the_tested_pieces"),
}

spec = importlib.util.spec_from_file_location("cfg", ROOT / "tests" / "test_desktop_config.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def red_tests(src: str) -> list[str]:
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "main.js").write_text(src, encoding="utf-8")
        mod.DESKTOP = Path(d)
        r = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
            unittest.TestLoader().loadTestsFromTestCase(mod.C10MainIsWired))
        return sorted(t.id().rsplit(".", 1)[-1] for t, _ in r.failures + r.errors)


bad = 0
got = red_tests(GOOD)
print(f"{'OK  ' if not got else 'FAIL'} 写对的样例 :: 红 {got or '无'}")
bad += bool(got)
for name, (old, new, want) in MUTANTS.items():
    assert GOOD.count(old) == 1, f"样例里找不到要变异的那段:{old}"
    got = red_tests(GOOD.replace(old, new))
    ok = want in got
    bad += not ok
    print(f"{'OK  ' if ok else 'FAIL'} {name} :: 红 {got or '无'}")
print(f"判据的判据:{bad} 例不符预期")
sys.exit(1 if bad else 0)
