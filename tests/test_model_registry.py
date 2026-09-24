"""判据:照 ZCode 重做模型设置 —— 后台(track opendesign-zcode-model-settings)。

    /root/.venvs/design-studio/bin/python tests/test_model_registry.py

主 agent 亲写,判据先单独 commit。

业主 09-24:「我填完api key为什么不能选择模型比如小米最新的v2，6呢」→「严格按照zcode做」。
ZCode 的做法:每家一张模型列表,内置几个 + 用户「添加模型」手填 ID;可加自定义供应商;厂商可启用/禁用;每个模型能「测试」。

4c 挑战(Grok)核实的坑,这里逐条问**真发出去的**(nanobot 自己的加载器):
- 用户加的模型、自定义供应商必须进同一张目录,否则菜单看不见、select_model 拒、起网关/合并时被清扫删(D1)。
- 自定义供应商只进额外槽、不写 api_type(nanobot 只许 providers.openai 设它,写了就拒载)、端点不许撞内置或别的自定义(D2)。
- 禁用只在菜单里藏、不动路由;正在用的那家不许禁用(D3)。
- 存 key 不改当前模型(D4;顺带收掉 kimi-glm #60)。

全假 key、零外网;「测试」按钮用本机起的假厂商(127.0.0.1)。
"""
from __future__ import annotations

import http.server
import json
import os
import subprocess
import sys
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
sys.path.insert(0, HERE)

import ds_credential  # noqa: E402
import test_per_vendor_keys as pv  # noqa: E402
from test_kimi_glm_vendors import KEYS  # noqa: E402

MERGER = os.path.join(ROOT, "bin", "ds_merge_config.py")
PROXY_KEY = "sk-oracle-proxy-0123456789abcdef0123"


def setUpModule():
    pv.setUpModule()


def tearDownModule():
    pv.tearDownModule()


class Rig(pv.Rig):
    """业主机器形状的家(出货模板 + 主槽 MiMo)。所有动作都走实现的公开入口,不直接改配置。"""

    def put_primary(self, vendor):
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider=vendor, key=KEYS[vendor])

    def add_extra(self, vendor, key=None):
        """有外壳时在设置页给第二家填 key(新页面:不换当前模型)。"""
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider=vendor,
                           key=key or KEYS[vendor], multi=True, switch=False)

    def select(self, model, provider):
        return ds_credential.select_model(self.cfg_path, model, provider=provider, home=self.home)

    def sends(self):
        """(模型, 端点, key):nanobot 真加载后下一句发给谁。"""
        snap = self.snapshot(self.gateway_env(), None)
        return snap.model, snap.provider.api_base, snap.provider.api_key

    def merge(self):
        r = subprocess.run([sys.executable, MERGER, pv.TEMPLATE, self.cfg_path],
                           capture_output=True, encoding="utf-8", timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)

    def view(self):
        return ds_credential.providers_view(self.home, self.cfg_path, multi=True)

    def group_models(self, provider):
        st = ds_credential.models_status(self.cfg_path, home=self.home)
        for g in st.get("groups") or []:
            if g["provider"] == provider:
                return [m["id"] for m in g["models"]]
        return None


MIMO_BASE = ds_credential.PROVIDERS["mimo"]["apiBase"]
KIMI_BASE = ds_credential.PROVIDERS["kimi"]["apiBase"]


class TestBuiltinCatalog(Rig):

    def test_z1_mimo_ships_with_v26(self):
        """小米服务端 /v1/models 09-24 实查已列 mimo-v2.6-pro / mimo-v2.6-flash(业主的原问题);内置目录要有。"""
        models = ds_credential.catalog(self.home)["mimo"]["models"]
        for m in ("mimo-v2.6-pro", "mimo-v2.6-flash", "mimo-v2.5", "mimo-v2.5-pro"):
            self.assertIn(m, models)
        self.put_primary("mimo")
        self.gateway_env()
        self.select("mimo-v2.6-pro", "mimo")
        self.assertEqual(self.sends(), ("mimo-v2.6-pro", MIMO_BASE, KEYS["mimo"]))


class TestAddedModels(Rig):

    def test_z2_a_model_added_on_the_primary_vendor_is_selectable_and_survives(self):
        """小米那页「添加模型」填一个新 ID ⇒ 菜单里有、选得上、发到小米;再存别家 key、起网关、合并更新都不丢。"""
        self.put_primary("mimo")
        ds_credential.add_model(self.home, self.cfg_path, "mimo", "mimo-x-next", context_window=262144)
        self.assertIn("mimo-x-next", self.group_models("mimo"))
        self.gateway_env()
        self.select("mimo-x-next", "mimo")
        self.assertEqual(self.sends(), ("mimo-x-next", MIMO_BASE, KEYS["mimo"]))
        self.assertEqual(self.snapshot(self.gateway_env(), None).context_window_tokens, 262144,
                         "上下文窗口没到 nanobot 手里")
        self.add_extra("deepseek")
        self.assertEqual(self.sends(), ("mimo-x-next", MIMO_BASE, KEYS["mimo"]))
        self.merge()
        self.assertEqual(self.sends(), ("mimo-x-next", MIMO_BASE, KEYS["mimo"]))

    def test_z3_a_model_added_on_an_extra_vendor_goes_to_that_vendor_with_its_params(self):
        """额外格 Kimi 加 kimi-k9 ⇒ 发到 Moonshot、带 Kimi 的 key、temperature≥1(Kimi 的 presetParams 照样套上)。"""
        self.put_primary("mimo")
        self.add_extra("kimi")
        self.gateway_env()
        ds_credential.add_model(self.home, self.cfg_path, "kimi", "kimi-k9")
        self.gateway_env()
        self.select("kimi-k9", "kimi")
        snap = self.snapshot(self.gateway_env(), None)
        self.assertEqual((snap.model, snap.provider.api_base, snap.provider.api_key),
                         ("kimi-k9", KIMI_BASE, KEYS["kimi"]))
        g = snap.provider.generation
        kw = snap.provider._build_kwargs([{"role": "user", "content": "hi"}], None, None,
                                         g.max_tokens, g.temperature, g.reasoning_effort, None)
        self.assertGreaterEqual(kw.get("temperature"), 1.0)

    def test_z8_builtin_and_in_use_models_cannot_be_removed(self):
        self.put_primary("mimo")
        with self.assertRaises(ds_credential.CredentialError):
            ds_credential.remove_model(self.home, self.cfg_path, "mimo", "mimo-v2.5")
        ds_credential.add_model(self.home, self.cfg_path, "mimo", "mimo-x-next")
        self.gateway_env()
        self.select("mimo-x-next", "mimo")
        with self.assertRaises(ds_credential.CredentialError, msg="删了正在用的模型"):
            ds_credential.remove_model(self.home, self.cfg_path, "mimo", "mimo-x-next")
        self.select("mimo-v2.5", "mimo")
        ds_credential.remove_model(self.home, self.cfg_path, "mimo", "mimo-x-next")
        self.gateway_env()
        self.assertNotIn("mimo-x-next", self.group_models("mimo"))
        self.assertFalse(any(p.get("model") == "mimo-x-next" for p in self.cfg()["model_presets"].values()),
                         "删掉的模型预设还留在配置里")

    def test_z12_context_window_edit_reaches_the_preset(self):
        self.put_primary("mimo")
        self.gateway_env()
        self.select("mimo-v2.5", "mimo")
        ds_credential.set_context_window(self.home, self.cfg_path, "mimo", "mimo-v2.5", 500000)
        self.assertEqual(self.snapshot(self.gateway_env(), None).context_window_tokens, 500000,
                         "改的上下文窗口没到 nanobot 手里")


class TestCustomProvider(Rig):

    def add_proxy(self, base="https://proxy.example/v1", models=("gpt-x",)):
        return ds_credential.add_custom_provider(self.home, self.cfg_path, label="我的中转", api_base=base,
                                                 models=list(models), key=PROXY_KEY, multi=True)

    def test_z4_a_custom_provider_is_selectable_routes_to_its_endpoint_and_survives(self):
        self.put_primary("mimo")
        pid = self.add_proxy()
        self.gateway_env()
        self.assertIn("gpt-x", self.group_models(pid))
        self.select("gpt-x", pid)
        self.assertEqual(self.sends(), ("gpt-x", "https://proxy.example/v1", PROXY_KEY))
        self.assertEqual(self.sends(), ("gpt-x", "https://proxy.example/v1", PROXY_KEY), "第二次起网关丢了")
        self.merge()
        self.assertEqual(self.sends(), ("gpt-x", "https://proxy.example/v1", PROXY_KEY), "合并更新后丢了")
        self.assertNotIn("api_type", json.dumps(self.cfg()["providers"]), "写了 api_type:nanobot 会拒载")
        self.assertNotIn(pid, [p["id"] for p in self.view()["providers"] if p["kind"] == "builtin"])

    def test_z5_a_custom_endpoint_may_not_collide_or_exist_without_a_shell(self):
        self.put_primary("mimo")
        for base in (ds_credential.PROVIDERS["deepseek"]["apiBase"], MIMO_BASE + "/"):
            with self.subTest(base=base), self.assertRaises(ds_credential.CredentialError):
                self.add_proxy(base=base)
        self.add_proxy()
        with self.assertRaises(ds_credential.CredentialError, msg="两个自定义供应商同一个端点"):
            self.add_proxy(base="https://proxy.example/v1/")
        with self.assertRaises(ds_credential.CredentialError, msg="没外壳也让加自定义供应商"):
            ds_credential.add_custom_provider(self.home, self.cfg_path, label="x", api_base="https://other.example/v1",
                                              models=["m"], key=PROXY_KEY, multi=False)

    def test_z4b_removing_a_custom_provider(self):
        self.put_primary("mimo")
        pid = self.add_proxy()
        self.gateway_env()
        self.select("gpt-x", pid)
        with self.assertRaises(ds_credential.CredentialError, msg="删了正在用的供应商"):
            ds_credential.remove_custom_provider(self.home, self.cfg_path, pid)
        self.select("mimo-v2.5", "mimo")
        ds_credential.remove_custom_provider(self.home, self.cfg_path, pid)
        self.gateway_env()
        self.assertNotIn(pid, [p["id"] for p in self.view()["providers"]])
        self.assertFalse(any(pid in name for name in self.cfg()["providers"]), "删掉的供应商槽还在")


    def test_z13_a_custom_provider_can_be_renamed_and_repointed_without_collisions(self):
        """QA-设计 Grok Q2 → 主裁定 Q8:照 ZCode,自定义供应商能改名、改 Base URL;改地址同样查撞车;key 不丢、当前模型跟着新地址。"""
        self.put_primary("mimo")
        pid = self.add_proxy()
        self.gateway_env()
        self.select("gpt-x", pid)
        ds_credential.update_custom_provider(self.home, self.cfg_path, pid, label="新名字",
                                             api_base="https://proxy2.example/v1")
        row = next(p for p in self.view()["providers"] if p["id"] == pid)
        self.assertEqual((row["label"], row["apiBase"]), ("新名字", "https://proxy2.example/v1"))
        self.assertEqual(self.sends(), ("gpt-x", "https://proxy2.example/v1", PROXY_KEY))
        for base in (ds_credential.PROVIDERS["kimi"]["apiBase"], "ftp://x", ""):
            with self.subTest(base=base), self.assertRaises(ds_credential.CredentialError):
                ds_credential.update_custom_provider(self.home, self.cfg_path, pid, api_base=base)
        with self.assertRaises(ds_credential.CredentialError):
            ds_credential.update_custom_provider(self.home, self.cfg_path, pid, label="  ")


class TestEnableAndKeys(Rig):

    def test_z6_disable_hides_from_the_menu_without_touching_routing(self):
        self.put_primary("mimo")
        self.add_extra("kimi")
        self.gateway_env()
        self.select("kimi-k3", "kimi")
        with self.assertRaises(ds_credential.CredentialError, msg="禁用了正在用的那家"):
            ds_credential.set_enabled(self.home, self.cfg_path, "kimi", False)
        self.select("mimo-v2.5", "mimo")
        ds_credential.set_enabled(self.home, self.cfg_path, "kimi", False)
        self.assertIsNone(self.group_models("kimi"), "禁用的那家还在换模型菜单里")
        with self.assertRaises(ds_credential.CredentialError):
            self.select("kimi-k3", "kimi")
        self.gateway_env()
        self.assertIn(ds_credential.extra_provider_name("kimi"), self.cfg()["providers"], "禁用动了路由(槽没了)")
        row = next(p for p in self.view()["providers"] if p["id"] == "kimi")
        self.assertFalse(row["enabled"])
        ds_credential.set_enabled(self.home, self.cfg_path, "kimi", True)
        self.assertIn("kimi-k3", self.group_models("kimi"))

    def test_z7_saving_a_key_never_changes_the_current_model(self):
        """设置页存 key 不换当前模型(ZCode);额外格同一家换 key 也不回默认(kimi-glm #60)。"""
        self.put_primary("mimo")
        self.gateway_env()
        self.select("mimo-v2.5-pro", "mimo")
        self.add_extra("kimi")
        self.assertEqual(self.sends(), ("mimo-v2.5-pro", MIMO_BASE, KEYS["mimo"]))
        self.select("kimi-k2.7-code", "kimi")
        self.add_extra("kimi", key=KEYS["kimi"] + "x")
        self.assertEqual(self.sends(), ("kimi-k2.7-code", KIMI_BASE, KEYS["kimi"] + "x"))


class TestView(Rig):

    def test_z9_the_settings_view_lists_every_vendor_with_status_and_models(self):
        self.put_primary("mimo")
        self.add_extra("kimi")
        ds_credential.add_model(self.home, self.cfg_path, "mimo", "mimo-x-next")
        self.gateway_env()
        self.select("mimo-v2.5-pro", "mimo")
        v = self.view()
        ids = [p["id"] for p in v["providers"]]
        self.assertEqual(ids[:5], ["mimo", "deepseek", "kimi", "glm_plan", "glm"])
        rows = {p["id"]: p for p in v["providers"]}
        self.assertTrue(rows["mimo"]["configured"] and rows["kimi"]["configured"])
        self.assertFalse(rows["deepseek"]["configured"])
        for p in v["providers"]:
            self.assertNotIn(KEYS["mimo"], json.dumps(p), "整把 key 出现在给界面的数据里")
            self.assertNotIn(KEYS["kimi"], json.dumps(p))
        mm = {m["id"]: m for m in rows["mimo"]["models"]}
        self.assertTrue(mm["mimo-v2.5"]["builtin"])
        self.assertFalse(mm["mimo-x-next"]["builtin"])
        self.assertEqual(rows["mimo"]["apiBase"], MIMO_BASE)
        self.assertTrue(rows["kimi"]["keyUrl"].startswith("https://"))
        self.assertEqual(v["current"], {"provider": "mimo", "model": "mimo-v2.5-pro"})

    def test_z11_a_0_98_11_machine_without_a_registry_file_just_works(self):
        self.put_primary("mimo")
        self.add_extra("kimi")
        self.gateway_env()
        self.select("kimi-k2.6", "kimi")
        self.assertFalse(os.path.exists(os.path.join(self.home, ".openDesign", "models.json")))
        v = self.view()
        self.assertEqual(v["current"], {"provider": "kimi", "model": "kimi-k2.6"})
        self.assertEqual(self.sends(), ("kimi-k2.6", KIMI_BASE, KEYS["kimi"]))


class _FakeVendor(http.server.BaseHTTPRequestHandler):
    key = PROXY_KEY
    seen: list = []

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        type(self).seen.append((self.path, body.get("model")))
        if self.headers.get("Authorization") != f"Bearer {self.key}":
            return self._send(401, {"error": {"message": "invalid api key"}})
        if body.get("model") != "gpt-x":
            return self._send(404, {"error": {"message": "model not found"}})
        self._send(200, {"id": "x", "object": "chat.completion", "model": "gpt-x",
                         "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"},
                                      "finish_reason": "stop"}]})

    def _send(self, code, obj):
        raw = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *a):
        pass


class TestConnectivity(Rig):

    def setUp(self):
        super().setUp()
        self.srv = http.server.HTTPServer(("127.0.0.1", 0), _FakeVendor)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.shutdown)
        self.base = f"http://127.0.0.1:{self.srv.server_port}/v1"
        _FakeVendor.seen = []

    def test_z10_the_test_button_really_asks_the_vendor_and_never_echoes_the_key(self):
        self.put_primary("mimo")
        pid = ds_credential.add_custom_provider(self.home, self.cfg_path, label="假厂商", api_base=self.base,
                                                models=["gpt-x", "gpt-missing"], key=PROXY_KEY, multi=True)
        r = ds_credential.test_model(self.home, self.cfg_path, pid, "gpt-x")
        self.assertTrue(r["ok"], r)
        self.assertEqual(_FakeVendor.seen[-1], ("/v1/chat/completions", "gpt-x"))
        r = ds_credential.test_model(self.home, self.cfg_path, pid, "gpt-missing")
        self.assertFalse(r["ok"])
        self.assertIn("model not found", r["message"])
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider=pid, key="sk-oracle-wrong-000000000000",
                           multi=True, switch=False)
        r = ds_credential.test_model(self.home, self.cfg_path, pid, "gpt-x")
        self.assertFalse(r["ok"])
        self.assertNotIn("sk-oracle-wrong", json.dumps(r), "测试结果把 key 回显出来了")


if __name__ == "__main__":
    unittest.main(verbosity=2)
