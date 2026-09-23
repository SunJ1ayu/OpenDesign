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
        cfg["model_presets"].pop("glm-5.3-flash", None)
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
        before = self.cfg_bytes()
        with self.assertRaises(ds_credential.CredentialError) as cm:
            ds_credential.select_model(self.cfg_path, "glm-5.3-flash")
        self.assertIn("哪一家", str(cm.exception), "拒绝时要说清是缺了厂商")
        self.assertEqual(self.cfg_bytes(), before)

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
