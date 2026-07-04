#!/usr/bin/env python3
"""开启 nanobot 的 WebSocket 通道(本地 WebUI)并设登录口令。

onboard 在 Windows 上不一定会启用 WebUI 通道(实测 channels 全为 false),
本脚本幂等地把它打开并设 token。改前先备份 config.json.bak,只动 websocket 段。

用法:
    python enable_webui.py <登录口令>
"""
import json
import os
import shutil
import sys


def main():
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("用法: python enable_webui.py <登录口令>", file=sys.stderr)
        sys.exit(1)
    token = sys.argv[1].strip()
    p = os.path.expanduser("~/.nanobot/config.json")
    if not os.path.exists(p):
        print(f"找不到 {p}(先跑 install.ps1 / nanobot onboard 生成配置)", file=sys.stderr)
        sys.exit(1)
    shutil.copy(p, p + ".bak")
    with open(p, encoding="utf-8") as f:
        c = json.load(f)
    ws = c.setdefault("channels", {}).setdefault("websocket", {})
    ws["enabled"] = True
    ws["token"] = token
    ws.setdefault("host", "127.0.0.1")
    ws.setdefault("port", 8765)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(c, f, indent=2, ensure_ascii=False)
    with open(p, encoding="utf-8") as f:
        d = json.load(f)["channels"]["websocket"]
    print(
        f"OK 写回确认 -> enabled={d['enabled']} "
        f"host={d.get('host')} port={d.get('port')} token={d['token']!r}"
    )
    print(f"备份: {p}.bak")


if __name__ == "__main__":
    main()
