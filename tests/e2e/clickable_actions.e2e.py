#!/usr/bin/env python3
"""T5 真链 e2e(track opendesign-clickable-actions):两个新写针孔 compose。
建档(POST /api/projects/create)→ 记一条(POST /api/changes/add)→ 读回
(GET /api/projects/<key>/changes),证明 create 造的项目 add 能写、GET 能见。
起真 ds_web 服务器,走真 HTTP。纯核心,无浏览器。"""
import http.client
import json
import os
import shutil
import sys
import tempfile
import threading
from urllib.parse import quote

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "bin"))
import ds_web  # noqa

fails = []
def chk(cond, msg):
    print(("  PASS " if cond else "  FAIL ") + msg)
    if not cond:
        fails.append(msg)

def _req(port, method, path, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    conn.request(method, path, body=data, headers=headers)
    r = conn.getresponse()
    b = r.read()
    conn.close()
    return r.status, (json.loads(b.decode("utf-8")) if b else None)

ds_root = tempfile.mkdtemp(prefix="clickable-e2e-")
dist = tempfile.mkdtemp(prefix="clickable-e2e-dist-")
open(os.path.join(dist, "index.html"), "w").write("<!doctype html><div>x</div>")
try:
    httpd = ds_web.make_server(ds_root, dist, port=0)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    key = "测试小区-101"
    print("① 建档:POST /api/projects/create")
    st, d = _req(port, "POST", "/api/projects/create",
                 {"project": key, "client": "测试业主"})
    chk(st == 200 and d.get("ok"), "create 200 + ok")
    chk(os.path.exists(os.path.join(ds_root, "projects", f"{key}.md")), "项目档案已落盘")

    print("② 记一条(写进刚建的项目):POST /api/changes/add")
    st, d = _req(port, "POST", "/api/changes/add",
                 {"project": key, "content": "主卫干湿分离", "space": "主卫"})
    chk(st == 200 and d.get("ok"), "add 200 + ok(证明 create 造的项目 add 能写)")

    print("③ 读回:GET /api/projects/<key>/changes")
    st, d = _req(port, "GET", f"/api/projects/{quote(key)}/changes")
    chk(st == 200, "GET changes 200")
    texts = [c.get("text", "") for c in (d.get("changes") or [])]
    spaces = [c.get("space", "") for c in (d.get("changes") or [])]
    chk(any("主卫干湿分离" in t for t in texts), "刚记的变更 GET 可见")
    chk("主卫" in spaces, "空间前缀正确解析回结构化字段")

    print("④ 建档幂等闸:重复 create 同名 → 409")
    st, d = _req(port, "POST", "/api/projects/create",
                 {"project": key, "client": "另一个"})
    chk(st == 409 and d.get("error") == "project_exists", "重复建档 409 project_exists")

    httpd.shutdown()
finally:
    shutil.rmtree(ds_root, ignore_errors=True)
    shutil.rmtree(dist, ignore_errors=True)

print(f"\n=== e2e: {'ALL PASS' if not fails else str(len(fails)) + ' FAIL'} ===")
sys.exit(1 if fails else 0)
