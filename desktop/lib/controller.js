"use strict";

const { createHostDecoder, hostExitMessage } = require("./hostProtocol");
const { versionMismatch } = require("./versionCheck");
const { navDecision, workbenchUrl } = require("./navPolicy");
const {
  initialUpdateState,
  reduceUpdate,
  canInstall,
  nextCheckDelayMs,
  FIRST_CHECK_DELAY_MS,
  configureUpdater,
} = require("./updateState");
const { installUpdate: handoffUpdate } = require("./lifecycle");

function createController(deps) {
  let quitting = false;
  let fatalShown = false;
  let origin = null;
  let state = initialUpdateState();
  let timer = null;
  let updatesStarted = false;

  const publish = (event) => {
    state = reduceUpdate(state, event);
    deps.pushUpdateState(state);
  };

  const schedule = (delay) => {
    if (timer !== null) deps.clearTimeout(timer);
    timer = deps.setTimeout(async () => {
      timer = null;
      await checkNow();
    }, delay);
  };

  const failUpdate = (error) => {
    const message = error && (error.stack || error.message) ? (error.stack || error.message) : String(error);
    deps.log(`[更新] ${message}`);
    publish({ type: "error", message });
    schedule(nextCheckDelayMs(state));
  };

  const onHostEvent = (message) => {
    deps.log(`[管家→] ${JSON.stringify(message)}`);
    switch (message.event) {
      case "ready": {
        const mismatch = versionMismatch(deps.appVersion, message.version);
        if (mismatch) {
          deps.log(mismatch);
          deps.showError(mismatch);
          return;
        }
        const url = workbenchUrl(message.web_port);
        origin = new URL(url).origin;
        deps.loadWorkbench(url);
        return;
      }
      case "show":
        deps.showWindow();
        return;
      case "fatal":
        fatalShown = true;
        deps.showError(message.message || "OpenDesign 后台启动失败。");
        return;
      case "alert":
      case "backend-died":
        deps.showError(message.message || "OpenDesign 后台发生错误。");
        return;
      case "already-running":
        fatalShown = true;
        deps.showError("另一个 OpenDesign 后台正在运行，请先从托盘退出它。");
        return;
      case "diagnostics":
        if (message.path) deps.revealFile(message.path);
        else if (message.error) deps.showError(message.error);
        return;
      default:
        return;
    }
  };

  const decoder = createHostDecoder(onHostEvent);

  async function checkNow() {
    if (timer !== null) {
      deps.clearTimeout(timer);
      timer = null;
    }
    try {
      await deps.updater.checkForUpdates();
    } catch (error) {
      failUpdate(error);
    }
  }

  function startUpdates() {
    if (updatesStarted) return;
    updatesStarted = true;
    configureUpdater(deps.updater, { log: deps.log });
    deps.updater.on("checking-for-update", () => publish({ type: "checking" }));
    deps.updater.on("update-available", (info) => publish({ type: "available", version: info && info.version }));
    deps.updater.on("download-progress", (progress) => publish({ type: "progress", percent: progress && progress.percent }));
    deps.updater.on("update-downloaded", (info) => publish({ type: "downloaded", version: info && info.version }));
    deps.updater.on("update-not-available", () => {
      publish({ type: "not-available" });
      schedule(nextCheckDelayMs(state));
    });
    deps.updater.on("error", failUpdate);
    schedule(FIRST_CHECK_DELAY_MS);
  }

  return {
    hostStdout(chunk) { decoder.push(chunk); },
    hostExit(code) {
      decoder.end();
      const message = hostExitMessage(code, { quitting, fatalShown });
      if (message) deps.showError(message);
    },
    setQuitting() { quitting = true; },
    navigate(url) {
      const decision = navDecision(url, origin);
      if (decision === "allow") return false;
      if (decision === "external") deps.openExternal(url);
      return true;
    },
    startUpdates,
    checkNow,
    updateState() { return state; },
    installUpdate(host) {
      if (!canInstall(state)) return Promise.resolve(false);
      quitting = true;
      return handoffUpdate({
        state,
        host,
        updater: deps.updater,
        graceMs: deps.graceMs,
        recover: async (error) => {
          deps.log(`[更新] 交给安装器失败：${error && (error.stack || error.message) ? (error.stack || error.message) : error}`);
          deps.showError("没能启动更新安装程序，OpenDesign 将重新打开。请稍后重试。");
          deps.relaunch();
        },
      });
    },
  };
}

module.exports = { createController };
