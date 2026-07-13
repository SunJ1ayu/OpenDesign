#!/usr/bin/env python3
"""nanobot config 的「当前大脑」解析 —— _read_model(ds_web)与 set_model.py 的单一真相源。

L1(07-13 盲评):这条『modelPreset 优先于 model 字段』的规则(schema.py:AgentDefaults)
此前抄在两处,正是 07-13 押错边那个雷的余震。抽成纯函数,两边共用,永不再漂。
纯 stdlib、只吃已解析的 cfg dict,不碰文件/IO。
"""
from __future__ import annotations


def active_preset_name(cfg: dict) -> str | None:
    """agents.defaults.modelPreset 为非空字符串则返回它,否则 None。
    『preset 布局 vs 纯 onboard 布局』的唯一判定点。"""
    name = cfg.get("agents", {}).get("defaults", {}).get("modelPreset")
    return name if isinstance(name, str) and name else None


def resolve_model(cfg: dict) -> str | None:
    """当前生效大脑:preset 布局取 model_presets[preset].model,悬空/未设回落
    agents.defaults.model;都没有 → None。只读 model 字段会在 preset 布局回显假值。"""
    name = active_preset_name(cfg)
    if name:
        preset = cfg.get("model_presets", {}).get(name)
        if isinstance(preset, dict):
            m = preset.get("model")
            if isinstance(m, str) and m:
                return m
    m = cfg.get("agents", {}).get("defaults", {}).get("model")
    return m if isinstance(m, str) and m else None
