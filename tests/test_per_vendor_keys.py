#!/usr/bin/env python3
"""判据:每家厂商各存各的 key、聊天框里换厂商不重粘不重启(track opendesign-per-vendor-keys)。

    /root/.venvs/design-studio/bin/python tests/test_per_vendor_keys.py

主 agent 亲写。设计与前提证据在 tracks/opendesign-per-vendor-keys/design.md。

## 这份判据最想挡住的一件事

**界面说换了、后台没换。** 实验 p2(真网关)证实:配置里只要引用了一个网关进程 env 里
没有的变量,nanobot 每句前的重读就抛错被吞,**悄悄保留旧厂商**。所以 v4 不看"字段写没写",
而是把配置交给 **nanobot 自己的加载器**,在"外壳真会给网关的那份 env"下加载 —— 不抛、
且每个预设拿到的都是对的端点、对的 key。只有这样才问得到"配置引用 ⊆ 网关手里的 key"。

## 它问不出什么

- 外壳(ds_shell.py,Windows 专有)**有没有真的调** prepare_gateway —— 接线闸只看得见源码;
- 真实 MiMo / DeepSeek 的回答 —— 全部用假 key,零外网;
- 运行中的网关下一句真的换了 —— 那是 tests/test_per_vendor_live.py 的事。
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
sys.path.insert(0, HERE)
import _tmpreg  # noqa: E402

import ds_credential  # noqa: E402
import ds_shell_core as core  # noqa: E402

TEMPLATE = os.path.join(ROOT, "config", "nanobot.config.windows.jsonc")

MIMO_KEY = "tp-oracle-mimo-0123456789abcdef0123"
DS_KEY = "sk-oracle-deepseek-0123456789abcdef"
NEW_KEY = "sk-oracle-rotated-9876543210fedcba"

_JUDGE_HOME = None
_SAVED: dict[str, str | None] = {}


def setUpModule():
    """判据自己不许够得着这台机器的真家,也不许被开发机上设过的 DS_* 变量带偏。"""
    global _JUDGE_HOME
    _JUDGE_HOME = _tmpreg.mkdtemp("ds-per-vendor-判据假家-")
    for k in ("HOME", "USERPROFILE"):
        _SAVED[k] = os.environ.get(k)
        os.environ[k] = _JUDGE_HOME
    for k in list(os.environ):
        if k.startswith("DS_LLM_KEY") or k == "MIMO_TP_KEY":
            _SAVED[k] = os.environ.pop(k)


def tearDownModule():
    for k, v in _SAVED.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def sweep(root: str, needle: str) -> list[str]:
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


def env_refs(provider_entry) -> set[str]:
    raw = str((provider_entry or {}).get("apiKey") or "")
    return set(core._ENV_REF.findall(raw))


class Rig(unittest.TestCase):
    """一个**业主机器形状**的家:配置 = 出货 Windows 模板(不在判据里另编一份),
    主槽里已经是 MiMo、key.txt 里有 MiMo 的 key —— 即今天装好并填过一次 key 的样子。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ds-per-vendor-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = os.path.join(self.tmp, "UserData")
        os.makedirs(os.path.join(self.home, ".nanobot"), exist_ok=True)
        self.cfg_path = os.path.join(self.home, ".nanobot", "config.json")
        cfg = ds_credential.load_jsonc(TEMPLATE)
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
        self.key_txt = os.path.join(self.home, ".openDesign", "key.txt")
        self.keys_dir = os.path.join(self.home, ".openDesign", "keys")

    # ---- 夹具动作 ------------------------------------------------------------
    def have_mimo_in_primary(self):
        os.makedirs(os.path.dirname(self.key_txt), exist_ok=True)
        with open(self.key_txt, "w", encoding="utf-8") as fh:
            fh.write(MIMO_KEY + "\n")

    def cfg(self) -> dict:
        with open(self.cfg_path, encoding="utf-8") as fh:
            return json.load(fh)

    def cfg_bytes(self) -> bytes:
        with open(self.cfg_path, "rb") as fh:
            return fh.read()

    def primary_var(self) -> str:
        return ds_credential.env_var_name(self.cfg())

    def gateway_env(self) -> dict:
        """外壳真会给网关的那份 key 环境:主槽变量(读 key.txt)+ prepare_gateway 给的额外变量。"""
        extra = ds_credential.prepare_gateway(self.home, self.cfg_path)
        env = {}
        k = ds_credential.read_key(self.home)
        if k:
            env[self.primary_var()] = k
        env.update(extra)
        return env

    def extra_entries(self, cfg=None) -> dict:
        cfg = cfg if cfg is not None else self.cfg()
        return {name: p for name, p in (cfg.get("providers") or {}).items()
                if name != "custom" and isinstance(p, dict) and env_refs(p)}

    def snapshot(self, env: dict, preset: str):
        """交给 **nanobot 自己** 加载:它才是真正决定"下一句发给谁、带哪把 key"的那一方。"""
        from nanobot.providers.factory import load_provider_snapshot
        from pathlib import Path
        with mock.patch.dict(os.environ, env):
            return load_provider_snapshot(Path(self.cfg_path), preset_name=preset)


# =============================================================================
class TestSavingASecondVendor(Rig):
    """v1~v3:存第二家。**有外壳**时各存各的、配置不动;**没外壳**时与今天逐字节相同。"""

    def test_v1_with_a_shell_the_second_key_gets_its_own_file_and_the_config_is_untouched(self):
        self.have_mimo_in_primary()
        before = self.cfg_bytes()
        ds_credential.save(home=self.home, cfg_path=self.cfg_path,
                           provider="deepseek", key=DS_KEY, multi=True)
        with open(os.path.join(self.keys_dir, "deepseek.txt"), encoding="utf-8") as fh:
            body = fh.read()
        self.assertEqual(body.strip(), DS_KEY)
        self.assertEqual(len([ln for ln in body.splitlines() if ln.strip()]), 1, f"不止一行:{body!r}")
        with open(self.key_txt, encoding="utf-8") as fh:
            self.assertEqual(fh.read().strip(), MIMO_KEY, "存第二家把第一家的 key 覆盖了 —— 本单要解决的正是这件事")
        # 🔴 配置一个字节都不许动:此刻网关手里没有 DeepSeek 的 key,
        #    往配置里加引用 = 实验 p2 第四句那种"界面说换了、后台没换"。
        self.assertEqual(self.cfg_bytes(), before, "保存那一下就改了配置 —— 额外厂商的条目只许外壳在起网关时写")

    def test_v2_each_key_lives_in_exactly_its_own_file_even_after_the_gateway_is_prepared(self):
        self.have_mimo_in_primary()
        saved = ds_credential.save(home=self.home, cfg_path=self.cfg_path,
                                   provider="deepseek", key=DS_KEY, multi=True)
        ds_credential.prepare_gateway(self.home, self.cfg_path)
        self.assertEqual(sweep(self.tmp, DS_KEY),
                         [os.path.join("UserData", ".openDesign", "keys", "deepseek.txt")])
        self.assertEqual(sweep(self.tmp, MIMO_KEY),
                         [os.path.join("UserData", ".openDesign", "key.txt")])
        for name, payload in (("save", saved),
                              ("status", ds_credential.status(self.home, self.cfg_path)),
                              ("models_status", ds_credential.models_status(self.cfg_path))):
            blob = json.dumps(payload, ensure_ascii=False)
            for k in (MIMO_KEY, DS_KEY):
                self.assertNotIn(k, blob, f"{name} 的返回里带着 key 原文")
                self.assertNotIn(k[4:20], blob, f"{name} 的返回里带着 key 的一段")

    def test_v3_without_a_shell_it_behaves_exactly_like_today(self):
        """git-pull / Linux 那两种启动器只认一个变量:配置里一旦出现额外引用,网关就起不来。"""
        self.have_mimo_in_primary()
        providers_before = set(self.cfg().get("providers", {}))
        ds_credential.save(home=self.home, cfg_path=self.cfg_path,
                           provider="deepseek", key=DS_KEY, multi=False)
        with open(self.key_txt, encoding="utf-8") as fh:
            self.assertEqual(fh.read().strip(), DS_KEY, "没外壳时应该和今天一样:覆盖主槽")
        self.assertFalse(os.path.exists(self.keys_dir), "没外壳时不该出现 keys/ 目录")
        cfg = self.cfg()
        self.assertEqual(set(cfg.get("providers", {})), providers_before, "没外壳时配置里多了 provider 条目")
        self.assertEqual(cfg["providers"]["custom"]["apiBase"], ds_credential.PROVIDERS["deepseek"]["apiBase"])

    def test_v3b_save_without_the_multi_argument_keeps_todays_behaviour(self):
        """旧调用方(不带 multi)一律按今天的单把语义 —— 默认值不许变成"多把"。"""
        self.have_mimo_in_primary()
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="deepseek", key=DS_KEY)
        with open(self.key_txt, encoding="utf-8") as fh:
            self.assertEqual(fh.read().strip(), DS_KEY)
        self.assertFalse(os.path.exists(self.keys_dir))

    def test_v13_fresh_install_first_key_goes_into_the_primary_slot_like_today(self):
        """全新装机(一把 key 都没有):第一把进主槽 —— 所有老启动器都认得它。"""
        ds_credential.save(home=self.home, cfg_path=self.cfg_path,
                           provider="deepseek", key=DS_KEY, multi=True)
        with open(self.key_txt, encoding="utf-8") as fh:
            self.assertEqual(fh.read().strip(), DS_KEY)
        self.assertFalse(os.path.exists(os.path.join(self.keys_dir, "deepseek.txt")))
        self.assertEqual(self.cfg()["providers"]["custom"]["apiBase"],
                         ds_credential.PROVIDERS["deepseek"]["apiBase"])

    def test_v14_saving_the_primary_vendor_again_rotates_key_txt_only(self):
        self.have_mimo_in_primary()
        ds_credential.save(home=self.home, cfg_path=self.cfg_path,
                           provider="mimo", key=NEW_KEY, multi=True)
        with open(self.key_txt, encoding="utf-8") as fh:
            self.assertEqual(fh.read().strip(), NEW_KEY)
        self.assertFalse(os.path.exists(os.path.join(self.keys_dir, "mimo.txt")),
                         "主槽厂商的 key 被存成了第二份 —— 两份会漂")
        self.assertEqual(sweep(self.tmp, MIMO_KEY), [], "旧 key 还躺在某个文件里")

    def test_v15_saving_the_extra_vendor_again_rotates_only_its_file(self):
        self.have_mimo_in_primary()
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="deepseek", key=DS_KEY, multi=True)
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="deepseek", key=NEW_KEY, multi=True)
        self.assertEqual(sweep(self.tmp, NEW_KEY),
                         [os.path.join("UserData", ".openDesign", "keys", "deepseek.txt")])
        self.assertEqual(sweep(self.tmp, DS_KEY), [])
        with open(self.key_txt, encoding="utf-8") as fh:
            self.assertEqual(fh.read().strip(), MIMO_KEY)


# =============================================================================
class TestPreparingTheGateway(Rig):
    """v4~v6、v9、v10、v12:外壳起网关那一刻。**配置引用的每个变量,网关都拿得到** —— 由 nanobot 自己来答。"""

    def test_v4_every_variable_the_config_references_is_one_the_gateway_is_given(self):
        self.have_mimo_in_primary()
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="deepseek", key=DS_KEY, multi=True)
        extra = ds_credential.prepare_gateway(self.home, self.cfg_path)
        cfg = self.cfg()
        entries = self.extra_entries(cfg)
        self.assertEqual(len(entries), 1, f"应该恰好多出一家:{list(entries)}")
        (name, entry), = entries.items()
        self.assertEqual(entry.get("apiBase"), ds_credential.PROVIDERS["deepseek"]["apiBase"])
        refs = env_refs(entry)
        self.assertEqual(set(extra), refs, "外壳要注入的变量 与 配置里引用的变量 对不上")
        self.assertEqual({extra[v] for v in refs}, {DS_KEY})
        self.assertNotIn(DS_KEY, json.dumps(cfg, ensure_ascii=False), "key 原文进了配置")
        self.assertTrue(all(v.startswith("DS_") for v in extra),
                        f"额外变量不以 DS_ 开头 ⇒ 业主自己环境里的同名变量会被 child_env 继承下去:{list(extra)}")

        env = self.gateway_env()
        for model in ds_credential.PROVIDERS["deepseek"]["models"]:
            snap = self.snapshot(env, model)
            self.assertEqual(snap.provider.api_base, ds_credential.PROVIDERS["deepseek"]["apiBase"], model)
            self.assertEqual(snap.provider.api_key, DS_KEY, model)
        for model in ds_credential.PROVIDERS["mimo"]["models"]:
            snap = self.snapshot(env, model)
            self.assertEqual(snap.provider.api_base, ds_credential.PROVIDERS["mimo"]["apiBase"], model)
            self.assertEqual(snap.provider.api_key, MIMO_KEY, model)

    def test_v5_an_entry_whose_key_is_gone_is_removed_and_nothing_dangles(self):
        self.have_mimo_in_primary()
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="deepseek", key=DS_KEY, multi=True)
        ds_credential.prepare_gateway(self.home, self.cfg_path)
        ds_credential.select_model(self.cfg_path, "deepseek-v4-pro")
        os.remove(os.path.join(self.keys_dir, "deepseek.txt"))
        extra = ds_credential.prepare_gateway(self.home, self.cfg_path)
        self.assertEqual(extra, {})
        cfg = self.cfg()
        self.assertEqual(self.extra_entries(cfg), {}, "key 没了,条目还挂着 ⇒ 网关缺变量起不来")
        dead = {n for n, p in cfg.get("model_presets", {}).items()
                if isinstance(p, dict) and p.get("provider") not in ("custom", "auto", None)}
        self.assertEqual(dead, set(), f"还有预设指向已删的条目:{dead}")
        active = cfg["agents"]["defaults"]["modelPreset"]
        self.assertIn(active, ds_credential.PROVIDERS["mimo"]["models"], f"悬空后没回落到主槽厂商:{active}")
        snap = self.snapshot(self.gateway_env(), None)          # nanobot 自己能加载 = 网关起得来
        self.assertEqual(snap.provider.api_key, MIMO_KEY)

    def test_v6_after_saving_a_second_vendor_the_gateway_start_switches_to_it_once(self):
        """今天「填 DeepSeek 的 key 保存」的结果就是换到了 DeepSeek —— 新版不许比今天差(F7)。"""
        self.have_mimo_in_primary()
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="deepseek", key=DS_KEY, multi=True)
        ds_credential.prepare_gateway(self.home, self.cfg_path)
        active = self.cfg()["agents"]["defaults"]["modelPreset"]
        self.assertEqual(active, ds_credential.PROVIDERS["deepseek"]["model"])
        # 业主随后自己换回 MiMo;下一次起网关**不许**再把他拽回 DeepSeek
        ds_credential.select_model(self.cfg_path, "mimo-v2.5")
        ds_credential.prepare_gateway(self.home, self.cfg_path)
        self.assertEqual(self.cfg()["agents"]["defaults"]["modelPreset"], "mimo-v2.5",
                         "「想换过去」只该生效一次")

    def test_v6b_the_switch_waits_while_the_key_is_not_there(self):
        self.have_mimo_in_primary()
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="deepseek", key=DS_KEY, multi=True)
        ds_key = os.path.join(self.keys_dir, "deepseek.txt")
        os.rename(ds_key, ds_key + ".aside")
        ds_credential.prepare_gateway(self.home, self.cfg_path)
        self.assertIn(self.cfg()["agents"]["defaults"]["modelPreset"], ds_credential.PROVIDERS["mimo"]["models"],
                      "key 不在也切过去了 ⇒ 网关按 DeepSeek 预设加载会缺变量")
        os.rename(ds_key + ".aside", ds_key)
        ds_credential.prepare_gateway(self.home, self.cfg_path)
        self.assertEqual(self.cfg()["agents"]["defaults"]["modelPreset"], ds_credential.PROVIDERS["deepseek"]["model"],
                         "key 回来之后没有切过去 ⇒ 标记被提前吃掉了")

    def test_v9_owner_who_moved_the_primary_slot_to_deepseek_then_adds_mimo(self):
        """业主机器上的真实形态之一:以前在界面里换过 DeepSeek ⇒ 主槽是 DeepSeek,
        而模板带来的 mimo-* 预设仍是 provider=custom —— 会被发到 **DeepSeek 的端点**。"""
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="deepseek", key=DS_KEY, multi=False)
        self.assertEqual(self.cfg()["model_presets"]["mimo-v2.5"].get("provider"), "custom", "夹具前提不成立")
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="mimo", key=MIMO_KEY, multi=True)
        env = self.gateway_env()
        for model in ds_credential.PROVIDERS["mimo"]["models"]:
            snap = self.snapshot(env, model)
            self.assertEqual(snap.provider.api_base, ds_credential.PROVIDERS["mimo"]["apiBase"],
                             f"{model} 被发往了 {snap.provider.api_base}")
            self.assertEqual(snap.provider.api_key, MIMO_KEY, model)
        for model in ds_credential.PROVIDERS["deepseek"]["models"]:
            snap = self.snapshot(env, model)
            self.assertEqual(snap.provider.api_base, ds_credential.PROVIDERS["deepseek"]["apiBase"], model)
            self.assertEqual(snap.provider.api_key, DS_KEY, model)

    def test_v10_a_broken_config_or_unreadable_key_never_raises_and_writes_nothing(self):
        self.have_mimo_in_primary()
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="deepseek", key=DS_KEY, multi=True)
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            fh.write("{ 这不是 json")
        before = self.cfg_bytes()
        self.assertEqual(ds_credential.prepare_gateway(self.home, self.cfg_path), {})
        self.assertEqual(self.cfg_bytes(), before)
        # key 文件读不了(被一个同名目录占着)
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            json.dump(ds_credential.load_jsonc(TEMPLATE), fh)
        os.remove(os.path.join(self.keys_dir, "deepseek.txt"))
        os.makedirs(os.path.join(self.keys_dir, "deepseek.txt"))
        extra = ds_credential.prepare_gateway(self.home, self.cfg_path)
        self.assertEqual(extra, {})
        self.assertEqual(self.extra_entries(), {})

    def test_v12_an_existing_single_key_install_is_left_byte_for_byte_alone(self):
        """零迁移:只有 key.txt 的老家,起网关不许改配置(改了就是在业主机器上做迁移)。"""
        self.have_mimo_in_primary()
        before = self.cfg_bytes()
        self.assertEqual(ds_credential.prepare_gateway(self.home, self.cfg_path), {})
        self.assertEqual(self.cfg_bytes(), before)
        st = ds_credential.status(self.home, self.cfg_path)
        self.assertTrue(st["configured"])
        self.assertEqual(st["provider"], "mimo")

    def test_v12b_a_single_key_install_that_moved_to_deepseek_is_also_left_alone(self):
        """另一种老家形状:以前在界面里换成过 DeepSeek(主槽 = DeepSeek,预设只有一个)。
        没有第二家的 key ⇒ 起网关照样一个字节都不许改。"""
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="deepseek", key=DS_KEY, multi=False)
        before = self.cfg_bytes()
        self.assertEqual(ds_credential.prepare_gateway(self.home, self.cfg_path), {})
        self.assertEqual(self.cfg_bytes(), before)


# =============================================================================
class TestMenuAndSwitching(Rig):
    """v7、v8:菜单只列**活的**厂商;跨厂商切换只改当前预设、不碰 key。"""

    def groups(self):
        got = ds_credential.models_status(self.cfg_path)
        return got, {g["provider"]: [m["id"] for m in g["models"]] for g in got["groups"]}

    def test_v7_the_menu_lists_a_vendor_only_once_the_gateway_has_its_key(self):
        self.have_mimo_in_primary()
        got, groups = self.groups()
        self.assertEqual(list(groups), ["mimo"])
        for k in ("provider", "label", "current", "models"):
            self.assertIn(k, got, f"老字段 {k} 没了 ⇒ 旧前端炸")
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="deepseek", key=DS_KEY, multi=True)
        _, groups = self.groups()
        self.assertEqual(list(groups), ["mimo"], "key 刚存、网关还没拿到,菜单就列出了 DeepSeek(F1/F2)")
        ds_credential.prepare_gateway(self.home, self.cfg_path)
        got, groups = self.groups()
        self.assertEqual(set(groups), {"mimo", "deepseek"})
        self.assertEqual(groups["deepseek"], ds_credential.PROVIDERS["deepseek"]["models"])
        self.assertEqual(groups["mimo"], ds_credential.PROVIDERS["mimo"]["models"])
        self.assertEqual(got["provider"], "deepseek", "顶层 provider 应该是当前在用的那家")
        self.assertEqual(got["current"], ds_credential.PROVIDERS["deepseek"]["model"])

    def test_v8_switching_across_vendors_changes_only_the_active_preset(self):
        self.have_mimo_in_primary()
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="deepseek", key=DS_KEY, multi=True)
        ds_credential.prepare_gateway(self.home, self.cfg_path)
        ds_credential.select_model(self.cfg_path, "mimo-v2.5-pro")
        cfg_before_keys = (open(self.key_txt).read(), open(os.path.join(self.keys_dir, "deepseek.txt")).read())
        got = ds_credential.select_model(self.cfg_path, "deepseek-v4-pro")
        self.assertEqual(self.cfg()["agents"]["defaults"]["modelPreset"], "deepseek-v4-pro")
        self.assertEqual(got["provider"], "deepseek")
        snap = self.snapshot(self.gateway_env(), None)
        self.assertEqual(snap.provider.api_base, ds_credential.PROVIDERS["deepseek"]["apiBase"])
        self.assertEqual(snap.provider.api_key, DS_KEY)
        self.assertEqual((open(self.key_txt).read(), open(os.path.join(self.keys_dir, "deepseek.txt")).read()),
                         cfg_before_keys, "换模型碰了 key 文件")
        # 显式带厂商也行
        ds_credential.select_model(self.cfg_path, "mimo-v2.5", provider="mimo")
        self.assertEqual(ds_credential.models_status(self.cfg_path)["provider"], "mimo")

    def test_v8b_a_vendor_the_gateway_does_not_have_is_refused_and_nothing_changes(self):
        self.have_mimo_in_primary()
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="deepseek", key=DS_KEY, multi=True)
        before = self.cfg_bytes()
        with self.assertRaises(ds_credential.CredentialError):
            ds_credential.select_model(self.cfg_path, "deepseek-v4-flash")   # 网关还没拿到这家的 key
        with self.assertRaises(ds_credential.CredentialError):
            ds_credential.select_model(self.cfg_path, "随便什么模型")
        with self.assertRaises(ds_credential.CredentialError):
            ds_credential.select_model(self.cfg_path, "mimo-v2.5", provider="deepseek")   # 厂商和模型对不上
        self.assertEqual(self.cfg_bytes(), before)


# =============================================================================
class TestStatusForTheCard(Rig):
    """v11:卡片上每家一行的状态。"""

    def vendors(self):
        st = ds_credential.status(self.home, self.cfg_path)
        blob = json.dumps(st, ensure_ascii=False)
        for k in (MIMO_KEY, DS_KEY):
            self.assertNotIn(k, blob)
        return st, {v["id"]: v for v in st["vendors"]}

    def test_v11_each_vendor_reports_configured_live_active_and_pending(self):
        st, v = self.vendors()
        self.assertEqual(set(v), set(ds_credential.PROVIDERS))
        for row in v.values():
            for k in ("id", "label", "configured", "hint", "live", "active", "pending"):
                self.assertIn(k, row)
        self.assertFalse(v["mimo"]["configured"])
        self.assertFalse(v["deepseek"]["configured"])

        self.have_mimo_in_primary()
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="deepseek", key=DS_KEY, multi=True)
        _, v = self.vendors()
        self.assertTrue(v["mimo"]["configured"] and v["mimo"]["live"] and v["mimo"]["active"])
        self.assertTrue(v["deepseek"]["configured"], "存了 key 却报没配置")
        self.assertFalse(v["deepseek"]["live"], "网关还没拿到就报活的")
        self.assertTrue(v["deepseek"]["pending"], "应该告诉业主「已保存,后台重启后能用」")
        self.assertTrue(v["deepseek"]["hint"] and DS_KEY[-4:] in v["deepseek"]["hint"])

        ds_credential.prepare_gateway(self.home, self.cfg_path)
        _, v = self.vendors()
        self.assertTrue(v["deepseek"]["live"] and v["deepseek"]["active"])
        self.assertFalse(v["deepseek"]["pending"])
        self.assertFalse(v["mimo"]["active"])
        self.assertTrue(v["mimo"]["live"])


# =============================================================================
class TestTheKeysOnlyReachTheGateway(unittest.TestCase):
    """外壳那侧的纯逻辑:额外变量**只进网关那条腿**(与主槽 key 同一条不变量,J 组同源)。"""

    def test_extra_keys_go_to_the_gateway_leg_only(self):
        envs = core.service_envs({"PATH": "/bin", "DS_LLM_KEY_DEEPSEEK": "业主机器上残留的旧值"},
                                 ds_root="/ds", user_home="/h", dsweb_port=1, ws_port=2,
                                 key=MIMO_KEY, key_var="DS_LLM_KEY",
                                 extra_keys={"DS_LLM_KEY_DEEPSEEK": DS_KEY})
        self.assertEqual(envs["网关"]["DS_LLM_KEY_DEEPSEEK"], DS_KEY)
        self.assertEqual(envs["网关"]["DS_LLM_KEY"], MIMO_KEY)
        for k, v in envs["ds-web"].items():
            self.assertNotIn(DS_KEY, v, f"ds-web 的环境里有 DeepSeek 的 key({k})")
            self.assertNotIn(MIMO_KEY, v)

    def test_without_extra_keys_nothing_changes(self):
        a = core.service_envs({"PATH": "/bin"}, ds_root="/ds", user_home="/h", dsweb_port=1, ws_port=2,
                              key=MIMO_KEY, key_var="DS_LLM_KEY")
        b = core.service_envs({"PATH": "/bin"}, ds_root="/ds", user_home="/h", dsweb_port=1, ws_port=2,
                              key=MIMO_KEY, key_var="DS_LLM_KEY", extra_keys={})
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
