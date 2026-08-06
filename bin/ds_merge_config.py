#!/usr/bin/env python3
"""把 OpenDesign Windows config 模板合并进已有的 nanobot config.json。

用法:
    python ds_merge_config.py TEMPLATE.jsonc TARGET.json [--api-base URL] [--model NAME]

只合并模板里的四段(TARGET 先备份为 TARGET.bak-<时间戳>):
    providers.custom / model_presets / agents.defaults / tools.mcpServers
channels 段永远不碰 —— websocket 归 `nanobot onboard` 管,feishu 是可选通道不预填。
--api-base/--model 不给时:**以目标配置里已有的为准**(不重置机主选好的大脑),
目标里也没有才落模板默认(MiMo 示例端点)。
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

    # ── 已经装过的机器:**不许把机主选好的大脑重置回模板默认**(2026-08-06)──────
    # 形状:装完之后机主用 `/model` 或 `set_model.py` 换了大脑;下次更新再合一次配置,
    # 不带 --model 时模板的 MiMo 示例默认会把 apiBase / modelPreset 原样盖回去。
    # **静默发生**,而机主不是程序员 —— 他看到的只是"助手突然变笨了",不会去翻配置。
    # 规则:显式给了 --api-base/--model 就照做;没给就以**目标里已有的**为准;
    #      目标里也没有(全新装机)才落模板默认。
    # 模板的**预设清单**照旧合进来(更新的意义就在这儿),只是不动"默认指向哪一个"。
    if args.api_base:
        tpl["providers"]["custom"]["apiBase"] = args.api_base
    else:
        existing_base = (cfg.get("providers", {}).get("custom", {}) or {}).get("apiBase")
        if existing_base:
            tpl["providers"]["custom"]["apiBase"] = existing_base

    if not args.model:
        existing_preset = (cfg.get("agents", {}).get("defaults", {}) or {}).get("modelPreset")
        own_presets = cfg.get("model_presets", {}) or {}
        # 机主的默认预设必须真的存在(自有的,或模板带来的),否则等于指向空气 ——
        # nanobot 对这种配置**直接拒绝加载**(schema.py 的 model validator 会抛),
        # 也就是说留着它 = 机器起不来。所以要回落。
        known = set(tpl["model_presets"]) | set(own_presets)
        if existing_preset and existing_preset in known:
            tpl["agents"]["defaults"]["modelPreset"] = existing_preset
        elif own_presets:
            # 悬空了,但机主自己还有别的预设 ⇒ 用他自己的第一个,别落回模板默认:
            # 那会产出「模板的模型 @ 机主的端点」这种自相矛盾态(四审 subdeepseek MEDIUM)——
            # 模型名在机主的端点上根本不存在,聊天时才炸。
            tpl["agents"]["defaults"]["modelPreset"] = next(iter(own_presets))

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

    # 汇总印**落地文件里的值**,不是模板的值。
    # 修好上面那条之后两者会不一样 —— 还照印模板,就成了"屏幕说大脑是 MiMo、
    # 盘上其实是机主的模型"。这台机器的规矩:盘上和回显对不上 = BLOCK。
    landed_base = cfg["providers"]["custom"]["apiBase"]
    landed_preset = cfg["agents"]["defaults"]["modelPreset"]
    landed_model = (cfg.get("model_presets", {}).get(landed_preset, {}) or {}).get("model", "?")
    print(f"ds_merge_config: 已合并 4 段进 {args.target}(备份: {backup.name})")
    print(f"  apiBase = {landed_base}")
    print(f"  model   = {landed_model}(默认预设 {landed_preset})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
