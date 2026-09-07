#!/usr/bin/env python3
"""e2e 端口预检的判据(track opendesign-stage-timer-e2e-red)。

🔴 **由来是一次真事故,不是假想**:`stage_timer.e2e.mjs` 连红五天以上,
被三个单子写成"既有红,非本单引入"传了下去。真因是 **2026-08-30 留下的一个
遗孤 `ds_web` 进程**一直占着它写死的端口 8814:

  · 遗孤的父进程死了,它活着;那次 run 的 trap 又把它的隔离 HOME 删了
    ⇒ 它读不到假 key ⇒ 前端弹"去配 key"的遮罩 ⇒ **每一次点击都被拦下**
  · 而 35 条自起服务的 e2e **全都**只等 `/api/health` 有人应答,
    **不问应答的是不是自己刚起的那个** ⇒ 对着八天前的旧服务跑完整场

杀掉遗孤后同一条 e2e **4 秒通过**(此前 92 秒全是点击重试超时)。

这道闸问的是**结果**:开跑之前端口干不干净。
"""
from __future__ import annotations

import os
import re
import socket
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREFLIGHT = os.path.join(ROOT, "tests", "e2e", "check-ports.sh")


def _run(*args):
    return subprocess.run(["bash", PREFLIGHT, *args],
                          capture_output=True, text=True, cwd=ROOT)


class E2EPortPreflight(unittest.TestCase):

    def test_p1_preflight_exists_and_is_runnable(self):
        """预检本身得在 —— 它不在的话,下面两条问的都是空气。"""
        self.assertTrue(
            os.path.isfile(PREFLIGHT),
            f"找不到 {PREFLIGHT} —— e2e 端口预检没了,"
            "那么「端口被遗孤占着」这件事又会以「产品坏了」的样子出现。")

    def test_p2_clean_ports_pass(self):
        """对照组:没人占的端口必须放行 —— **误报和假绿一样坏**。

        用一个几乎不可能有人用的高位端口,避免把开发机上正常的服务算进来。
        """
        r = _run("65431", "65432")
        self.assertEqual(
            0, r.returncode,
            f"没人占的端口被报成占用了 —— 误报。\n{r.stdout}\n{r.stderr}")

    def test_p3_an_occupied_port_is_caught_and_named(self):
        """真占上一个端口,预检必须红,而且**要说出是哪个端口、谁占的**。

        只说"有问题"不够:2026-08-30 那个遗孤之所以活了八天没人发现,
        就是因为没有任何一句话把"端口被占"和"测试红了"连起来。
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.listen(1)
        try:
            r = _run(str(port))
        finally:
            s.close()

        self.assertEqual(
            1, r.returncode,
            f"端口 {port} 上明明有人监听,预检却放行了。\n{r.stdout}\n{r.stderr}")
        self.assertIn(
            str(port), r.stdout,
            f"预检红了,但没说是哪个端口 —— 人得能照着它去查。\n{r.stdout}")
        self.assertIn(
            "pid=", r.stdout,
            f"预检没报出占用者的 pid —— 那就还是查不动。\n{r.stdout}")

    def test_p5_no_ss_must_fail_closed(self):
        """🔴 `ss` 用不了的时候,预检必须**喊停**,不许说"干净"。

        由来(2026-09-07,三条评审腿里两条**各自独立**命中,我自己复现):
        第一版把 `ss` 的错误 `2>/dev/null` 吞掉,拿到空串就当"没人占" ——
        于是在没有 iproute2 的机器(最小容器/Alpine)上,**这道闸恒绿**。
        我建它就是为了消灭恒绿的检查,结果它自己是恒绿的。

        实测(fake ss 返回 127,端口上真有人监听):
        旧版打印 `✅ e2e 端口预检:1 个端口都没人占`,rc=0。
        """
        import tempfile
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.listen(1)
        with tempfile.TemporaryDirectory() as fake:
            ss = os.path.join(fake, "ss")
            with open(ss, "w", encoding="utf-8") as fh:
                fh.write("#!/bin/bash\nexit 127\n")
            os.chmod(ss, 0o755)
            env = dict(os.environ, PATH=fake + os.pathsep + os.environ["PATH"])
            try:
                r = subprocess.run(["bash", PREFLIGHT, str(port)],
                                   capture_output=True, text=True, cwd=ROOT, env=env)
            finally:
                s.close()

        self.assertNotEqual(
            0, r.returncode,
            "ss 用不了的时候预检说了「干净」—— 这是恒绿,"
            f"而端口 {port} 上真的有人监听。\n{r.stdout}\n{r.stderr}")

    def test_p5b_missing_ss_binary_must_fail_closed(self):
        """`ss` **根本不存在**时也必须喊停(p5 测的是"ss 在但坏了")。

        走 `SS_BIN` 接缝 —— 那个接缝存在的唯一理由就是让这条分支**能被判**:
        不给接缝,这条分支在任何装了 iproute2 的机器上都跑不到,
        它就成了一条死断言,而死断言正是本单在治的病。
        """
        env = dict(os.environ, SS_BIN="definitely-not-a-real-ss-binary")
        r = subprocess.run(["bash", PREFLIGHT, "65434"],
                           capture_output=True, text=True, cwd=ROOT, env=env)
        self.assertNotEqual(
            0, r.returncode,
            f"没有 ss 的时候预检说了「干净」—— 恒绿。\n{r.stdout}\n{r.stderr}")

    def test_p6_every_scene_that_starts_a_server_contributes_a_port(self):
        """🔴 "抓到一部分" 必须响 —— 只防"一个都没抓到"是不够的。

        由来:两条腿都指出正则 `^const PORT = N` 只认一种写法
        (行首/大写/有空格/字面量),谁把某个场景改成 `let PORT` 或从配置读,
        这道闸就对**那一个**场景永远瞎,而总数还是 29、30,兜底不触发。

        这里不写死一个 MIN_PORTS 魔数(那个数字自己会过期),
        而是问一个真不变量:**凡是自起 ds_web 的场景,都必须贡献至少一个端口。**
        """
        import glob
        r = subprocess.run(["bash", PREFLIGHT, "--list"],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(
            0, r.returncode,
            f"预检的 --list 模式跑不起来。\n{r.stdout}\n{r.stderr}")
        listed = r.stdout.split()

        missing = []
        for f in sorted(glob.glob(os.path.join(ROOT, "tests", "e2e", "*.e2e.mjs"))):
            with open(f, encoding="utf-8") as fh:
                src = fh.read()
            if "ds_web.py" not in src:
                continue
            mine = re.findall(r"(?m)^const PORT = ([0-9]+)", src)
            if not mine:
                missing.append(os.path.basename(f))
        self.assertEqual(
            [], missing,
            f"这些场景自起 ds_web,却没有被端口扫描抓到:{missing}\n"
            "⇒ 预检对它们永远瞎,而总数看起来还很正常。")

    def test_p7_derived_ports_are_scanned_too(self):
        """🔴 `PORT + 1` 起的第二个服务也要扫。

        由来:两条腿都点名 `button_roles.e2e.mjs:97` 的 `spawnWeb(planRoot, PORT + 1)`
        = 8825,**完全不在扫描范围内**;`gallery_head_buttons` 的 PORT+1 = 8820
        碰巧被别的场景声明覆盖了 —— **是巧合,不是机制**。
        """
        import glob
        r = subprocess.run(["bash", PREFLIGHT, "--list"],
                           capture_output=True, text=True, cwd=ROOT)
        listed = set(r.stdout.split())

        want = {}
        for f in sorted(glob.glob(os.path.join(ROOT, "tests", "e2e", "*.e2e.mjs"))):
            with open(f, encoding="utf-8") as fh:
                src = fh.read()
            m = re.search(r"(?m)^const PORT = ([0-9]+)", src)
            if not m:
                continue
            base = int(m.group(1))
            for off in set(re.findall(r"PORT \+ ([0-9]+)", src)):
                want[str(base + int(off))] = os.path.basename(f)

        gap = {p: f for p, f in want.items() if p not in listed}
        self.assertEqual(
            {}, gap,
            f"这些**派生端口**没被扫到:{gap}\n"
            "场景用 PORT+N 另起了一个 ds_web,遗孤占着那个端口时预检照样放行。")

    def test_p4_wired_into_the_e2e_runner(self):
        """🔴 光有闸不算数,得有人叫它 —— 这个项目在"守卫没接线"上栽过不止一次。"""
        runner = os.path.join(ROOT, "tests", "e2e", "run-all.sh")
        with open(runner, encoding="utf-8") as fh:
            src = fh.read()
        # 🔴 用 assertTrue 而不是 assertIn:assertIn 失败时会把**整份 run-all.sh**
        #    打进失败消息,而那里面有一把 e2e 夹具用的假 key ——
        #    2026-09-07 第一版就是这么写的,runlog 的秘密扫描当场拒绝出收据(拒对了)。
        #    判据不该把被测文件整个吐出来,既泄漏又没法读。
        self.assertTrue(
            "check-ports.sh" in src,
            "e2e 总跑(tests/e2e/run-all.sh)没有调用端口预检 —— "
            "闸建好了没接线,等于没建。")


if __name__ == "__main__":
    unittest.main()
