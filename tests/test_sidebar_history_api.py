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
     CT 不是 json / key 非法 / 跨站 ⇒ 拒且不写;网关连不上 ⇒ 502;删除成功后清这条的置顶与改名。
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
import ds_sessions  # noqa: E402
import ds_web  # noqa: E402

TOKEN = "sidebar-oracle-token"
CFG_DIR = _tmpreg.mkdtemp("ds-sidebar-判据配置-")
WS_DIR = _tmpreg.mkdtemp("ds-sidebar-工作区-")
SESS = os.path.join(WS_DIR, "sessions")


def _call(name, **args):
    return {"id": "c", "type": "function",
            "function": {"name": f"mcp_design-studio_{name}_tool", "arguments": json.dumps(args, ensure_ascii=False)}}


def _write_session(chat_id, lines):
    os.makedirs(SESS, exist_ok=True)
    path = os.path.join(SESS, f"websocket_{chat_id}.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"_type": "metadata", "key": f"websocket:{chat_id}", "metadata": {"title": "t"}},
                            ensure_ascii=False) + "\n")
        for ln in lines:
            fh.write((ln if isinstance(ln, str) else json.dumps(ln, ensure_ascii=False)) + "\n")
    return path


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
            return self._json(srv.delete_status, {"deleted": True})
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
        yield httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()


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
        with _upstream() as up, _serve(up.server_address[1]) as port:
            st, body = _req(port, "/api/chat/session-projects")
            self.assertEqual(st, 200)
            self.assertEqual(body["sessions"].get("websocket:a"), ["翡翠湾-1801"])
            self.assertEqual(up.requests, [], "只读本机文件,不碰网关")

    def test_e2_sidebar_state_only_two_fields(self):
        with _upstream() as up, _serve(up.server_address[1]) as port:
            st, body = _req(port, "/api/chat/sidebar-state")
            self.assertEqual(st, 200)
            self.assertEqual(body, {"pinned_keys": ["websocket:old"], "title_overrides": {"websocket:old": "老名字"}})
            self.assertEqual(up.requests[0]["auth"], f"Bearer {TOKEN}", "口令由 ds_web 替前端签")

    def test_e3_pin_rename_read_modify_write(self):
        with _upstream() as up, _serve(up.server_address[1]) as port:
            st, body = _req(port, "/api/chat/sessions/websocket:a/pin", "POST", {"pinned": True})
            self.assertEqual(st, 200, body)
            self.assertEqual(body["pinned_keys"], ["websocket:old", "websocket:a"])
            st, body = _req(port, "/api/chat/sessions/websocket:a/rename", "POST", {"title": "  王女士吊顶 "})
            self.assertEqual(st, 200, body)
            self.assertEqual(body["title_overrides"]["websocket:a"], "王女士吊顶")
            st, body = _req(port, "/api/chat/sessions/websocket:old/rename", "POST", {"title": ""})
            self.assertNotIn("websocket:old", body["title_overrides"], "空 ⇒ 恢复自动名字")
            for k in ("archived_keys", "project_name_overrides", "tags_by_key", "collapsed_groups", "view"):
                self.assertEqual(up.state[k], STATE[k], f"网关状态里的 {k} 被原样写回")
            self.assertEqual(up.updates, 3)

    def test_e4_rejects_without_writing(self):
        with _upstream() as up, _serve(up.server_address[1]) as port:
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
            self.assertEqual(up.updates, 0, "被拒的一条都没写")

    def test_e5_delete_cleans_pin_and_title(self):
        with _upstream() as up, _serve(up.server_address[1]) as port:
            st, _ = _req(port, "/api/chat/sessions/websocket:old/delete", "POST", {})
            self.assertEqual(st, 200)
            self.assertNotIn("websocket:old", up.state["pinned_keys"])
            self.assertNotIn("websocket:old", up.state["title_overrides"])
            self.assertEqual(up.state["archived_keys"], STATE["archived_keys"])

    def test_e6_delete_failure_keeps_state(self):
        with _upstream() as up, _serve(up.server_address[1]) as port:
            up.delete_status = 409
            st, _ = _req(port, "/api/chat/sessions/websocket:old/delete", "POST", {})
            self.assertEqual(st, 409, "上游拒删的状态码原样透传")
            self.assertEqual(up.updates, 0, "没删成就不清置顶 / 改名")

    def test_e7_gateway_down(self):
        with _serve(1) as port:
            st, _ = _req(port, "/api/chat/sessions/websocket:a/pin", "POST", {"pinned": True})
            self.assertEqual(st, 502)
            st, _ = _req(port, "/api/chat/sidebar-state")
            self.assertEqual(st, 502)


if __name__ == "__main__":
    unittest.main(verbosity=2)
