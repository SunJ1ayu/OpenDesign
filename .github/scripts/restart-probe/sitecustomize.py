# 只在 windows-restart-probe 里临时放进包的 site-packages;出货包里没有它。
# 网关一进 Python 就记一笔(证明进程真的跑起来了),之后每 20s 把所有线程卡在哪一行打进网关.log。
import os
import sys

if os.environ.get("PROBE_FAULT") == "1" and "nanobot" in " ".join(getattr(sys, "orig_argv", [])):
    import faulthandler
    import time
    sys.stderr.write(f"[probe] nanobot 进程已进入 Python pid={os.getpid()} ppid={os.getppid()} {time.strftime('%H:%M:%S')}\n")
    sys.stderr.flush()
    faulthandler.dump_traceback_later(20, repeat=True, file=sys.stderr)
