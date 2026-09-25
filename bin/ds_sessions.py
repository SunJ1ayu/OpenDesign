#!/usr/bin/env python3
"""侧栏「历史对话 + 项目」的后台纯逻辑(track opendesign-sidebar-history)。

两件事:
  1. 对话碰过哪些项目 —— **从网关已有的对话记录读出来**,不另建索引(design C8 驳回理由)。
     网关把每段对话存成 `<工作区>/sessions/websocket_<id>.jsonl`:第一行 `_type: metadata`(带 key),
     其后每行一条消息;助手调项目工具时,工具名 `mcp_design-studio_<工具>_tool`、参数在
     `tool_calls[].function.arguments`(通常是 JSON 串,偶尔是对象)。认这几种:
       - 参数 `project`(append_change / set_stage / log_communication …);
       - `read_project_tool` 的 `name`(只读过档案也算碰过 —— QA 设计);
       - `rename_project_tool` 的 `old` / `new`,并记成别名 旧 ⇒ 新(改名前的对话归到新名下,4c C2);
       - 首条用户消息开头的「【当前项目:X】」(项目栏发起的对话,前缀与 web/src/chat/projectThread.ts 同源)。
     别的 MCP 服务(organize / refs)与客户工具(create_client 等的 name 是客户名)不算。
     名字原样返回(可能是项目 key,也可能只是名字),由前端对上当前项目列表。
     按文件 (mtime, size) 缓存:每次侧栏刷新只重读变了的文件。
  2. 置顶 / 改名(design P3′):存 ds_web 自己的 `<数据根>/config/sidebar.json`,**不经网关** ——
     网关的状态更新口把整份状态塞进网址,请求行 8192 字节就断(探针收据见 track evidence)。
     只动 pinned_keys / title_overrides 两个字段,文件里别的字段原样;锁内读 - 改 - 写 + 原子替换。
"""
from __future__ import annotations

import json
import os
import re
import threading

import ds_common

TITLE_MAX = 160            # 与网关标题上限一致(nanobot sidebar_state._MAX_TITLE_LEN)
_KEY_MAX = 512
_TOOL_PREFIX = "mcp_design-studio_"
_PREFIX_RE = re.compile(r"^【当前项目:([^】]+)】")
_ENV_REF_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")   # 与网关 config/loader.py 同规则


# ---------------------------------------------------------------- 网关工作区

def workspace_dir(cfg_path: str) -> str | None:
    """网关工作区目录:配置 agents.defaults.workspace,`${VAR}` 与 `~` 照网关规则展开;
    没写 ⇒ ~/.nanobot/workspace(网关默认)。配置读不了 / 变量没设 ⇒ None(网关自己也起不来)。"""
    try:
        with open(cfg_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, ValueError):
        return None
    ws = ((cfg.get("agents") or {}).get("defaults") or {}).get("workspace") if isinstance(cfg, dict) else None
    if not isinstance(ws, str) or not ws.strip():
        ws = "~/.nanobot/workspace"
    missing = [v for v in _ENV_REF_RE.findall(ws) if v not in os.environ]
    if missing:
        return None
    ws = _ENV_REF_RE.sub(lambda m: os.environ[m.group(1)], ws)
    return os.path.expanduser(ws)


# ---------------------------------------------------------------- 对话碰过哪些项目

_cache: dict[str, tuple[tuple[int, int], tuple[str, list[str], list[tuple[str, str]]]]] = {}
_cache_lock = threading.Lock()


def _args(fn: dict) -> dict:
    raw = fn.get("arguments")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            obj = json.loads(raw)
        except ValueError:
            return {}
        return obj if isinstance(obj, dict) else {}
    return {}


def _user_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                return part["text"]
    return ""


def _scan_file(path: str, fallback_key: str) -> tuple[str, list[str], list[tuple[str, str]]]:
    """一个对话文件 ⇒ (会话 key, 碰过的项目名按出现顺序, 改名别名[(旧, 新)])。坏行跳过。"""
    key = fallback_key
    names: list[str] = []
    aliases: list[tuple[str, str]] = []
    seen_user = False

    def add(v):
        if isinstance(v, str) and v.strip() and v.strip() not in names:
            names.append(v.strip())

    with open(path, encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            # 首条用户消息之前的行(元数据)照解析;之后只解析带项目工具名的行 —— 工具结果常常很长
            if seen_user and _TOOL_PREFIX not in line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if not isinstance(row, dict):
                continue
            if i == 0 and row.get("_type") == "metadata":
                if isinstance(row.get("key"), str) and row["key"]:
                    key = row["key"]
                continue
            if row.get("role") == "user" and not seen_user:
                seen_user = True
                m = _PREFIX_RE.match(_user_text(row.get("content")))
                if m:
                    add(m.group(1))
                continue
            for call in row.get("tool_calls") or []:
                fn = call.get("function") if isinstance(call, dict) else None
                if not isinstance(fn, dict):
                    continue
                name = fn.get("name")
                if not isinstance(name, str) or not name.startswith(_TOOL_PREFIX):
                    continue
                tool = name[len(_TOOL_PREFIX):]
                a = _args(fn)
                if tool == "rename_project_tool":
                    old, new = a.get("old"), a.get("new")
                    add(old)
                    add(new)
                    if isinstance(old, str) and isinstance(new, str) and old.strip() and new.strip():
                        aliases.append((old.strip(), new.strip()))
                elif tool == "read_project_tool":
                    add(a.get("name"))
                else:
                    add(a.get("project"))
    return key, names, aliases


def _resolve(name: str, alias: dict[str, str]) -> str:
    seen = {name}
    while name in alias and alias[name] not in seen:   # 改名链 a⇒b⇒c 走到底;成环就停
        name = alias[name]
        seen.add(name)
    return name


def session_projects(sessions_dir: str) -> dict[str, list[str]]:
    """{"websocket:<id>": [项目名, …]};没碰过项目的对话不出现;目录不在 ⇒ {}。"""
    try:
        entries = [e for e in os.scandir(sessions_dir)
                   if e.name.startswith("websocket_") and e.name.endswith(".jsonl") and e.is_file()]
    except OSError:
        return {}
    scanned = []
    with _cache_lock:
        live = set()
        for e in entries:
            try:
                st = e.stat()
            except OSError:
                continue
            sig = (st.st_mtime_ns, st.st_size)
            live.add(e.path)
            hit = _cache.get(e.path)
            if hit is None or hit[0] != sig:
                fallback = "websocket:" + e.name[len("websocket_"):-len(".jsonl")]
                try:
                    hit = (sig, _scan_file(e.path, fallback))
                except OSError:
                    continue
                _cache[e.path] = hit
            scanned.append(hit[1])
        for gone in [p for p in _cache if os.path.dirname(p) == sessions_dir and p not in live]:
            del _cache[gone]
    alias: dict[str, str] = {}
    for _key, _names, pairs in scanned:
        for old, new in pairs:
            if old != new:
                alias[old] = new
    out: dict[str, list[str]] = {}
    for key, names, _pairs in scanned:
        resolved: list[str] = []
        for n in names:
            r = _resolve(n, alias)
            if r not in resolved:
                resolved.append(r)
        if resolved:
            out[key] = resolved
    return out


# ---------------------------------------------------------------- 置顶 / 改名

def clean_title(raw) -> str | None:
    """去首尾空格;空 / 不是字符串 ⇒ None(= 恢复自动名字);超长截到 160。"""
    if not isinstance(raw, str):
        return None
    t = raw.strip()
    return t[:TITLE_MAX] if t else None


def _pins(state: dict) -> list[str]:
    v = state.get("pinned_keys")
    return [k for k in v if isinstance(k, str) and k] if isinstance(v, list) else []


def _titles(state: dict) -> dict[str, str]:
    v = state.get("title_overrides")
    if not isinstance(v, dict):
        return {}
    return {k: t for k, t in v.items() if isinstance(k, str) and isinstance(t, str) and t}


def patch_sidebar(state: dict, key: str, *, pinned: bool | None = None, title=...) -> dict:
    """只动 pinned_keys / title_overrides,返回新 dict;title=None ⇒ 删改名,不传 ⇒ 不碰。"""
    out = dict(state)
    if pinned is not None:
        pins = [k for k in _pins(state) if k != key]
        if pinned:
            pins.append(key)
        out["pinned_keys"] = pins
    if title is not ...:
        titles = _titles(state)
        t = clean_title(title)
        if t is None:
            titles.pop(key, None)
        else:
            titles[key] = t
        out["title_overrides"] = titles
    return out


def forget_session(state: dict, key: str) -> dict:
    """对话删掉后,把它从置顶与改名里一起去掉(4c C11)。"""
    return patch_sidebar(state, key, pinned=False, title=None)


def public_state(state: dict) -> dict:
    """回给前端的只有这两个字段。"""
    return {"pinned_keys": _pins(state), "title_overrides": _titles(state)}


def sidebar_path(ds_root: str) -> str:
    return os.path.join(ds_common.data_root(ds_root), "config", "sidebar.json")


def _read_state(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            obj = json.load(fh)
    except (OSError, ValueError):
        return {}                       # 没有 / 坏了 ⇒ 当空(坏文件下一次写会被整份替换)
    return obj if isinstance(obj, dict) else {}


def load_sidebar(ds_root: str) -> dict:
    return public_state(_read_state(sidebar_path(ds_root)))


def valid_key(key: str) -> bool:
    return isinstance(key, str) and 0 < len(key) <= _KEY_MAX


def update_sidebar(ds_root: str, fn) -> dict:
    """锁内读 - 改 - 写:fn(state) ⇒ 新 state;原子替换。返回回给前端的两个字段。"""
    path = sidebar_path(ds_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with ds_common.archive_lock(path):
        state = fn(_read_state(path))
        ds_common.atomic_write_text(path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    return public_state(state)
