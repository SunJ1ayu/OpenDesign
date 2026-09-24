#!/usr/bin/env python3
"""把 OpenDesign Windows config 模板合并进已有的 nanobot config.json。

用法:
    python ds_merge_config.py TEMPLATE.jsonc TARGET.json

只合并模板里的四段(TARGET 先备份为 TARGET.bak-<时间戳>):
    providers.custom / model_presets / agents.defaults / tools.mcpServers
channels 段永远不碰 —— websocket 归 `nanobot onboard` 管,feishu 是可选通道不预填。
端点与当前模型**以目标配置里已有的为准**(不重置机主选好的大脑),目标里也没有才落模板默认(MiMo)。
**换厂商、换模型不在这里做**(09-24 起,track opendesign-kimi-glm-vendors):--api-base/--model 已取消,
给了就报错退出 —— 换厂商只走界面这一扇门(照 ZCode;老安装脚本手填端点+模型是第 9 轮 #31/#33 的写口)。
"""

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import ds_credential  # 厂商目录、预设命名与「预设只发到主人那家」对齐的唯一真相源


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


def _talk_utf8() -> None:
    """把自己的 stdout/stderr 重设成 UTF-8。

    🔴 **一句成功提示不该有能力弄死一次已经成功的合并**(2026-08-25,云机器实测
    run 32801760571)。英文 Windows 上这个进程的 stdout 是 cp1252,写不出
    "已合并"三个汉字 ⇒ `UnicodeEncodeError` ⇒ 退出码非零 ⇒ 上一层判定"合并失败"
    ⇒ 临时配置被删 ⇒ **全新的非中文 Windows 装不上,而且现象是安装程序假死**。
    配置那时其实早就写好了 —— 死的只是最后那句话。

    `errors="replace"` 是刻意的:输出通道是给人看的,**它有权难看,没权杀进程**。
    判据:tests/test_ds_provision.py 的 f1/f2。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass   # 拿不到就算了:这一步是保险,不是功能


def main() -> int:
    _talk_utf8()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("template", type=Path)
    ap.add_argument("target", type=Path)
    ap.add_argument("--api-base", default=None)
    ap.add_argument("--model", default=None)
    args = ap.parse_args()
    if args.api_base is not None or args.model is not None:
        print("ds_merge_config: 不再支持 --api-base / --model。换厂商、换模型请在 OpenDesign 界面的「AI 模型 key」里操作。"
              "(配置一字未动)", file=sys.stderr)
        return 2

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
    # 形状:装完之后机主在界面、`/model` 或 `set_model.py` 换了大脑;下次更新再合一次配置,
    # 模板的 MiMo 示例默认会把 apiBase / modelPreset 原样盖回去。
    # **静默发生**,而机主不是程序员 —— 他看到的只是"助手突然变笨了",不会去翻配置。
    # 规则:以**目标里已有的**为准;目标里也没有(全新装机)才落模板默认。
    # 模板的**预设清单**照旧合进来(更新的意义就在这儿),只是不动"默认指向哪一个" ——
    # 例外是机主自配的端点:模板预设全是 MiMo 的,不合(见下)。
    existing_base = (cfg.get("providers", {}).get("custom", {}) or {}).get("apiBase")
    if existing_base:
        tpl["providers"]["custom"]["apiBase"] = existing_base

    existing_preset = (cfg.get("agents", {}).get("defaults", {}) or {}).get("modelPreset")
    own_presets = cfg.get("model_presets", {}) or {}
    # 模板的预设全是 MiMo 的。主槽是机主以前自配的端点(认不出是哪家)时,合进来就会指 custom、
    # `mimo-v2.5` 发到他那个端点 ⇒ 不合,也不替他设 modelPreset(它压过 agents.defaults.model,
    # 纯 onboard 形态的机主会被换成一个他端点上没有的模型 ⇒ 聊天连不上;第 10 轮 #36,d5/d5b)。
    # 认得出的别家端点照合:之后的对齐会把它们删掉或指回 MiMo 自己的槽。
    foreign = bool(existing_base) and ds_credential._vendor_by_base(existing_base) is None
    if foreign:
        tpl["model_presets"] = {}
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
    elif foreign:
        tpl["agents"]["defaults"].pop("modelPreset", None)

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
    # 模板的 MiMo 预设合进了别家端点的配置(机主在界面换过厂商)、或盘上留着老安装写的裸名:
    # 与 save / 起网关同一条规矩对齐 —— 目录里的模型只以那家的正式名字挂在那家的槽上;当前模型因此悬空就回落。
    ds_credential._route_presets(cfg)
    ds_credential._fallback_if_dangling(cfg)
    defaults = cfg.setdefault("agents", {}).setdefault("defaults", {})
    if foreign and defaults.get("modelPreset") and defaults["modelPreset"] not in (cfg.get("model_presets") or {}):
        defaults.pop("modelPreset")              # 悬空的 modelPreset 网关直接拒绝加载;自配端点上不无中生有,删掉让 model 字段生效
    args.target.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 汇总印**落地文件里的值**,不是模板的值。
    # 修好上面那条之后两者会不一样 —— 还照印模板,就成了"屏幕说大脑是 MiMo、
    # 盘上其实是机主的模型"。这台机器的规矩:盘上和回显对不上 = BLOCK。
    landed_base = cfg["providers"]["custom"]["apiBase"]
    landed_preset = defaults.get("modelPreset")
    landed_model = ((cfg.get("model_presets", {}).get(landed_preset, {}) or {}).get("model")
                    if landed_preset else defaults.get("model")) or "?"
    print(f"ds_merge_config: 已合并 4 段进 {args.target}(备份: {backup.name})")
    print(f"  apiBase = {landed_base}")
    print(f"  model   = {landed_model}(默认预设 {landed_preset})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
