# 只在 windows-restart-probe 里临时放进包的 site-packages;出货包里没有它。
# 网关一进 Python 就记一笔(证明进程真的跑起来了),之后每 20s 把所有线程卡在哪一行打进网关.log。
import os
import sys

# probe-5 起网关经 ds_gateway.py 起(track opendesign-key-restart),命令行里不再有 "nanobot"
if os.environ.get("PROBE_FAULT") == "1" and any(s in " ".join(getattr(sys, "orig_argv", []))
                                                 for s in ("nanobot", "ds_gateway.py")):
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

# probe-5(QA 执行):管家 / 工作台进程里把目录端点改到本机假厂商(PROBE_VENDOR_BASES);网关只读配置,不用改。
# 与 tests/test_per_vendor_live.py 里 mock.patch.dict(ds_credential.PROVIDERS, …) 同一件事,只是换到真进程里做。
_argv = " ".join(getattr(sys, "orig_argv", []))
if os.environ.get("PROBE_VENDOR_BASES") and ("ds_host.py" in _argv or "ds_web.py" in _argv):
    import json as _json
    _script = next(a for a in sys.orig_argv if a.endswith(("ds_host.py", "ds_web.py")))
    sys.path.insert(0, os.path.dirname(os.path.abspath(_script)))
    import ds_credential as _dc
    for _v, _base in _json.loads(os.environ["PROBE_VENDOR_BASES"]).items():
        _dc.PROVIDERS[_v]["apiBase"] = _base
