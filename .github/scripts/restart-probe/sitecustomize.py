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

# probe-4:验证「新网关卡在 Python 初始化 = 继承了管家那条正被同步读着的 stdin 管道」。
# 只在管家进程里、且 PROBE_DEVNULL=1 的组里生效:子进程默认 stdin=DEVNULL(产品代码不动)。
if os.environ.get("PROBE_DEVNULL") == "1" and "ds_host.py" in " ".join(getattr(sys, "orig_argv", [])):
    import subprocess

    _orig_init = subprocess.Popen.__init__

    def _init(self, *args, **kwargs):
        kwargs.setdefault("stdin", subprocess.DEVNULL)
        return _orig_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = _init
