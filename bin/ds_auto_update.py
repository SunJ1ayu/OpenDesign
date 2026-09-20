#!/usr/bin/env python3
"""打开软件倒计时自动更新的本机记账。

只记录"这个版本自动试过":接力脚本回滚时界面已经没了,失败事实来不及补写,
所以必须在动手前预写。文件放在数据根 Logs 下,不碰用户数据目录。
"""
from __future__ import annotations

import json
import os
import tempfile
import time

RECORD_NAME = "auto-update-attempts.json"
RECENT_FAILURE_SECONDS = 600


def record_path(data_root: str) -> str:
    return os.path.join(str(data_root), "Logs", RECORD_NAME)


def read_attempts(data_root: str) -> dict[str, float]:
    try:
        with open(record_path(data_root), encoding="utf-8") as fh:
            body = json.load(fh)
    except (OSError, ValueError, TypeError):
        return {}
    raw = body.get("attempts") if isinstance(body, dict) else None
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for version, ts in raw.items():
        if not isinstance(version, str):
            continue
        try:
            out[version] = float(ts)
        except (TypeError, ValueError):
            continue
    return out


def attempted_at(data_root: str, version: object) -> float | None:
    if not isinstance(version, str) or not version:
        return None
    attempts = read_attempts(data_root)
    return attempts.get(version)


def auto_eligible(data_root: str, version: object) -> bool:
    """这一版还够不够格**自动**更新 —— 链上三处共用的**唯一**判据。

    🔴 为什么要有这个函数(2026-09-20 第 2 轮外审,subcursor 与 subdeepseek 各自独立报):
    在它之前,这本账只有**真装那一刻**(`ds_web._auto_update_status`)在读。而"要不要
    自动装这一版"这个问题,链上其实有**三个**地方在答:

        prepare(后台要不要把 46MB 下下来)   —— 原来只问 check_cached
        startup(打开软件要不要弹更新界面装) —— 原来只看 update-state.json
        apply(真装)                          —— 原来唯一读账的一处

    于是出现这条不收敛的链:装失败 → 记账 + 删包 → 业主开着软件满 60s → 后台把**同一个
    装不上的包**重新下回来 → 下次打开又弹一次更新界面 → 又判 attempted → 又删……
    症状从"每次打开"变成"每两次打开",外加每轮 46MB 流量。**在末端删文件,永远追不上
    前端重新备货** —— 这是同一类问题的第二个补丁,所以改抽象:判断只写一处,三处共用。

    语义:**同一版自动只试一次**(永久,不是时效窗口)。
    - 拿 `recent_failure`(10 分钟窗口)冒充资格 ⇒ 过了窗口又重下一遍、又空演一次(判据 el1b)。
    - 账读不出来时当作"没试过" —— 与 `_auto_update_status` 一直以来的语义保持一致,
      不在这里制造第二种解释;账真写不进去时的防线是 apply 侧的 `auto_unrecorded`。
    - 只管**自动**更新。业主自己点「更新」永远不受它限制(判据 el6)。
    """
    return attempted_at(data_root, version) is None


def recent_failure(data_root: str, version: object, now: float | None = None) -> bool:
    ts = attempted_at(data_root, version)
    if ts is None:
        return False
    if now is None:
        now = time.time()
    return now - ts < RECENT_FAILURE_SECONDS


def record_attempt(data_root: str, version: object, now: float | None = None) -> tuple[bool, str | None]:
    """把一个版本的自动尝试原子写到账里;失败时旧账保持原样。"""
    if not isinstance(version, str) or not version:
        return False, "没有可记录的版本号"
    if now is None:
        now = time.time()
    logs = os.path.join(str(data_root), "Logs")
    try:
        os.makedirs(logs, exist_ok=True)
        attempts = read_attempts(data_root)
        attempts[version] = float(now)
        payload = {"attempts": attempts}
        fd, tmp = tempfile.mkstemp(prefix=".auto-update-attempts-", suffix=".tmp", dir=logs)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, record_path(data_root))
        except Exception:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise
    except Exception as exc:  # noqa: BLE001 —— 端点要把它变成 auto_unrecorded,不甩栈给业主
        return False, str(exc) or exc.__class__.__name__
    return True, None
