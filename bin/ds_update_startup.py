"""打开软件时的更新决策 —— **只读盘,一次网络都不发**。

track opendesign-startup-not-blocked-by-update(2026-09-19)。

## 为什么有这个模块

0.98.7 把「查更新 + 下载 + 安装」整条链放在**启动路径**上,并用全屏卡片挡住界面。
实测最坏 **20.1 秒**干等(后端串行两跳 × 10s;收据见 track 的 evidence/)。
业主原话:「现在每次打开都会弹出正在检测更新,这严重拖慢了我们开软件的速度」。

## 这里的规矩

**启动只回答一个问题:盘上有没有一个已经下好、且校验得过的新版安装包?**
有 ⇒ 装(那时进度条是真的在装,不是在等网络);没有 ⇒ 立刻进工作区。
查更新和下载都挪到进入工作区**之后**的后台 —— 用户本来就开着软件,那时候慢不碍事。

🔴 **本模块的函数永远不许抛。** 它读的是**盘上的数据**,不是我们自己造的对象:
文件可能半写、可能是上一个版本写的、可能被人手改过、指向的安装包可能已经被删了。
本项目已经有四次"注入/时机"导致整页白或打不开的前科(0.94、0.98 两次白屏、
0.98.0 装不上、0.98.7 启动阻塞)——**"不更新"是小事,"打不开"是大事。**
判据 su13 钉这一条。
"""
import json
import os
import random
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ds_update  # 只借 parse_version(避免两份版本比较逻辑漂移);**不调用它的任何取数函数**

SCHEMA = 1
STATE_NAME = "update-state.json"


def state_path(data_root):
    """状态文件放数据根的 Logs 下,**和既有的 auto-update-attempts.json 同侧**。

    不进安装目录(更新会覆盖、卸载会删 —— 业主卸载丢资料那一单的教训),
    也不进用户数据目录(那是他的真实档案)。判据 sp1/sp2。
    """
    return os.path.join(str(data_root), "Logs", STATE_NAME)

# 进入工作区之后,等这么久才做第一次检查。不许是 0 —— 那等于换个地方接着抢启动资源。
FIRST_CHECK_DELAY_S = 60
BASE_INTERVAL_S = 600          # 平时 10 分钟轮询一次
MAX_BACKOFF_S = 3600           # 连续失败最多退到 1 小时,不许退到天荒地老
JITTER = 0.2                   # ±20% 抖动:别让所有客户端同一秒去打服务器


def next_delay(attempt=0, rand=None):
    """下一次检查等多久。attempt 是**连续失败次数**,0 表示上一次是成功的。

    指数退避 + 抖动,封顶 MAX_BACKOFF_S。判据 sc2~sc4。
    """
    try:
        n = max(0, int(attempt))
    except Exception:  # noqa: BLE001 —— 永不抛
        n = 0
    base = min(BASE_INTERVAL_S * (2 ** min(n, 16)), MAX_BACKOFF_S)
    r = random.random() if rand is None else rand
    delay = base * (1.0 + JITTER * (2.0 * r - 1.0))
    # 抖动不许把间隔算成 0 或负数(判据 sc4)
    return max(1.0, min(delay, MAX_BACKOFF_S))


def read_state(path):
    """读盘上的状态。**任何读不出来的情况都返回 None,绝不抛**(判据 sw3/sw4)。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:  # noqa: BLE001 —— 文件不在/半写/非 JSON/权限/编码,一律当没有
        return None
    return data if isinstance(data, dict) else None


def write_state(path, state):
    """原子写:临时文件写满 + fsync,再 os.replace 换上去(判据 sw2)。

    半写的文件**绝不能出现在那个路径上** —— 启动路径会读它,
    而半写的 JSON 会让 read_state 返回 None、白白错过一次已经下好的更新。
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".update-state-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(p))
        tmp = None
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _enter(reason):
    return {"action": "enter", "reason": reason}


def startup_decision(state, current_version, now=None):
    """打开软件时该干什么:装,还是直接进工作区。

    **只有一条路通向 install**;其余一切 —— 包括任何我没预料到的输入 —— 都是 enter。
    reason 是稳定枚举(判据 su14),界面和判据都认它。

    🔴 整个函数包在一个 try 里:漏掉任何一种坏输入,代价是业主打不开软件。
    """
    try:
        if not isinstance(state, dict):
            return _enter("no_state")
        if state.get("schema") != SCHEMA:
            return _enter("unknown_schema")
        if state.get("phase") != "ready":
            return _enter("not_ready")

        version = state.get("version")
        current = ds_update.parse_version(current_version) if isinstance(current_version, str) else None
        target = ds_update.parse_version(version) if isinstance(version, str) else None
        if target is None or current is None:
            return _enter("unreadable_version")
        if target <= current:
            return _enter("not_newer")

        asset = state.get("asset")
        path = state.get("path")
        if not isinstance(asset, dict) or not isinstance(path, str) or not path:
            return _enter("incomplete_state")

        # 符号链接一律拒:那是"包被换掉"最省事的一条路(worktree 符号链接事故的同族)。
        if os.path.islink(path) or not os.path.isfile(path):
            return _enter("package_missing")

        want_size, want_sha = asset.get("size"), asset.get("sha256")
        if not isinstance(want_size, int) or not isinstance(want_sha, str) or len(want_sha) != 64:
            return _enter("incomplete_state")
        if os.path.getsize(path) != want_size:
            return _enter("size_mismatch")

        import hashlib
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest().lower() != want_sha.lower():
            return _enter("digest_mismatch")

        return {"action": "install", "reason": "ready", "version": version, "path": path}
    except Exception:  # noqa: BLE001 —— 判据 su13:宁可不更新,绝不许打不开
        return _enter("decision_failed")
