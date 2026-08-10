#!/usr/bin/env python3
"""业主同意闸:危险动作先暂存,只由 ds_web 批准后执行。"""
from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
from datetime import datetime

import ds_lock

MODE_ASK = "ask"
MODE_ALLOW = "allow"
GUARDED_ACTIONS = ("set_workspace", "bind_project")

_PENDING_ID_RE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{6}$")


def _config_dir(ds_root: str) -> str:
    return os.path.join(ds_root, "config")


def _consent_path(ds_root: str) -> str:
    return os.path.join(_config_dir(ds_root), "consent.json")


def _pending_dir(ds_root: str) -> str:
    return os.path.join(_config_dir(ds_root), "pending")


def _pending_path(ds_root: str, pending_id: str) -> str:
    return os.path.join(_pending_dir(ds_root), f"{pending_id}.json")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _write_json(path: str, obj: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=os.path.dirname(path),
                prefix=f".{os.path.basename(path)}.", suffix=".tmp",
                delete=False) as fh:
            tmp = fh.name
            json.dump(obj, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
        tmp = None
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass


def load_mode(ds_root: str) -> str:
    """读取同意档位;任何坏状态一律 fail-closed 到 ask。"""
    try:
        with open(_consent_path(ds_root), encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return MODE_ASK
    if not isinstance(raw, dict):
        return MODE_ASK
    mode = raw.get("mode")
    return mode if mode in (MODE_ASK, MODE_ALLOW) else MODE_ASK


def set_mode(ds_root: str, mode: str) -> dict:
    if mode not in (MODE_ASK, MODE_ALLOW):
        return {"error": "mode_invalid"}
    _write_json(_consent_path(ds_root), {"mode": mode})
    return {"ok": True, "mode": mode}


def is_valid_pending_id(pid) -> bool:
    return isinstance(pid, str) and bool(_PENDING_ID_RE.match(pid))


def _read_pending_file(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as fh:
            rec = json.load(fh)
    except (OSError, ValueError):
        return None
    return rec if isinstance(rec, dict) else None


def _pending_lock_path(ds_root: str) -> str:
    return os.path.join(_config_dir(ds_root), "pending.lock")


def _with_pending_lock(ds_root: str):
    os.makedirs(_config_dir(ds_root), exist_ok=True)
    return open(_pending_lock_path(ds_root), "a+b")


def _public_pending(rec: dict) -> dict:
    return {
        "pending_id": rec.get("pending_id"),
        "action": rec.get("action"),
        "params": rec.get("params"),
        "created": rec.get("created"),
    }


def _find_same_unresolved(ds_root: str, action: str, params: dict) -> dict | None:
    for rec in list_pending(ds_root):
        if rec.get("action") == action and rec.get("params") == params:
            return rec
    return None


def create_pending(ds_root: str, action: str, params: dict) -> dict:
    if action not in GUARDED_ACTIONS or not isinstance(params, dict):
        return {"error": "bad_pending"}
    with _with_pending_lock(ds_root) as lock_fh, ds_lock.exclusive(lock_fh):
        same = _find_same_unresolved(ds_root, action, params)
        if same is not None:
            return {"ok": True, "pending": True, "pending_id": same["pending_id"]}
        os.makedirs(_pending_dir(ds_root), exist_ok=True)
        while True:
            pid = datetime.now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3)
            path = _pending_path(ds_root, pid)
            if not os.path.exists(path):
                break
        rec = {
            "pending_id": pid,
            "action": action,
            "params": params,
            "created": _now(),
            "resolved_at": None,
        }
        _write_json(path, rec)
    return {"ok": True, "pending": True, "pending_id": pid}


def list_pending(ds_root: str) -> list:
    out = []
    try:
        names = sorted(os.listdir(_pending_dir(ds_root)))
    except OSError:
        return out
    for name in names:
        if not (name.endswith(".json")
                and is_valid_pending_id(name[:-5])):
            continue
        rec = _read_pending_file(os.path.join(_pending_dir(ds_root), name))
        if not isinstance(rec, dict) or rec.get("resolved_at") is not None:
            continue
        if rec.get("action") not in GUARDED_ACTIONS:
            continue
        if not isinstance(rec.get("params"), dict):
            continue
        pid = rec.get("pending_id") if is_valid_pending_id(rec.get("pending_id")) \
            else name[:-5]
        rec["pending_id"] = pid
        out.append(_public_pending(rec))
    return out


def get_pending(ds_root: str, pending_id: str) -> dict | None:
    if not is_valid_pending_id(pending_id):
        return None
    rec = _read_pending_file(_pending_path(ds_root, pending_id))
    if not isinstance(rec, dict):
        return None
    rec.setdefault("pending_id", pending_id)
    rec.setdefault("resolved_at", None)
    return rec


def resolve_pending(ds_root: str, pending_id: str, approve: bool,
                    apply_fn=None) -> dict:
    """批准/拒绝一条待确认。**批准时由调用方传进来的 `apply_fn` 执行。**

    ⚠️ **为什么执行器是注入的,而不是本模块自己 import ds_tools**:
    第一版在这里写了 `import ds_tools`(函数内延迟导入),而 `ds_tools` 顶部又
    `import ds_consent`(它要在写口上插闸)—— 一个新的循环依赖。
    `tests/test_no_import_cycles.py` 当场抓到,**人眼审 diff 时我没看出来**
    (那道闸的立身之本就是这个:结构问题肉眼不完备)。

    注入还更贴 design:那里写的就是「业主点同意 → **ds_web 后端**照 pending 里
    记的参数执行」。所以执行器本来就该来自 ds_web 那一侧。

    `apply_fn(action, params, ds_root) -> dict`;没给就**不执行**(fail-closed),
    绝不因为"没人告诉我怎么执行"而把它当成批准。
    """
    if not is_valid_pending_id(pending_id):
        return {"error": "bad_pending_id"}
    if not isinstance(approve, bool):
        return {"error": "bad_approve"}
    with _with_pending_lock(ds_root) as lock_fh, ds_lock.exclusive(lock_fh):
        path = _pending_path(ds_root, pending_id)
        rec = _read_pending_file(path)
        if rec is None:
            return {"error": "pending_not_found"}
        if rec.get("resolved_at") is not None:
            return {"error": "already_resolved"}
        action = rec.get("action")
        params = rec.get("params")
        if action not in GUARDED_ACTIONS or not isinstance(params, dict):
            return {"error": "bad_pending"}
        if approve:
            if apply_fn is None:
                # fail-closed:没有执行器就不执行,也不标已决 —— 卡片留着,
                # 业主下次还能点。绝不把"我不知道怎么执行"当成批准。
                return {"error": "no_applier"}
            applied = apply_fn(action, params, ds_root)
            if not applied.get("ok"):
                return applied
        rec["resolved_at"] = _now()
        _write_json(path, rec)
    return {"ok": True, "applied": bool(approve)}
