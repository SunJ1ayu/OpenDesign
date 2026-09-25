#!/usr/bin/env python3
"""网关启动器:让运行中的 nanobot 网关**每次解析 `${VAR}` 时现读 key 文件**(track opendesign-key-restart)。

外壳起网关用它(`ds_shell_core.gateway_argv`),其余参数原样交给 `nanobot gateway`。

为什么要有它:以前 key 只在起网关时以环境变量注入,存新 key ⇒ 必须重启网关;
而那条重启在 Windows 上卡死(业主 09-25:「新对话一直显示链接不上gateway」)。
nanobot 本来就每句话前重读配置、重解析 `${VAR}`、key 变了就换 provider ——
只差「解析时去哪拿值」。这里把那一处换成:key 文件优先,读不到落回环境变量,两边都没有照 nanobot 原样抛。
配置里仍只有 `${VAR}` 引用,key 原文不进配置。

🔴 钩的是 nanobot 私有函数 `nanobot.config.loader._env_replace`(loader 内按模块全局名查它)。
   nanobot 升级改了这一处 ⇒ 启动器**拒绝开跑**、说一句人话(外壳会把它弹给业主),
   不许静默退回「只认启动时的 env」:那样存 key 不生效,界面却说下一句就用(判据 G4)。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import ds_credential  # noqa: E402

REFUSE = ("OpenDesign 的网关启动器和这一版 nanobot 对不上(找不到解析 key 的那一处),"
          "存了 key 不会自动生效,所以先不启动。请把 OpenDesign 更新到最新版,或把这句话发给开发者。")


def install_live_keys() -> None:
    """把 key 文件现读装到 nanobot 的 `${VAR}` 解析上。钩点不在 ⇒ SystemExit(REFUSE)。"""
    import nanobot.config.loader as loader

    orig = getattr(loader, "_env_replace", None)
    users = [getattr(loader, n, None) for n in ("_resolve_in_place", "_resolve_env_vars")]
    if not callable(orig) or not all(
            callable(f) and "_env_replace" in f.__code__.co_names for f in users):
        raise SystemExit(REFUSE)

    home = os.path.expanduser("~")

    def _live_env_replace(match):
        name = match.group(1)
        try:
            value = ds_credential.live_key(home, name, str(loader.get_config_path()))
        except Exception:        # 读 key 出什么错都不许把网关每句前的重读炸掉:落回 env
            value = None
        return value if value else orig(match)

    loader._env_replace = _live_env_replace


def main() -> None:
    install_live_keys()
    from nanobot.cli.commands import app
    sys.argv = ["nanobot", "gateway", *sys.argv[1:]]
    app()


if __name__ == "__main__":
    main()
