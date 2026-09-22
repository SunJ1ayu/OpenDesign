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
  try {
    updater.quitAndInstall();
    return true;
  } catch (error) {
    if (recover) await recover(error);
    return false;
  }
}

module.exports = { shutdownHost, installUpdate };
