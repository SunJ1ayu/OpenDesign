"use strict";

const stopping = new WeakMap();

function shutdownHost(child, { graceMs = 15000 } = {}) {
  if (!child || child.exitCode !== null) return Promise.resolve();
  if (stopping.has(child)) return stopping.get(child);

  const promise = new Promise((resolve) => {
    let finished = false;
    let timer = null;
    const done = () => {
      if (finished) return;
      finished = true;
      if (timer) clearTimeout(timer);
      resolve();
    };
    child.once("exit", done);
    child.once("close", done);
    try {
      child.stdin.end();
    } catch {
      done();
      return;
    }
    timer = setTimeout(() => {
      if (child.exitCode === null) {
        try { child.kill(); } catch { done(); }
      } else {
        done();
      }
    }, graceMs);
  });
  stopping.set(child, promise);
  return promise;
}

async function installUpdate({ state, host, updater, graceMs = 15000, recover }) {
  const { canInstall } = require("./updateState");
  if (!canInstall(state)) return false;
  await shutdownHost(host, { graceMs });
  // electron-updater 装不上时**不抛**:install() 里 dispatchError(e) ⇒ 同步发 "error" 事件、return false,
  // quitAndInstall 看到 false 就什么都不做(6.8.9 out/BaseUpdater.js:13-26,42-67)。只认「抛了」会把失败当成交棒成功:
  // 后台已收、窗口留着、托盘也退不掉(T5 R1-2)。⇒ 交棒那一下期间收到的 error 也算失败。
  let failure = null;
  const onError = (error) => { if (!failure) failure = error || new Error("quitAndInstall 报错但没给原因"); };
  const listens = typeof updater.on === "function" && typeof updater.removeListener === "function";
  if (listens) updater.on("error", onError);
  try {
    updater.quitAndInstall();
  } catch (error) {
    failure = failure || error;
  } finally {
    if (listens) updater.removeListener("error", onError);
  }
  if (!failure) return true;
  if (recover) await recover(failure);
  return false;
}

module.exports = { shutdownHost, installUpdate };
