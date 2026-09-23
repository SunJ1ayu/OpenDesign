"use strict";

// 发给管家的命令(window-shown / report / quit / export-diagnostics)走这一处(track opendesign-instant-ui)。
// 窗口现在比管家先起:页面画完的首帧上报、窗口显示的那一声,都可能在管家 stdin 能写之前就发出。
// 以前直接丢 ⇒ 管家的 90 秒首帧看门等不到信号,写一份假的「界面没画出来」诊断(挑战腿指出)。
// 现在先攒着(有上限),attach 之后按原顺序补发。**不许 require("electron")**。

const { encodeCommand } = require("./hostProtocol");

const MAX_PENDING = 200;

function createHostSender({ log }) {
  let child = null;
  const pending = [];

  function write(command) {
    if (!child || child.exitCode !== null || !child.stdin || !child.stdin.writable) {
      log(`[管家 stdin] 管家不在,丢弃 ${command && command.cmd}`);
      return;
    }
    try {
      child.stdin.write(encodeCommand(command), "utf8");
    } catch (error) {
      log(`[管家 stdin] ${error}`);
    }
  }

  return {
    send(command) {
      if (child) {
        write(command);
        return;
      }
      if (pending.length >= MAX_PENDING) pending.shift();
      pending.push(command);
    },
    attach(next) {
      child = next;
      const queued = pending.splice(0);
      for (const command of queued) write(command);
    },
  };
}

module.exports = { createHostSender, MAX_PENDING };
