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

// 站内 = 与窗口源站同协议、同主机、无端口无账号(track opendesign-instant-ui:源站是 app://opendesign)。
// 🔴 不能拿 `url.origin` 比:Node/WHATWG 对非特殊协议(app:)给的 origin 恒为 "null",
//    那样任何 app://xxx 都会被当成站内。
function sameSite(raw, origin) {
  if (!origin) return false;
  try {
    const u = new URL(raw);
    const o = new URL(origin);
    if (o.protocol === "http:" || o.protocol === "https:") return u.origin === o.origin;
    return u.protocol === o.protocol && u.hostname === o.hostname && u.port === o.port
      && !u.username && !u.password;
  } catch {
    return false;
  }
}

function navDecision(raw, origin) {
  if (sameSite(raw, origin)) return "allow";
  const url = httpUrl(raw);
  if (!url) return typeof raw === "string" && /^https?:\/\//i.test(raw) ? "external" : "deny";
  return "external";
}

function windowOpenDecision(raw) {
  return httpUrl(raw) ? "external" : "deny";
}

module.exports = { navDecision, windowOpenDecision, SHELL_MARK };
