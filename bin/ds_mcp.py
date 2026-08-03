#!/usr/bin/env python3
"""design-studio 三个 MCP server 的**唯一入口**(track opendesign-mcp-registry)。

## ⚠️ 改这个文件的路径或参数之前先读这段

**用户机器上的 `~/.nanobot/config.json` 直接钉死本文件**:

```jsonc
"design-studio":          { "args": [".../bin/ds_mcp.py", "tools"] },
"design-studio-organize": { "args": [".../bin/ds_mcp.py", "organize"] },
"design-studio-refs":     { "args": [".../bin/ds_mcp.py", "refs"] }
```

而**那份 config 不在仓库里**(装机时由 `config/nanobot.config*.jsonc` 经
`install.ps1` Step 7 / `bin/ds_merge_config.py` 合并生成),**`git pull` 更新不到它**。

⇒ 改本文件的**文件名、位置、或三个 key 的拼写**,已装机的用户会在下一次使用时
发现**助手什么都不会做了**,而且他自己修不好(他不是程序员)。
真要改:同时改仓库里两份模板 **并且**让每台已装机的机器重跑一次装机脚本。
`tests/test_mcp_entry_contract.py` 钉着"模板必须指向本文件",但它**钉不住用户机上
那份已经生成的 config** —— 那一段只能靠人。

## 为什么入口要独立成一个文件(而不是让 ds_tools.py 自己当入口)

登记层原来长在三个业务模块里,登记时要反向 import 别的业务模块 ⇒ 全仓 3 个循环依赖,
只能靠"把 import 藏进函数里"绕开。把入口独立出来后依赖变单向
(`ds_mcp` → `ds_*_server` → 业务模块),环归零。
**如果让业务模块保留 `__main__` 入口再去 import 自己的 server,会留下
「入口 ⇄ 自己的 server」自环** —— 实测验证过,所以没走那条路。

## 契约(判据钉着,别改)

- `build(key)`:`key ∈ {"tools","organize","refs"}`;**坏 key 必须抛异常**,
  不许静默返回空 server(那会表现成"助手突然什么都不会了"却查不出原因)。
- `python bin/ds_mcp.py <key>` 起 stdio server;`--selftest` 只建不跑、打印工具数、退出 0。
- 三个 server 名(`design-studio` / `-organize` / `-refs`)是 config 里的键,**一字不许变**。
- `mcp` 包一律**延迟导入**:没装 mcp 时业务模块与 tests 要照常可用(承重墙)。
"""
from __future__ import annotations

import argparse
import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:                       # 仅类型检查期可见,运行期不 import mcp(承重墙)
    from mcp.server.fastmcp import FastMCP


def build(key: str) -> "FastMCP":
    if key == "tools":
        import ds_tools_server
        return ds_tools_server.build()
    if key == "organize":
        import ds_organize_server
        return ds_organize_server.build()
    if key == "refs":
        import ds_refs_server
        return ds_refs_server.build()
    raise ValueError(f"unknown MCP server key: {key}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("key", choices=("tools", "organize", "refs"))
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    server = build(args.key)
    if args.selftest:
        print(len(asyncio.run(server.list_tools())))
        return
    server.run()


if __name__ == "__main__":
    main()
