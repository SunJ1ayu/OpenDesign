#!/usr/bin/env python3
"""把模型预设按【模型名】命名,让 `/model` 的当前/可选显示都是模型名;可选设启动默认档。

nanobot 的 `/model` 显示的"可选预设"用的是预设 key(不读 label),所以要让可选列表显示
`mimo-v2.5` / `mimo-v2.5-pro`,预设 key 就得直接起成模型名。本脚本把 model_presets 重排成:
  - key `mimo-v2.5`      → 标准档
  - key `mimo-v2.5-pro`  → pro 档
两档共用现有 primary 的 provider/端点/参数(只换模型名),清掉旧的 primary/pro 角色名 key,
并把【启动默认档】设为 --default 指定的那个(缺省 mimo-v2.5)。切换随时用 `/model <模型名>`。

幂等;改前备份 config.json.bak;不动 providers/key/tools。

用法:
    python add_model_presets.py                         # 默认档 = mimo-v2.5
    python add_model_presets.py --default mimo-v2.5-pro # 默认档 = pro
    python add_model_presets.py --pro <别的pro名>       # 端点上 pro 叫别的名字时
"""
import argparse
import copy
import json
import os
import shutil
import sys

STD_MODEL = "mimo-v2.5"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pro", default="mimo-v2.5-pro", help="pro 档的模型名(端点上的确切名)")
    ap.add_argument("--default", dest="default", default=STD_MODEL,
                    help="启动默认档(须是 mimo-v2.5 或上面 --pro 的名字)")
    args = ap.parse_args()
    pro_model = args.pro.strip()
    default_model = args.default.strip()
    if default_model not in (STD_MODEL, pro_model):
        print(f"--default 必须是 {STD_MODEL} 或 {pro_model},收到 {default_model!r}", file=sys.stderr)
        sys.exit(1)

    p = os.path.expanduser("~/.nanobot/config.json")
    if not os.path.exists(p):
        print(f"找不到 {p}(先跑 install.ps1 / nanobot onboard)", file=sys.stderr)
        sys.exit(1)
    with open(p, encoding="utf-8") as f:
        c = json.load(f)
    key = "model_presets" if "model_presets" in c else "modelPresets"
    presets = c.get(key) or {}
    base = copy.deepcopy(
        presets.get("primary")
        or next(iter(presets.values()), None)
        or {"provider": "custom", "maxTokens": 8192, "contextWindowTokens": 128000, "temperature": 0.1}
    )
    shutil.copy(p, p + ".bak")

    def mk(model):
        d = copy.deepcopy(base)
        d["model"] = model
        d["label"] = model
        d.setdefault("provider", "custom")
        return d

    for old in ("primary", "pro"):
        presets.pop(old, None)
    presets[STD_MODEL] = mk(STD_MODEL)
    presets[pro_model] = mk(pro_model)
    c[key] = presets
    c.setdefault("agents", {}).setdefault("defaults", {})["modelPreset"] = default_model

    with open(p, "w", encoding="utf-8") as f:
        json.dump(c, f, indent=2, ensure_ascii=False)
    print(f"OK 预设已按模型名重排 -> {list(presets.keys())}")
    print(f"启动默认档 = {default_model}")
    print(f"随时切换:聊天框  /model {pro_model}  或  /model {STD_MODEL}")
    print(f"备份: {p}.bak")


if __name__ == "__main__":
    main()
