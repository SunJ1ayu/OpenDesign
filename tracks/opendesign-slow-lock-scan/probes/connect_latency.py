"""量一次:连到一个**正常 accept** 的回环监听者,要多久?

为什么要有这支探针(2026-09-01,评审腿 subdeepseek 指出的):
`lock_timeouts()` 的整个设计都压在"中位 0.049ms / p99 1023ms / max 1060ms"这组数上,
而那组数原本**只写在 docstring 里** —— 仓库里复现不出来,等于没有证据。

⚠️ 量具翻过一次车:第一版我连了**不 accept** 的监听者,把 `listen(8)` 的 backlog 自己
灌满,于是量到"1ms 超时 0/40 连不上",差点得出**相反**的结论。必须起一个真的在
accept 的监听者 —— 下面的 `_accepting_listener` 就是为这件事存在的。

用法:python3 tracks/opendesign-slow-lock-scan/probes/connect_latency.py [样本数]
"""
import socket
import statistics
import sys
import threading
import time

N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
TIMEOUT = 5.0


def _accepting_listener(stop: threading.Event) -> tuple[socket.socket, int, threading.Thread]:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    srv.settimeout(0.2)
    port = srv.getsockname()[1]

    def serve():
        while not stop.is_set():
            try:
                conn, _ = srv.accept()
            except OSError:
                continue
            conn.close()          # 真 accept 再关掉:握手由内核完成,应用线程也确实醒过
    t = threading.Thread(target=serve, daemon=True)
    t.start()
    return srv, port, t


def main() -> int:
    stop = threading.Event()
    srv, port, thread = _accepting_listener(stop)
    samples = []
    failures = 0
    try:
        for _ in range(N):
            t0 = time.monotonic()
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=TIMEOUT):
                    pass
            except OSError:
                failures += 1
                continue
            samples.append((time.monotonic() - t0) * 1000.0)
    finally:
        stop.set()
        srv.close()
        thread.join(timeout=1.0)

    samples.sort()
    p99 = samples[min(len(samples) - 1, int(len(samples) * 0.99))]
    print(f"样本 {len(samples)}/{N}(连不上 {failures} 次),对面是**正常 accept** 的监听者")
    print(f"  中位 {statistics.median(samples):.3f}ms")
    print(f"  p99  {p99:.3f}ms")
    print(f"  max  {samples[-1]:.3f}ms")
    print()
    print("判读:lock_timeouts()['connect'] 必须罩得住 max —— 罩不住就等于")
    print("     '快扫有一定概率把活实例看成不存在',而那条路的代价是业主开出两份。")
    print(f"  当前 connect 期限盖过 max 了吗:", end=" ")
    sys.path.insert(0, "bin")
    import ds_shell_core as core                      # noqa: E402
    connect_ms = core.lock_timeouts()["connect"] * 1000.0
    print(f"connect={connect_ms:.0f}ms vs max={samples[-1]:.0f}ms "
          f"⇒ {'盖得住' if connect_ms >= samples[-1] else '盖不住'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
