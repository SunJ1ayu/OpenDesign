"use strict";

const SHELL_MARK = "shell=1";

function httpUrl(raw) {
  try {
    const url = new URL(raw);
    return url.protocol === "http:" || url.protocol === "https:" ? url : null;
  } catch {
    return null;
  }
}

function navDecision(raw, origin) {
  const url = httpUrl(raw);
  if (!url) return typeof raw === "string" && /^https?:\/\//i.test(raw) ? "external" : "deny";
  if (origin && url.origin === origin) return "allow";
  return "external";
}

function windowOpenDecision(raw) {
  return httpUrl(raw) ? "external" : "deny";
}

function workbenchUrl(port) {
  return `http://127.0.0.1:${port}/?${SHELL_MARK}`;
}

module.exports = { navDecision, windowOpenDecision, workbenchUrl, SHELL_MARK };
