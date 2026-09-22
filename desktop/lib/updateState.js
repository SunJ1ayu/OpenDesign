"use strict";

const FIRST_CHECK_DELAY_MS = 15 * 1000;
const NORMAL_CHECK_DELAY_MS = 4 * 60 * 60 * 1000;
const ERROR_CHECK_DELAY_MS = 15 * 60 * 1000;

function initialUpdateState() {
  return { phase: "idle" };
}

function reduceUpdate(state, event) {
  if (state.phase === "downloaded" && (event.type === "checking" || event.type === "error")) return state;
  switch (event.type) {
    case "checking":
      return { phase: "checking" };
    case "available":
      return { phase: "downloading", version: event.version };
    case "progress":
      return { ...state, phase: "downloading", percent: event.percent };
    case "downloaded":
      return { phase: "downloaded", version: event.version || state.version };
    case "not-available":
      return { phase: "latest" };
    case "error":
      return { phase: "error", version: event.version || state.version, error: event.message || "更新检查失败" };
    default:
      return state;
  }
}

function canInstall(state) {
  return !!state && state.phase === "downloaded";
}

function nextCheckDelayMs(state) {
  return state && state.phase === "error" ? ERROR_CHECK_DELAY_MS : NORMAL_CHECK_DELAY_MS;
}

function configureUpdater(updater, { log }) {
  updater.autoDownload = true;
  updater.autoInstallOnAppQuit = false;
  updater.disableWebInstaller = true;
  updater.allowDowngrade = false;
  updater.logger = {
    info: (message) => log(`[更新] ${message}`),
    warn: (message) => log(`[更新] 警告 ${message}`),
    error: (message) => log(`[更新] 错误 ${message}`),
    debug: (message) => log(`[更新] ${message}`),
  };
  return updater;
}

module.exports = {
  initialUpdateState,
  reduceUpdate,
  canInstall,
  nextCheckDelayMs,
  FIRST_CHECK_DELAY_MS,
  configureUpdater,
};
