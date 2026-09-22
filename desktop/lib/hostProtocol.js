"use strict";

const { StringDecoder } = require("node:string_decoder");

function parseHostLine(line) {
  if (typeof line !== "string" || !line.trim()) return null;
  try {
    const value = JSON.parse(line.trim());
    if (!value || Array.isArray(value) || typeof value !== "object") return null;
    if (typeof value.event !== "string" || !value.event) return null;
    return value;
  } catch {
    return null;
  }
}

function createHostDecoder(onEvent) {
  const decoder = new StringDecoder("utf8");
  let pending = "";

  function consume(text) {
    pending += text;
    const lines = pending.split("\n");
    pending = lines.pop() ?? "";
    for (const line of lines) {
      const event = parseHostLine(line);
      if (event) onEvent(event);
    }
  }

  return {
    push(chunk) {
      if (typeof chunk === "string") consume(chunk);
      else if (chunk != null) consume(decoder.write(chunk));
    },
    end() {
      consume(decoder.end());
      const event = parseHostLine(pending);
      pending = "";
      if (event) onEvent(event);
    },
  };
}

function encodeCommand(command) {
  return `${JSON.stringify(command)}\n`;
}

function hostExitMessage(code, { quitting, fatalShown }) {
  if (quitting || fatalShown) return null;
  return `OpenDesign 后台意外退出了（退出码 ${code}）。请从托盘退出后重新打开。`;
}

module.exports = { parseHostLine, createHostDecoder, encodeCommand, hostExitMessage };
