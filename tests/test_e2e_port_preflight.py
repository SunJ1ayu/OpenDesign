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
