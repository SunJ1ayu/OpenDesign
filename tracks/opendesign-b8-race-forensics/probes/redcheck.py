#!/usr/bin/env python3
"""track opendesign-b8-race-forensics 的红检夹具 —— 判据的判据。

四个情景,两类病:

  R1   ① 判据自污染:段内本来就有一个真 InstanceLock 在应答。
       造法:占住一个端口拿到真锁,再把 test 模块的 `free_port` 打桩成 P-3。
  R2a  ② 真产品缺陷(让位方向坏了):`_someone_ahead_of` 恒真 ⇒ 两份都让位。
       读数里两份 port **不同值**(各自绑的那一格)。
  R2b  ② 真产品缺陷(扫描误判):`_scan` 恒命中 base ⇒ 两份都以为"已有一份"。
       读数里两份 port **同值** —— 与 2026-09-20 那条红**完全同形**,
       而段内真的一个人都没有。🔴 这条是本单的承重墙:
       它证明「两份 port 同值」这个形状 ① 和 ② 都做得出,**分辨不了病因**,
       所以 E1 只说明 ① 充分,不说明"那次就是 ①"。
  R2c  ② 真产品缺陷(握手恒真):`_send_show` 恒返回 True。
       🔴 这条专钉**前置断言的独立性**:开轮前那句"段内有没有真锁"如果图省事复用了
       产品自己的 `_send_show`,这个变异会让它**误报"环境脏"**,把真缺陷伪装成判据问题
       —— 那就是自动化版的"调钝报警器"。所以探测必须自己发 socket,
       新 b8 在这条下必须红在"恰好 1 份赢",**不许**红在前置断言。
  R3   正常树 ⇒ 必须绿。

变异只许打在**仓外副本**上(活仓零改动)。`--repo` 指向活仓且要求变异时本夹具拒绝跑。

跑法:
  python3 probes/redcheck.py --repo <仓或副本> --case r1|r2a|r2b|r3 [--repeat N]
"""
import argparse
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

LIVE_REPO = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
TEST_NAME = "test_b8_two_instances_racing_at_the_same_moment_still_yield_one"


def mutate(repo: str, case: str) -> str:
    """在副本里动产品代码,返回改了什么的人话描述。"""
    path = os.path.join(repo, "bin", "ds_shell_core.py")
    src = open(path, encoding="utf-8").read()
    if case == "r2a":
        old = "    def _someone_ahead_of(self, mine: int) -> bool:\n"
        new = old + "        return True  # [MUTANT r2a] 让位方向坏了:谁都认为前面有人\n"
    elif case == "r2b":
        old = "    def _scan(self"
        idx = src.index(old)
        head = src[:idx]
        rest = src[idx:]
        sig_end = rest.index("\n", rest.index(":\n")) + 1
        # 插在函数体第一行(跳过 def 行),让它恒命中 base
        new_src = head + rest[:sig_end] + \
            "        return self.base_port  # [MUTANT r2b] 扫描恒误判:段内没人也说有人\n" + \
            rest[sig_end:]
        open(path, "w", encoding="utf-8").write(new_src)
        return "_scan 恒返回 base_port(段内无人也报有人)"
    elif case == "r2c":
        old = "    def _send_show(self, port: int, patient: bool = False) -> bool:\n"
        new = old + "        return True  # [MUTANT r2c] 握手恒真:任何端口都被当成另一份 OpenDesign\n"
    else:
        return "无变异"
    if old not in src:
        raise SystemExit(f"变异锚点没找到,拒绝继续:{old!r}")
    open(path, "w", encoding="utf-8").write(src.replace(old, new, 1))
    return {"r2a": "_someone_ahead_of 恒返回 True(两份都让位)",
            "r2c": "_send_show 恒返回 True(任何端口都被当成另一份 OpenDesign)"}[case]


def run_case(repo: str, case: str) -> tuple[bool, str]:
    sys.path.insert(0, os.path.join(repo, "tests"))
    sys.path.insert(0, os.path.join(repo, "bin"))
    import test_ds_shell_core as T

    squatter = None
    patcher = None
    if case == "r1":
        # 造 ①:起一个真 InstanceLock 子进程占住 P,再让 b8 的 base 落成 P-3
        import ds_shell_core  # noqa: F401  (确认副本的 bin 在 path 上)
        tmp = tempfile.mkdtemp(prefix="b8-redcheck-r1-")
        base0 = T.free_port()
        squatter = subprocess.Popen(
            [sys.executable, "-c", T.LOCK_CHILD, os.path.join(repo, "bin"),
             str(base0), "5", os.path.join(tmp, "shown.txt")],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        import json
        r = json.loads(squatter.stdout.readline())
        assert r["acquired"], f"占位实例没拿到锁:{r}"
        held = r["port"]
        patcher = mock.patch.object(T, "free_port", lambda: held - 3)
        patcher.start()
        print(f"# R1 占位端口={held} ⇒ b8 的 base 被打桩成 {held - 3},段=[{held-3},{held+2}]")

    try:
        suite = unittest.defaultTestLoader.loadTestsFromName(
            f"test_ds_shell_core.RaceAndLock.{TEST_NAME}"
            if _has_class(T, "RaceAndLock") else _locate(T))
        buf = _Capture()
        res = unittest.TextTestRunner(stream=buf, verbosity=2).run(suite)
        return res.wasSuccessful(), buf.getvalue()
    finally:
        if patcher:
            patcher.stop()
        if squatter:
            squatter.kill()
            squatter.wait(timeout=10)
            for f in (squatter.stdout, squatter.stderr):
                f.close()


def _has_class(mod, name):
    return hasattr(mod, name)


def _locate(mod):
    for name in dir(mod):
        obj = getattr(mod, name)
        if isinstance(obj, type) and issubclass(obj, unittest.TestCase) \
                and hasattr(obj, TEST_NAME):
            return f"test_ds_shell_core.{name}.{TEST_NAME}"
    raise SystemExit("找不到 b8 所在的 TestCase 类")


class _Capture:
    def __init__(self):
        self.parts = []

    def write(self, s):
        self.parts.append(s)
        sys.__stdout__.write(s)

    def flush(self):
        sys.__stdout__.flush()

    def getvalue(self):
        return "".join(self.parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=LIVE_REPO)
    ap.add_argument("--case", required=True, choices=["r1", "r2a", "r2b", "r2c", "r3"])
    ap.add_argument("--repeat", type=int, default=1)
    a = ap.parse_args()
    repo = os.path.realpath(a.repo)

    if a.case in ("r2a", "r2b", "r2c"):
        if repo == LIVE_REPO:
            raise SystemExit("🔴 拒绝:变异只许打在仓外副本上,--repo 不能是活仓")
        what = mutate(repo, a.case)
        print(f"# 变异({a.case}):{what}  repo={repo}")
    else:
        print(f"# 无变异({a.case})  repo={repo}")

    expect_red = a.case in ("r1", "r2a", "r2b", "r2c")
    for i in range(a.repeat):
        t0 = time.time()
        ok, out = run_case(repo, a.case)
        verdict = "绿" if ok else "红"
        want = "红" if expect_red else "绿"
        mark = "符合预期" if (ok != expect_red) else "🔴 不符合预期"
        print(f"\n# [{a.case} 第{i+1}/{a.repeat}遍] 结果={verdict} 期望={want} {mark} "
              f"({time.time()-t0:.1f}s)")
        if ok == expect_red:
            sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
