#!/usr/bin/env python3
"""判据:输入框里换模型的两个接口(track opendesign-composer-model-picker)。

编号的权威表在 `tracks/opendesign-composer-model-picker/design.md` 的 `## Test strategy (oracle)`。
**这里不重抄语义,只标 id。** 前缀 `lm`。

    /root/.venvs/design-studio/bin/python -m unittest tests.test_ds_llm_model

**这份考卷此刻应该全红** —— 接口还不存在。判据先行单独一笔。

## 它问不出什么

- 真网关里"下一句真的换了模型"(本机没有 LLM key)。`lm3` 能问到的最近一步:
  **用 nanobot 自己的读取函数**(它每条入站消息前就是这么重读配置的)读我们写出的配置,读出来的就是新模型。
"""
from __future__ import annotations

import copy
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
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))

import ds_credential  # noqa: E402
import ds_web  # noqa: E402

DEEPSEEK_BASE = ds_credential.PROVIDERS["deepseek"]["apiBase"]


def _template_cfg():
    """出货模板(MiMo 形态)—— 业主机器上配置的来源,不在考卷里另编一份。"""
    return ds_credential.load_jsonc(ds_credential.WINDOWS_TEMPLATE)


def _deepseek_cfg():
    """业主在「AI 模型 key」里换成 DeepSeek 之后的形态(与 ds_credential.save 写出的一致)。"""
    cfg = _template_cfg()
    cfg["providers"]["custom"]["apiBase"] = DEEPSEEK_BASE
    cfg["model_presets"]["deepseek-v4-flash"] = {"label": "deepseek-v4-flash", "provider": "custom",
                                                 "model": "deepseek-v4-flash", "apiBase": DEEPSEEK_BASE}
    cfg["agents"]["defaults"]["modelPreset"] = "deepseek-v4-flash"
    return cfg


class Rig(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ds-llm-model-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = os.path.join(self.tmp, "UserData")
        os.makedirs(os.path.join(self.home, ".nanobot"))
        os.makedirs(os.path.join(self.home, ".openDesign"))
        self.cfg_path = os.path.join(self.home, ".nanobot", "config.json")
        self.key_path = os.path.join(self.home, ".openDesign", "key.txt")
        with open(self.key_path, "w", encoding="utf-8") as fh:
            fh.write("sk-oracle-model-picker-0000\n")
        saved = {k: os.environ.get(k) for k in ("DS_NANOBOT_CONFIG", "HOME", "USERPROFILE")}

        def restore():
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        self.addCleanup(restore)
        os.environ["DS_NANOBOT_CONFIG"] = self.cfg_path
        os.environ["HOME"] = self.home
        os.environ["USERPROFILE"] = self.home
        self.ds_root = os.path.join(self.tmp, "ds")
        os.makedirs(os.path.join(self.ds_root, "projects"))
        self.dist = os.path.join(self.tmp, "dist")
        os.makedirs(self.dist)
        with open(os.path.join(self.dist, "index.html"), "w", encoding="utf-8") as fh:
            fh.write("<!doctype html><div>x</div>")

    def write_cfg(self, cfg):
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)

    def cfg(self):
        with open(self.cfg_path, encoding="utf-8") as fh:
            return json.load(fh)

    def raw(self, path):
        with open(path, "rb") as fh:
            return fh.read()

    @contextmanager
    def serve(self):
        httpd = ds_web.make_server(self.ds_root, self.dist, port=0, nanobot_port=1)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            yield httpd.server_address[1]
        finally:
            httpd.shutdown()
            httpd.server_close()

    def req(self, port, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        hd = {"Host": "127.0.0.1:%d" % port}
        data = None
        if body is not None:
            hd["Content-Type"] = "application/json"
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        hd.update(headers or {})
        conn.request(method, path, body=data, headers=hd)
        r = conn.getresponse()
        raw = r.read()
        conn.close()
        try:
            return r.status, (json.loads(raw.decode("utf-8")) if raw else None)
        except ValueError:
            return r.status, None

    def nanobot_reads_model(self):
        """nanobot 每条入站消息前重读配置用的就是这个函数(agent/loop.py → providers/factory.py)。"""
        from nanobot.providers.factory import load_provider_snapshot
        env_keys = sorted(set(re.findall(r"\$\{([^}]+)\}", json.dumps(self.cfg()))))
        saved = {k: os.environ.get(k) for k in env_keys}
        try:
            for k in env_keys:
                os.environ.setdefault(k, self.tmp)
            return load_provider_snapshot(Path(self.cfg_path)).model
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


class ReadTheCurrentModel(Rig):
    def test_lm1_mimo_config_lists_the_template_models(self):
        self.write_cfg(_template_cfg())
        tpl_presets = sorted(k for k, v in _template_cfg()["model_presets"].items()
                             if v.get("provider") == "custom")
        with self.serve() as port:
            st, d = self.req(port, "GET", "/api/llm/models")
        self.assertEqual(st, 200, d)
        self.assertEqual(d.get("provider"), "mimo")
        self.assertEqual(d.get("label"), ds_credential.PROVIDERS["mimo"]["label"])
        self.assertEqual(d.get("current"), "mimo-v2.5")
        self.assertEqual(sorted(m["id"] for m in d.get("models", [])), tpl_presets)
        # 09-24 业主要 v2.6(小米服务端 /v1/models 实查已列),模板加了两个(track opendesign-zcode-model-settings)
        self.assertEqual(tpl_presets, ["mimo-v2.5", "mimo-v2.5-pro", "mimo-v2.6-flash", "mimo-v2.6-pro"],
                         "前提:模板里就是这四个")
        for m in d["models"]:
            self.assertTrue(m.get("label"), "每个模型得有给人看的名字:%r" % m)


class SwitchWithinTheCurrentKey(Rig):
    def test_lm2_post_changes_only_the_active_preset(self):
        self.write_cfg(_template_cfg())
        before = self.cfg()
        key_before = self.raw(self.key_path)
        with self.serve() as port:
            st, d = self.req(port, "POST", "/api/llm/model", {"model": "mimo-v2.5-pro"})
        self.assertEqual(st, 200, d)
        self.assertEqual(d.get("current"), "mimo-v2.5-pro", "回包没说现在是哪个")
        after = self.cfg()
        self.assertEqual(after["agents"]["defaults"]["modelPreset"], "mimo-v2.5-pro")
        expected = copy.deepcopy(before)
        expected["agents"]["defaults"]["modelPreset"] = "mimo-v2.5-pro"
        self.assertEqual(after, expected, "除了 modelPreset,配置里还有别的东西被动了")
        self.assertEqual(self.raw(self.key_path), key_before, "换模型碰了 key.txt")
        with self.serve() as port:
            _st, again = self.req(port, "GET", "/api/llm/models")
        self.assertEqual(again.get("current"), "mimo-v2.5-pro", "换完再读,还是旧的 —— 没记住")

    def test_lm3_nanobot_itself_reads_the_new_model(self):
        self.write_cfg(_template_cfg())
        self.assertEqual(self.nanobot_reads_model(), "mimo-v2.5", "前提:nanobot 读出的默认模型")
        with self.serve() as port:
            st, d = self.req(port, "POST", "/api/llm/model", {"model": "mimo-v2.5-pro"})
        self.assertEqual(st, 200, d)
        self.assertEqual(self.nanobot_reads_model(), "mimo-v2.5-pro",
                         "我们写进去了,可 nanobot 自己读出来的还不是新模型 —— 下一句不会换")

    def test_lm4_ids_outside_the_current_catalog_are_refused(self):
        self.write_cfg(_template_cfg())
        before = self.raw(self.cfg_path)
        bad_bodies = ({"model": "deepseek-v4-pro"},      # 别家的(当前 key 是 MiMo)
                      {"model": "gpt-4o"},               # 随便的串
                      # 09-24 补:点名厂商的那条路(新菜单每次都带厂商)—— 这家目录里没有的一样拒;
                      # 原来只问了不带厂商的一半,删掉那道检查整套 python 判据全绿(红检 mutation-model-picker a1)
                      {"model": "gpt-4o", "provider": "mimo"}, {"model": "deepseek-v4-pro", "provider": "mimo"},
                      {"model": ""}, {"model": None}, {"model": ["mimo-v2.5-pro"]}, {})
        with self.serve() as port:
            for body in bad_bodies:
                with self.subTest(body=body):
                    st, _d = self.req(port, "POST", "/api/llm/model", body)
                    self.assertEqual(st, 400)
                    self.assertEqual(self.raw(self.cfg_path), before, "被拒的请求改动了配置")


class DeepSeekKey(Rig):
    def test_lm5_deepseek_catalog_and_switching_to_pro(self):
        self.write_cfg(_deepseek_cfg())
        with self.serve() as port:
            st, d = self.req(port, "GET", "/api/llm/models")
            self.assertEqual(st, 200, d)
            self.assertEqual(d.get("provider"), "deepseek")
            self.assertEqual(sorted(m["id"] for m in d["models"]), ["deepseek-v4-flash", "deepseek-v4-pro"])
            self.assertNotIn("mimo-v2.5", [m["id"] for m in d["models"]],
                             "配置里残留的 MiMo 预设被列成了「当前 key 能用」—— 选了会被发到 DeepSeek 的地址")
            st, d = self.req(port, "POST", "/api/llm/model", {"model": "deepseek-v4-pro"})
        self.assertEqual(st, 200, d)
        preset = self.cfg()["model_presets"].get("deepseek-v4-pro")
        self.assertIsNotNone(preset, "没建出 deepseek-v4-pro 的预设")
        self.assertEqual(preset.get("model"), "deepseek-v4-pro")
        self.assertEqual(preset.get("apiBase"), DEEPSEEK_BASE)
        self.assertEqual(self.cfg()["agents"]["defaults"]["modelPreset"], "deepseek-v4-pro")
        self.assertEqual(self.nanobot_reads_model(), "deepseek-v4-pro")


class NothingToChooseFrom(Rig):
    def test_lm6_missing_broken_or_unknown_config(self):
        cases = (("missing", None), ("broken", "{不是 json"),
                 ("unknown provider", "json"))
        for name, content in cases:
            with self.subTest(case=name):
                if os.path.exists(self.cfg_path):
                    os.remove(self.cfg_path)
                if content == "json":
                    cfg = _template_cfg()
                    cfg["providers"]["custom"]["apiBase"] = "https://某个没登记的厂商/v1"
                    self.write_cfg(cfg)
                elif content is not None:
                    with open(self.cfg_path, "w", encoding="utf-8") as fh:
                        fh.write(content)
                before = self.raw(self.cfg_path) if os.path.exists(self.cfg_path) else None
                with self.serve() as port:
                    st, d = self.req(port, "GET", "/api/llm/models")
                    self.assertEqual(st, 200, d)
                    self.assertIsNone(d.get("provider"))
                    self.assertEqual(d.get("models"), [])
                    st, _d = self.req(port, "POST", "/api/llm/model", {"model": "mimo-v2.5-pro"})
                self.assertIn(st, (400, 409))
                if before is None:
                    self.assertFalse(os.path.exists(self.cfg_path), "配置不存在,换模型却建出了一份")
                else:
                    self.assertEqual(self.raw(self.cfg_path), before)


class CrossSite(Rig):
    def test_lm7_cross_site_post_is_refused(self):
        self.write_cfg(_template_cfg())
        before = self.raw(self.cfg_path)
        with self.serve() as port:
            st, _d = self.req(port, "POST", "/api/llm/model", {"model": "mimo-v2.5-pro"},
                              headers={"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"})
        self.assertEqual(st, 403)
        self.assertEqual(self.raw(self.cfg_path), before)


class CatalogHasOneSource(unittest.TestCase):
    def test_lm8_mimo_models_come_from_the_template(self):
        """MiMo 那半的模型名从出货模板读,ds_credential 里不许再抄一份(抄了就会和模板漂)。"""
        with open(os.path.join(ROOT, "bin", "ds_credential.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("mimo-v2.5-pro", src)
        self.assertIn("models", ds_credential.PROVIDERS["mimo"], "PROVIDERS 里没有模型目录")
        tpl = sorted(k for k, v in _template_cfg()["model_presets"].items() if v.get("provider") == "custom")
        self.assertEqual(sorted(ds_credential.PROVIDERS["mimo"]["models"]), tpl)


if __name__ == "__main__":
    unittest.main()
