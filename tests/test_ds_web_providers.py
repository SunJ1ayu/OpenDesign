"""判据:设置页(照 ZCode)的 ds-web 接口(track opendesign-zcode-model-settings)。

    /root/.venvs/design-studio/bin/python tests/test_ds_web_providers.py

主 agent 亲写,判据先单独 commit。后台语义在 test_model_registry.py;这里问的是**界面够得着的那一层**:
路径、状态码、报错说人话、回包永不带 key、没外壳时的边界、跨站照样挡。
"""
from __future__ import annotations

import http.server
import json
import os
import sys
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "bin"))
sys.path.insert(0, HERE)

import test_ds_llm_model as lm  # noqa: E402
from test_model_registry import _FakeVendor, PROXY_KEY  # noqa: E402

KIMI_KEY = "sk-oracle-web-kimi-0123456789abcdef"
PRIMARY_KEY = "sk-oracle-model-picker-0000"


class Rig(lm.Rig):
    def setUp(self):
        super().setUp()
        self.write_cfg(lm._template_cfg())
        saved = os.environ.get("DS_SHELL_LOCK_PORT")
        self.addCleanup(lambda: os.environ.__setitem__("DS_SHELL_LOCK_PORT", saved) if saved is not None
                        else os.environ.pop("DS_SHELL_LOCK_PORT", None))
        os.environ.pop("DS_SHELL_LOCK_PORT", None)

    def with_shell(self):
        os.environ["DS_SHELL_LOCK_PORT"] = "1"       # 有外壳(没人听:重启请求回 manual,不影响保存本身)

    def call(self, method, path, body=None):
        with self.serve() as port:
            return self.req(port, method, path, body)


class TestProvidersApi(Rig):

    def test_w1_the_settings_view(self):
        st, d = self.call("GET", "/api/llm/providers")
        self.assertEqual(st, 200, d)
        ids = [p["id"] for p in d["providers"]]
        self.assertEqual(ids[:5], ["mimo", "deepseek", "kimi", "glm_plan", "glm"])
        self.assertEqual(d["current"], {"provider": "mimo", "model": "mimo-v2.5"})
        self.assertNotIn(PRIMARY_KEY, json.dumps(d, ensure_ascii=False))
        self.assertIn("mimo-v2.6-pro", [m["id"] for m in d["providers"][0]["models"]])

    def test_w2_add_a_model_then_pick_it_in_the_chat_box(self):
        st, d = self.call("POST", "/api/llm/providers/models",
                          {"op": "add", "provider": "mimo", "model": "mimo-x-next", "contextWindow": 262144})
        self.assertEqual(st, 200, d)
        row = next(p for p in d["providers"] if p["id"] == "mimo")
        added = next(m for m in row["models"] if m["id"] == "mimo-x-next")
        self.assertEqual((added["builtin"], added["contextWindow"]), (False, 262144))
        st, d = self.call("GET", "/api/llm/models")
        self.assertIn("mimo-x-next", [m["id"] for g in d["groups"] if g["provider"] == "mimo" for m in g["models"]])
        st, d = self.call("POST", "/api/llm/model", {"model": "mimo-x-next", "provider": "mimo"})
        self.assertEqual(st, 200, d)
        self.assertEqual(d["current"], "mimo-x-next")

    def test_w3_refusals_speak_human(self):
        for body in ({"op": "remove", "provider": "mimo", "model": "mimo-v2.5"},
                     {"op": "add", "provider": "mimo", "model": "bad id"},
                     {"op": "add", "provider": "nope", "model": "x"},
                     {"op": "context", "provider": "mimo", "model": "mimo-v2.5", "contextWindow": 12},
                     {"op": "explode", "provider": "mimo", "model": "mimo-v2.5"}):
            with self.subTest(body=body):
                st, d = self.call("POST", "/api/llm/providers/models", body)
                self.assertEqual(st, 400, d)
                self.assertTrue(d.get("error"), d)
        st, d = self.call("POST", "/api/llm/providers/enabled", {"provider": "mimo", "enabled": False})
        self.assertEqual(st, 400, "禁用了正在用的那家")
        self.assertIn("正在用", d["error"])

    def test_w4_no_shell_means_no_custom_provider(self):
        st, d = self.call("POST", "/api/llm/providers/custom",
                          {"op": "add", "label": "中转", "apiBase": "https://proxy.example/v1", "models": ["gpt-x"],
                           "key": PROXY_KEY})
        self.assertEqual(st, 400, d)
        st, d = self.call("GET", "/api/llm/providers")
        self.assertFalse(d["multi"])

    def test_w5_with_a_shell_a_key_save_keeps_the_model_and_asks_for_a_restart(self):
        self.with_shell()
        st, d = self.call("POST", "/api/llm/providers/key", {"provider": "kimi", "key": KIMI_KEY})
        self.assertEqual(st, 200, d)
        self.assertIn("restart", d)
        self.assertNotIn(KIMI_KEY, json.dumps(d, ensure_ascii=False))
        row = next(p for p in d["providers"] if p["id"] == "kimi")
        self.assertTrue(row["configured"])
        self.assertEqual(d["current"], {"provider": "mimo", "model": "mimo-v2.5"}, "存 key 换了当前模型")
        st, d = self.call("POST", "/api/llm/providers/custom",
                          {"op": "add", "label": "中转", "apiBase": "https://proxy.example/v1", "models": ["gpt-x"],
                           "key": PROXY_KEY})
        self.assertEqual(st, 200, d)
        self.assertNotIn(PROXY_KEY, json.dumps(d, ensure_ascii=False))
        custom = [p for p in d["providers"] if p["kind"] == "custom"]
        self.assertEqual([p["label"] for p in custom], ["中转"])
        st, d = self.call("POST", "/api/llm/providers/custom", {"op": "remove", "provider": custom[0]["id"]})
        self.assertEqual(st, 200, d)
        self.assertFalse([p for p in d["providers"] if p["kind"] == "custom"])

    def test_w6_the_test_button(self):
        self.with_shell()
        srv = http.server.HTTPServer(("127.0.0.1", 0), _FakeVendor)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        st, d = self.call("POST", "/api/llm/providers/custom",
                          {"op": "add", "label": "假厂商", "apiBase": f"http://127.0.0.1:{srv.server_port}/v1",
                           "models": ["gpt-x"], "key": PROXY_KEY})
        self.assertEqual(st, 200, d)
        pid = next(p["id"] for p in d["providers"] if p["kind"] == "custom")
        st, d = self.call("POST", "/api/llm/test", {"provider": pid, "model": "gpt-x"})
        self.assertEqual(st, 200, d)
        self.assertTrue(d["ok"], d)
        self.assertNotIn(PROXY_KEY, json.dumps(d))

    def test_w7_cross_site_writes_are_refused(self):
        with self.serve() as port:
            st, _ = self.req(port, "POST", "/api/llm/providers/models",
                             {"op": "add", "provider": "mimo", "model": "evil"},
                             headers={"Origin": "http://evil.example"})
        self.assertIn(st, (400, 403))
        st, d = self.call("GET", "/api/llm/providers")
        self.assertNotIn("evil", [m["id"] for m in d["providers"][0]["models"]])

    def test_w8_a_key_from_the_environment_is_read_only_here(self):
        """旧 key 卡片 H1 的后台一半(09-24 移植):启动脚本 env 优先 ⇒ 被环境变量供着的那一家在设置页只读、说清为什么;
        别家照常能存(额外格不受那个变量影响)。"""
        env_key = "sk-oracle-from-env-var-0123456789"
        saved = os.environ.get("DS_LLM_KEY")
        self.addCleanup(lambda: os.environ.__setitem__("DS_LLM_KEY", saved) if saved is not None
                        else os.environ.pop("DS_LLM_KEY", None))
        os.environ["DS_LLM_KEY"] = env_key
        self.with_shell()
        st, d = self.call("GET", "/api/llm/providers")
        self.assertEqual(st, 200, d)
        rows = {p["id"]: p for p in d["providers"]}
        self.assertIs(rows["mimo"]["writable"], False, "被环境变量供着的那一家要标成只读")
        self.assertTrue(rows["mimo"]["hint"] and rows["mimo"]["hint"].endswith(env_key[-4:]), "末四位要报真正生效的那把")
        self.assertIs(rows["deepseek"]["writable"], True)
        self.assertNotIn(env_key, json.dumps(d, ensure_ascii=False))
        st, d = self.call("POST", "/api/llm/providers/key", {"provider": "mimo", "key": KIMI_KEY})
        self.assertEqual(st, 400, d)
        self.assertIn("环境变量", d["error"])
        st, d = self.call("POST", "/api/llm/providers/key", {"provider": "deepseek", "key": KIMI_KEY})
        self.assertEqual(st, 200, d)


if __name__ == "__main__":
    unittest.main(verbosity=2)
