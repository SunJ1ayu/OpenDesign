#!/usr/bin/env python3
"""判据:加 Kimi 按量 / GLM 套餐 / GLM 按量三家 + 每家「获取 API Key」链接(track opendesign-kimi-glm-vendors)。

    /root/.venvs/design-studio/bin/python tests/test_kimi_glm_vendors.py

主 agent 亲写,判据先单独 commit。设计与前提证据在 tracks/opendesign-kimi-glm-vendors/design.md。

## 最想挡住的一件事

**两家 GLM 有同名模型(glm-5.3),切来切去串了家** —— 界面说用套餐,实际发去按量端点、扣按量的钱(或反过来)。
k4 不看配置字段,而是把配置交给 **nanobot 自己的加载器**、在外壳真会给网关的那份 env 下加载,问它
「这一句发去哪个端点、带哪把 key」。夹具沿用 tests/test_per_vendor_keys.py 的 Rig(同一个业主机器形状)。

## 它问不出什么

- 真 key 能不能连上、模型名/大小写对不对 —— 全部假 key、零外网;业主没有 Kimi/GLM 的 key(design.md 前提 2)。
- 链接在 Electron 里点了会不会打开 —— navPolicy 既有判据 + 发版单云 e2e。
"""
from __future__ import annotations

import http.client
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
sys.path.insert(0, HERE)

import ds_credential  # noqa: E402
import ds_web  # noqa: E402
import test_per_vendor_keys as pv  # noqa: E402  复用业主机器形状的 Rig 与假家

KIMI_KEY = "sk-oracle-kimi-0123456789abcdef01"
GLM_PLAN_KEY = "oracle-glmplan-0123456789abcdef.0123"
GLM_KEY = "oracle-glmapi-fedcba9876543210.9876"

# 2026-09-23 的事实(ZCode config/provider/zcode-builtin.json + 官方文档 + 无 key 探测 401);**会过期**,过期时这里会红。
EXPECTED = {
    "kimi": {"apiBase": "https://api.moonshot.cn/v1", "model": "kimi-k3",
             "models": ["kimi-k3", "kimi-k2.7-code", "kimi-k2.6"],
             "keyUrl": "https://platform.kimi.com/console/api-keys"},
    "glm_plan": {"apiBase": "https://open.bigmodel.cn/api/coding/paas/v4", "model": "glm-5.3",
                 "models": ["glm-5.3", "glm-5.3-flash"],
                 "keyUrl": "https://bigmodel.cn/coding-plan/personal/overview"},
    "glm": {"apiBase": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-5.3",
            "models": ["glm-5.3", "glm-5.3-flash", "glm-5v-turbo", "glm-5.1"],
            "keyUrl": "https://bigmodel.cn/usercenter/proj-mgmt/apikeys"},
}
KEY_URLS_OLD = {
    # MiMo:我们接的是**套餐**端点(token-plan-cn),套餐 key 只在套餐订阅页建 —— 不能照 ZCode 链平台首页
    "mimo": "https://platform.xiaomimimo.com/token-plan",
    "deepseek": "https://platform.deepseek.com/api_keys",
}


def setUpModule():
    pv.setUpModule()


def tearDownModule():
    pv.tearDownModule()


class TestTheTable(unittest.TestCase):

    def test_k1_three_new_vendors_with_their_endpoints_and_models(self):
        P = ds_credential.PROVIDERS
        for vid, want in EXPECTED.items():
            self.assertIn(vid, P, f"厂商表里没有 {vid}")
            for k in ("apiBase", "model", "models"):
                self.assertEqual(P[vid][k], want[k], f"{vid}.{k}")
            self.assertIn(P[vid]["model"], P[vid]["models"], f"{vid} 默认模型不在自己的菜单里")
            self.assertTrue(P[vid]["label"].strip(), f"{vid} 没有给界面看的名字")
        labels = [p["label"] for p in P.values()]
        self.assertEqual(len(labels), len(set(labels)), "两家同名 ⇒ 下拉里分不清")
        self.assertIn("套餐", P["glm_plan"]["label"])
        self.assertIn("按量", P["glm"]["label"])
        self.assertIn("按量", P["kimi"]["label"])
        # 老两家原样
        self.assertEqual(list(P)[:2], ["mimo", "deepseek"], "老厂商顺序变了(下拉默认选第一家)")

    def test_k2_every_vendor_links_to_where_its_key_is_made(self):
        P = ds_credential.PROVIDERS
        want = {**{k: v["keyUrl"] for k, v in EXPECTED.items()}, **KEY_URLS_OLD}
        self.assertEqual(set(P), set(want), "有厂商没核过链接")
        for vid, url in want.items():
            self.assertEqual(P[vid].get("keyUrl"), url, f"{vid} 的获取 key 链接")
            self.assertTrue(url.startswith("https://"))

    def test_k3_vendor_ids_are_safe_as_file_and_variable_names(self):
        seen = set()
        for vid in ds_credential.PROVIDERS:
            self.assertRegex(vid, r"^[a-z][a-z0-9_]*$", f"{vid} 不能安全地当文件名 keys/<id>.txt")
            var = ds_credential.extra_var_name(vid)
            self.assertRegex(var, r"^DS_LLM_KEY_[A-Z0-9_]+$")
            self.assertNotIn(var, seen, f"{vid} 的变量名和别家撞了 ⇒ 两把 key 互相覆盖")
            seen.add(var)
        bases = [ds_credential._norm_base(p["apiBase"]) for p in ds_credential.PROVIDERS.values()]
        self.assertEqual(len(bases), len(set(bases)), "两家同端点 ⇒ 按端点认主槽会认错家")


class TestRouting(pv.Rig):

    def add(self, vendor, key):
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider=vendor, key=key, multi=True)

    def test_k4_same_model_name_in_both_glm_vendors_never_crosses_over(self):
        self.have_mimo_in_primary()
        self.add("glm_plan", GLM_PLAN_KEY)
        self.add("glm", GLM_KEY)
        env = self.gateway_env()
        groups = {g["provider"]: [m["id"] for m in g["models"]]
                  for g in ds_credential.models_status(self.cfg_path)["groups"]}
        self.assertIn("glm_plan", groups)
        self.assertIn("glm", groups)
        for vendor, key in (("glm", GLM_KEY), ("glm_plan", GLM_PLAN_KEY), ("glm", GLM_KEY)):
            got = ds_credential.select_model(self.cfg_path, "glm-5.3", provider=vendor)
            self.assertEqual(got["provider"], vendor, f"选了 {vendor} 的 glm-5.3,回包说是 {got['provider']}")
            snap = self.snapshot(env, None)
            self.assertEqual(snap.provider.api_base, EXPECTED[vendor]["apiBase"],
                             f"选 {vendor} 的 glm-5.3,nanobot 发去了别的端点")
            self.assertEqual(snap.provider.api_key, key, f"选 {vendor} 的 glm-5.3,带的是别家的 key")

    def test_k4b_the_glm_choice_survives_a_gateway_restart(self):
        """🔴 自审抓到的:prepare_gateway 每次起网关都把同名预设按「最后一家」重指 ⇒
        业主选了套餐 glm-5.3,重启一次就悄悄改走按量(扣另一份钱)。三种槽位组合都要守住。"""
        combos = (
            ("mimo 主槽,两家 GLM 都在额外槽", None),
            ("GLM 套餐在主槽", "glm_plan"),
            ("GLM 按量在主槽", "glm"),
        )
        for name, primary in combos:
            with self.subTest(name):
                self.setUp()
                if primary is None:
                    self.have_mimo_in_primary()
                    self.add("glm_plan", GLM_PLAN_KEY)
                    self.add("glm", GLM_KEY)
                else:
                    ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider=primary,
                                       key=GLM_PLAN_KEY if primary == "glm_plan" else GLM_KEY)
                    other = "glm" if primary == "glm_plan" else "glm_plan"
                    self.add(other, GLM_KEY if other == "glm" else GLM_PLAN_KEY)
                self.gateway_env()
                for vendor, key in (("glm_plan", GLM_PLAN_KEY), ("glm", GLM_KEY)):
                    ds_credential.select_model(self.cfg_path, "glm-5.3", provider=vendor)
                    for _ in range(2):                       # 重启两次(每次起网关都跑 prepare_gateway)
                        env = self.gateway_env()
                    snap = self.snapshot(env, None)
                    self.assertEqual(snap.provider.api_base, EXPECTED[vendor]["apiBase"],
                                     f"[{name}] 选了 {vendor},重启后改走了别家")
                    self.assertEqual(snap.provider.api_key, key)
                    self.assertEqual(ds_credential.models_status(self.cfg_path)["provider"], vendor)

    def test_k4c_adding_the_other_glm_key_still_switches_to_it_after_restart(self):
        """k4b 的反面:存了另一家 GLM 的 key =「想换过去」(switch-to 标记),重启后要真换到**那一家**,
        不能因为同名预设归了原来那家就又落回原来那家(那样界面说已切换、实际没换)。"""
        for first, second in (("glm_plan", "glm"), ("glm", "glm_plan")):
            with self.subTest(f"{first} → {second}"):
                self.setUp()
                self.have_mimo_in_primary()
                keys = {"glm_plan": GLM_PLAN_KEY, "glm": GLM_KEY}
                self.add(first, keys[first])
                self.gateway_env()
                ds_credential.select_model(self.cfg_path, "glm-5.3", provider=first)
                self.add(second, keys[second])            # 存第二家 ⇒ 留下「想换过去」
                snap = self.snapshot(self.gateway_env(), None)
                self.assertEqual(snap.provider.api_base, EXPECTED[second]["apiBase"],
                                 f"存了 {second} 的 key、重启后还在用 {first}")
                self.assertEqual(snap.provider.api_key, keys[second])
                # 兑现一次之后,再重启不许又被拽走
                snap = self.snapshot(self.gateway_env(), None)
                self.assertEqual(snap.provider.api_base, EXPECTED[second]["apiBase"])

    def test_k7_kimi_is_always_sent_temperature_at_least_1(self):
        """🔴 自审抓到的:Kimi K2.5+ 拒收 temperature<1.0(nanobot 自带 moonshot 规格的注释与 model_overrides);
        我们走 custom / od_kimi 通道,那条覆盖不生效,预设默认 0.1 ⇒ 每句都被拒。
        问的是**真发出去的请求参数**(nanobot 的 _build_kwargs),不是配置字段。"""
        def sent_temperature(env):
            p = self.snapshot(env, None).provider
            g = p.generation
            kw = p._build_kwargs([{"role": "user", "content": "hi"}], None, None,
                                 g.max_tokens, g.temperature, g.reasoning_effort, None)
            return kw.get("temperature")

        # 额外槽:每个 Kimi 模型、重启后也一样
        self.have_mimo_in_primary()
        self.add("kimi", KIMI_KEY)
        env = self.gateway_env()
        for m in EXPECTED["kimi"]["models"]:
            ds_credential.select_model(self.cfg_path, m, provider="kimi")
            t = sent_temperature(self.gateway_env())
            self.assertIsNotNone(t)
            self.assertGreaterEqual(t, 1.0, f"{m} 发出去的 temperature={t},Kimi 会拒")
        # 换回 MiMo:别把 MiMo 也改成 1.0(它一直是 0.1)
        ds_credential.select_model(self.cfg_path, "mimo-v2.5", provider="mimo")
        self.assertEqual(sent_temperature(self.gateway_env()), 0.1)

    def test_k7b_kimi_as_the_first_and_only_vendor_too(self):
        self.add("kimi", KIMI_KEY)                  # 新装第一把 ⇒ 主槽
        for m in EXPECTED["kimi"]["models"]:
            ds_credential.select_model(self.cfg_path, m, provider="kimi")
            p = self.snapshot(self.gateway_env(), None).provider
            g = p.generation
            # 第 1 轮评审(MiMo):与 k7 同一出口 —— 问真发出去的参数,不只看 generation
            kw = p._build_kwargs([{"role": "user", "content": "hi"}], None, None,
                                 g.max_tokens, g.temperature, g.reasoning_effort, None)
            self.assertGreaterEqual(kw.get("temperature") or 0, 1.0, f"主槽 {m} 发出去的 temperature")

    def test_k8_a_model_name_two_live_vendors_share_never_switches_vendor_silently(self):
        """第 1 轮评审(MiMo)发现:POST /api/llm/model 不带 provider 时按厂商表序取第一家 ⇒
        正用 GLM 按量的 glm-5.3,来一个只带模型名的请求就被改成套餐(换端点、换 key、换账单)。
        要么留在现在那家,要么拒绝并要求指明厂商 —— 不许悄悄换家。"""
        self.have_mimo_in_primary()
        self.add("glm_plan", GLM_PLAN_KEY)
        self.add("glm", GLM_KEY)
        env = self.gateway_env()
        for current, key in (("glm", GLM_KEY), ("glm_plan", GLM_PLAN_KEY)):
            ds_credential.select_model(self.cfg_path, "glm-5.3", provider=current)
            got = ds_credential.select_model(self.cfg_path, "glm-5.3")          # 不带厂商
            self.assertEqual(got["provider"], current, f"正用 {current},只带模型名就被换到 {got['provider']}")
            snap = self.snapshot(env, None)
            self.assertEqual(snap.provider.api_base, EXPECTED[current]["apiBase"])
            self.assertEqual(snap.provider.api_key, key)
        # 当前在 MiMo、两家 GLM 都能用 glm-5.3-flash 且谁都还没用过它 ⇒ 分不清就拒绝,配置不动
        ds_credential.select_model(self.cfg_path, "mimo-v2.5", provider="mimo")
        cfg = self.cfg()
        # 第 4 轮(两家):改设计后预设名是 `glm-5.3-flash@<厂商>`,只 pop 裸名是空操作 ⇒ 前提「谁都还没用过」没造出来
        for v in ("glm_plan", "glm"):
            self.assertIsNotNone(cfg["model_presets"].pop(f"glm-5.3-flash@{v}", None), f"{v} 的 flash 预设不在")
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
        before = self.cfg_bytes()
        with self.assertRaises(ds_credential.CredentialError) as cm:
            ds_credential.select_model(self.cfg_path, "glm-5.3-flash")
        self.assertIn("哪一家", str(cm.exception), "拒绝时要说清是缺了厂商")
        self.assertEqual(self.cfg_bytes(), before)

    def test_k8b_without_a_vendor_the_current_vendor_wins(self):
        """第 2 轮评审(Grok)复现:正用 GLM 按量 glm-5.3,只带模型名要 glm-5.3-flash,
        而 flash 的预设还归套餐 ⇒ 被换到套餐。老菜单只列**当前这家**的目录,不带厂商的请求意思就是「这家里的那个模型」。"""
        self.have_mimo_in_primary()
        self.add("glm_plan", GLM_PLAN_KEY)
        self.add("glm", GLM_KEY)                    # 存完 ⇒「想换过去」标记指向按量
        env = self.gateway_env()                    # 兑现:glm-5.3 归按量,glm-5.3-flash 仍归套餐
        ds_credential.select_model(self.cfg_path, "glm-5.3", provider="glm")
        got = ds_credential.select_model(self.cfg_path, "glm-5.3-flash")
        self.assertEqual(got["provider"], "glm", f"正用按量,只带模型名就被换到 {got['provider']}")
        snap = self.snapshot(env, None)
        self.assertEqual(snap.provider.api_base, EXPECTED["glm"]["apiBase"])
        self.assertEqual(snap.provider.api_key, GLM_KEY)

    def test_k9_losing_one_glm_key_falls_back_to_the_default_not_to_the_other_glm(self):
        """第 2 轮评审(Grok):正用套餐 glm-5.3,套餐的 key 文件没了再起网关 ⇒ 预设被删又被按量重建,
        当前模型悄悄改扣按量的钱。应与 DeepSeek 丢 key 一样回落主槽默认,让业主自己再选。"""
        self.have_mimo_in_primary()
        self.add("glm_plan", GLM_PLAN_KEY)
        self.add("glm", GLM_KEY)
        self.gateway_env()
        ds_credential.select_model(self.cfg_path, "glm-5.3", provider="glm_plan")
        os.remove(os.path.join(self.keys_dir, "glm_plan.txt"))
        snap = self.snapshot(self.gateway_env(), None)
        self.assertNotEqual(snap.provider.api_base, EXPECTED["glm"]["apiBase"],
                            "套餐 key 没了,当前模型被悄悄改走按量")
        self.assertEqual(snap.provider.api_key, pv.MIMO_KEY, "应回落主槽(MiMo)的默认模型")
        # 按量那家照旧能手选
        ds_credential.select_model(self.cfg_path, "glm-5.3", provider="glm")
        snap = self.snapshot(self.gateway_env(), None)
        self.assertEqual(snap.provider.api_key, GLM_KEY)

    def test_k9b_losing_a_glm_key_symmetric_and_bystander_positions(self):
        """第 3 轮评审(MiMo)补的对位:
        ① 主槽就是另一家 GLM:丢了额外那家的 key ⇒ 按「回落主槽默认」的既定规矩落到主槽那家(和 DeepSeek 丢 key 回 MiMo 同一条),
           且真发出去的端点/key 就是主槽那家 —— 不许出现「名字说主槽、预设指着别处」;
        ② 人在 Kimi,丢一家 GLM 的 key ⇒ 留在 Kimi,不许被踢走。"""
        with self.subTest("主槽=GLM 按量,丢套餐"):
            self.setUp()
            ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="glm", key=GLM_KEY)
            self.add("glm_plan", GLM_PLAN_KEY)
            self.gateway_env()
            ds_credential.select_model(self.cfg_path, "glm-5.3", provider="glm_plan")
            os.remove(os.path.join(self.keys_dir, "glm_plan.txt"))
            snap = self.snapshot(self.gateway_env(), None)
            self.assertEqual(snap.provider.api_base, EXPECTED["glm"]["apiBase"])
            self.assertEqual(snap.provider.api_key, GLM_KEY)
            self.assertEqual(ds_credential.models_status(self.cfg_path)["provider"], "glm",
                             "菜单打勾要和真发的是同一家")
        with self.subTest("人在 Kimi,丢一家 GLM"):
            self.setUp()
            self.have_mimo_in_primary()
            self.add("glm_plan", GLM_PLAN_KEY)
            self.add("glm", GLM_KEY)
            self.add("kimi", KIMI_KEY)
            self.gateway_env()
            ds_credential.select_model(self.cfg_path, "kimi-k2.6", provider="kimi")
            os.remove(os.path.join(self.keys_dir, "glm_plan.txt"))
            snap = self.snapshot(self.gateway_env(), None)
            self.assertEqual(snap.provider.api_key, KIMI_KEY, "丢的是 GLM 的 key,人却被踢出了 Kimi")

    def test_k10_each_glm_vendor_keeps_its_own_preset_for_a_shared_model_name(self):
        """根治(第 3 轮后回头改设计):同名模型按厂商各存一份预设,谁也改不动谁的 ——
        两家都选过 glm-5.3 之后,任一家的那份预设都还指着它自己。"""
        self.have_mimo_in_primary()
        self.add("glm_plan", GLM_PLAN_KEY)
        self.add("glm", GLM_KEY)
        self.gateway_env()
        ds_credential.select_model(self.cfg_path, "glm-5.3", provider="glm_plan")
        ds_credential.select_model(self.cfg_path, "glm-5.3", provider="glm")
        self.gateway_env()
        owners = {}
        for name, p in self.cfg()["model_presets"].items():
            if isinstance(p, dict) and p.get("model") == "glm-5.3":
                owners.setdefault(p.get("provider"), []).append(name)
        self.assertEqual(set(owners), {"od_glm_plan", "od_glm"},
                         f"glm-5.3 应该两家各一份预设,实际 {owners}")
        for prov, names in owners.items():
            self.assertEqual(len(names), 1, f"{prov} 有多份 glm-5.3 预设:{names}")
        # 第 4 轮(两家):不只数 provider 字段 —— 咬名字,并按名字交给 nanobot 加载,各发各家
        presets = self.cfg()["model_presets"]
        self.assertNotIn("glm-5.3", presets, "出现了不带厂商的裸名 glm-5.3(第三份,谁都能改它的归属)")
        env = self.gateway_env()
        for vendor, key in (("glm_plan", GLM_PLAN_KEY), ("glm", GLM_KEY)):
            snap = self.snapshot(env, f"glm-5.3@{vendor}")
            self.assertEqual((snap.provider.api_base, snap.provider.api_key), (EXPECTED[vendor]["apiBase"], key),
                             f"glm-5.3@{vendor} 没发去 {vendor}")
        # 不重名的模型预设名照旧就是模型名(老配置、nanobot /model 列表不变)
        presets = self.cfg()["model_presets"]
        self.assertIn("mimo-v2.5", presets)
        self.assertIn("glm-5v-turbo", presets)

    def test_k5_kimi_as_a_second_vendor_end_to_end(self):
        self.have_mimo_in_primary()
        self.add("kimi", KIMI_KEY)
        self.assertEqual(open(os.path.join(self.keys_dir, "kimi.txt")).read().strip(), KIMI_KEY)
        env = self.gateway_env()
        got = ds_credential.select_model(self.cfg_path, "kimi-k2.6", provider="kimi")
        self.assertEqual(got["provider"], "kimi")
        snap = self.snapshot(env, None)
        self.assertEqual(snap.provider.api_base, EXPECTED["kimi"]["apiBase"])
        self.assertEqual(snap.provider.api_key, KIMI_KEY)
        # key 原文只在它自己的文件里(外加网关 env,那不落盘)
        self.assertEqual(pv.sweep(self.home, KIMI_KEY), [os.path.join(".openDesign", "keys", "kimi.txt")])

    def test_k5b_kimi_on_a_fresh_install_goes_into_the_primary_slot(self):
        self.add("kimi", KIMI_KEY)
        st = ds_credential.status(self.home, self.cfg_path)
        self.assertEqual(st["provider"], "kimi")
        self.assertEqual(self.cfg()["providers"]["custom"]["apiBase"], EXPECTED["kimi"]["apiBase"])


KEYS = {"mimo": pv.MIMO_KEY, "deepseek": pv.DS_KEY, "kimi": KIMI_KEY, "glm_plan": GLM_PLAN_KEY, "glm": GLM_KEY}


def owner_of(name, preset):
    """判据自己认「这份预设属于哪家」,不借实现的 helper:名字带 `@厂商` ⇒ 那家;
    否则模型只在一家目录里 ⇒ 那家;认不出(业主手写的)⇒ None,不管它。"""
    if "@" in name and name.rsplit("@", 1)[1] in ds_credential.PROVIDERS:
        return name.rsplit("@", 1)[1]
    hits = [v for v, p in ds_credential.PROVIDERS.items() if preset.get("model") in p["models"]]
    return hits[0] if len(hits) == 1 else None


class TestEveryPresetGoesToItsOwner(pv.Rig):
    """第 4 轮两家 BLOCK 的根因:主槽 `custom` 的厂商会变,指向它的预设却不带厂商 ⇒ 主槽换人后,
    旧主槽留下的预设(`glm-5.3@glm_plan`、`mimo-v2.5`)跟着发到新主槽。前五个补丁和那个洞都是它的症状。

    k11 不追某一条序列,而是问一条**不变量**:存完 key / 起完网关之后,配置里**每一份认得出主人的预设**,
    交给 nanobot 按名字加载,都发到它主人的端点、带它主人的 key;主人手里没 key ⇒ 这份预设就不该还在。
    (`/model <名字>` 和 agent 的 model_preset 工具都能按名字选任何一份,所以每一份都要问,不只问当前那份。)"""

    def add(self, vendor, key):
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider=vendor, key=key, multi=True)

    def plain_env(self):
        """没外壳的启动器给网关的 env:只有主槽那一个变量,不跑 prepare_gateway。"""
        k = ds_credential.read_key(self.home)
        return pv.core.service_envs({"PATH": os.environ.get("PATH", "")}, ds_root=pv.ROOT, user_home=self.home,
                                 dsweb_port=1, ws_port=2, key=k, key_var=self.primary_var(), extra_keys={})["网关"]

    def replace_primary(self, vendor, *, shell=True):
        """业主把主槽换成另一家:有外壳时 = 主槽 key 没了再存(外壳只有这样才会写主槽);没外壳 = 直接覆盖。"""
        if shell:
            os.remove(self.key_txt)
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider=vendor, key=KEYS[vendor], multi=shell)

    def assert_every_preset_goes_to_its_owner(self, env, live, where):
        """每一份都问完再报(不在第一份上停):哪几份错、错成什么,一次看全。"""
        cfg = self.cfg()
        bad, checked = [], 0
        for name, preset in cfg["model_presets"].items():
            owner = owner_of(name, preset) if isinstance(preset, dict) else None
            if owner is None:
                continue
            checked += 1
            if owner not in live:
                bad.append(f"{name}:{owner} 已经没 key,预设还留着")
                continue
            snap = self.snapshot(env, name)
            got = (snap.provider.api_base, snap.provider.api_key)
            if got != (ds_credential.PROVIDERS[owner]["apiBase"], KEYS[owner]):
                who = [v for v, k in KEYS.items() if k == got[1]]
                bad.append(f"{name}:属于 {owner},实际发去 {got[0]}(带 {who} 的 key)")
        self.assertGreater(checked, 0, f"[{where}] 一份认得出主人的预设都没有 ⇒ 这条没问到东西")
        self.assertEqual(bad, [], f"[{where}] 这些预设发不到自己那家")
        snap = self.snapshot(env, None)
        self.assertIn(snap.provider.api_key, [KEYS[v] for v in live], f"[{where}] 当前模型发去了没 key 的厂商")

    def test_k11_after_the_primary_vendor_changes_every_preset_still_goes_to_its_owner(self):
        with self.subTest("有外壳:只有 GLM 套餐一把 → 换成 GLM 按量(第 4 轮 #15 原样)"):
            self.setUp()
            self.add("glm_plan", GLM_PLAN_KEY)
            self.gateway_env()
            self.replace_primary("glm")
            self.assert_every_preset_goes_to_its_owner(self.gateway_env(), {"glm"}, "壳 套餐→按量")
        with self.subTest("没外壳:GLM 套餐 → GLM 按量,存完就问(不起网关也不许错)"):
            self.setUp()
            ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="glm_plan", key=GLM_PLAN_KEY)
            self.replace_primary("glm", shell=False)
            self.assert_every_preset_goes_to_its_owner(self.plain_env(), {"glm"}, "无壳 套餐→按量")
        with self.subTest("没外壳:MiMo → DeepSeek(#16,已发版本就有的同根毛病)"):
            self.setUp()
            self.have_mimo_in_primary()
            self.replace_primary("deepseek", shell=False)
            self.assert_every_preset_goes_to_its_owner(self.plain_env(), {"deepseek"}, "无壳 MiMo→DeepSeek")
        with self.subTest("有外壳:主槽套餐 + 额外 Kimi → 主槽换成按量"):
            self.setUp()
            self.add("glm_plan", GLM_PLAN_KEY)
            self.add("kimi", KIMI_KEY)
            self.gateway_env()
            self.replace_primary("glm")
            self.assert_every_preset_goes_to_its_owner(self.gateway_env(), {"glm", "kimi"}, "壳 套餐+Kimi→按量")
        with self.subTest("有外壳:主槽 MiMo + 两家 GLM 额外 → 主槽换成套餐(额外那家变主槽)"):
            self.setUp()
            self.have_mimo_in_primary()
            self.add("glm_plan", GLM_PLAN_KEY)
            self.add("glm", GLM_KEY)
            self.gateway_env()
            self.replace_primary("glm_plan")
            self.assert_every_preset_goes_to_its_owner(self.gateway_env(), {"glm_plan", "glm"}, "壳 MiMo→套餐")

    def test_k11b_a_misrouted_config_already_on_disk_is_aligned_when_the_gateway_starts(self):
        """save 现在不会再造出错指的预设,但**已经在业主盘上的**会:0.98.10 及以前换 DeepSeek 后留下的 mimo-*
        (base 53560cc 亲跑核过)、手改过的配置。起网关是唯一一定会经过的地方 ⇒ 那里也要对齐,两条路都要问:
        只有主槽一把 key 的老家(快路径),和有额外槽的家。"""
        def leave_behind(presets):
            cfg = self.cfg()
            cfg["model_presets"].update(presets)
            with open(self.cfg_path, "w", encoding="utf-8") as fh:
                json.dump(cfg, fh, ensure_ascii=False, indent=2)

        with self.subTest("老家:主槽 DeepSeek,盘上留着指 custom 的 mimo-*"):
            self.setUp()
            ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="deepseek", key=pv.DS_KEY)
            leave_behind(ds_credential.load_jsonc(pv.TEMPLATE)["model_presets"])
            self.assert_every_preset_goes_to_its_owner(self.gateway_env(), {"deepseek"}, "老家 DeepSeek")
        with self.subTest("主槽 GLM 按量 + 额外 Kimi,盘上留着指 custom 的 glm-5.3@glm_plan"):
            self.setUp()
            ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="glm", key=GLM_KEY)
            self.add("kimi", KIMI_KEY)
            self.gateway_env()
            leave_behind({"glm-5.3@glm_plan": {"label": "glm-5.3", "provider": "custom", "model": "glm-5.3"}})
            self.assert_every_preset_goes_to_its_owner(self.gateway_env(), {"glm", "kimi"}, "按量+Kimi")

    def test_k12_set_model_script_keeps_the_vendor_in_the_preset_name(self):
        """第 4 轮(MiMo)#17:bin/set_model.py 一律写裸模型名 ⇒ 与 `glm-5.3-flash@glm` 并存出第三份。
        它在当前厂商目录里认得这个模型时,要写成那家的预设名,并且真发到那家。"""
        import subprocess
        self.have_mimo_in_primary()
        self.add("glm_plan", GLM_PLAN_KEY)
        self.add("glm", GLM_KEY)
        self.gateway_env()
        ds_credential.select_model(self.cfg_path, "glm-5.3", provider="glm")
        r = subprocess.run([sys.executable, os.path.join(ROOT, "bin", "set_model.py"), "glm-5.3-flash",
                            "--config", self.cfg_path], capture_output=True, encoding="utf-8", timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        cfg = self.cfg()
        self.assertEqual(cfg["agents"]["defaults"]["modelPreset"], "glm-5.3-flash@glm")
        self.assertNotIn("glm-5.3-flash", cfg["model_presets"], "set_model 造出了不带厂商的裸名")
        snap = self.snapshot(self.gateway_env(), None)
        self.assertEqual((snap.provider.api_base, snap.provider.api_key), (EXPECTED["glm"]["apiBase"], GLM_KEY))
        self.assert_every_preset_goes_to_its_owner(self.gateway_env(), {"mimo", "glm_plan", "glm"}, "set_model 后")


class TestTheWebEndpoint(unittest.TestCase):

    @contextmanager
    def serve(self):
        tmp = tempfile.mkdtemp(prefix="ds-kimi-glm-web-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        home = os.path.join(tmp, "UserData")
        os.makedirs(os.path.join(home, ".nanobot"))
        cfg = os.path.join(home, ".nanobot", "config.json")
        with open(cfg, "w", encoding="utf-8") as fh:
            json.dump({"providers": {"custom": {"apiKey": "${DS_LLM_KEY}", "apiBase": "https://旧/v1"}},
                       "model_presets": {}, "agents": {"defaults": {}}}, fh)
        old = {k: os.environ.get(k) for k in ("DS_NANOBOT_CONFIG", "HOME", "USERPROFILE")}
        os.environ.update(DS_NANOBOT_CONFIG=cfg, HOME=home, USERPROFILE=home)
        self.addCleanup(lambda: [os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
                                 for k, v in old.items()])
        ds_root = os.path.join(tmp, "ds")
        os.makedirs(os.path.join(ds_root, "projects"))
        dist = os.path.join(tmp, "dist")
        os.makedirs(dist)
        with open(os.path.join(dist, "index.html"), "w", encoding="utf-8") as fh:
            fh.write("<!doctype html>")
        httpd = ds_web.make_server(ds_root, dist, port=0, nanobot_port=1)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            yield httpd.server_address[1]
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_k6_the_card_is_told_each_vendors_key_link(self):
        with self.serve() as port:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            conn.request("GET", "/api/llm/credential", headers={"Host": f"127.0.0.1:{port}"})
            r = conn.getresponse()
            d = json.loads(r.read().decode("utf-8"))
            conn.close()
        self.assertEqual(r.status, 200)
        got = {p["id"]: p for p in d["providers"]}
        for vid, p in ds_credential.PROVIDERS.items():
            self.assertIn(vid, got, f"界面拿不到 {vid}")
            self.assertEqual(got[vid].get("keyUrl"), p["keyUrl"], f"{vid} 的链接没带给界面")


if __name__ == "__main__":
    unittest.main(verbosity=2)
