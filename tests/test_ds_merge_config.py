#!/usr/bin/env python3
"""ds_merge_config.py 的契约测试 —— 用仓库里的真实 Windows 模板跑,钉住
「模板结构 ↔ 合并脚本」不再脱节(2026-07-13 真机装机崩:p4 把 model_presets
的 primary 键换成真实模型名,脚本还在打印 tpl['model_presets']['primary'])。

覆盖:
  1. 默认合并(不带 --model)rc=0,且 agents.defaults.modelPreset 指向的预设存在;
  2. --api-base/--model 换端点:rc=0,apiBase 生效、新模型有预设、modelPreset 指过去;
  3. channels 段永远不动;
  4. 改前备份存在。
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "bin" / "ds_merge_config.py"
TEMPLATE = REPO / "config" / "nanobot.config.windows.jsonc"

BASE_TARGET = {
    "channels": {"websocket": {"enabled": True, "token": "secret-keep"}},
    "tools": {"file": {"enable": True, "workspaceOnly": True}},
}


def run_merge(target: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(TEMPLATE), str(target), *extra],
        capture_output=True, text=True,
    )


class TestMergeConfig(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "config.json"
        self.target.write_text(json.dumps(BASE_TARGET), encoding="utf-8")

    def merged(self) -> dict:
        return json.loads(self.target.read_text(encoding="utf-8"))

    def test_default_merge_succeeds_and_preset_resolves(self):
        p = run_merge(self.target)
        self.assertEqual(p.returncode, 0, msg=p.stderr)
        cfg = self.merged()
        preset = cfg["agents"]["defaults"]["modelPreset"]
        self.assertIn(preset, cfg["model_presets"],
                      "默认 modelPreset 必须能在 model_presets 里找到")
        # 摘要打印不崩且报的是默认预设的模型
        self.assertIn(cfg["model_presets"][preset]["model"], p.stdout)
        # 危险内置工具全关(opendesign-intake 审出的 exec 洞):file 早关,exec 新关——
        # exec 开着 = 模型可直接创建 .approved,人工批准闸的"物理绕不过"就不成立。
        # 只断 enable 子键:deep_merge 有意保留 onboard 写的其它字段(如 workspaceOnly)。
        self.assertIs(cfg["tools"]["file"]["enable"], False)
        self.assertIs(cfg["tools"]["exec"]["enable"], False)

    def test_model_override_creates_preset_and_repoints_default(self):
        p = run_merge(self.target, "--api-base", "https://ex.com/v1",
                      "--model", "glm-5.2")
        self.assertEqual(p.returncode, 0, msg=p.stderr)
        cfg = self.merged()
        self.assertEqual(cfg["providers"]["custom"]["apiBase"], "https://ex.com/v1")
        preset = cfg["agents"]["defaults"]["modelPreset"]
        self.assertEqual(cfg["model_presets"][preset]["model"], "glm-5.2")
        self.assertEqual(cfg["model_presets"][preset]["provider"], "custom")


    # ── 2026-08-06:合配置**不许把机主已经选好的大脑重置回模板默认** ────────────
    # 记忆里挂了两天的那条("合配置会把大脑重置成 MiMo,无论打不打包都该修")。
    # 形状:装完之后机主用 /model 或 set_model.py 换了大脑;下次更新再合一次配置,
    # 不带 --model 时模板的 MiMo 默认会把 apiBase / modelPreset 原样盖回去 ——
    # **静默**,而机主不是程序员,只会看到"助手突然变笨了"。
    def test_existing_brain_survives_a_plain_remerge(self):
        # 机主已经把大脑换成别家(端点 + 预设都不是模板那套)
        owned = dict(BASE_TARGET)
        owned["providers"] = {"custom": {"apiBase": "https://owner-llm.example.com/v1"}}
        owned["model_presets"] = {"owner-model": {"label": "owner-model", "model": "owner-model"}}
        owned["agents"] = {"defaults": {"modelPreset": "owner-model"}}
        self.target.write_text(json.dumps(owned), encoding="utf-8")

        r = run_merge(self.target)          # 更新时的普通合并:不带 --api-base/--model
        self.assertEqual(r.returncode, 0, r.stderr)
        cfg = json.loads(self.target.read_text(encoding="utf-8"))

        self.assertEqual(cfg["providers"]["custom"]["apiBase"],
                         "https://owner-llm.example.com/v1", "端点被模板盖回去了")
        self.assertEqual(cfg["agents"]["defaults"]["modelPreset"], "owner-model",
                         "默认预设被模板盖回去了(= 大脑被重置)")
        self.assertIn("owner-model", cfg["model_presets"], "机主自己的预设被删了")
        # 模板带来的新预设仍然要合进来(更新的意义就在这儿),只是不许改默认指向
        self.assertGreater(len(cfg["model_presets"]), 1, "模板预设没合进来")

    def test_explicit_flags_still_win(self):
        # 显式指定时必须照做 —— 这条防止上面那条修过头,变成"永远改不了大脑"
        owned = dict(BASE_TARGET)
        owned["providers"] = {"custom": {"apiBase": "https://owner-llm.example.com/v1"}}
        owned["agents"] = {"defaults": {"modelPreset": "owner-model"}}
        owned["model_presets"] = {"owner-model": {"label": "owner-model", "model": "owner-model"}}
        self.target.write_text(json.dumps(owned), encoding="utf-8")

        r = run_merge(self.target, "--api-base", "https://new.example.com/v1",
                      "--model", "brand-new-model")
        self.assertEqual(r.returncode, 0, r.stderr)
        cfg = json.loads(self.target.read_text(encoding="utf-8"))
        self.assertEqual(cfg["providers"]["custom"]["apiBase"], "https://new.example.com/v1")
        self.assertEqual(cfg["agents"]["defaults"]["modelPreset"], "brand-new-model")

    def test_summary_prints_what_actually_landed(self):
        # 收尾那两行原来印的是**模板**的值 —— 修好之后模板值和落地值会不一样,
        # 还照印模板 = 屏幕上说着"大脑是 MiMo",盘上其实是机主的模型。
        owned = dict(BASE_TARGET)
        owned["providers"] = {"custom": {"apiBase": "https://owner-llm.example.com/v1"}}
        owned["agents"] = {"defaults": {"modelPreset": "owner-model"}}
        owned["model_presets"] = {"owner-model": {"label": "owner-model", "model": "owner-model"}}
        self.target.write_text(json.dumps(owned), encoding="utf-8")
        r = run_merge(self.target)
        self.assertIn("owner-llm.example.com", r.stdout, "汇总印的还是模板的端点")
        self.assertIn("owner-model", r.stdout, "汇总印的还是模板的模型")

    def test_channels_untouched_and_backup_written(self):
        p = run_merge(self.target)
        self.assertEqual(p.returncode, 0, msg=p.stderr)
        cfg = self.merged()
        self.assertEqual(cfg["channels"],
                         {"websocket": {"enabled": True, "token": "secret-keep"}})
        baks = list(Path(self.tmp.name).glob("config.json.bak-*"))
        self.assertEqual(len(baks), 1)
        self.assertEqual(json.loads(baks[0].read_text(encoding="utf-8")), BASE_TARGET)


if __name__ == "__main__":
    unittest.main(verbosity=2)
