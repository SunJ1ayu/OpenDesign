"use strict";

function trayMenuTemplate({ onOpen, onExport, onQuit }) {
  return [
    { label: "打开 OpenDesign", click: onOpen },
    { label: "导出本次启动诊断", click: onExport },
    { type: "separator" },
    { label: "退出", click: onQuit },
  ];
}

function contextMenuTemplate(params) {
  const flags = params.editFlags || {};
  if (params.isEditable) {
    return [
      ...(flags.canCut ? [{ label: "剪切", role: "cut" }] : []),
      ...(flags.canCopy ? [{ label: "复制", role: "copy" }] : []),
      ...(flags.canPaste ? [{ label: "粘贴", role: "paste" }] : []),
      ...(flags.canSelectAll ? [{ label: "全选", role: "selectAll" }] : []),
    ];
  }
  return params.selectionText && flags.canCopy ? [{ label: "复制", role: "copy" }] : [];
}

module.exports = { trayMenuTemplate, contextMenuTemplate };
