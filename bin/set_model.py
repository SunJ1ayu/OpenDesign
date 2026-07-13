#!/usr/bin/env python3
"""set_model.py — 切换 OpenDesign 大脑,写入口 = nanobot 真正读的那个字段。

用法:
    python bin/set_model.py xiaomi/mimo-v2.5-pro
    python bin/set_model.py xiaomi/mimo-v2.5 --config C:\\Users\\PC\\.nanobot\\config.json

nanobot 的解析规则(schema.py:AgentDefaults):agents.defaults.modelPreset 设了就赢,
model 字段被无视。所以切换必须跟着同一条规则写,否则静默无效(07-13 真机发现):
  - modelPreset 已设(install.ps1 合并模板后的形态)→ 建/更新 model_presets[<新模型名>]
    (参数抄当前激活预设;悬空/无预设则最小新建 provider=custom)+ 重指 modelPreset;
    输家 model 字段一字不碰,旧预设保留供 /model 切回;
  - modelPreset 未设(纯 onboard 形态)→ 改 agents.defaults.model(此时它才是真相源)。

其余契约不变(oracle tests/test_set_model.py 锁定):
  - 上面点名之外的字段值一个不碰(整文件按标准 JSON 缩进重排——值不变,空白归一);
  - 改前把原文备份到 config.json.bak;
  - config 缺失/损坏 → 非零退出且不写任何文件(不越权创建配置,装机走 install.ps1);
  - 切换只落盘 —— 必须重启 gateway 才生效(运行中的进程不自动换脑,部署目标规则)。

设计定位(07-12 拍板):浏览器不做写端点(ds-web 只读铁律),模型切换 = 仓内脚本,
与 enable_webui.py 同模式;设置弹层只负责回显 /api/health 的 model 字段。
"""
import argparse
import json
import os
import sys

DEFAULT_CONFIG = os.path.join(os.path.expanduser("~"), ".nanobot", "config.json")


def main() -> int:
    ap = argparse.ArgumentParser(description="切换 nanobot agents.defaults.model")
    ap.add_argument("model", help="模型 id,如 xiaomi/mimo-v2.5-pro")
    ap.add_argument("--config", default=DEFAULT_CONFIG,
                    help=f"nanobot config 路径(默认 {DEFAULT_CONFIG})")
    args = ap.parse_args()

    model = args.model.strip()
    if not model:
        print("set_model: 模型 id 不能为空", file=sys.stderr)
        return 2
    if not os.path.isfile(args.config):
        print(f"set_model: 找不到 config {args.config} —— 先完成安装(install.ps1)",
              file=sys.stderr)
        return 2

    with open(args.config, encoding="utf-8") as fh:
        original = fh.read()
    try:
        cfg = json.loads(original)
    except ValueError as e:
        print(f"set_model: config 不是合法 JSON({e}),一字未动", file=sys.stderr)
        return 2

    defaults = cfg.setdefault("agents", {}).setdefault("defaults", {})
    active_preset = defaults.get("modelPreset")
    if isinstance(active_preset, str) and active_preset:
        # preset 布局:写 preset 侧(nanobot 里它优先于 model 字段)
        presets = cfg.setdefault("model_presets", {})
        base = presets.get(active_preset)
        old = base.get("model", active_preset) if isinstance(base, dict) else active_preset
        entry = dict(base) if isinstance(base, dict) else {"provider": "custom"}
        entry.update(label=model, model=model)
        presets[model] = entry
        defaults["modelPreset"] = model
    else:
        old = defaults.get("model")
        defaults["model"] = model

    with open(args.config + ".bak", "w", encoding="utf-8") as fh:
        fh.write(original)                      # 备份 = 改前原文
    with open(args.config, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print(f"set_model: {old or '(未设)'} → {model}")
    print("已落盘;重启 gateway 生效(关掉 ds-nanobot 窗口重开,或重启服务)。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
