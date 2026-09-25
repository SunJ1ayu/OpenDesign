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
_TOOL_PREFIX = "mcp_design-studio_"
_PREFIX_RE = re.compile(r"^【当前项目:([^】]+)】")
_ENV_REF_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")   # 与网关 config/loader.py 同规则
_TS_RE = re.compile(r'"timestamp":\s*"([^"]+)"')   # 行上自己的时间;工具结果里的是转义过的 \"timestamp\",对不上


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

def webui_dir(cfg_path: str) -> str:
    """网关界面回放记录的目录:配置文件旁边的 webui/(nanobot config/paths.py get_runtime_subdir)。"""
    return os.path.join(os.path.dirname(os.path.abspath(cfg_path)), "webui")


# path ⇒ ((mtime_ns, size), 解析结果);对话文件与回放记录共用,每次只重读变了的文件
_cache: dict[str, tuple[tuple[int, int], tuple]] = {}
_cache_lock = threading.Lock()


def _args(raw) -> dict:
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


class _Touched:
    """一段记录里碰过的项目名(按出现顺序、去重)+ 改名别名。"""

    def __init__(self):
        self.names: list[str] = []
        self.aliases: list[tuple[str, str]] = []

    def add(self, v):
        if isinstance(v, str) and v.strip() and v.strip() not in self.names:
            self.names.append(v.strip())

    def prefix(self, text: str):
        m = _PREFIX_RE.match(text or "")
        if m:
            self.add(m.group(1))

    def tool(self, name, args: dict, ok: bool | None = None):
        """ok = 工具回的是不是成功;None = 这一行还看不到结果(对话文件里结果在后面的 tool 行,见 _scan_file)。
        改名只在成功时记别名 —— 失败的改名(新名被占 name_taken 等)照记会把旧名的对话挂到别的项目下(评审 GPT H1)。"""
        if not isinstance(name, str) or not name.startswith(_TOOL_PREFIX):
            return None
        tool = name[len(_TOOL_PREFIX):]
        if tool == "rename_project_tool":
            old, new = args.get("old"), args.get("new")
            self.add(old)
            self.add(new)
            if isinstance(old, str) and isinstance(new, str) and old.strip() and new.strip():
                pair = (old.strip(), new.strip())
                if ok:
                    self.aliases.append(pair)
                return pair
        elif tool == "read_project_tool":
            self.add(args.get("name"))
        else:
            self.add(args.get("project"))
        return None


def _tool_ok(result) -> bool:
    """工具回话是否成功:ds_tools 成功回 {"ok": true, …},失败回 {"error": …}。"""
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except ValueError:
            return False
    return isinstance(result, dict) and result.get("ok") is True and "error" not in result


def _scan_file(path: str, fallback_key: str) -> tuple:
    """一个对话文件 ⇒ (会话 key, 碰过的项目名, 改名别名, 最后一条消息的 timestamp)。坏行跳过。"""
    key = fallback_key
    t = _Touched()
    seen_user = False
    last_ts = None
    pending: dict = {}      # 改名调用 id ⇒ (旧, 新):等后面的 tool 行说成功才记别名
    with open(path, encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            if i > 0:
                # 最后聊天时间 = 最后一条带时间的消息(网关空闲压缩会刷元数据 updated_at,留下的最近几条带原时间,design P6);
                # 逐行找而不是只看最后一行:最后一行碰巧没带时间也不退回被刷过的 updated_at(评审 Kimi F1)
                ts = _TS_RE.findall(line)
                if ts:
                    last_ts = ts[-1]
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
                t.prefix(_user_text(row.get("content")))
                continue
            if row.get("role") == "tool":
                pair = pending.pop(row.get("tool_call_id"), None)
                if pair and _tool_ok(row.get("content")):
                    t.aliases.append(pair)
                continue
            for call in row.get("tool_calls") or []:
                fn = call.get("function") if isinstance(call, dict) else None
                if isinstance(fn, dict):
                    pair = t.tool(fn.get("name"), _args(fn.get("arguments")))
                    if pair:
                        pending[call.get("id")] = pair
    return key, t.names, t.aliases, last_ts


def _scan_transcript(path: str) -> tuple:
    """一份界面回放记录(只追加,不被空闲压缩)⇒ (这份第一句用户话里的项目前缀, 工具碰过的项目名, 改名别名, 这份里有没有用户话)。
    事件:`user`(text)、`message.tool_events[]`(name / arguments 对象)。"""
    t = _Touched()
    first = _Touched()
    has_user = False
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            is_user = '"user"' in line
            if not is_user and _TOOL_PREFIX not in line:
                continue          # 流式正文 / 思考片段占了绝大多数行,不解析
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if not isinstance(ev, dict):
                continue
            if ev.get("event") == "user":
                if not has_user:
                    first.prefix(ev.get("text") if isinstance(ev.get("text"), str) else "")
                has_user = True
                continue
            for te in ev.get("tool_events") or []:
                if isinstance(te, dict):
                    t.tool(te.get("name"), _args(te.get("arguments")), ok=_tool_ok(te.get("result")))
    return (first.names[0] if first.names else None), t.names, t.aliases, has_user


def _cached(path: str, parse, live: set):
    try:
        st = os.stat(path)
    except OSError:
        return None
    sig = (st.st_mtime_ns, st.st_size)
    live.add(path)
    hit = _cache.get(path)
    if hit is None or hit[0] != sig:
        try:
            hit = (sig, parse(path))
        except OSError:
            return None
        _cache[path] = hit
    return hit[1]


def _list(d: str, pred) -> list[str]:
    try:
        return sorted(e.path for e in os.scandir(d) if pred(e))
    except OSError:
        return []


def _scan_all(sessions_dir: str, webui: str | None) -> tuple[dict, dict, dict]:
    """⇒ (key ⇒ 项目名列表(未展开别名), key ⇒ 最后一条消息时间, 旧名 ⇒ 新名)。"""
    is_ws = lambda e: e.name.startswith("websocket_") and e.name.endswith(".jsonl") and e.is_file()  # noqa: E731
    names: dict[str, list[str]] = {}
    last: dict[str, str] = {}
    pairs: list[tuple[str, str]] = []

    def merge(key, got):
        cur = names.setdefault(key, [])
        for n in got:
            if n not in cur:
                cur.append(n)

    with _cache_lock:
        live: set = set()
        if webui:
            # 回放记录在前:它是完整历史(早的分段 → 当前那份),首句的项目前缀也在这里
            for path in _list(webui, is_ws):
                key = "websocket:" + os.path.basename(path)[len("websocket_"):-len(".jsonl")]
                seg_dir = path[:-len(".jsonl")] + ".segments"
                user_seen = False
                for seg in _list(seg_dir, lambda e: e.name.endswith(".jsonl") and e.is_file()) + [path]:
                    got = _cached(seg, _scan_transcript, live)
                    if got is None:
                        continue
                    prefix, seg_names, seg_pairs, has_user = got
                    # 项目前缀只认整段历史的第一句(项目栏发起的对话只有第一句带);后面分段里第一句的前缀是正文里后来写的
                    merge(key, ([prefix] if prefix and not user_seen else []) + seg_names)
                    pairs.extend(seg_pairs)
                    user_seen = user_seen or has_user
        for path in _list(sessions_dir, is_ws):
            fallback = "websocket:" + os.path.basename(path)[len("websocket_"):-len(".jsonl")]
            got = _cached(path, lambda p, fb=fallback: _scan_file(p, fb), live)
            if got is None:
                continue
            key, got_names, got_pairs, last_ts = got
            merge(key, got_names)
            pairs.extend(got_pairs)
            if last_ts:
                last[key] = last_ts
        for gone in [p for p in _cache if p not in live and (p.startswith(sessions_dir) or (webui and p.startswith(webui)))]:
            del _cache[gone]
    alias = {old: new for old, new in pairs if old != new}
    return names, last, alias


def _resolve(name: str, alias: dict[str, str]) -> str:
    seen = {name}
    while name in alias and alias[name] not in seen:   # 改名链 a⇒b⇒c 走到底;成环就停
        name = alias[name]
        seen.add(name)
    return name


def session_projects(sessions_dir: str, webui: str | None = None) -> dict[str, list[str]]:
    """{"websocket:<id>": [项目名, …]};没碰过项目的对话不出现;目录不在 ⇒ {}。
    webui = 网关界面回放记录目录(见 webui_dir);给了就一起读(长对话被空闲压缩后,早期的工具调用只在那里,design P1′)。"""
    names, _last, alias = _scan_all(sessions_dir, webui)
    out: dict[str, list[str]] = {}
    for key, ns in names.items():
        resolved: list[str] = []
        for n in ns:
            r = _resolve(n, alias)
            if r not in resolved:
                resolved.append(r)
        if resolved:
            out[key] = resolved
    return out


def last_active(sessions_dir: str) -> dict[str, str]:
    """{"websocket:<id>": 最后一条消息的 timestamp};消息没带时间的不出现(前端退回网关的 updated_at)。"""
    return _scan_all(sessions_dir, None)[1]


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


def update_sidebar(ds_root: str, fn) -> dict:
    """锁内读 - 改 - 写:fn(state) ⇒ 新 state;原子替换。返回回给前端的两个字段。"""
    path = sidebar_path(ds_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with ds_common.archive_lock(path):
        state = fn(_read_state(path))
        ds_common.atomic_write_text(path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    return public_state(state)
