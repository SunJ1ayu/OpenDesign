"""冒烟:真起一次 ds-web,走真 `/api/update/prepare`,证明 #25 改签名没把后台备货打断。

为什么不能只靠单测:单测直接调函数,证明不了**端点 → 线程 → prepare_update** 那一跳的实参
对不对得上。签名改错时那一跳会在后台线程里抛 TypeError —— 端点照样回 started:true,
**界面上完全看不出来**,要到下一次发版才发现"更新不来了"。所以这里看的是 stderr 有没有栈。

无出口:整个进程跑在 `unshare -rn` 里(与本仓 e2e 同一条不变量)。
"""
import json, os, socket, sys, tempfile, threading, time, urllib.request

# 用法(必须无出口 + loopback 起着):
#   unshare -rn bash -c 'ip link set lo up; python3 tracks/<t>/prepare-smoke.py'
#   SABOTAGE=arity  ← 红检:证明这条冒烟真的看得见后台那一跳挂了
#   SABOTAGE=oldsig ← 反例:这一种它**看不见**(见下面注释)

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "bin"))

# 出口实测(fail-closed)
try:
    s = socket.create_connection(("1.1.1.1", 443), timeout=3)
    s.close()
    print("🔴 还有外网出口,拒跑"); sys.exit(78)
except OSError:
    print("无出口 ✓")

tmp = tempfile.mkdtemp(prefix="prep-smoke-")
appdata = os.path.join(tmp, "appdata"); os.makedirs(appdata)
install = os.path.join(tmp, "OpenDesign")
os.makedirs(os.path.join(install, "ds", "bin"), exist_ok=True)
open(os.path.join(install, "OpenDesign.exe"), "w").close()
open(os.path.join(install, "ds", "bin", "ds_shell.py"), "w").close()
os.environ["LOCALAPPDATA"] = appdata
os.environ["DS_SHELL_LOCK_PORT"] = "47123"

dist = os.path.join(tmp, "dist"); os.makedirs(dist)
open(os.path.join(dist, "index.html"), "w").write("<html></html>")

import ds_web  # noqa: E402
import ds_update_startup  # noqa: E402

# 🔴 红检:证明这条冒烟真的看得见"后台那一跳挂了"。SABOTAGE=1 时把 prepare_update 换成
#    一个参数对不上的替身(= 改签名忘了改调用点那种故障)。没有这一步,"stderr 没有栈"
#    只是"我没看见",不是"它看得见"。
if os.environ.get("SABOTAGE") == "arity":
    # 真正的参数个数不匹配 ⇒ 后台线程抛 TypeError ⇒ stderr 上必须看得见栈。
    def _broken(info, paths, must_be_passed):
        return None
    ds_update_startup.prepare_update = _broken
    print("[SABOTAGE=arity] 换成少一个必填参数的替身")
elif os.environ.get("SABOTAGE") == "oldsig":
    # 🔴 **这一种是无声的**:旧签名 (info, data_root, ..., paths=None) 被新调用点
    #    `prepare_update(info, paths)` 调到时,paths 字典直接落进 data_root,不报任何错。
    #    这条冒烟**抓不到它** —— 抓它的是 el17(用 inspect 钉签名形状)。写在这里,
    #    是为了别让下一个人以为"冒烟绿了 = 这条跳没问题"。
    def _broken(info, data_root, download=None, now=None, paths=None):
        return None
    ds_update_startup.prepare_update = _broken
    print("[SABOTAGE=oldsig] 换成旧签名替身(预期:这条冒烟看不出来)")

httpd = ds_web.make_server(os.path.join(install, "ds"), dist, port=0)
port = httpd.server_address[1]
threading.Thread(target=httpd.serve_forever, daemon=True).start()

def post(path, body=b"{}"):
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path), data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status, json.loads(r.read().decode())

st, body = post("/api/update/prepare")
print("POST /api/update/prepare ->", st, body)
time.sleep(3.0)          # 让后台那条线程跑完
st2, body2 = post("/api/update/prepare")
print("再 POST 一次(闸没被卡死才会放行)->", st2, body2)
httpd.shutdown()
print("DONE")
