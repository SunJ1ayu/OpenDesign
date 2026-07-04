#!/usr/bin/env python3
"""关闭 nanobot 内置文件工具(edit_file/write_file/apply_patch/read_file/grep/…)。

为什么:PKB(clients/projects)必须只经 design-studio 的 MCP 工具读写。内置文件工具给了
弱模型一条绕过安全层的路 —— 实测 MiMo 被要求"新建项目"时,用内置 edit_file 把文件写进
nanobot workspace(≠ DS_ROOT),导致 list_todos 扫不到。关掉它,只留 MCP 工具这一条路。

幂等:只设 tools.file.enable=false,改前备份 config.json.bak;不动 onboard/LLM/mcpServers。
新装机器由 install.ps1 的 config 合并自动带上此项,本脚本用于已装好的机器补设。

用法:  python disable_builtin_file_tools.py
"""
import json
import os
import shutil
import sys


def main():
    p = os.path.expanduser("~/.nanobot/config.json")
    if not os.path.exists(p):
        print(f"找不到 {p}(先跑 install.ps1 / nanobot onboard)", file=sys.stderr)
        sys.exit(1)
    shutil.copy(p, p + ".bak")
    with open(p, encoding="utf-8") as f:
        c = json.load(f)
    tools = c.setdefault("tools", {})
    filecfg = tools.setdefault("file", {})
    filecfg["enable"] = False
    with open(p, "w", encoding="utf-8") as f:
        json.dump(c, f, indent=2, ensure_ascii=False)
    with open(p, encoding="utf-8") as f:
        d = json.load(f)["tools"]["file"]["enable"]
    print(f"OK 写回确认 -> tools.file.enable={d}(内置文件工具已关闭)")
    print(f"备份: {p}.bak")


if __name__ == "__main__":
    main()
