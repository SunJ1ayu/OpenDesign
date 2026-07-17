#!/usr/bin/env python3
"""把 OpenDesign Windows config 模板合并进已有的 nanobot config.json。

用法:
    python ds_merge_config.py TEMPLATE.jsonc TARGET.json [--api-base URL] [--model NAME]

只合并模板里的四段(TARGET 先备份为 TARGET.bak-<时间戳>):
    providers.custom / model_presets / agents.defaults / tools.mcpServers
channels 段永远不碰 —— websocket 归 `nanobot onboard` 管,feishu 是可选通道不预填。
--api-base/--model 不给时保持模板默认(MiMo 示例端点)。
"""

import argparse
import json
import shutil
import sys
import time
from pathlib import Path


def strip_jsonc(text: str) -> str:
    """去掉 // 与 /* */ 注释;字符串字面量里的 `//`(如 https://)原样保留。"""
    out = []
    i, n = 0, len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:  # 转义对(如 \"、\\)整对跳过
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
        elif c == '"':
            in_str = True
            out.append(c)
            i += 1
        elif c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
        elif c == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def deep_merge(dst: dict, src: dict) -> None:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            deep_merge(dst[k], v)
        else:
            dst[k] = v


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("template", type=Path)
    ap.add_argument("target", type=Path)
    ap.add_argument("--api-base", default=None)
    ap.add_argument("--model", default=None)
    args = ap.parse_args()

    if not args.target.exists():
        print(f"ds_merge_config: 目标 {args.target} 不存在(先跑 nanobot onboard)", file=sys.stderr)
        return 1

    tpl = json.loads(strip_jsonc(args.template.read_text(encoding="utf-8")))
    try:
        cfg = json.loads(args.target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ds_merge_config: {args.target} 不是合法 JSON({e}),不动它", file=sys.stderr)
        return 1

    if args.api_base:
        tpl["providers"]["custom"]["apiBase"] = args.api_base
    if args.model:
        # 换端点 = 模板的 MiMo 示例预设全部作废:替换成机主模型的单一预设
        # (预设 key 直接用模型名,与模板"/model 列表显示模型名"的约定一致),
        # 并把默认预设指过去。maxTokens 等参数沿用模板第一个预设的值。
        base = dict(next(iter(tpl["model_presets"].values())))
        base.update(label=args.model, model=args.model)
        tpl["model_presets"] = {args.model: base}
        tpl["agents"]["defaults"]["modelPreset"] = args.model

    wanted = {
        "providers": {"custom": tpl["providers"]["custom"]},
        "model_presets": tpl["model_presets"],   # 全部预设(primary + pro…),供 /model 切换
        "agents": {"defaults": tpl["agents"]["defaults"]},
        # tools.file.enable=false 一并合并:关内置文件工具,逼 PKB 只走 MCP(见模板注释)。
        # tools.exec.enable=false 同理(opendesign-intake 审出):nanobot 内置 exec 默认开且
        # restrictToWorkspace 默认 false,模型能跑任意命令直接造 `.approved`/搬文件 ——
        # 整个"人工批准闸物理绕不过"的不变量(deploy-security §0)靠它关掉才成立。
        # 产品流程不用 exec(定时提醒走内置 cron 工具),关掉零功能损失。
        # deep_merge 只覆盖 enable 子键,不动 onboard 写的其它字段。
        "tools": {
            "mcpServers": tpl["tools"]["mcpServers"],
            "file": tpl["tools"].get("file", {"enable": False}),
            "exec": tpl["tools"].get("exec", {"enable": False}),
        },
    }

    backup = args.target.with_name(args.target.name + f".bak-{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(args.target, backup)

    deep_merge(cfg, wanted)
    args.target.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"ds_merge_config: 已合并 4 段进 {args.target}(备份: {backup.name})")
    print(f"  apiBase = {tpl['providers']['custom']['apiBase']}")
    default_preset = tpl["agents"]["defaults"]["modelPreset"]
    print(f"  model   = {tpl['model_presets'][default_preset]['model']}(默认预设 {default_preset})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
