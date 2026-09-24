#!/usr/bin/env python3
"""判据:换厂商只有一扇门 + 主槽换人时不属于新厂商的预设一份不留(track opendesign-kimi-glm-vendors 第 9 轮后改设计)。

    /root/.venvs/design-studio/bin/python tests/test_vendor_one_door.py

主 agent 亲写,判据先单独 commit。

## 为什么改设计(业主 09-24:「不如直接抄 zcode」)

九轮评审找到的缝几乎都是同一个形状:主槽 `providers.custom` 的厂商会变,而指向它的预设不带厂商;
写配置的入口又有好几个(界面、老安装脚本 install.ps1 手填端点/模型、安装合并、set_model.py、起网关)。
ZCode 的做法是:厂商只在设置页里换,模型永远属于某一家。这里照它收两件事:

1. **老安装脚本不再能换端点/模型**:install.ps1 不问、ds_merge_config 不收 --api-base/--model(d1/d2)。
   第 9 轮 #31(认得出的端点 + 别家的共享模型名)和 #33(换端点沿用旧 key)的写口因此不存在。
2. **主槽端点真的换了的那一刻**,指向 custom 的预设里,凡不是新厂商的(别家的、裸共享名、机主手写的)
   一律不许再指 custom:主人另有槽就改指它,否则删掉 —— 它们绑的是旧端点,留着就发错家(d3)。
   端点没换(同一家换 key)时机主手写的一份不碰(d4,和 k14 同一条)。

## d3 为什么是穷举

第 9 轮 #32:k11/k15 只钉了 glm-5.3 一个名字、几条序列。d3 不挑序列:五家两两换(有外壳/没外壳),
主槽里事先种下**每一家每一个模型**的裸名和 `模型@厂商` 两种名字、外加机主手写的,换完问一条性质:
指向 custom 的每一份都必须是新厂商目录里的模型,名字带厂商的必须带新厂商。

## 它问不出什么

- 真 key 连不连得上(全假 key、零外网)。
- 装好的机器上已经存在、主槽**不再换人**的旧错配(那是 k11b 起网关对齐管的)。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "bin"))
sys.path.insert(0, HERE)

import ds_credential  # noqa: E402
import test_per_vendor_keys as pv  # noqa: E402
from test_kimi_glm_vendors import KEYS  # noqa: E402

VENDORS = list(ds_credential.PROVIDERS)
MERGER = os.path.join(ROOT, "bin", "ds_merge_config.py")
INSTALL_PS1 = os.path.join(ROOT, "bin", "install.ps1")
CHECK_PACKAGE = os.path.join(ROOT, "tracks", "opendesign-windows-installer", "spike", "check-package.sh")


def setUpModule():
    pv.setUpModule()


def tearDownModule():
    pv.tearDownModule()


class TestTheOldInstallerCannotChangeTheVendor(pv.Rig):

    def test_d1_install_ps1_no_longer_asks_for_an_endpoint_or_a_model(self):
        with open(INSTALL_PS1, encoding="utf-8-sig") as fh:
            body = fh.read()
        code = "\n".join(ln for ln in body.splitlines() if not ln.lstrip().startswith("#"))
        self.assertNotIn("--api-base", code, "install.ps1 还在把端点交给合并")
        self.assertNotIn("--model", code, "install.ps1 还在把模型交给合并")
        prompts = re.findall(r'Read-Host\s+"([^"]*)"', code)
        for p in prompts:
            self.assertNotRegex(p, r"(?i)base\s*url|apiBase|model", f"install.ps1 还在问:{p}")

    def merge(self, *args):
        return subprocess.run([sys.executable, MERGER, pv.TEMPLATE, self.cfg_path, *args],
                              capture_output=True, encoding="utf-8", timeout=30)

    def test_d2_the_merger_refuses_to_change_the_endpoint_or_the_model(self):
        self.have_mimo_in_primary()
        for args in (["--api-base", ds_credential.PROVIDERS["kimi"]["apiBase"], "--model", "glm-5.3"],
                     ["--api-base", "https://my-own-proxy.example/v1"],
                     ["--model", "glm-5.3"]):
            with self.subTest(args=args):
                before = self.cfg_bytes()
                baks = set(os.listdir(os.path.dirname(self.cfg_path)))
                r = self.merge(*args)
                self.assertNotEqual(r.returncode, 0, f"合并还接受 {args}:{r.stdout}")
                self.assertIn("界面", r.stderr, "拒绝时要告诉机主去界面里换")
                self.assertEqual(self.cfg_bytes(), before, "拒绝了还改了配置")
                self.assertEqual(set(os.listdir(os.path.dirname(self.cfg_path))), baks, "拒绝了还留下了备份")
        r = self.merge()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_d5_an_update_merge_adds_no_template_preset_to_somebody_elses_endpoint(self):
        """模板的预设全是 MiMo 的。主槽不是 MiMo(机主以前自配的端点)时,普通更新合并把它们加进来并指 custom
        ⇒ `/model mimo-v2.5` 发到机主那个端点。主槽是 MiMo 时照常补齐(更新的意义)。"""
        cfg = self.cfg()
        cfg["providers"]["custom"]["apiBase"] = "https://my-own-proxy.example/v1"
        cfg["model_presets"] = {"my-model": {"label": "my-model", "provider": "custom", "model": "my-model"}}
        cfg["agents"]["defaults"]["modelPreset"] = "my-model"
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
        r = self.merge()
        self.assertEqual(r.returncode, 0, r.stderr)
        got = self.cfg()
        self.assertEqual(got["providers"]["custom"]["apiBase"], "https://my-own-proxy.example/v1")
        self.assertEqual(set(got["model_presets"]), {"my-model"}, "模板的 MiMo 预设被合进了别人的端点")
        self.assertEqual(got["agents"]["defaults"]["modelPreset"], "my-model")

        self.setUp()                                  # 对照:主槽是 MiMo ⇒ 模板预设照常补齐
        cfg = self.cfg()
        tpl_presets = set(cfg["model_presets"])
        cfg["model_presets"] = {n: p for n, p in cfg["model_presets"].items() if n == "mimo-v2.5"}
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
        self.assertEqual(self.merge().returncode, 0)
        self.assertEqual(set(self.cfg()["model_presets"]), tpl_presets)

    def test_d6_the_package_check_requires_the_modules_the_merger_imports(self):
        """第 9 轮 #35:合并器 import ds_credential(它再 import ds_model),出货包少了它们安装就合并失败。"""
        with open(CHECK_PACKAGE, encoding="utf-8") as fh:
            body = fh.read()
        need = " ".join(re.findall(r'NEED="([^"]*)"', body))
        for mod in ("ds/bin/ds_credential.py", "ds/bin/ds_model.py"):
            self.assertIn(mod, need.split(), f"check-package.sh 的必需清单缺 {mod}")


class TestWhenThePrimaryVendorChanges(pv.Rig):

    def put_primary(self, vendor):
        """主槽是 vendor、key.txt 有它的 key(没外壳那条路写,与装好后第一次填 key 同形)。"""
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider=vendor, key=KEYS[vendor])

    def plant(self):
        """主槽里种下:每家每个模型的裸名 + `模型@厂商`,全指 custom;外加机主手写的两份。"""
        cfg = self.cfg()
        presets = cfg["model_presets"]
        for v, p in ds_credential.PROVIDERS.items():
            for m in p["models"]:
                presets.setdefault(m, {"label": m, "provider": "custom", "model": m})
                presets[f"{m}@{v}"] = {"label": m, "provider": "custom", "model": m}
        presets["我的模型"] = {"label": "x", "provider": "custom", "model": "my-own-model"}
        presets["没写provider"] = {"label": "x", "model": "whatever"}
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)

    def replace_primary(self, vendor, shell):
        if shell:
            os.remove(self.key_txt)                   # 有外壳时主槽只在「主槽没 key」时才会被写
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider=vendor, key=KEYS[vendor], multi=shell)

    def violations(self, new):
        cfg = self.cfg()
        bad = []
        for name, p in cfg["model_presets"].items():
            if not isinstance(p, dict) or p.get("provider") != "custom":
                continue
            if p.get("model") not in ds_credential.PROVIDERS[new]["models"]:
                bad.append(f"{name}(模型 {p.get('model')})指着主槽,而主槽现在是 {new}")
            elif "@" in name and name.rsplit("@", 1)[1] in ds_credential.PROVIDERS and name.rsplit("@", 1)[1] != new:
                bad.append(f"{name} 名字说是别家,却指着主槽 {new}")
        if cfg["model_presets"].get("没写provider") != {"label": "x", "model": "whatever"}:
            bad.append("没写 provider 的手写预设被动了(它不指我们的槽)")
        return bad

    def test_d3_after_any_primary_change_nothing_but_the_new_vendor_points_at_the_primary_slot(self):
        for shell in (False, True):
            for old in VENDORS:
                for new in VENDORS:
                    if new == old:
                        continue
                    with self.subTest(shell=shell, old=old, new=new):
                        self.setUp()
                        self.put_primary(old)
                        self.plant()
                        self.replace_primary(new, shell)
                        self.assertEqual(self.violations(new), [], "存完 key 就查(还没起网关)")
                        env = self.gateway_env() if shell else None
                        cfg = self.cfg()
                        cur = cfg["agents"]["defaults"]["modelPreset"]
                        self.assertIn(cur, cfg["model_presets"], "当前模型悬空")
                        if env is not None:
                            snap = self.snapshot(env, None)
                            self.assertEqual((snap.provider.api_base, snap.provider.api_key),
                                             (ds_credential.PROVIDERS[new]["apiBase"], KEYS[new]))
                            self.assertEqual(self.violations(new), [], "起完网关再查")

    # ── 稳态:不等端点变(方案挑战 Grok 两份夹具,evidence/20260924-design-challenge-grok.md)────────────
    def on_disk(self, presets, current):
        cfg = self.cfg()
        cfg["model_presets"].update(presets)
        cfg["agents"]["defaults"]["modelPreset"] = current
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)

    def extra_key(self, vendor):
        os.makedirs(self.keys_dir, exist_ok=True)
        with open(os.path.join(self.keys_dir, f"{vendor}.txt"), "w", encoding="utf-8") as fh:
            fh.write(KEYS[vendor] + "\n")

    def test_d7_a_bare_shared_name_already_on_disk_is_dropped_not_kept_on_the_wrong_vendor(self):
        """主槽早就是 Kimi(没人再改端点),盘上留着老安装写的裸名 glm-5.3→custom 且正在用 ⇒ 每句 glm-5.3 发到 Moonshot。
        起网关(有外壳的对齐、只有主槽的快路径)都要把它删掉、回落 Kimi 默认并带 temperature=1.0;旁边有 od_glm 也不许改指过去。"""
        for extra in (False, True):
            with self.subTest(od_glm=extra):
                self.setUp()
                self.put_primary("kimi")
                if extra:
                    self.extra_key("glm")
                self.on_disk({"glm-5.3": {"label": "glm-5.3", "provider": "custom", "model": "glm-5.3"}}, "glm-5.3")
                env = self.gateway_env()
                cfg = self.cfg()
                self.assertNotIn("glm-5.3", cfg["model_presets"], "裸名 glm-5.3 还留着")
                cur = cfg["agents"]["defaults"]["modelPreset"]
                self.assertEqual(cfg["model_presets"][cur]["model"], "kimi-k3")
                self.assertGreaterEqual(cfg["model_presets"][cur].get("temperature", 0), 1.0, "回落的 Kimi 预设没带 temperature=1.0")
                snap = self.snapshot(env, None)
                self.assertEqual((snap.provider.api_base, snap.provider.api_key),
                                 (ds_credential.PROVIDERS["kimi"]["apiBase"], KEYS["kimi"]))

    def test_d8_a_bare_shared_name_is_never_moved_to_the_other_glm(self):
        """主槽 GLM 套餐 + od_glm(按量)+ 裸名 glm-5.3→custom 正在用:改指到 od_glm = 套餐的账记到按量。只许删,回落套餐自己的 glm-5.3@glm_plan。"""
        self.put_primary("glm_plan")
        self.extra_key("glm")
        self.on_disk({"glm-5.3": {"label": "glm-5.3", "provider": "custom", "model": "glm-5.3"}}, "glm-5.3")
        env = self.gateway_env()
        cfg = self.cfg()
        self.assertNotIn("glm-5.3", cfg["model_presets"])
        self.assertEqual(cfg["agents"]["defaults"]["modelPreset"], "glm-5.3@glm_plan")
        snap = self.snapshot(env, None)
        self.assertEqual((snap.provider.api_base, snap.provider.api_key),
                         (ds_credential.PROVIDERS["glm_plan"]["apiBase"], KEYS["glm_plan"]))

    def test_d8b_a_catalog_model_under_a_name_that_is_not_ours_is_dropped_too(self):
        """名模不一致(名字 glm-5.3@glm_plan、模型 kimi-k3、指着 MiMo 主槽):发到的那家没有这个模型 ⇒ 删。
        目录外的手写模型(my-own-model)、没写 provider 的,端点不变时照旧不碰(与 k14 同一条)。"""
        self.put_primary("mimo")
        keep = {"我的@kimi": {"label": "x", "provider": "custom", "model": "my-own-model"},
                "没写provider": {"label": "x", "model": "deepseek-v4-flash"}}
        self.on_disk({"glm-5.3@glm_plan": {"label": "x", "provider": "custom", "model": "kimi-k3"}, **keep}, "mimo-v2.5")
        self.gateway_env()
        got = self.cfg()["model_presets"]
        self.assertNotIn("glm-5.3@glm_plan", got)
        for name, p in keep.items():
            self.assertEqual(got.get(name), p)

    def test_d4_same_vendor_new_key_leaves_hand_written_presets_alone(self):
        for shell in (False, True):
            with self.subTest(shell=shell):
                self.setUp()
                self.put_primary("glm")
                self.plant()
                before = self.cfg()["model_presets"]["我的模型"]
                if shell:
                    os.remove(self.key_txt)
                ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="glm",
                                   key=KEYS["glm"] + "x", multi=shell)
                self.assertEqual(self.cfg()["model_presets"].get("我的模型"), before, "同一家换 key,手写预设被动了")


if __name__ == "__main__":
    unittest.main(verbosity=2)
