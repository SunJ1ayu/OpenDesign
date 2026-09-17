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
