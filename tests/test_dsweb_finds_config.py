#!/usr/bin/env python3
"""ds-web 在**外壳给它的那份环境**里,找不找得到网关配置。

## 为什么要单独有这一条

业主的登录口令**不由他输** —— ds-web 从网关配置里读出来替前端签
(`ds_web._gateway_password()`,track opendesign-key-onboarding)。这条链上
外壳和 ds-web 之间靠的是一个**隐式契约**:

  · 外壳改写的是 `<user_home>/.nanobot/config.json`(ds_shell.py:149);
  · 外壳**不设** `DS_NANOBOT_CONFIG`,只把 `HOME`/`USERPROFILE` 设成 user_home
    (ds_shell_core.child_env);
  · ds-web 于是靠 `expanduser("~")` 推出同一份文件。

三步里**没有一步是显式说出来的**。现有判据全都自己 `os.environ["DS_NANOBOT_CONFIG"]=…`
再测代签 —— 那问的是"给对了路径,代签能不能工作",**不是**"生产环境下它找不找得到"。
两张卷子对同一个前提做了相反的假设,而没有一张去问那个前提本身
(同 08-14 那条:Linux 的 G2 给假 key、Windows 的 S1b 故意不给 key)。

这条断了会怎样:`_gateway_password()` 返回 None ⇒ 前端不带凭证 ⇒ **聊天连不上**,
而两条腿都活着、日志全绿、什么都不报错。**业主 0.88.0 报的第一个症状就是
「聊天连不上」,它的根因至今没有确认** —— 这条是候选之一,所以先把它问出来。
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bin"))

import ds_shell_core as core  # noqa: E402
import ds_web  # noqa: E402

PASSWORD = "e2e-fixture-password-9"


class DsWebFindsTheConfig(unittest.TestCase):

    def setUp(self):
        self.home = tempfile.mkdtemp()
        # 外壳改写的就是这一份(ds_shell.py:149 `home / ".nanobot" / "config.json"`)
        self.cfg = Path(self.home) / ".nanobot" / "config.json"
        self.cfg.parent.mkdir(parents=True, exist_ok=True)
        self.cfg.write_text(json.dumps({
            "channels": {"websocket": {"enabled": True, "token": PASSWORD}},
        }), encoding="utf-8")

    def tearDown(self):
        importlib.reload(ds_web)     # 还原模块级常量,别把状态漏给别的判据

    def _shell_env(self) -> dict:
        """外壳真正交给 ds-web 那条腿的环境(key 不进这条腿,见 service_envs)。"""
        return core.service_envs(
            {}, ds_root=os.path.join(self.home, "ds"), user_home=self.home,
            dsweb_port=8766, ws_port=8765, key=None, key_var=None, lock_port=8767,
        )["ds-web"]

    def test_g1_ds_web_finds_the_password_with_only_what_the_shell_gave_it(self):
        """**只给外壳给的那些变量**(clear=True),ds-web 必须能读出口令。

        红在这里 = 业主装好之后聊天连不上,而且哪儿都不报错。
        """
        env = self._shell_env()
        self.assertNotIn("DS_NANOBOT_CONFIG", env,
                         "外壳开始显式告诉 ds-web 配置在哪了 —— 那这条隐式契约就不存在了,"
                         "本判据该换成直接咬那个变量")
        with mock.patch.dict(os.environ, env, clear=True):
            importlib.reload(ds_web)     # 模块级常量按新 HOME 重算
            got = ds_web._gateway_password()
        self.assertEqual(PASSWORD, got,
                         "ds-web 在外壳给的环境里找不到网关配置 ⇒ 它不会替前端签 token ⇒ "
                         "**聊天连不上,而两条腿都活着、日志全绿**")

    def test_g2_the_explicit_override_still_wins(self):
        """`DS_NANOBOT_CONFIG` 显式给时必须优先 —— e2e 和 git-pull 那两台靠它。"""
        other = Path(self.home) / "别处" / "config.json"
        other.parent.mkdir(parents=True, exist_ok=True)
        # 🔴 口令用 ASCII:第一版我在这儿写了中文,红了 —— 而那是**实现对的**
        #    (非 latin-1 的口令进不了 HTTP 头,`_gateway_password` 有意降级成 None)。
        #    判据自己踩了被判方的一条正确防线,顺带把那条防线也验了一遍。
        other.write_text(json.dumps({
            "channels": {"websocket": {"enabled": True, "token": "another-fixture-token"}},
        }), encoding="utf-8")
        env = dict(self._shell_env(), DS_NANOBOT_CONFIG=str(other))
        with mock.patch.dict(os.environ, env, clear=True):
            importlib.reload(ds_web)
            self.assertEqual("another-fixture-token", ds_web._gateway_password())

    def test_g4_a_non_latin1_password_degrades_instead_of_exploding(self):
        """中文口令 ⇒ 回 None(交给手输兜底),不许抛也不许原样返回。
        它进不了 HTTP 头 —— 原样返回的话前端会炸在 fetch 上,而不是给出一句人话。"""
        self.cfg.write_text(json.dumps({
            "channels": {"websocket": {"enabled": True, "token": "中文口令"}},
        }), encoding="utf-8")
        with mock.patch.dict(os.environ, self._shell_env(), clear=True):
            importlib.reload(ds_web)
            self.assertIsNone(ds_web._gateway_password())

    def test_g3_no_token_means_no_signing_not_a_crash(self):
        """配置里没口令时回 None(交给前端的手输兜底),不许抛 —— 抛了整个页面就白了。"""
        self.cfg.write_text(json.dumps({"channels": {"websocket": {"enabled": True}}}),
                            encoding="utf-8")
        with mock.patch.dict(os.environ, self._shell_env(), clear=True):
            importlib.reload(ds_web)
            self.assertIsNone(ds_web._gateway_password())


if __name__ == "__main__":
    unittest.main(verbosity=2)
