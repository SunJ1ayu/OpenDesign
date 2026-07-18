#!/usr/bin/env python3
"""T4 真链 e2e(track opendesign-inbox-scan):收件箱"扫描整理"全链。
丢文件 → POST /api/intake/scan(自动暂存确定性建议)→ GET /api/intake 见待确认 plan
→ POST /api/intake/approve 落位。证明 scan 针孔与既有 approve 针孔 compose。
起真 ds_web,走真 HTTP;纯核心无浏览器。"""
import http.client
import json
import os
import shutil
import sys
import tempfile
import threading

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

ds = tempfile.mkdtemp(prefix="inbox-scan-e2e-ds-")
ws = tempfile.mkdtemp(prefix="inbox-scan-e2e-ws-")
dist = tempfile.mkdtemp(prefix="inbox-scan-e2e-dist-")
open(os.path.join(dist, "index.html"), "w").write("<!doctype html><div>x</div>")
inbox = os.path.join(ws, "00-收件箱")
ref_lib = os.path.join(ws, "03-共享资源", "参考图库")
try:
    os.makedirs(inbox)
    os.makedirs(os.path.join(ws, "01-项目", "20260612 周宁 龙腾世纪 12#1802"))
    os.makedirs(ref_lib)
    os.makedirs(os.path.join(ds, "config"))
    json.dump({"root": ws, "projects": {}},
              open(os.path.join(ds, "config", "workspace.json"), "w"), ensure_ascii=False)
    # 确定性:客厅参考.jpg → 参考图(workspace 级)自动暂存;神秘.xyz → 未知留 skipped
    open(os.path.join(inbox, "客厅参考.jpg"), "w").write("img")
    open(os.path.join(inbox, "神秘.xyz"), "w").write("?")

    httpd = ds_web.make_server(ds, dist, port=0)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    print("① 扫描整理:POST /api/intake/scan")
    st, r = _req(port, "POST", "/api/intake/scan", {})
    chk(st == 200 and r.get("ok"), "scan 200 + ok")
    chk(r.get("staged") == 1, "1 个确定性文件被暂存(客厅参考.jpg)")
    chk([s["name"] for s in r.get("skipped", [])] == ["神秘.xyz"], "未知扩展名留 skipped")
    plan_id = r.get("plan_id")
    chk(bool(plan_id), "返回 plan_id")

    print("② 待确认可见:GET /api/intake")
    st, r = _req(port, "GET", "/api/intake")
    chk(st == 200, "GET intake 200")
    pending_ids = [p.get("plan_id") or p.get("id") for p in (r.get("pending") or [])]
    chk(plan_id in pending_ids, "刚暂存的 plan 出现在待确认区")
    # 扫描是暂存,零移动:文件仍在收件箱
    chk(os.path.exists(os.path.join(inbox, "客厅参考.jpg")), "scan 阶段零移动(图仍在收件箱)")

    print("③ 确认执行:POST /api/intake/approve")
    st, r = _req(port, "POST", "/api/intake/approve", {"plan_id": plan_id})
    chk(st == 200 and r.get("ok"), "approve 200 + ok")
    chk(os.path.exists(os.path.join(ref_lib, "客厅参考.jpg")), "图落位到 03-共享资源/参考图库/")
    chk(not os.path.exists(os.path.join(inbox, "客厅参考.jpg")), "收件箱里已清走")
    chk(os.path.exists(os.path.join(inbox, "神秘.xyz")), "未认领的 xyz 岿然不动")

    httpd.shutdown()
finally:
    for d in (ds, ws, dist):
        shutil.rmtree(d, ignore_errors=True)

print(f"\n=== e2e: {'ALL PASS' if not fails else str(len(fails)) + ' FAIL'} ===")
sys.exit(1 if fails else 0)
