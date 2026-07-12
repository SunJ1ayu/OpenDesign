#!/usr/bin/env python3
"""set_model.py — 切换 OpenDesign 大脑(nanobot 的 agents.defaults.model)。

用法:
    python bin/set_model.py xiaomi/mimo-v2.5-pro
    python bin/set_model.py xiaomi/mimo-v2.5 --config C:\\Users\\PC\\.nanobot\\config.json

契约(oracle tests/test_set_model.py 锁定):
  - 只改 agents.defaults.model 一个字段,其余(端点/key/channels)一字不碰;
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

    old = cfg.setdefault("agents", {}).setdefault("defaults", {}).get("model")
    cfg["agents"]["defaults"]["model"] = model

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
