#!/usr/bin/env python3
"""判据:业主在界面里填大模型 key(track opendesign-key-onboarding)。

    /root/.venvs/design-studio/bin/python tests/test_credential.py

## 为什么这份判据存在

装完第一次打开,业主现在看到的是一句「没找到大模型 key,请把它放进 …\\key.txt」——
他得自己找文件、贴 key、重启程序。这一单让他在界面里填。

**而 key 是凭据**:它会经我们的手落盘、进配置、进日志、进我这边的收据。
所以本文件的重心不是"填了能不能用",是**"填完之后它有没有从别的口漏出去"**。

## 它问的最硬的一条不是"不回显"

规划双出 B 卷点破:只查"接口回没回原文"是**枚举表面** —— 我只查得到我想得到的那几面。
所以 A 组换成**扫整棵树**:在隔离的家里跑完整流程,断言这把 key **恰好只出现在
`key.txt` 一处**,别处零命中。**漏了哪个口不需要我事先知道。**

## 它问不出什么

- **重启之后模型真的回话** —— 判据只能验"发出了重启请求";真跑通只有真机能答
  (B 卷也点了这条:不许照抄 DSH 的"无 reload 就生效",我们是 env 注入,做不到)。
- **Windows 上 key.txt 的文件权限**(ACL 才是真的,`chmod` 语义不同)。
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))

import ds_credential  # noqa: E402

TEMPLATE = os.path.join(ROOT, "config", "nanobot.config.windows.jsonc")
LINUX_TEMPLATE = os.path.join(ROOT, "config", "nanobot.config.jsonc")

# 一把长得像真 key 的串。**必须是纯 ASCII** —— 第一版我在里面写了中文,
# 被实现自己的 latin-1 闸拦下了(那道闸是对的:key 要经 HTTP 头和环境变量,
# 非 latin-1 的东西一路走不通)。**实现挡住了判据的夹具,这次是判据错。**
FAKE_KEY = "sk-oracle-do-not-ship-0123456789abcdef0123456789"

# 判据自己不许够得着这台机器的真家(08-15 那笔账的机械版)
_JUDGE_HOME = None
_SAVED: dict[str, str | None] = {}


def setUpModule():
    global _JUDGE_HOME
    _JUDGE_HOME = tempfile.mkdtemp(prefix="ds-credential-判据假家-")
    for k in ("HOME", "USERPROFILE"):
        _SAVED[k] = os.environ.get(k)
        os.environ[k] = _JUDGE_HOME


def tearDownModule():
    for k, v in _SAVED.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def sweep(root: str, needle: str) -> list[str]:
    """整棵树里哪些文件含这个串。**这是本文件最重要的一个函数**:
    它不需要我事先知道有哪些泄漏口。"""
    hits = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for fn in files:
            p = os.path.join(base, fn)
            try:
                with open(p, "rb") as fh:
                    if needle.encode("utf-8") in fh.read():
                        hits.append(os.path.relpath(p, root))
            except OSError:
                pass
    return sorted(hits)


class Rig(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ds-credential-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = os.path.join(self.tmp, "UserData")
        os.makedirs(os.path.join(self.home, ".nanobot"), exist_ok=True)
        self.cfg_path = os.path.join(self.home, ".nanobot", "config.json")
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            json.dump({
                "providers": {"custom": {"apiKey": "${DS_LLM_KEY}",
                                         "apiBase": "https://旧的/v1"}},
                "model_presets": {"旧模型": {"provider": "custom", "model": "旧模型"}},
                "agents": {"defaults": {"modelPreset": "旧模型"}},
            }, fh, ensure_ascii=False, indent=2)


class TestSecretDoesNotLeak(Rig):
    """A 组:**本文件最硬的一组** —— 跑完整流程之后,这把 key 恰好只在一处。"""

    def test_a1_the_key_lands_in_exactly_one_file(self):
        ds_credential.save(home=self.home, cfg_path=self.cfg_path,
                           provider="deepseek", key=FAKE_KEY)
        hits = sweep(self.tmp, FAKE_KEY)
        self.assertEqual(hits, [os.path.join("UserData", ".openDesign", "key.txt")],
                         f"这把 key 出现在了不该出现的地方:{hits}")

    def test_a2_nothing_the_api_returns_contains_the_key(self):
        saved = ds_credential.save(home=self.home, cfg_path=self.cfg_path,
                                   provider="deepseek", key=FAKE_KEY)
        got = ds_credential.status(home=self.home, cfg_path=self.cfg_path)
        for name, payload in (("save", saved), ("status", got)):
            blob = json.dumps(payload, ensure_ascii=False)
            self.assertNotIn(FAKE_KEY, blob, f"{name} 的返回里带着 key 原文:{blob[:200]}")
            self.assertNotIn(FAKE_KEY[4:20], blob, f"{name} 的返回里带着 key 的一段")

    def test_a3_the_config_never_holds_the_key(self):
        """与 test_ds_provision 的 a6 同一条不变量(配置会进日志、截图、我的收据)。"""
        ds_credential.save(home=self.home, cfg_path=self.cfg_path,
                           provider="mimo", key=FAKE_KEY)
        body = open(self.cfg_path, encoding="utf-8").read()
        self.assertNotIn(FAKE_KEY, body, "key 被写进配置文件了")
        self.assertIn("${", body, "配置里的 apiKey 不再是 ${VAR} 引用形态")

    def test_a4_the_failure_path_does_not_leak_it_either(self):
        """只跑 happy path 是 B 卷点名的骗法之一:坏路径上的报错最容易把入参回显出来。"""
        bad = os.path.join(self.tmp, "没有这个目录", "config.json")
        try:
            ds_credential.save(home=self.home, cfg_path=bad,
                               provider="mimo", key=FAKE_KEY)
        except Exception as exc:                       # 报错是可以的,带着 key 不行
            self.assertNotIn(FAKE_KEY, str(exc), f"报错信息里带着 key:{exc}")
        hits = sweep(self.tmp, FAKE_KEY)
        self.assertNotIn(os.path.join("没有这个目录", "config.json"), hits)

    def test_a5_the_hint_is_a_hint_not_the_key(self):
        got = ds_credential.save(home=self.home, cfg_path=self.cfg_path,
                                 provider="mimo", key=FAKE_KEY)
        hint = str(got.get("hint") or "")
        self.assertTrue(hint, "没给业主任何'已配置'的凭证提示")
        self.assertNotIn(FAKE_KEY, hint)
        self.assertLess(len(hint), len(FAKE_KEY), f"所谓提示几乎就是原文:{hint}")


class TestWritesLandWhereTheyShould(Rig):
    """B 组:写对地方。"""

    def test_b1_key_file_is_one_clean_line(self):
        """白名单掩盖二次写入(B 卷骗法):允许 key 在 key.txt,那它往里多写点别的就看不见。"""
        ds_credential.save(home=self.home, cfg_path=self.cfg_path,
                           provider="mimo", key=FAKE_KEY)
        body = open(os.path.join(self.home, ".openDesign", "key.txt"),
                    encoding="utf-8").read()
        self.assertEqual(body.strip(), FAKE_KEY)
        self.assertEqual(len([ln for ln in body.splitlines() if ln.strip()]), 1,
                         f"key.txt 里不止一行:{body!r}")

    def test_b2_provider_lands_in_the_config(self):
        ds_credential.save(home=self.home, cfg_path=self.cfg_path,
                           provider="deepseek", key=FAKE_KEY)
        cfg = json.load(open(self.cfg_path, encoding="utf-8"))
        self.assertIn("deepseek", json.dumps(cfg, ensure_ascii=False),
                      "厂商没写进配置(apiBase / 模型预设)")

    def test_b3_the_presets_come_from_the_shipped_template_not_a_second_copy(self):
        """骗法四:模型名/端点在判据里再硬编码一遍 ⇒ 两边一起错也发现不了。
        这一条要求实现的预设值**能在出货模板里找到出处**。"""
        tpl = open(TEMPLATE, encoding="utf-8").read()
        mimo = ds_credential.PROVIDERS["mimo"]
        self.assertIn(mimo["apiBase"], tpl, "MiMo 的 apiBase 与出货模板对不上")
        self.assertIn(mimo["model"], tpl, "MiMo 的默认模型与出货模板对不上")

    def test_b4_deepseek_models_are_the_ones_that_still_exist(self):
        """08-15 现拉 `GET /models` 核过:官方只剩这两个,老的两个已下架。
        写死在这儿是**故意的** —— 它是一条会过期的断言,过期时应该有人来重新核。"""
        ds = ds_credential.PROVIDERS["deepseek"]
        self.assertEqual(ds["apiBase"], "https://api.deepseek.com/v1")
        self.assertIn(ds["model"], ("deepseek-v4-flash", "deepseek-v4-pro"))


class TestEnvVarNameComesFromTheConfig(Rig):
    """C 组:🔴 规划双出 B 卷抓到的、我本来会直接发出去的那条。

    Windows 那份配置引用 `${DS_LLM_KEY}`,而**Linux 那份引用 `${MIMO_TP_KEY}`**。
    重启网关时要是把变量名写死,**两台 git-pull 机器上网关必死**。
    """

    def test_c1_reads_whatever_variable_the_config_references(self):
        for var in ("DS_LLM_KEY", "MIMO_TP_KEY", "随便什么名字"):
            cfg = {"providers": {"custom": {"apiKey": "${%s}" % var}}}
            self.assertEqual(ds_credential.env_var_name(cfg), var)

    def test_c2_the_shipped_linux_template_really_uses_a_different_name(self):
        """这条锁的是"B 卷说的那件事仍然成立" —— 哪天两份模板统一了,它会红,
        提醒下一个人回来把 C 组的理由重写,而不是让理由悄悄过期。"""
        win = json.dumps(_load_jsonc(TEMPLATE), ensure_ascii=False)
        lin = json.dumps(_load_jsonc(LINUX_TEMPLATE), ensure_ascii=False)
        self.assertIn("${DS_LLM_KEY}", win)
        self.assertIn("${MIMO_TP_KEY}", lin,
                      "Linux 模板不再引用 MIMO_TP_KEY —— C 组的理由要重写")

    def test_c3_no_reference_is_an_error_not_a_silent_default(self):
        cfg = {"providers": {"custom": {"apiKey": "写死的明文"}}}
        with self.assertRaises(ds_credential.CredentialError):
            ds_credential.env_var_name(cfg)


class TestShellStartsTheUiEvenWithoutAKey(unittest.TestCase):
    """D 组:🔴 B 卷抓到的第二条 —— **没有它这一单交付不出来**。

    今天 `ds_shell.start_backend` 是"缺 key 就整个 die()",而那发生在**开窗口之前**
    ⇒ 引导页永远没机会出现。正确形状:ds-web 无条件起、网关有 key 才起。
    """

    def test_d1_without_a_key_the_web_starts_and_the_gateway_waits(self):
        import ds_shell_core as core
        plan = core.startup_plan(has_key=False)
        self.assertIn("ds-web", plan["start"], "缺 key 时界面也不起 ⇒ 业主看不到引导页")
        self.assertIn("网关", plan["wait"], "缺 key 时网关不该起(它会自己死在缺变量上)")

    def test_d2_with_a_key_both_legs_start(self):
        import ds_shell_core as core
        plan = core.startup_plan(has_key=True)
        self.assertIn("ds-web", plan["start"])
        self.assertIn("网关", plan["start"])
        self.assertEqual(plan["wait"], [])


class TestWhichLayerActuallySuppliesTheKey(Rig):
    """E 组:**界面说的「已配置」必须和真正生效的那把 key 是同一件事。**

    2026-08-16 对照 DeepSeek Harness 的 credentials seam 补的
    (`docs/subsystems/credentials.zh.md`:`describe()` 报告**来源层**与 `writable`,
    并把「由当前进程环境供值」的引用标成不可写 —— 因为那样的写入
    **表面成功而解析持续返回遮蔽值**,所以它选择直接拒绝)。

    我们这边的实际形状:`bin/ds-nanobot.ps1` 是 **env 优先**
    (`if (-not $env:DS_LLM_KEY) { 读 key.txt }`),而 `status()` **只看 key.txt**。
    两边看的不是同一个地方,于是有两个业主会踩的坑:

    - **误弹卡片**:机器预设了环境变量、没有 key.txt ⇒ 网关明明能用,界面却报
      「没配」并自动弹卡催他填。**这台开发机就是这个情况**(key 走 mimocode 的
      auth.json)—— 08-16 那 29 条 e2e 被遮罩挡住,根子就在这儿,当时我只是用
      「给测试塞一把假 key.txt」绕开了症状。
    - **表面成功**(更坏):预设了环境变量时业主填新 key ⇒ 写进 key.txt、界面显示
      **新 key 的末四位**;重启后启动脚本看见 env 已有值就不读 key.txt,网关继续用
      旧的那把。**业主从界面上完全查不出来。**

    ⚠️ 本组只问「报告得对不对」。「网关真的用了哪把」只有真机能答 —— 已进真机清单。
    """

    VAR = "DS_LLM_KEY"          # Rig 的 cfg 引用的就是它(变量名仍从配置读,见 C 组)

    def _env(self, value: str | None) -> None:
        old = os.environ.get(self.VAR)

        def restore() -> None:
            if old is None:
                os.environ.pop(self.VAR, None)
            else:
                os.environ[self.VAR] = old

        self.addCleanup(restore)
        if value is None:
            os.environ.pop(self.VAR, None)
        else:
            os.environ[self.VAR] = value

    def test_e1_env_supplied_counts_as_configured(self):
        """没有 key.txt 但环境变量有值 ⇒ 已配置。报"没配"就会催业主填一把他根本不需要的 key。"""
        self._env(FAKE_KEY)
        st = ds_credential.status(self.home, self.cfg_path)
        self.assertTrue(st["configured"],
                        "环境变量供着 key,界面却说没配 ⇒ 装完就弹一张不该弹的卡")

    def test_e2_env_supplied_reports_its_layer(self):
        self._env(FAKE_KEY)
        st = ds_credential.status(self.home, self.cfg_path)
        self.assertEqual(st["source"], "env")

    def test_e3_file_supplied_reports_its_layer(self):
        self._env(None)
        ds_credential.save(home=self.home, cfg_path=self.cfg_path,
                           provider="deepseek", key=FAKE_KEY)
        st = ds_credential.status(self.home, self.cfg_path)
        self.assertTrue(st["configured"])
        self.assertEqual(st["source"], "file")

    def test_e4_when_both_exist_it_reports_the_one_that_actually_wins(self):
        """🔴 本组最该守的一条:两边都有值时,报告的必须是**真正生效**的那把。

        启动脚本 env 优先 ⇒ 生效的是 env。若 hint 报的是 key.txt 那把的末四位,
        业主换完 key 会看见"新的末四位"、用着旧的 key,而且无从发现。
        """
        env_key = FAKE_KEY[:-4] + "EEEE"
        file_key = FAKE_KEY[:-4] + "FFFF"
        self._env(None)
        ds_credential.save(home=self.home, cfg_path=self.cfg_path,
                           provider="deepseek", key=file_key)
        self._env(env_key)
        st = ds_credential.status(self.home, self.cfg_path)
        self.assertEqual(st["source"], "env")
        # 期望值从实现自己的 hint 函数现读,不在这儿拼第二份格式(骗法四)
        self.assertEqual(st["hint"], ds_credential._hint(env_key))
        self.assertNotEqual(st["hint"], ds_credential._hint(file_key),
                            "报的是 key.txt 那把 ⇒ 业主看见的末四位是假的")

    def test_e5_empty_env_is_absent_not_configured(self):
        """DSH 的 seam 级规则:空的存储值在任何地方都视为不存在。
        启动脚本那句 `if (-not $env:DS_LLM_KEY)` 对空串同样成立 ⇒ 空串该回落到 key.txt。"""
        self._env("")
        st = ds_credential.status(self.home, self.cfg_path)
        self.assertFalse(st["configured"],
                         "空串被当成配好了 ⇒ 界面不弹卡,而网关起不来")
        self.assertIsNone(st["source"])

    def test_e6_env_supplied_is_not_writable(self):
        """写 key.txt 改不动 env 供的值 ⇒ 必须提前把这一格标成只读,别让业主白填一次。"""
        self._env(FAKE_KEY)
        st = ds_credential.status(self.home, self.cfg_path)
        self.assertFalse(st["writable"])

    def test_e7_without_env_it_is_writable(self):
        self._env(None)
        st = ds_credential.status(self.home, self.cfg_path)
        self.assertTrue(st["writable"], "没人遮蔽的时候必须能写,否则业主永远填不上")
        self.assertFalse(st["configured"])
        self.assertIsNone(st["source"])

    def test_e8_saving_while_shadowed_is_refused_and_says_which_variable(self):
        """DSH 选择直接拒绝,我们照做:让它"成功"就是在骗业主。
        错误话里必须点名那个变量,否则他不知道该去改哪儿。"""
        self._env(FAKE_KEY)
        with self.assertRaises(ds_credential.CredentialError) as ctx:
            ds_credential.save(home=self.home, cfg_path=self.cfg_path,
                               provider="deepseek", key=FAKE_KEY[:-4] + "NEWK")
        self.assertIn(self.VAR, str(ctx.exception))

    def test_e9_the_launcher_really_is_env_first(self):
        """锚定前提:上面整组都建立在"启动脚本 env 优先"上。哪天它改成 file 优先,
        这一条先红,提醒下一个人回来把 E 组的理由重写,而不是让理由悄悄过期
        (同 C 组 c2 的手法)。"""
        ps1 = os.path.join(ROOT, "bin", "ds-nanobot.ps1")
        with open(ps1, encoding="utf-8") as fh:
            body = fh.read()
        self.assertIn("if (-not $env:DS_LLM_KEY)", body,
                      "启动脚本不再是 env 优先 —— E 组的理由要重写")


def _load_jsonc(path: str) -> dict:
    """出货模板是 jsonc(带注释)。复用实现那一份读法,别自己写第二个解析器。"""
    return ds_credential.load_jsonc(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
