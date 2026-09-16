"""无出口守卫(python 版)—— track opendesign-e2e-no-egress-browser-tmp,2026-09-16。

不变量只有一句:**跑判据的进程不许有外网出口。**

用法(`.e2e.py` 顶部,任何本仓模块之前):

    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import _no_egress  # noqa: F401  ← 无出口守卫

导入即生效。逻辑与 `helpers.mjs` 顶部的 node 版逐条对应(取舍写在那边):
fail-closed、**不认环境变量**(比 /proc/*/ns/net)、进去之后还要实测一次出口。

照搬 aiwork `tests/_no_egress.py`(08-10 起跑了一个月),只把环境变量名换成本仓的。
⚠️ 强度:挡手滑,不挡蓄意(root 一行 nsenter 就出去)。
"""

import errno
import os
import socket
import subprocess
import sys

_EXIT_REFUSED = 78
_TRIED = "DS_E2E_NOEGRESS_TRIED"


def _die(msg):
    sys.stderr.write("🔴 无出口守卫:%s\n" % msg)
    sys.stderr.write("   e2e 判据进程必须没有外网出口(不许在跑判据时把业主的额度花出去)。\n")
    sys.stderr.write("   来源:tests/e2e/_no_egress.py,track opendesign-e2e-no-egress-browser-tmp。\n")
    sys.stderr.flush()
    os._exit(_EXIT_REFUSED)


def _isolated():
    """已经在独立网络命名空间里?——看内核,不看环境变量(环境变量是零成本后门)。"""
    try:
        return os.readlink("/proc/self/ns/net") != os.readlink("/proc/1/ns/net")
    except OSError:
        return False


def _egress_open():
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=3).close()
        return True
    except OSError:
        return False


def _enforce():
    if not _isolated():
        if os.environ.get(_TRIED):
            _die("已经自举过一次,却仍然不在独立的网络命名空间里(unshare 没生效?)")
        # 先探再 exec:直接 exec 的话 unshare 失败会替换掉本进程,一句解释都留不下。
        try:
            rc = subprocess.call(["unshare", "-n", "--", "true"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            _die("找不到 unshare,做不到网络隔离 ⇒ 拒跑")
        if rc != 0:
            _die("unshare -n 用不了(没权限?内核不支持?)⇒ 拒跑")

        env = dict(os.environ, **{_TRIED: "1"})
        script = os.path.abspath(sys.argv[0])
        try:
            os.execvpe(
                "unshare",
                ["unshare", "-n", "--", "bash", "-c",
                 'ip link set lo up 2>/dev/null || true; exec "$0" "$@"',
                 sys.executable, script] + sys.argv[1:],
                env,
            )
        except OSError as exc:
            # 探得过、却 exec 不动:不许抛裸 traceback(那和"判据自己坏了"长得一样)。
            _die("unshare 探得过、却 exec 不动(%s)⇒ 拒跑" % exc)
        _die("exec unshare 没能替换掉本进程 ⇒ 拒跑")  # 正常到不了

    # 隔离成功就摘掉"试过一次"的标记:它是给本进程打断死循环用的,不是身份牌。
    os.environ.pop(_TRIED, None)

    # 🔴 回环起不来要**响亮地红**(与 node 版逐条对应):`ip link set lo up` 的失败被
    # `|| true` 吞掉时,自起 ds_web 的判据会红成"产品坏了"的样子。
    # 回环活着 = 连不上时 ECONNREFUSED;回环没起来 = ENETUNREACH/EHOSTUNREACH。
    try:
        socket.create_connection(("127.0.0.1", 1), timeout=3).close()
    except OSError as exc:
        if exc.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH):
            _die("进了隔离,但**回环(lo)没起来** ⇒ 自起的 ds_web 一律连不上。"
                 "这不是产品坏了,是 `ip link set lo up` 没成功")

    if _egress_open():
        _die("已经进了命名空间,却**仍然连得出去** ⇒ 拒跑(别把没生效的闸当生效)")


_enforce()
