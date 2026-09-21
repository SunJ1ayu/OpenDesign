#!/usr/bin/env python3
"""track opendesign-b8-race-forensics 第 1 步:主动造出假设 ①(判据跨轮自污染)。

读数要解释的是这一条(2026-09-20 r4 最终回归,python 全量唯一一条红):
    第 5 轮同时起两份,0 份都认为自己是唯一实例:
    [{'acquired': False, 'port': 40305}, {'acquired': False, 'port': 40305}]

本探针**不改判据、不改产品代码**,只回答三问:
  E1 段内有一个真 InstanceLock 在应答时,同时起两份 ⇒ 是不是 0 份赢、且两份 port 同值?
  E2 段内无人时,同一套起法 ⇒ 是不是恰好 1 份赢?(对照组,证明 E1 的红不是起法本身造的)
  E3 复刻 b8 的循环结构(赢家 sleep(120) 不退、每轮 free_port),只把 span 放大
     ——同一机制加大剂量,看跨轮存活的赢家会不会被后面轮次自然扫到。

子进程代码直接 import 判据本体的 LOCK_CHILD,不自己重写近似版。
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BIN = os.path.join(ROOT, "bin")
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, BIN)
from test_ds_shell_core import LOCK_CHILD  # noqa: E402  判据本体的子进程代码

TMP = tempfile.mkdtemp(prefix="b8-crossround-")
PROCS = []


def free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    s.listen(8)
    p = s.getsockname()[1]
    s.close()
    return p


def spawn(base, span, tag, go=None):
    argv = [sys.executable, "-c", LOCK_CHILD, BIN, str(base), str(span),
            os.path.join(TMP, f"shown-{tag}.txt")]
    if go:
        argv.append(go)
    p = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    PROCS.append(p)
    return p


def readout(p):
    line = p.stdout.readline()
    if not line.strip():
        return {"dead": True, "stderr": p.stderr.read()[:300]}
    return json.loads(line)


def race(base, span, tag):
    """复刻 b8 的起法:两份都堵在发令枪前,同时冲。"""
    go = os.path.join(TMP, f"go-{tag}")
    procs = [spawn(base, span, f"{tag}-{i}", go) for i in range(2)]
    time.sleep(0.3)
    with open(go, "w") as f:
        f.write("go")
    return [readout(p) for p in procs]


def cleanup():
    for p in PROCS:
        try:
            p.kill()
            p.wait(timeout=10)
        finally:
            for f in (p.stdout, p.stderr):
                if f:
                    f.close()


def main():
    print(f"# python={sys.version.split()[0]}  ephemeral_range="
          f"{open('/proc/sys/net/ipv4/ip_local_port_range').read().strip()}")

    # ---- E1:段内有一个真锁在应答 ------------------------------------------
    first = spawn(free_port(), 5, "e1-squatter")
    r0 = readout(first)
    assert r0.get("acquired"), f"占位实例没拿到锁:{r0}"
    squat = r0["port"]
    base = squat - 3                      # 让 squat 落进 [base, base+5] 的中间
    got = race(base, 5, "e1")
    winners = [r for r in got if r.get("acquired")]
    print(f"E1 段内有人(占位端口={squat}, base={base}, 段=[{base},{base+5}]): "
          f"{len(winners)} 份赢 -> {got}")
    print(f"E1 两份 port 同值且等于占位端口: "
          f"{all(r.get('port') == squat for r in got)}")

    # ---- E2:对照,段内无人 -------------------------------------------------
    got2 = race(free_port(), 5, "e2")
    w2 = [r for r in got2 if r.get("acquired")]
    print(f"E2 段内无人(对照): {len(w2)} 份赢 -> {got2}")

    # ---- E3:复刻 b8 结构,只放大 span --------------------------------------
    span = int(os.environ.get("E3_SPAN", "3000"))
    rounds = int(os.environ.get("E3_ROUNDS", "6"))
    alive = []                            # 前面轮次赢家占住的端口(它们 sleep(120) 不退)
    for rn in range(rounds):
        b = free_port()
        got3 = race(b, span, f"e3-{rn}")
        w3 = [r for r in got3 if r.get("acquired")]
        hit = [p for p in alive if b <= p <= b + span]
        print(f"E3 轮{rn} base={b} 段=[{b},{b+span}] 段内前轮存活={hit} "
              f"=> {len(w3)} 份赢 {got3}")
        alive += [r["port"] for r in w3]
    print(f"E3 结束,存活赢家端口={alive}")


if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup()
