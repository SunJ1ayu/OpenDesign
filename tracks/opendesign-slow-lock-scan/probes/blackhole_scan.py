"""业主那台机器的形状:6 个锁位一个都不肯快速失败,只能等我们自己超时。

Linux 上空端口是**瞬间**被拒的(实测 6 个口 4.4ms),所以本机复现不出他那台的
真实机制。这支探针只模拟**那一个**已知事实 —— "connect 到空锁位 = 耗满超时" ——
然后量新旧两版 acquire() 的墙钟。

⚠️ 它证明的是"给定每口都耗满,新旧各花多久",**不是**"他那台为什么耗满"。
后者仍是敞着的(见 proposal.md「还不知道的」)。用法:
    python3 tracks/opendesign-slow-lock-scan/probes/blackhole_scan.py <旧版路径>
"""
import importlib.util, socket, sys, time, types

REAL = socket.create_connection


def load(path: str, name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def blackhole(addr, timeout=None, *a, **kw):
    """SYN 被悄悄丢掉的样子:干等到我们自己的超时,然后 TimeoutError(OSError 的子类)。"""
    time.sleep(timeout if timeout else 0.0)
    raise TimeoutError("simulated: SYN dropped")


def measure(mod, label):
    mod.socket.create_connection = blackhole
    lock = mod.InstanceLock(base_port=free_base(), span=5)
    t0 = time.monotonic()
    got = lock.acquire()
    spent = (time.monotonic() - t0) * 1000.0
    lock.release()
    print(f"{label:>10}: acquire()={got}  墙钟 {spent:8.1f}ms")
    return spent


def free_base() -> int:
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    return p


if __name__ == "__main__":
    sys.path.insert(0, "bin")
    old = measure(load(sys.argv[1], "old_core"), "修之前")
    new = measure(load("bin/ds_shell_core.py", "new_core"), "修之后")
    print(f"{'':>10}  快了 {old / new:.0f} 倍;省下 {(old - new) / 1000:.1f}s")
