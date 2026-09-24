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

**我们管的配置**(主槽端点认得出是哪家,或界面里加过额外厂商的 key)里,这个脚本不自己写,改走和界面同一个入口
`ds_credential.select_model`:只许选网关手里有 key 的那几家目录里的模型、同名模型按厂商命名(`glm-5.3@glm`)、
两家都有又没给 `--provider` 就拒绝、手选盖过「想换过去」标记。以前它自己写,正用 Kimi 时 `set_model.py glm-5.3`
会把 glm-5.3 发到 Kimi 的端点(track opendesign-kimi-glm-vendors 第 5 轮;判据 k13/k13b/k13c)。
一个我们的厂商槽都没有的配置(只有自配端点 / 纯 onboard)照下面的老办法写(k13e)。

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

import ds_credential  # 厂商目录与预设命名(preset_name)的唯一真相源
import ds_model  # preset-优先规则单一真相源(L1;与 ds_web._read_model 同源)

DEFAULT_CONFIG = os.path.join(os.path.expanduser("~"), ".nanobot", "config.json")


def main() -> int:
    ap = argparse.ArgumentParser(description="切换 nanobot agents.defaults.model")
    ap.add_argument("model", help="模型 id,如 xiaomi/mimo-v2.5-pro")
    ap.add_argument("--config", default=DEFAULT_CONFIG,
                    help=f"nanobot config 路径(默认 {DEFAULT_CONFIG})")
    ap.add_argument("--provider", default=None,
                    help="厂商 id(如 glm_plan / glm);模型名几家都有时必须给")
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

    # 「我们管的配置」= 配置里有任何一个我们管的厂商槽(主槽认得出,或界面加过的额外厂商)。
    # 只看主槽不够:自配端点(老版本 install.ps1 手填过的,09-24 起不再能填)+ 界面加了两家 GLM 时会走老分支,无视 --provider(第 6 轮 #26,k13d)。
    # 目录 = 内置 ⊕ 设置页登记(track opendesign-zcode-model-settings P4):自定义供应商的额外槽也算「我们管的」
    with ds_credential.catalog_scope(ds_credential.home_of(args.config)):
        ours = isinstance(cfg, dict) and bool(ds_credential._live_vendors(cfg))
    if ours:
        return _select_via_the_ui_entry(args, cfg, original)

    defaults = cfg.setdefault("agents", {}).setdefault("defaults", {})
    active_preset = ds_model.active_preset_name(cfg)  # 与 _read_model 同一判定(L1)
    if active_preset:
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


def _select_via_the_ui_entry(args, cfg: dict, original: str) -> int:
    old = ds_model.resolve_model(cfg)
    nb_dir = os.path.dirname(os.path.abspath(args.config))
    # 装法里配置在 <home>/.nanobot/config.json,「想换过去」标记在同一个 home 下 —— 手选要把它作废(v18 / k13c)
    home = os.path.dirname(nb_dir) if os.path.basename(nb_dir) == ".nanobot" else None
    try:
        st = ds_credential.select_model(args.config, args.model.strip(), provider=args.provider, home=home)
    except ds_credential.CredentialError as exc:
        print(f"set_model: {exc}(配置一字未动)", file=sys.stderr)
        return 2
    with open(args.config + ".bak", "w", encoding="utf-8") as fh:
        fh.write(original)                      # 备份 = 改前原文
    print(f"set_model: {old or '(未设)'} → {st.get('current')}({st.get('label')})")
    print("已落盘;网关每句话前重读配置,下一句起生效。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
