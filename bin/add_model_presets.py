#!/usr/bin/env python3
"""把模型预设按【模型名】命名,让 `/model` 的当前/可选显示都是模型名。

nanobot 的 `/model` 显示的"可选预设"用的是预设 key(不读 label),所以要让可选列表显示
`mimo-v2.5` / `mimo-v2.5-pro`,预设 key 就得直接起成模型名。本脚本把 model_presets 重排成:
  - key `mimo-v2.5`      → 标准档
  - key `mimo-v2.5-pro`  → pro 档
两档共用现有 primary 的 provider/端点/参数(只换模型名),并把默认档设为 mimo-v2.5、清掉旧的
primary/pro 角色名 key。切换:聊天框 `/model mimo-v2.5-pro` / `/model mimo-v2.5`。

幂等;改前备份 config.json.bak;不动 providers/key/tools。

用法:  python add_model_presets.py [pro_model_id]
        pro_model_id 缺省 = mimo-v2.5-pro(端点上 pro 若是别的名字,传进来)
"""
import copy
import json
import os
import shutil
import sys

STD_MODEL = "mimo-v2.5"


def main():
    pro_model = sys.argv[1].strip() if len(sys.argv) > 1 and sys.argv[1].strip() else "mimo-v2.5-pro"
    p = os.path.expanduser("~/.nanobot/config.json")
    if not os.path.exists(p):
        print(f"找不到 {p}(先跑 install.ps1 / nanobot onboard)", file=sys.stderr)
        sys.exit(1)
    with open(p, encoding="utf-8") as f:
        c = json.load(f)
    key = "model_presets" if "model_presets" in c else "modelPresets"
    presets = c.get(key) or {}
    # 基准参数:取现有 primary,退而取任一现有预设,再退到最小默认
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

    for old in ("primary", "pro"):          # 清掉旧角色名 key,可选列表只留模型名
        presets.pop(old, None)
    presets[STD_MODEL] = mk(STD_MODEL)
    presets[pro_model] = mk(pro_model)
    c[key] = presets
    c.setdefault("agents", {}).setdefault("defaults", {})["modelPreset"] = STD_MODEL

    with open(p, "w", encoding="utf-8") as f:
        json.dump(c, f, indent=2, ensure_ascii=False)
    print(f"OK 预设已按模型名重排 -> {list(presets.keys())}")
    print(f"默认档 = {STD_MODEL}")
    print(f"切换:聊天框  /model {pro_model}   切到 pro;  /model {STD_MODEL}   切回。")
    print(f"备份: {p}.bak")


if __name__ == "__main__":
    main()
