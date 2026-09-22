"use strict";

function versionMismatch(appVersion, hostVersion) {
  if (hostVersion === appVersion) return null;
  const shownHost = hostVersion || "未报告";
  return `OpenDesign 这次安装没装完整：桌面程序是 ${appVersion}，后台是 ${shownHost}。请重新运行安装包。`;
}

module.exports = { versionMismatch };
