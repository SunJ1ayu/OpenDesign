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
