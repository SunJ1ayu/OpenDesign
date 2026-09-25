#!/usr/bin/env python3
"""侧栏「历史对话 + 项目」后台 oracle —— track opendesign-sidebar-history(主 agent 亲写)。
跑法:python3 tests/test_sidebar_history_api.py

两块:
  A. bin/ds_sessions.py(纯逻辑):
     - workspace_dir(cfg_path):网关工作区 = 配置 agents.defaults.workspace(`${VAR}` 与 `~` 照网关规则展开),没写 ⇒ ~/.nanobot/workspace;
     - session_projects(sessions_dir):读 websocket_*.jsonl,收集 design-studio 项目工具调用参数里的项目名
       (project / read_project 的 name / rename_project 的 old,new —— 4c C4)+ 首条用户消息的「【当前项目:X】」;
       rename_project 做别名(旧名 ⇒ 新名,4c C2);坏行不崩;非 websocket_ 文件不管;别的 MCP 服务的工具不算;
     - patch_sidebar / forget_session:只动 pinned_keys / title_overrides,其余字段原样(4c C9 / C11)。
  B. ds_web 针孔(记录型假网关,照 tests/test_ds_web_proxy.py):
     GET  /api/chat/session-projects、GET /api/chat/sidebar-state(只回两个字段);
     POST /api/chat/sessions/<key>/pin {"pinned":bool}、…/rename {"title":str}:锁内读 - 改 - 写,别的字段原样回写;
     CT 不是 json / key 非法 / 跨站 ⇒ 拒且不写;删除成功后清这条的置顶与改名;删除时网关连不上 ⇒ 502、不清。
  碰过的项目还要读网关的**界面回放记录** `<配置目录>/webui/websocket_<id>.jsonl`(+ `.segments/*.jsonl`):网关每 15 分钟把闲置对话
     「空闲压缩」成最近约 8 条,长对话早期的工具调用从对话文件里没了,回放记录是只追加的(design P1′,探针 probe-idle-compact);
     最后聊天时间 = 对话文件里最后一条消息的 timestamp —— 元数据 updated_at 每次压缩都被刷成当时(design P6,探针 probe-real-sessions-time)。
  置顶 / 改名存在 ds_web 自己的 `<数据根>/config/sidebar.json`(同 consent.json 的位置与写法),**不经网关**:
     网关的状态更新口把整份状态塞进网址,请求行上限 8192 字节 —— 实测 60 条 10 字改名或 6 条 160 字改名就被断开,
     且之后每次写都要发整份 ⇒ 永远存不上、连取消置顶都取消不了(evidence/20260925T*-probe-gateway-longline.txt)。
     所以 e3b 存 100 条 160 字的改名必须全在;e3c 20 个置顶同时发一条不丢(锁)。
样本形状照本机真对话文件(~/.nanobot/workspace/sessions/websocket_*.jsonl,09-25 查):
  {"_type":"metadata","key":"websocket:<id>",...} 一行 + 消息行;工具调用在 assistant 行的 tool_calls[].function{name, arguments(JSON 串)}。
纯 stdlib、离线、端口 0。
"""
import http.client
import json
import os
import sys
import threading
import time
import unittest
import urllib.parse
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
sys.path.insert(0, HERE)

import _tmpreg  # noqa: E402
import ds_common  # noqa: E402
import ds_sessions  # noqa: E402
import ds_web  # noqa: E402

TOKEN = "sidebar-oracle-token"
CFG_DIR = _tmpreg.mkdtemp("ds-sidebar-判据配置-")
WS_DIR = _tmpreg.mkdtemp("ds-sidebar-工作区-")
SESS = os.path.join(WS_DIR, "sessions")
WEBUI = os.path.join(CFG_DIR, "webui")   # 网关把回放记录放在配置文件旁边的 webui/(nanobot config/paths.py get_runtime_subdir)


def _call(tool, /, **args):
    return {"id": "c", "type": "function",
            "function": {"name": f"mcp_design-studio_{tool}_tool", "arguments": json.dumps(args, ensure_ascii=False)}}


def _write_session(chat_id, lines):
    os.makedirs(SESS, exist_ok=True)
    path = os.path.join(SESS, f"websocket_{chat_id}.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"_type": "metadata", "key": f"websocket:{chat_id}", "metadata": {"title": "t"},
                             "updated_at": "2026-09-25T21:12:19.316099"},   # 网关空闲压缩刷成的「当时」
                            ensure_ascii=False) + "\n")
        for ln in lines:
            fh.write((ln if isinstance(ln, str) else json.dumps(ln, ensure_ascii=False)) + "\n")
    return path


def _transcript(chat_id, events, segment=None):
    """网关界面回放记录的形状(本机 ~/.nanobot/webui/websocket_*.jsonl,09-25 查):每行一个事件。"""
    d = os.path.join(WEBUI, f"websocket_{chat_id}.segments") if segment else WEBUI
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, segment or f"websocket_{chat_id}.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
    return path


def _tool_event(tool, /, **args):
    return {"event": "message", "chat_id": "x", "text": "", "kind": "progress", "tool_events": [
        {"version": 1, "phase": "end", "call_id": "c", "name": f"mcp_design-studio_{tool}_tool",
         "arguments": args, "result": "{\"ok\": true}", "error": None, "files": [], "embeds": []}]}


def _fixture():
    # a:记过翡翠湾的变更
    _write_session("a", [
        {"role": "user", "content": "帮我记一下"},
        {"role": "assistant", "content": "", "tool_calls": [_call("append_change", project="翡翠湾-1801", content="吊顶降 5cm")]},
        {"role": "tool", "name": "mcp_design-studio_append_change_tool", "content": "{\"ok\": true}"},
    ])
    # b:项目对话(首句带前缀)+ 读过另一个项目的档案(read_project 的参数叫 name)+ 一行坏的
    _write_session("b", [
        {"role": "user", "content": "【当前项目:陈总办公室】这周进度怎样"},
        "这一行不是 JSON",
        {"role": "assistant", "content": "", "tool_calls": [_call("read_project", name="滨江-12F")]},
        {"role": "user", "content": "【当前项目:不该算】正文里后来又出现的前缀不算"},
    ])
    # c:把「老宅」改名成「老宅翻新」;d:改名前记过「老宅」⇒ 应归到「老宅翻新」
    _write_session("c", [{"role": "assistant", "content": "", "tool_calls": [_call("rename_project", old="老宅", new="老宅翻新")]}])
    _write_session("d", [{"role": "assistant", "content": "", "tool_calls": [_call("append_change", project="老宅", content="x")]}])
    # e:arguments 是对象而不是串;别的 MCP 服务的工具不算;没碰项目
    _write_session("e", [
        {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "mcp_design-studio_set_stage_tool", "arguments": {"project": "翡翠湾-1801", "stage": "施工"}}},
            {"function": {"name": "mcp_organize_stage_intake_tool", "arguments": json.dumps({"project": "不该算"})}},
        ]},
    ])
    _write_session("f", [{"role": "user", "content": "今天天气"}, {"role": "assistant", "content": "晴"}])
    # 用户消息是多段(带图)时的前缀
    _write_session("g", [{"role": "user", "content": [{"type": "text", "text": "【当前项目:翡翠湾-1801】看这张"},
                                                     {"type": "image_url", "image_url": {"url": "x"}}]}])
    # i:长对话被网关空闲压缩过 —— 对话文件里只剩后面的闲聊;早期的项目前缀与记账只在回放记录里
    _write_session("i", [{"role": "user", "content": "那就这样吧", "timestamp": "2026-08-16T09:00:00.000000"},
                         {"role": "assistant", "content": "好", "timestamp": "2026-08-16T09:30:00.000000"}])
    _transcript("i", [{"event": "user", "chat_id": "i", "text": "【当前项目:滨江-12F】先看看进度"},
                      _tool_event("append_change", project="翡翠湾-1801", content="吊顶"),
                      {"event": "user", "chat_id": "i", "text": "【当前项目:不该算】后来的话"},
                      {"event": "turn_end", "chat_id": "i"}])
    # j:回放记录超 8MB 后挪进分段文件的早期部分
    _write_session("j", [{"role": "user", "content": "继续", "timestamp": "2026-08-10T08:00:00.000000"}])
    _transcript("j", [_tool_event("read_project", name="陈总办公室")], segment="000001.jsonl")
    _transcript("j", [{"event": "user", "chat_id": "j", "text": "继续"}])
    # 不是 websocket_ 的文件不管
    with open(os.path.join(SESS, "cli_direct.jsonl"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"role": "assistant", "tool_calls": [_call("append_change", project="翡翠湾-1801")]}) + "\n")


def setUpModule():
    _fixture()
    cfg = os.path.join(CFG_DIR, "config.json")
    with open(cfg, "w", encoding="utf-8") as fh:
        json.dump({"channels": {"websocket": {"enabled": True, "token": TOKEN}},
                   "agents": {"defaults": {"workspace": WS_DIR}}}, fh)
    os.environ["DS_NANOBOT_CONFIG"] = cfg


def tearDownModule():
    os.environ.pop("DS_NANOBOT_CONFIG", None)


# ---------------------------------------------------------------- A. 纯逻辑

class TestWorkspaceDir(unittest.TestCase):
    def _cfg(self, obj):
        p = os.path.join(_tmpreg.mkdtemp("ds-sidebar-cfg-"), "config.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(obj, fh)
        return p

    def test_w1_default_when_missing(self):
        self.assertEqual(ds_sessions.workspace_dir(self._cfg({})), os.path.expanduser("~/.nanobot/workspace"))

    def test_w2_env_and_tilde(self):
        os.environ["DS_SIDEBAR_TEST_HOME"] = "/tmp/某处"
        try:
            p = self._cfg({"agents": {"defaults": {"workspace": "${DS_SIDEBAR_TEST_HOME}/ws"}}})
            self.assertEqual(ds_sessions.workspace_dir(p), "/tmp/某处/ws")
        finally:
            os.environ.pop("DS_SIDEBAR_TEST_HOME", None)
        self.assertEqual(ds_sessions.workspace_dir(self._cfg({"agents": {"defaults": {"workspace": "~/w"}}})),
                         os.path.expanduser("~/w"))

    def test_w3_unreadable_config_is_none(self):
        self.assertIsNone(ds_sessions.workspace_dir(os.path.join(CFG_DIR, "不存在.json")))


class TestSessionProjects(unittest.TestCase):
    def test_p1_derived_mapping(self):
        got = ds_sessions.session_projects(SESS)
        self.assertEqual(got.get("websocket:a"), ["翡翠湾-1801"])
        self.assertEqual(got.get("websocket:b"), ["陈总办公室", "滨江-12F"], "首句前缀在前;read_project 的 name 也算;后来正文里的前缀不算;坏行跳过")
        self.assertEqual(got.get("websocket:c"), ["老宅翻新"], "改名本身:旧名经别名归到新名,不重复")
        self.assertEqual(got.get("websocket:d"), ["老宅翻新"], "改名前记过旧名的对话归到新名下(4c C2)")
        self.assertEqual(got.get("websocket:e"), ["翡翠湾-1801"], "arguments 是对象也认;别的 MCP 服务的工具不算")
        self.assertNotIn("websocket:f", got, "没碰项目的不出现")
        self.assertEqual(got.get("websocket:g"), ["翡翠湾-1801"], "多段用户消息里的前缀也认")
        self.assertFalse(any(k.startswith("cli") for k in got), "非 websocket_ 文件不管")

    def test_p4_transcript_after_idle_compact(self):
        got = ds_sessions.session_projects(SESS, WEBUI)
        self.assertEqual(got.get("websocket:i"), ["滨江-12F", "翡翠湾-1801"],
                         "对话文件被压缩后,回放记录里的首句前缀与记账照认;后来的前缀不算(design P1′)")
        self.assertEqual(got.get("websocket:j"), ["陈总办公室"], "挪进 .segments 的早期回放也读")
        self.assertEqual(got.get("websocket:a"), ["翡翠湾-1801"], "没有回放记录的对话照旧只看对话文件")
        self.assertNotIn("websocket:i", ds_sessions.session_projects(SESS), "不给回放目录就只看对话文件(证明上面那条靠的是回放记录)")

    def test_p5_transcript_change_is_reread(self):
        p = _transcript("m", [{"event": "user", "chat_id": "m", "text": "随便聊"}])
        _write_session("m", [{"role": "user", "content": "随便聊"}])
        self.assertNotIn("websocket:m", ds_sessions.session_projects(SESS, WEBUI))
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(_tool_event("set_stage", project="翡翠湾-1801", stage="施工"), ensure_ascii=False) + "\n")
        os.utime(p, (time.time() + 5, time.time() + 5))
        self.assertEqual(ds_sessions.session_projects(SESS, WEBUI).get("websocket:m"), ["翡翠湾-1801"], "回放记录变了要重读")
        os.remove(p)
        os.remove(os.path.join(SESS, "websocket_m.jsonl"))

    def test_p6_last_active_is_last_message_time(self):
        la = ds_sessions.last_active(SESS)
        self.assertEqual(la.get("websocket:i"), "2026-08-16T09:30:00.000000",
                         "最后一条消息的时间,不是元数据 updated_at(网关每次空闲压缩都刷它,design P6)")
        self.assertEqual(la.get("websocket:j"), "2026-08-10T08:00:00.000000")
        self.assertNotIn("websocket:a", la, "消息没带时间 ⇒ 不给,前端退回网关的 updated_at")

    def test_p2_missing_dir_is_empty(self):
        self.assertEqual(ds_sessions.session_projects(os.path.join(WS_DIR, "没有这个")), {})

    def test_p3_changed_file_is_reread(self):
        before = ds_sessions.session_projects(SESS)
        self.assertNotIn("websocket:h", before)
        p = _write_session("h", [])
        self.assertNotIn("websocket:h", ds_sessions.session_projects(SESS))
        time.sleep(0.01)
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"role": "assistant", "tool_calls": [_call("log_communication", project="陈总办公室", text="x")]}) + "\n")
        os.utime(p, (time.time() + 5, time.time() + 5))
        self.assertEqual(ds_sessions.session_projects(SESS).get("websocket:h"), ["陈总办公室"], "文件变了要重读(mtime 缓存不许让它过期不刷)")
        os.remove(p)


STATE = {
    "schema_version": 1, "pinned_keys": ["websocket:old"], "archived_keys": ["websocket:arch"],
    "title_overrides": {"websocket:old": "老名字"}, "project_name_overrides": {"x": "y"},
    "tags_by_key": {"websocket:t": ["标签"]}, "collapsed_groups": {"g": True},
    "view": {"density": "compact", "show_previews": True, "show_timestamps": False, "show_archived": False, "sort": "title_asc"},
    "updated_at": "2026-09-01T00:00:00Z",
}


class TestPatch(unittest.TestCase):
    def _others(self, s):
        return {k: v for k, v in s.items() if k not in ("pinned_keys", "title_overrides", "updated_at")}

    def test_s1_pin_unpin_keeps_other_fields(self):
        s = ds_sessions.patch_sidebar(json.loads(json.dumps(STATE)), "websocket:a", pinned=True)
        self.assertEqual(s["pinned_keys"], ["websocket:old", "websocket:a"])
        self.assertEqual(self._others(s), self._others(STATE), "别的字段一个都不许动")
        s = ds_sessions.patch_sidebar(s, "websocket:a", pinned=True)
        self.assertEqual(s["pinned_keys"].count("websocket:a"), 1, "重复置顶不叠")
        s = ds_sessions.patch_sidebar(s, "websocket:old", pinned=False)
        self.assertEqual(s["pinned_keys"], ["websocket:a"])

    def test_s2_rename_set_and_clear(self):
        s = ds_sessions.patch_sidebar(json.loads(json.dumps(STATE)), "websocket:a", title="新名")
        self.assertEqual(s["title_overrides"], {"websocket:old": "老名字", "websocket:a": "新名"})
        s = ds_sessions.patch_sidebar(s, "websocket:old", title=None)
        self.assertEqual(s["title_overrides"], {"websocket:a": "新名"}, "None = 恢复自动名字")
        self.assertEqual(self._others(s), self._others(STATE))

    def test_s3_forget(self):
        s = ds_sessions.forget_session(json.loads(json.dumps(STATE)), "websocket:old")
        self.assertEqual(s["pinned_keys"], [])
        self.assertEqual(s["title_overrides"], {})
        self.assertEqual(self._others(s), self._others(STATE))

    def test_s4_clean_title(self):
        self.assertEqual(ds_sessions.clean_title("  王女士 "), "王女士")
        self.assertIsNone(ds_sessions.clean_title("   "))
        self.assertIsNone(ds_sessions.clean_title(None))
        self.assertEqual(len(ds_sessions.clean_title("长" * 300)), 160)


# ---------------------------------------------------------------- B. ds_web 针孔

class _Up(BaseHTTPRequestHandler):
    def do_GET(self):
        srv = self.server
        base, _, q = self.path.partition("?")
        srv.requests.append({"path": base, "query": q, "auth": self.headers.get("Authorization")})
        if base == "/api/webui/sidebar-state":
            return self._json(200, srv.state)
        if base == "/api/webui/sidebar-state/update":
            raw = urllib.parse.parse_qs(q).get("state", [None])[0]
            srv.state = json.loads(raw)
            srv.updates += 1
            return self._json(200, srv.state)
        if base.startswith("/api/sessions/") and base.endswith("/delete"):
            return self._json(srv.delete_status, srv.delete_body)
        return self._json(404, {"error": "nope"})

    def _json(self, status, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@contextmanager
def _upstream():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Up)
    httpd.requests, httpd.state, httpd.updates, httpd.delete_status = [], json.loads(json.dumps(STATE)), 0, 200
    httpd.delete_body = {"deleted": True}
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        httpd.server_close()


@contextmanager
def _serve(nanobot_port):
    root = _tmpreg.mkdtemp("ds-sidebar-root-")
    os.makedirs(os.path.join(root, "projects"))
    dist = _tmpreg.mkdtemp("ds-sidebar-dist-")
    with open(os.path.join(dist, "index.html"), "w", encoding="utf-8") as fh:
        fh.write("<!doctype html>")
    httpd = ds_web.make_server(root, dist, port=0, nanobot_port=nanobot_port)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield httpd.server_address[1], root
    finally:
        httpd.shutdown()
        httpd.server_close()


def _side_path(root):
    """置顶 / 改名的家:业主数据根下的 config/sidebar.json(重装、清浏览器缓存都不丢)。"""
    return os.path.join(ds_common.data_root(root), "config", "sidebar.json")


FILE_STATE = {"pinned_keys": ["websocket:old"], "title_overrides": {"websocket:old": "老名字"},
              "将来的字段": {"别动": [1, 2]}}


def _seed(root, obj=FILE_STATE):
    p = _side_path(root)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        if isinstance(obj, str):
            fh.write(obj)
        else:
            json.dump(obj, fh, ensure_ascii=False)
    return p


def _load(root):
    with open(_side_path(root), encoding="utf-8") as fh:
        return json.load(fh)


def _bytes(root):
    try:
        with open(_side_path(root), "rb") as fh:
            return fh.read()
    except FileNotFoundError:
        return None


def _req(port, path, method="GET", body=None, ctype="application/json", headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    h = dict(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if not isinstance(body, bytes) else body
        h["Content-Type"] = ctype
        h["Content-Length"] = str(len(data))
    conn.request(method, path, body=data, headers=h)
    r = conn.getresponse()
    raw = r.read()
    conn.close()
    try:
        return r.status, json.loads(raw.decode("utf-8") or "null")
    except ValueError:
        return r.status, raw


class TestEndpoints(unittest.TestCase):
    def test_e1_session_projects(self):
        with _upstream() as up, _serve(up.server_address[1]) as (port, _root):
            st, body = _req(port, "/api/chat/session-projects")
            self.assertEqual(st, 200)
            self.assertEqual(body["sessions"].get("websocket:a"), ["翡翠湾-1801"])
            self.assertEqual(body["sessions"].get("websocket:i"), ["滨江-12F", "翡翠湾-1801"], "回放记录在配置文件旁边的 webui/ 下")
            self.assertEqual(body["last_active"].get("websocket:i"), "2026-08-16T09:30:00.000000")
            self.assertEqual(up.requests, [], "只读本机文件,不碰网关")

    def test_e2_sidebar_state_only_two_fields(self):
        with _upstream() as up, _serve(up.server_address[1]) as (port, root):
            st, body = _req(port, "/api/chat/sidebar-state")
            self.assertEqual((st, body), (200, {"pinned_keys": [], "title_overrides": {}}), "还没有文件 ⇒ 空")
            _seed(root)
            st, body = _req(port, "/api/chat/sidebar-state")
            self.assertEqual(st, 200)
            self.assertEqual(body, {"pinned_keys": ["websocket:old"], "title_overrides": {"websocket:old": "老名字"}})
            _seed(root, "{坏的")
            st, body = _req(port, "/api/chat/sidebar-state")
            self.assertEqual((st, body), (200, {"pinned_keys": [], "title_overrides": {}}), "坏文件不崩,当空")
            self.assertEqual(up.requests, [], "置顶 / 改名不经网关")

    def test_e3_pin_rename_read_modify_write(self):
        with _upstream() as up, _serve(up.server_address[1]) as (port, root):
            _seed(root)
            st, body = _req(port, "/api/chat/sessions/websocket:a/pin", "POST", {"pinned": True})
            self.assertEqual(st, 200, body)
            self.assertEqual(body["pinned_keys"], ["websocket:old", "websocket:a"])
            st, body = _req(port, "/api/chat/sessions/websocket:a/rename", "POST", {"title": "  王女士吊顶 "})
            self.assertEqual(st, 200, body)
            self.assertEqual(body["title_overrides"]["websocket:a"], "王女士吊顶")
            st, body = _req(port, "/api/chat/sessions/websocket:old/rename", "POST", {"title": ""})
            self.assertNotIn("websocket:old", body["title_overrides"], "空 ⇒ 恢复自动名字")
            disk = _load(root)
            self.assertEqual(disk["pinned_keys"], ["websocket:old", "websocket:a"], "真写到盘上了")
            self.assertEqual(disk["title_overrides"], {"websocket:a": "王女士吊顶"})
            self.assertEqual(disk["将来的字段"], FILE_STATE["将来的字段"], "文件里别的字段原样")
            st, body = _req(port, "/api/chat/sessions/websocket:old/pin", "POST", {"pinned": False})
            self.assertEqual(body["pinned_keys"], ["websocket:a"])
            self.assertEqual(up.requests, [], "不经网关")

    def test_e3b_many_long_titles_all_kept(self):
        # 网关状态口把整份状态放进网址,6 条 160 字就断 —— 换了存法,100 条也得全在
        with _upstream() as up, _serve(up.server_address[1]) as (port, root):
            for i in range(100):
                st, body = _req(port, f"/api/chat/sessions/websocket:k{i:03d}/rename", "POST", {"title": "长" * 160})
                self.assertEqual(st, 200, f"第 {i + 1} 条改名没存上:{body}")
            st, body = _req(port, "/api/chat/sidebar-state")
            self.assertEqual(len(body["title_overrides"]), 100)
            self.assertTrue(all(len(t) == 160 for t in body["title_overrides"].values()))

    def test_e3c_concurrent_pins_none_lost(self):
        with _upstream() as up, _serve(up.server_address[1]) as (port, root):
            errs = []

            def pin(i):
                st, body = _req(port, f"/api/chat/sessions/websocket:c{i:02d}/pin", "POST", {"pinned": True})
                if st != 200:
                    errs.append((i, st, body))

            ts = [threading.Thread(target=pin, args=(i,)) for i in range(20)]
            for t in ts:
                t.start()
            for t in ts:
                t.join()
            self.assertEqual(errs, [])
            self.assertEqual(sorted(_load(root)["pinned_keys"]), [f"websocket:c{i:02d}" for i in range(20)],
                             "同时点的置顶一条不丢(读 - 改 - 写要在锁里)")

    def test_e4_rejects_without_writing(self):
        with _upstream() as up, _serve(up.server_address[1]) as (port, root):
            _seed(root)
            before = _bytes(root)
            st, _ = _req(port, "/api/chat/sessions/websocket:a/pin", "POST", b'{"pinned": true}', ctype="text/plain")
            self.assertEqual(st, 400, "CT 不是 json ⇒ 拒(CSRF 纵深,同删除针孔)")
            st, _ = _req(port, "/api/chat/sessions/..%2F..%2Fx/pin", "POST", {"pinned": True})
            self.assertIn(st, (400, 404))
            st, _ = _req(port, "/api/chat/sessions/websocket:a/pin", "POST", {"pinned": "是"})
            self.assertEqual(st, 400, "pinned 必须是布尔")
            st, _ = _req(port, "/api/chat/sessions/websocket:a/rename", "POST", {"title": 5})
            self.assertEqual(st, 400)
            st, _ = _req(port, "/api/chat/sessions/websocket:a/pin", "POST", {"pinned": True},
                         headers={"Origin": "http://evil.example", "Sec-Fetch-Site": "cross-site"})
            self.assertIn(st, (400, 403), "跨站拒")
            st, _ = _req(port, "/api/chat/sessions/websocket:a/pin", "GET")
            self.assertIn(st, (404, 405), "GET 面不许有写")
            self.assertEqual(_bytes(root), before, "被拒的一条都没写")

    def test_e5_delete_cleans_pin_and_title(self):
        with _upstream() as up, _serve(up.server_address[1]) as (port, root):
            _seed(root)
            st, _ = _req(port, "/api/chat/sessions/websocket:old/delete", "POST", {})
            self.assertEqual(st, 200)
            self.assertTrue(any(r["path"] == "/api/sessions/websocket:old/delete" for r in up.requests), "删除照旧交给网关")
            disk = _load(root)
            self.assertNotIn("websocket:old", disk["pinned_keys"])
            self.assertNotIn("websocket:old", disk["title_overrides"])
            self.assertEqual(disk["将来的字段"], FILE_STATE["将来的字段"])

    def test_e6_delete_failure_keeps_state(self):
        with _upstream() as up, _serve(up.server_address[1]) as (port, root):
            _seed(root)
            before = _bytes(root)
            up.delete_status = 409
            st, _ = _req(port, "/api/chat/sessions/websocket:old/delete", "POST", {})
            self.assertEqual(st, 409, "上游拒删的状态码原样透传")
            self.assertEqual(_bytes(root), before, "没删成就不清置顶 / 改名")

    def test_e6b_delete_blocked_by_automation_keeps_state(self):
        # 网关拒删(对话绑了定时任务)回的是 200 + deleted:false(nanobot ws_http _handle_session_delete)——
        # 只看状态码会把一段没删掉的对话的置顶 / 改名清掉
        with _upstream() as up, _serve(up.server_address[1]) as (port, root):
            _seed(root)
            before = _bytes(root)
            up.delete_body = {"deleted": False, "blocked_by_automations": True, "automations": []}
            st, body = _req(port, "/api/chat/sessions/websocket:old/delete", "POST", {})
            self.assertEqual((st, body.get("blocked_by_automations")), (200, True), "上游的回话原样透传给前端提示")
            self.assertEqual(_bytes(root), before, "没删掉就不清置顶 / 改名")

    def test_e7_gateway_down(self):
        with _serve(1) as (port, root):
            _seed(root)
            before = _bytes(root)
            st, _ = _req(port, "/api/chat/sessions/websocket:old/delete", "POST", {})
            self.assertEqual(st, 502)
            self.assertEqual(_bytes(root), before, "网关没起 ⇒ 没删成 ⇒ 不清")
            st, body = _req(port, "/api/chat/sessions/websocket:a/pin", "POST", {"pinned": True})
            self.assertEqual(st, 200, "置顶不靠网关")


if __name__ == "__main__":
    unittest.main(verbosity=2)
