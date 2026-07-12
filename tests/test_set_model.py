#!/usr/bin/env python3
"""set_model.py oracle — track opendesign-workbench-p4 T2。

跑法:  python3 tests/test_set_model.py
契约:改 agents.defaults.model 前先备份 .bak;config 缺失/损坏 → 非零退出不写;
成功后提示重启 gateway(切换只落盘,运行中的进程不自动换脑)。
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(ROOT, "bin", "set_model.py")


def _run(*args):
    return subprocess.run([sys.executable, SCRIPT, *args],
                          capture_output=True, encoding="utf-8", timeout=30)


def _mkcfg(payload) -> str:
    d = tempfile.mkdtemp(prefix="set_model_test_")
    p = os.path.join(d, "config.json")
    with open(p, "w", encoding="utf-8") as fh:
        if isinstance(payload, str):
            fh.write(payload)
        else:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
    return p


class TestSetModel(unittest.TestCase):

    # ① 回环:改 model 成功,其余字段一字不动,.bak 是改前原文
    def test_01_roundtrip(self):
        cfg = _mkcfg({"agents": {"defaults": {"model": "xiaomi/mimo-v2.5",
                                              "maxTokens": 8192}},
                      "channels": {"websocket": {"enabled": True}}})
        before = open(cfg, encoding="utf-8").read()
        r = _run("xiaomi/mimo-v2.5-pro", "--config", cfg)
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.load(open(cfg, encoding="utf-8"))
        self.assertEqual(d["agents"]["defaults"]["model"], "xiaomi/mimo-v2.5-pro")
        self.assertEqual(d["agents"]["defaults"]["maxTokens"], 8192)   # 别的字段不碰
        self.assertTrue(d["channels"]["websocket"]["enabled"])
        self.assertEqual(open(cfg + ".bak", encoding="utf-8").read(), before)
        self.assertIn("重启", r.stdout)   # 提示重启 gateway(部署目标规则)

    # ② config 缺失 → 非零退出,不创建文件
    def test_02_missing_config(self):
        missing = os.path.join(tempfile.mkdtemp(prefix="set_model_test_"), "nope.json")
        r = _run("m/x", "--config", missing)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(os.path.exists(missing))

    # ③ config 损坏 → 非零退出,原文件一字不动
    def test_03_broken_config(self):
        cfg = _mkcfg("{broken")
        r = _run("m/x", "--config", cfg)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(open(cfg, encoding="utf-8").read(), "{broken")

    # ④ 空 model id → 非零退出(防手滑清空)
    def test_04_empty_model(self):
        cfg = _mkcfg({"agents": {"defaults": {"model": "a/b"}}})
        r = _run("", "--config", cfg)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(json.load(open(cfg, encoding="utf-8"))
                         ["agents"]["defaults"]["model"], "a/b")


if __name__ == "__main__":
    unittest.main(verbosity=2)
