#!/usr/bin/env python3
"""备货 → 启动 → 安装,三个端点必须读同一个数据根(track opendesign-startup-not-blocked-by-update)。

主 agent 亲写,2026-09-20 第 1 轮外审之后补。

🔴 **由来**:subdeepseek 在第 1 轮报了一条我和另一条腿都没看见的阻断,我核实成立 ——
装出来的那一份里,**两个都叫 data_root 的东西不是一个东西**:

- `ds_common.data_root(ds_root)` 认 `DS_DATA_ROOT`,外壳给 ds-web 注的是
  `<应用状态根>\\Data`(`ds_shell_core.data_root_for`)⇒ 备货与启动接口写/读
  `…\\OpenDesign\\Data\\Logs\\update-state.json`;
- `ds_update_apply.paths_for_update()` 的默认 data_root 是
  `%LOCALAPPDATA%\\OpenDesign`(那一层装着 `Data\\` 和 `UserData\\`)⇒ 安装那一侧去读
  `…\\OpenDesign\\Logs\\update-state.json`,**那个文件根本不存在**。

真机症状:每次打开后端都说"该装",前端弹「正在更新到 X」,apply 一句 `auto_skipped` 静默跳过,
落回工作区。**那一版永远装不上,而盘上 46MB 一直留着。**

**为什么原来的判据结构上问不出它**:没有任何一条把这三个端点串起来跑过,
而且全 tests/ 没有一处设过 `DS_DATA_ROOT` —— 单测里两个根恰好相等,于是各自都绿。
e2e 又把 `/api/update/startup` 整个 route 掉了,根本不碰真后端。
所以这一卷的形状是刻意的:**设 DS_DATA_ROOT + 只替换网络和真安装器,其余一律走真代码。**
"""
import http.client
import json
import os
import sys
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
sys.path.insert(0, HERE)
import ds_common           # noqa: E402
import ds_update           # noqa: E402
import ds_update_apply     # noqa: E402
import ds_update_startup   # noqa: E402
import ds_web              # noqa: E402
import test_ds_web_auto_update as base   # noqa: E402

AUTO = base.AUTO
_post = base._post
_get = base._get
PKG_BODY = b"pretend installer bytes for 0.99.0"


class UpdateRootsAgree(unittest.TestCase):
    """三个端点、一个数据根。借 test_ds_web_auto_update 的装机夹具,不继承它的题目。"""

    setUpFixture = base.AutoUpdate.setUp
    _install = base.AutoUpdate._install
    _serve = base.AutoUpdate._serve

    def setUp(self):
        self.setUpFixture()
        # 🔴 生产布局:外壳给 ds-web 注的数据根是 <应用状态根>\Data,
        #    而不是 paths_for_update 默认的那一层。两者不等,正是本卷要盯的。
        self.shell_data_root = os.path.join(self.data_root, "Data")
        os.makedirs(self.shell_data_root, exist_ok=True)
        env = mock.patch.dict(os.environ, {"DS_DATA_ROOT": self.shell_data_root})
        env.start()
        self.addCleanup(env.stop)

        info = {"current": "0.90.0", "update_available": True, "latest": "0.99.0",
                "asset": {"name": "OpenDesign-Setup-0.99.0.exe",
                          "url": "https://example.invalid/OpenDesign-Setup-0.99.0.exe",
                          "size": len(PKG_BODY),
                          "digest": "sha256:" + __import__("hashlib").sha256(PKG_BODY).hexdigest()},
                "notes": "", "error": None, "release_url": None}
        real_cached = ds_update.check_cached
        self.addCleanup(setattr, ds_update, "check_cached", real_cached)
        ds_update.check_cached = lambda *a, **kw: info

        real_dl = ds_update_apply._default_download
        self.addCleanup(setattr, ds_update_apply, "_default_download", real_dl)

        def fake_download(url, dest):
            with open(dest, "wb") as fh:
                fh.write(PKG_BODY)
        ds_update_apply._default_download = fake_download

    def _state_files(self):
        """盘上所有 update-state.json —— 正常情况下**只许有一份**。"""
        out = []
        for base_dir, _dirs, files in os.walk(self.appdata):
            for f in files:
                if f == ds_update_startup.STATE_NAME:
                    p = os.path.join(base_dir, f)
                    out.append((p, (ds_update_startup.read_state(p) or {}).get("phase")))
        return sorted(out)

    def _wait_ready(self, port, timeout=10.0):
        end = time.time() + timeout
        while time.time() < end:
            _st, body = _get(port, "/api/update/startup")
            if (body or {}).get("action") == "install":
                return body
            time.sleep(0.1)
        return None

    def test_ur1_prepare_then_startup_then_install_all_read_the_same_root(self):
        """ur1:后台备好 ⇒ 启动接口说该装 ⇒ 自动安装真的走到安装那一步。

        这三步在真机上读的必须是同一个文件。中间**任何一步换了根**,这条就红。
        """
        with self._serve() as port:
            st, body = _post(port, "/api/update/prepare", b"{}")
            self.assertEqual(st, 200, body)
            self.assertIs(body.get("started"), True, body)

            startup = self._wait_ready(port)
            self.assertIsNotNone(startup, "备好之后启动接口仍然不说该装:%r" % (self._state_files(),))
            self.assertEqual(startup.get("version"), "0.99.0", startup)

            st, body = _post(port, "/api/update/apply", AUTO)

        self.assertEqual(st, 200, body)
        self.assertIs(body.get("ok"), True,
                      "启动接口说该装,自动安装却没装成 —— 多半是两侧读的不是同一个数据根:%r / 盘上:%r"
                      % (body, self._state_files()))
        self.assertEqual(self.order.count("apply"), 1, "没走到安装:%r" % (self.order,))

    def test_ur2_only_one_state_file_exists(self):
        """ur2:盘上只许有一份 update-state.json。

        两份 = 两个根各写各的(写的人和读的人从此各看各的),那正是 ur1 失败时的形状;
        这一条把症状钉成一个**一眼可查的事实**,免得下次又只能靠读代码发现。
        """
        with self._serve() as port:
            _post(port, "/api/update/prepare", b"{}")
            self._wait_ready(port)
            _post(port, "/api/update/apply", AUTO)
        files = self._state_files()
        self.assertEqual(len(files), 1, "盘上有 %d 份状态文件:%r" % (len(files), files))

    def test_ur3_the_state_sits_next_to_the_attempts_log(self):
        """ur3:状态文件与既有的 auto-update-attempts.json **同侧**。

        这是 design.md 里写的("卸载不带走、安装不覆盖"),原来的 sp1 在单测里成立、
        **在生产布局下不成立** —— 因为它从没设过 DS_DATA_ROOT。
        """
        with self._serve() as port:
            _post(port, "/api/update/prepare", b"{}")
            self._wait_ready(port)
            _post(port, "/api/update/apply", AUTO)
        files = self._state_files()
        self.assertTrue(files, "一份状态文件都没写出来")
        self.assertEqual(os.path.dirname(files[0][0]), os.path.dirname(self.record),
                         "状态文件和记账文件不在同一侧:%r vs %r" % (files[0][0], self.record))


if __name__ == "__main__":
    unittest.main()
