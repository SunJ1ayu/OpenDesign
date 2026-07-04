#!/usr/bin/env python3
"""加一个 "pro" 模型预设,方便用 `/model` 命令在 v2.5 / v2.5-pro 间切换。

nanobot 的模型切换 = 命名预设 + 聊天里打 `/model <名>`(不需要前端按钮)。本脚本在
config.json 的 model_presets 里补一个 "pro" 预设(拷贝现有 primary 的端点/参数,只换模型名),
之后聊天框输 `/model pro` 切到 pro、`/model primary` 切回。默认(重启后)仍是 primary。

幂等:只增/更新 "pro" 预设,不动 primary、provider、key;改前备份 config.json.bak。

用法:  python add_model_presets.py [pro_model_id]
        pro_model_id 缺省 = mimo-v2.5-pro(若你的端点上 pro 是别的名字,传进来即可)
"""
import copy
import json
import os
import shutil
import sys


def main():
    pro_model = sys.argv[1].strip() if len(sys.argv) > 1 and sys.argv[1].strip() else "mimo-v2.5-pro"
    p = os.path.expanduser("~/.nanobot/config.json")
    if not os.path.exists(p):
        print(f"找不到 {p}(先跑 install.ps1 / nanobot onboard)", file=sys.stderr)
        sys.exit(1)
    with open(p, encoding="utf-8") as f:
        c = json.load(f)
    presets = c.get("model_presets") or c.get("modelPresets")
    key = "model_presets" if "model_presets" in c else "modelPresets"
    if not presets or "primary" not in presets:
        print("config 里没有 model_presets.primary,无法拷贝基准预设", file=sys.stderr)
        sys.exit(1)
    shutil.copy(p, p + ".bak")
    pro = copy.deepcopy(presets["primary"])   # 继承 primary 的 provider/maxTokens/温度等
    pro["label"] = "MiMo Pro"
    pro["model"] = pro_model
    presets["pro"] = pro
    c[key] = presets
    with open(p, "w", encoding="utf-8") as f:
        json.dump(c, f, indent=2, ensure_ascii=False)
    print(f"OK 已加预设 pro -> model={pro_model}(provider={pro.get('provider')})")
    print("切换:聊天框输  /model pro   切到 pro;  /model primary   切回。默认仍 primary。")
    print(f"备份: {p}.bak")


if __name__ == "__main__":
    main()
