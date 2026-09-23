"use strict";

const { createHostDecoder, hostExitMessage } = require("./hostProtocol");
const { versionMismatch } = require("./versionCheck");
const { navDecision } = require("./navPolicy");
const { APP_ORIGIN } = require("./appProtocol");
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
  // 源站在窗口创建时就定了(track opendesign-instant-ui):站内跳转不用等后台。
  const origin = APP_ORIGIN;
  let backend = { phase: "starting" };
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

  // 起不来:弹完这一个框就整个退出。加载页整页是拖动带、没有按钮,
  // 不退的话业主点掉框看到的是一直转圈的「正在启动…」(旧版 die() 也是弹框后退出)。
  const giveUp = (message) => {
    if (fatalShown) return;
    fatalShown = true;
    deps.showError(message);
    quitting = true;
    deps.quitApp();
  };

  const onHostEvent = (message) => {
    deps.log(`[管家→] ${JSON.stringify(message)}`);
    switch (message.event) {
      case "ready": {
        const mismatch = versionMismatch(deps.appVersion, message.version);
        if (mismatch) {
          deps.log(mismatch);
          giveUp(mismatch);
          return;
        }
        // 页面早就在了,这里只放行那些挂着的 /api 请求;**不换页**(换页 = 业主看到整页再来一次)。
        if (backend.phase === "ready") return;
        backend = { phase: "ready" };
        deps.backendReady(message.web_port);
        deps.pushBackendState(backend);
        return;
      }
      case "show":
        deps.showWindow();
        return;
      case "fatal":
        giveUp(message.message || "OpenDesign 后台启动失败。");
        return;
      case "alert":
      case "backend-died":
        deps.showError(message.message || "OpenDesign 后台发生错误。");
        return;
      case "already-running":
        giveUp("另一个 OpenDesign 后台正在运行，请先从托盘退出它。");
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
    // spawn 发 error(python.exe 缺失 / 被杀软隔离;收摊时 kill 失败也走这里)。
    hostError(error) {
      deps.log(`[管家] 进程出错:${error && (error.stack || error.message) ? (error.stack || error.message) : error}`);
      if (quitting) return;
      giveUp("OpenDesign 的后台程序没能启动，可能是安装不完整或被杀毒软件拦截。请重新运行安装包。");
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
    backendState() { return backend; },
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
