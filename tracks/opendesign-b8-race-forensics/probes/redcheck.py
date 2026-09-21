#!/usr/bin/env python3
"""track opendesign-b8-race-forensics 的红检夹具 —— 判据的判据。

四个情景,两类病:

  R1   ① 判据自污染:段内本来就有一个真 InstanceLock 在应答。
       造法:占住一个端口拿到真锁,再把 test 模块的 `free_port` 打桩成 P-3。
  R2a  ② 真产品缺陷(让位方向坏了):`_someone_ahead_of` 恒真 ⇒ 两份都让位。
       ⚠️ 2026-09-21 外审(subcursor)对着收据抓到我这里写过一句假话:原文说
       "读数里两份 port **不同值**(各自绑的那一格)",而 after-s1-fix-r2a.txt 里
       两份都是 46135。真实机制:先起的那份绑住 base 并开始应答,后起的那份
       `_scan` 就命中了它 ⇒ 走扫描命中分支(`self.port = hit`)⇒ 同值。
       ⇒ **两份 port 同值这个形状 r2a 也做得出**,更说明形状分不出病因(见 R2b)。
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
  R2d  ② 真产品缺陷(让位整个失灵):`_scan` 恒 None + `_someone_ahead_of` 恒 False
       ⇒ **两份都赢**。红的第三种长相 —— 业主双击两下开出**两个**窗口,
       那正是 b8 最初存在的理由。前两种长相都是 0 份赢,只造它们会漏掉这一半。
  R2d-no-ss  同上,但把 `ss` 从判据眼里藏掉(`shutil.which("ss") -> None`)。
  R2d-no-tools  同上,但 `ss` **和** `lsof` 都藏掉 ⇒ 一个 pid 都查不到。
       🔴 这条钉的是**取证知不知道自己不知道**:查不出归属时不许把应答者
       笃定地记进"环境残留",更不许顺着它把产品缺陷判成"判据环境脏"。
       该打印的是"归属查不出"+"先别下结论"。2026-09-21 外审两腿独立命中(F1)。
       🔴 这条钉的是**取证在降级路径上会不会说反话**:两份赢家还在监听,取证得认出
       "这两个是我自己",靠的是 `listener_pids`;它只认 `ss` 的 `pid=` 格式时,
       没装 ss 的机器上会把本轮自己算成"环境残留" ⇒ 把产品缺陷写成"判据环境脏"。
       修之前这条必然形状错(CLEAN_ENV 缺失),修之后与 r2d 同形。
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

# 🔴 只问"红不红"是不够的 —— 本单的产出是**分型能力**,不是红绿。
# 2026-09-21 实证:--lazy-probe 那次被变异骗到、把产品缺陷红成"环境脏",
# 而当时的夹具照印"符合预期"。所以这里钉的是**红在哪条断言上**。
PRE_GATE = "开轮前,锁位段"                  # 前置断言:判据环境脏
RACE_GATE = "份认为自己是唯一实例"           # 竞态断言:恰好 1 份赢
CLEAN_ENV = "(=环境残留):没有"              # 取证当场认定:段内没有外来残留
TWO_WINDOWS = "开出两个窗口"                 # 分型结论句:这次红的是"2 份都赢"那一种
ONE_WINDOW = "一个窗口都不开"                # 分型结论句:0 份赢那一种
UNKNOWN_OWNER = "归属查不出的格子"           # 取证承认:这几格是谁的,工具没说
NO_VERDICT = "先别下结论"                    # 承认之后的正确动作:不分型
# 🔴 **两支结论句都要钉,而且互相禁止**(2026-09-21 外审 F3,我复现过):
# 原来只有 r2d 钉了 TWO_WINDOWS,0 份赢那三条一个分型锚点都没有 ⇒ 把结论句硬写成
# "开出两个窗口",r2a/r2b/r2d 照印"形状=对" —— **改坏了分型而全套红检通过**,
# 正是这份夹具最该防住的事。
SHAPES = {
    # case -> (必须出现, 不许出现)
    "r1":  ([PRE_GATE], [RACE_GATE]),
    "r2a": ([RACE_GATE, CLEAN_ENV, ONE_WINDOW], [PRE_GATE, TWO_WINDOWS]),
    "r2b": ([RACE_GATE, CLEAN_ENV, ONE_WINDOW], [PRE_GATE, TWO_WINDOWS]),
    "r2c": ([RACE_GATE, CLEAN_ENV, ONE_WINDOW], [PRE_GATE, TWO_WINDOWS]),
    # 🔴 两份赢家红的那一刻**还在监听**,取证必须认出"这两个是我自己"(不是环境残留),
    # 而且结论句要落到"开出两个窗口"这一支上 —— 只钉 RACE_GATE 的话,说反话也算过。
    "r2d": ([RACE_GATE, CLEAN_ENV, TWO_WINDOWS], [PRE_GATE, ONE_WINDOW]),
    "r3":  ([], []),
}
# 偷懒版探测**必须**被 r2c 骗到,否则这条对照实验就不成立(它证明的是
# "复用被测代码做探测会把产品缺陷伪装成环境问题")。
SHAPES_LAZY = {"r2c": ([PRE_GATE], [RACE_GATE])}
# 一个 pid 都查不到时:承认查不出、别下分型结论 —— 两支结论句都不许出现。
SHAPES_NOTOOLS = {"r2d": ([RACE_GATE, UNKNOWN_OWNER, NO_VERDICT],
                          [PRE_GATE, TWO_WINDOWS, ONE_WINDOW])}

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
    elif case == "r2d":
        # 两处一起改:只关让位仲裁的话,先 bind 的那份可能被另一份的 _scan 扫到 ⇒
        # 退化成"恰好一份赢",造不出这种红。
        anchor = "    def _someone_ahead_of(self, mine: int) -> bool:\n"
        if anchor not in src or "    def _scan(self" not in src:
            raise SystemExit("变异锚点没找到,拒绝继续:r2d 要 _someone_ahead_of + _scan")
        src = src.replace(
            anchor,
            anchor + "        return False  # [MUTANT r2d] 让位仲裁失灵:谁都认为自己在最前面\n", 1)
        idx = src.index("    def _scan(self")
        head, rest = src[:idx], src[idx:]
        sig_end = rest.index("\n", rest.index(":\n")) + 1
        src = head + rest[:sig_end] + \
            "        return None  # [MUTANT r2d] 扫描恒说段内没人\n" + rest[sig_end:]
        open(path, "w", encoding="utf-8").write(src)
        return "_someone_ahead_of 恒 False + _scan 恒 None(两份都赢)"
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


def run_case(repo: str, case: str, lazy_probe: bool = False,
             hide_tools: tuple = ()) -> tuple[bool, str]:
    sys.path.insert(0, os.path.join(repo, "tests"))
    sys.path.insert(0, os.path.join(repo, "bin"))
    import test_ds_shell_core as T

    squatter = None
    patcher = None
    lazy = None
    hidden = None
    if hide_tools:
        # 把点名的工具从判据眼里藏掉 —— 模拟没装它们的机器(容器里很常见)。
        # 只挡点名的那几个,别的 which 照常。
        import shutil as _sh
        _real_which = _sh.which

        def _which_hiding(cmd, *a, **k):
            return None if cmd in hide_tools else _real_which(cmd, *a, **k)

        hidden = mock.patch.object(_sh, "which", _which_hiding)
        hidden.start()
        print(f"# ⚠️ 降级实验:判据眼里没有 {'/'.join(hide_tools)}")
    if lazy_probe:
        import ds_shell_core as _core

        def _lazy(base, span, timeout=1.5):
            """偷懒版:直接问产品自己的握手 —— 这正是本单**没有**采用的写法。"""
            probe = _core.InstanceLock(base_port=base, span=span)
            return [p for p in range(base, base + span + 1) if probe._send_show(p)]

        if not hasattr(T, "lock_responders_in"):
            raise SystemExit("🔴 这棵树上的 b8 还没有独立探测(lock_responders_in),"
                             "对照实验不适用 —— 这本身就是本单要改掉的状态")
        lazy = mock.patch.object(T, "lock_responders_in", _lazy)
        lazy.start()
        print("# ⚠️ 对照实验:前置探测已换成偷懒版(复用产品 _send_show)")
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
        if hidden:
            hidden.stop()
        if lazy:
            lazy.stop()
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
    ap.add_argument("--case", required=True,
                    choices=["r1", "r2a", "r2b", "r2c", "r2d", "r3"])
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--lazy-probe", action="store_true",
                    help="把 b8 的前置探测换成**偷懒版**(复用产品自己的 _send_show)。"
                         "对照实验:证明'探测必须独立'不是我嘴上说的 —— 配 r2c 跑,"
                         "偷懒版会被变异骗到,红在前置断言(把产品缺陷说成环境脏)。")
    ap.add_argument("--no-tools", action="store_true",
                    help="把 `ss` 和 `lsof` 都藏掉 ⇒ 一个 pid 都查不到。配 r2d 跑:"
                         "取证必须承认'归属查不出'并**先别下结论**,"
                         "不许把自己的赢家笃定地记成环境残留。")
    ap.add_argument("--no-ss", action="store_true",
                    help="把 `ss` 从判据眼里藏掉(模拟没装 ss 的机器)。配 r2d 跑:"
                         "两份赢家还在监听,取证必须仍认出'这两个是我自己'。")
    a = ap.parse_args()
    repo = os.path.realpath(a.repo)

    if a.case in ("r2a", "r2b", "r2c", "r2d"):
        if repo == LIVE_REPO:
            raise SystemExit("🔴 拒绝:变异只许打在仓外副本上,--repo 不能是活仓")
        what = mutate(repo, a.case)
        print(f"# 变异({a.case}):{what}  repo={repo}")
    else:
        print(f"# 无变异({a.case})  repo={repo}")

    expect_red = a.case in ("r1", "r2a", "r2b", "r2c", "r2d")
    if a.no_ss and a.no_tools:
        raise SystemExit("--no-ss 与 --no-tools 二选一(后者已经包含前者)")
    hide = ("ss", "lsof") if a.no_tools else (("ss",) if a.no_ss else ())
    shapes = SHAPES_NOTOOLS if a.no_tools else (SHAPES_LAZY if a.lazy_probe else SHAPES)
    for i in range(a.repeat):
        t0 = time.time()
        ok, out = run_case(repo, a.case, a.lazy_probe, hide)
        verdict = "绿" if ok else "红"
        want = "红" if expect_red else "绿"
        bad = []
        if ok == expect_red:
            bad.append(f"红绿不对(得到{verdict},要{want})")
        must, forbid = shapes[a.case]
        for anchor in must:
            if anchor not in out:
                bad.append(f"该红在这条断言上却没有:{anchor!r}")
        for anchor in forbid:
            if anchor in out:
                bad.append(f"红错了断言,不该出现:{anchor!r}")
        mark = "符合预期" if not bad else "🔴 不符合预期:" + " / ".join(bad)
        print(f"\n# [{a.case} 第{i+1}/{a.repeat}遍] 结果={verdict} 期望={want} "
              f"形状={'对' if not bad else '错'} {mark} ({time.time()-t0:.1f}s)")
        if bad:
            sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
