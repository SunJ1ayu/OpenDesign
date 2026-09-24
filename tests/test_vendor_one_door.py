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
2. **目录里的模型只以那家的正式名字挂在那家的槽上**(稳态,save / 起网关 / 合并都守;第 10 轮起):
   我们起的名字按主人归位;名字不正式但那格厂商有这个模型 ⇒ 原地改成正式名(模型不变、当前模型跟着改名,d7b);
   那格厂商没有这个模型 ⇒ 删(不改指到别格,d8)。主槽端点真的换了 ⇒ 绑在旧端点上的手写预设也删(d3);
   端点没换(同一家换 key)时手写预设和当前模型都不动(d4/d4b)。

## d3 为什么是穷举

第 9 轮 #32:k11/k15 只钉了 glm-5.3 一个名字、几条序列。d3 不挑序列:五家两两换(有外壳/没外壳),
主槽里事先种下**每一家每一个模型**的裸名和 `模型@厂商` 两种名字、外加机主手写的,换完问一条性质:
指向我们槽位的每一份都必须是那格厂商目录里的模型、且是那家的正式名(第 10 轮起也问 od_*、也有额外槽在场的组合)。

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

    def test_d5b_a_self_configured_endpoint_without_presets_gets_no_mimo_brain(self):
        """第 10 轮(MiMo #36):纯 onboard 形态(自配端点、没有 model_presets、只有 agents.defaults.model)
        合并后不许多出 MiMo 预设、也不许设 modelPreset(它压过 model 字段 ⇒ MiMo 模型名发到机主端点,聊天连不上)。
        悬空的 modelPreset 删掉,不无中生有。"""
        for presets, current in ((None, None), ({}, "gone-model")):
            with self.subTest(presets=presets, current=current):
                self.setUp()
                cfg = {"providers": {"custom": {"apiKey": "${DS_LLM_KEY}", "apiBase": "https://corp-proxy.example/v1"}},
                       "agents": {"defaults": {"model": "corp/llama-3"}}}
                if presets is not None:
                    cfg["model_presets"] = presets
                if current:
                    cfg["agents"]["defaults"]["modelPreset"] = current
                with open(self.cfg_path, "w", encoding="utf-8") as fh:
                    json.dump(cfg, fh)
                r = self.merge()
                self.assertEqual(r.returncode, 0, r.stderr)
                got = self.cfg()
                self.assertEqual(got.get("model_presets") or {}, {}, "MiMo 模板预设合进了机主的端点")
                self.assertNotIn("modelPreset", got["agents"]["defaults"], "modelPreset 会压过机主的 model 字段")
                self.assertEqual(got["agents"]["defaults"]["model"], "corp/llama-3")
                self.assertEqual(got["providers"]["custom"]["apiBase"], "https://corp-proxy.example/v1")

    def test_d9_an_update_merge_aligns_what_is_already_on_disk(self):
        """第 10 轮(DeepSeek #39):老 git-pull 形态不跑起网关对齐,更新合并是唯一一次清扫 —— 它也要守同一条不变量。"""
        for primary, leftovers, current, want_model in (
                ("deepseek", {"mimo-v2.5": "mimo-v2.5", "mimo-v2.5-pro": "mimo-v2.5-pro"}, "mimo-v2.5", "deepseek-v4-flash"),
                ("kimi", {"glm-5.3": "glm-5.3"}, "glm-5.3", "kimi-k3"),
                ("glm_plan", {"glm-5.3-flash": "glm-5.3-flash"}, "glm-5.3-flash", "glm-5.3-flash")):
            with self.subTest(primary=primary):
                self.setUp()
                ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider=primary, key=KEYS[primary])
                cfg = self.cfg()
                for n, m in leftovers.items():
                    cfg["model_presets"][n] = {"label": n, "provider": "custom", "model": m}
                cfg["agents"]["defaults"]["modelPreset"] = current
                with open(self.cfg_path, "w", encoding="utf-8") as fh:
                    json.dump(cfg, fh, ensure_ascii=False, indent=2)
                r = self.merge()
                self.assertEqual(r.returncode, 0, r.stderr)
                got = self.cfg()
                cat = ds_credential.PROVIDERS[primary]["models"]
                for n, p in got["model_presets"].items():
                    if isinstance(p, dict) and p.get("provider") == "custom":
                        self.assertIn(p.get("model"), cat, f"{n} 的模型不属于主槽 {primary}")
                        self.assertEqual(n, ds_credential.preset_name(primary, p["model"]), f"{n} 不是正式名")
                cur = got["agents"]["defaults"]["modelPreset"]
                self.assertEqual(got["model_presets"][cur]["model"], want_model)

    def test_d10_install_ps1_lets_you_skip_the_mimo_key(self):
        """第 10 轮(DeepSeek #40):没有 MiMo key 的人回车跳过,装完在界面里选厂商填 key —— 不许逼他把别家的 key 塞进 MiMo 槽。"""
        with open(INSTALL_PS1, encoding="utf-8-sig") as fh:
            code = "\n".join(ln for ln in fh.read().splitlines() if not ln.lstrip().startswith("#"))
        self.assertNotRegex(code, r'if \(-not \$key\) \{ Write-Error', "空 key 仍然终止安装")
        self.assertIn("跳过", code)

    def test_d5c_merge_never_invents_a_current_model_on_a_self_configured_endpoint(self):
        """第 11 轮(MiMo F1,#46):自配端点 + 机主有自己的预设 + 从没设过 modelPreset(他用的是 agents.defaults.model)
        ⇒ 合并不许替他挑一份当当前模型(照 ZCode:不改用户原来的选择)。"""
        cfg = {"providers": {"custom": {"apiKey": "${DS_LLM_KEY}", "apiBase": "https://corp-proxy.example/v1"}},
               "model_presets": {"my-aaa": {"label": "a", "provider": "custom", "model": "my-own-model"}},
               "agents": {"defaults": {"model": "corp/llama-3"}}}
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)
        r = self.merge()
        self.assertEqual(r.returncode, 0, r.stderr)
        got = self.cfg()
        self.assertNotIn("modelPreset", got["agents"]["defaults"], "合并替机主挑了当前模型")
        self.assertEqual(got["agents"]["defaults"]["model"], "corp/llama-3")
        self.assertEqual(set(got["model_presets"]), {"my-aaa"})

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
        """第 10 轮(MiMo #43)起问的是整条不变量,不只问指 custom 的:
        指向我们槽位(custom / od_*)的每一份,若模型在目录里 ⇒ 必须在**那一格厂商**的目录里、且名字就是那家的正式名;
        指 custom 的目录外模型(机主手写,绑旧端点)⇒ 主槽刚换过端点,不许留。"""
        cfg = self.cfg()
        catalog = {m for p in ds_credential.PROVIDERS.values() for m in p["models"]}
        bad = []
        for name, p in cfg["model_presets"].items():
            if not isinstance(p, dict):
                continue
            prov, model = p.get("provider"), p.get("model")
            if prov == "custom":
                slot_vendor = new
            elif isinstance(prov, str) and prov.startswith("od_") and prov[3:] in ds_credential.PROVIDERS:
                slot_vendor = prov[3:]
            else:
                continue
            if model not in catalog:
                if prov == "custom":
                    bad.append(f"{name}(手写 {model})还指着换过端点的主槽 {new}")
                continue
            if model not in ds_credential.PROVIDERS[slot_vendor]["models"]:
                bad.append(f"{name}(模型 {model})挂在 {prov}({slot_vendor})上,那家没有这个模型")
            elif name != ds_credential.preset_name(slot_vendor, model):
                bad.append(f"{name}(模型 {model})挂在 {prov} 上,名字不是 {slot_vendor} 的正式名")
        if cfg["model_presets"].get("没写provider") != {"label": "x", "model": "whatever"}:
            bad.append("没写 provider 的手写预设被动了(它不指我们的槽)")
        return bad

    def test_d3_after_any_primary_change_nothing_but_the_new_vendor_points_at_the_primary_slot(self):
        for shell, with_extra in ((False, False), (True, False), (True, True)):
            for old in VENDORS:
                for new in VENDORS:
                    if new == old:
                        continue
                    extra = next(v for v in VENDORS if v not in (old, new)) if with_extra else None
                    with self.subTest(shell=shell, old=old, new=new, extra=extra):
                        self.setUp()
                        self.put_primary(old)
                        if extra:
                            self.extra_key(extra)
                            self.gateway_env()          # 额外槽条目由起网关写
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

    def test_d7b_a_working_preset_under_an_old_name_keeps_its_model(self):
        """第 10 轮(MiMo #37):主槽 GLM 套餐 + 老安装写的裸名 glm-5.3-flash(路由本来对、正在用)。
        清扫只许**原地改成正式名**,不许删了回落默认 glm-5.3 —— 那是把业主选好的模型换掉。名模不一致但那家有这个模型的同理。"""
        for primary, name, model, want in (("glm_plan", "glm-5.3-flash", "glm-5.3-flash", "glm-5.3-flash@glm_plan"),
                                           ("glm_plan", "glm-5.3", "glm-5.3", "glm-5.3@glm_plan"),
                                           ("kimi", "kimi-k3", "kimi-k2.6", "kimi-k2.6")):
            for how in ("起网关", "同家存 key"):
                with self.subTest(primary=primary, name=name, model=model, how=how):
                    self.setUp()
                    self.put_primary(primary)
                    self.on_disk({name: {"label": name, "provider": "custom", "model": model}}, name)
                    if how == "起网关":
                        env = self.gateway_env()
                    else:
                        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider=primary, key=KEYS[primary])
                        env = self.gateway_env()
                    cfg = self.cfg()
                    cur = cfg["agents"]["defaults"]["modelPreset"]
                    self.assertEqual(cur, want)
                    self.assertEqual(cfg["model_presets"][cur]["model"], model, "业主选好的模型被换了")
                    if primary == "kimi":           # 第 11 轮(DeepSeek 1,#50):改名后也得带上那家必带的参数
                        self.assertGreaterEqual(cfg["model_presets"][cur].get("temperature", 0), 1.0,
                                                "改名后的 Kimi 预设没带 temperature=1.0 ⇒ 每句被拒")
                    snap = self.snapshot(env, None)
                    self.assertEqual(snap.provider.api_base, ds_credential.PROVIDERS[primary]["apiBase"])

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

    def test_d12_losing_an_extra_key_leaves_nothing_pointing_at_the_gone_slot(self):
        """清理后补的(主裁自查):额外格 od_kimi 的 key 没了、条目删了,指着它的**任何**预设(我们起的、改名能救的、手写的)都得跟着走 ——
        改名只在格还在时才有意义;留一份指向不存在的格,nanobot 按名字加载就是悬空。"""
        self.put_primary("mimo")
        self.extra_key("kimi")
        self.gateway_env()
        self.on_disk({"my-kimi": {"label": "x", "provider": "od_kimi", "model": "kimi-k2.6"},
                      "my-own": {"label": "x", "provider": "od_kimi", "model": "my-own-model"}}, "my-kimi")
        os.remove(os.path.join(self.keys_dir, "kimi.txt"))
        env = self.gateway_env()
        cfg = self.cfg()
        self.assertNotIn("od_kimi", cfg["providers"])
        left = {n: p["provider"] for n, p in cfg["model_presets"].items()
                if isinstance(p, dict) and str(p.get("provider", "")).startswith("od_")}
        self.assertEqual(left, {}, "还有预设指着已经没有的格")
        for name in cfg["model_presets"]:
            self.snapshot(env, name)                  # 每一份都要能被 nanobot 按名字加载
        self.assertEqual(self.snapshot(env, None).provider.api_key, KEYS["mimo"])

    def test_d4c_a_vendor_moving_into_the_primary_slot_keeps_the_model_you_picked(self):
        """第 11 轮(DeepSeek 3/5,#52):主槽 MiMo、额外格 GLM 按量、正用 glm-5.1;主槽 key 没了、再存一次 GLM 的 key
        (GLM 挪进主槽)⇒ 当前还是 glm-5.1、发到按量。换到**别家**时才回到那家默认(对照)。"""
        self.put_primary("mimo")
        self.extra_key("glm")
        self.gateway_env()
        ds_credential.select_model(self.cfg_path, "glm-5.1", provider="glm")
        os.remove(self.key_txt)
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="glm", key=KEYS["glm"], multi=True)
        cfg = self.cfg()
        self.assertEqual(cfg["model_presets"][cfg["agents"]["defaults"]["modelPreset"]]["model"], "glm-5.1")
        snap = self.snapshot(self.gateway_env(), None)
        self.assertEqual(snap.provider.api_base, ds_credential.PROVIDERS["glm"]["apiBase"])

        self.setUp()                                  # 对照:正用 mimo-v2.5-pro,换成 DeepSeek ⇒ DeepSeek 默认
        self.put_primary("mimo")
        ds_credential.select_model(self.cfg_path, "mimo-v2.5-pro")
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="deepseek", key=KEYS["deepseek"])
        self.assertEqual(self.cfg()["agents"]["defaults"]["modelPreset"], "deepseek-v4-flash")

    def test_d4d_same_vendor_new_key_leaves_a_model_field_brain_alone(self):
        """第 11 轮(MiMo F2,#47):当前模型写在 agents.defaults.model(没有 modelPreset)⇒ 同一家换 key 不许替他设 modelPreset。"""
        self.put_primary("glm")
        cfg = self.cfg()
        cfg["agents"]["defaults"].pop("modelPreset", None)
        cfg["agents"]["defaults"]["model"] = "glm-5.1"
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
        ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="glm", key=KEYS["glm"] + "x")
        got = self.cfg()["agents"]["defaults"]
        self.assertNotIn("modelPreset", got, "同一家换 key,替他换了当前模型")
        self.assertEqual(got["model"], "glm-5.1")

    def test_d12b_losing_an_extra_key_on_a_self_configured_primary_still_starts(self):
        """第 11 轮(MiMo F3,#48):主槽是机主自配端点、正用额外格 Kimi;Kimi 的 key 没了 ⇒ modelPreset 不许悬空(网关会拒绝加载),
        回到他原来的 agents.defaults.model。"""
        self.have_mimo_in_primary()
        cfg = self.cfg()
        cfg["providers"]["custom"]["apiBase"] = "https://corp-proxy.example/v1"
        cfg["agents"]["defaults"]["model"] = "corp/llama-3"
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
        self.extra_key("kimi")
        self.gateway_env()
        ds_credential.select_model(self.cfg_path, "kimi-k3", provider="kimi")
        os.remove(os.path.join(self.keys_dir, "kimi.txt"))
        env = self.gateway_env()
        d = self.cfg()["agents"]["defaults"]
        self.assertNotIn("modelPreset", d, "modelPreset 悬空或被随便挑了一份")
        self.assertEqual(d["model"], "corp/llama-3")
        self.snapshot(env, None)                      # nanobot 加载得起来

    def test_d13_losing_the_current_vendors_key_falls_back_to_the_primary_not_to_whatever_is_first(self):
        """第 11 轮(DeepSeek 2,#51):额外格 Kimi 的预设排在最前,正用 GLM 按量;GLM 的 key 没了 ⇒ 回落**主槽** MiMo 默认,
        不许落到排在最前的 Kimi(换家扣钱)。"""
        self.put_primary("mimo")
        self.extra_key("kimi")
        self.extra_key("glm")
        self.gateway_env()
        ds_credential.select_model(self.cfg_path, "glm-5.1", provider="glm")
        cfg = self.cfg()
        kimi_first = {n: p for n, p in cfg["model_presets"].items() if p.get("provider") == "od_kimi"}
        kimi_first.update({n: p for n, p in cfg["model_presets"].items() if n not in kimi_first and n != "mimo-v2.5"})
        kimi_first["mimo-v2.5"] = cfg["model_presets"]["mimo-v2.5"]
        cfg["model_presets"] = kimi_first
        with open(self.cfg_path, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
        os.remove(os.path.join(self.keys_dir, "glm.txt"))
        env = self.gateway_env()
        self.assertEqual(self.cfg()["agents"]["defaults"]["modelPreset"], "mimo-v2.5")
        self.assertEqual(self.snapshot(env, None).provider.api_key, KEYS["mimo"])

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

    def test_d4b_same_vendor_new_key_keeps_the_current_model(self):
        """第 10 轮(MiMo #38):选好 glm-5.1 之后再存一次 GLM 的 key(换 key)⇒ 当前模型不许回到默认 glm-5.3。"""
        for shell in (False, True):
            with self.subTest(shell=shell):
                self.setUp()
                self.put_primary("glm")
                ds_credential.select_model(self.cfg_path, "glm-5.1", provider="glm")
                if shell:
                    os.remove(self.key_txt)
                ds_credential.save(home=self.home, cfg_path=self.cfg_path, provider="glm",
                                   key=KEYS["glm"] + "x", multi=shell)
                self.assertEqual(self.cfg()["agents"]["defaults"]["modelPreset"], "glm-5.1")

    def test_d11_picking_a_model_fixes_a_preset_whose_model_field_was_wrong(self):
        """第 10 轮(MiMo 残留 #44):正式名 glm-5.1 的预设里 model 被手改成 glm-5.3,界面选 glm-5.1 ⇒ 发出去的必须是 glm-5.1。"""
        self.put_primary("glm")
        self.on_disk({"glm-5.1": {"label": "glm-5.1", "provider": "custom", "model": "glm-5.3"}}, "glm-5.3@glm")
        ds_credential.select_model(self.cfg_path, "glm-5.1", provider="glm")
        self.assertEqual(self.cfg()["model_presets"]["glm-5.1"]["model"], "glm-5.1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
