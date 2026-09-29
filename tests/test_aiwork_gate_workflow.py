#!/usr/bin/env python3
"""aiwork 放行关卡的 workflow 形状(M1;计划见 SunJ1ayu/aiwork 的 WORKFLOW-MIGRATION-PLAN.md)。

关卡的判定逻辑在 tests/test_aiwork_gate.mjs 里测;这里钉的是"判它的代码是谁的":
  · 只由 pull_request_target / workflow_run 触发 ⇒ 跑的永远是 main 上的 workflow 与 .github/aiwork-gate/;
    一旦混进 pull_request / push,PR 就能改掉正在判它的关卡;
  · 检出的是默认分支、不留凭据 ⇒ 不执行 PR 的代码;
  · 私钥只从 environment `aiwork-gate` 来(只许 main 用),仓库级 secret 同仓库分支的 PR 拿得到;
  · 顶层权限全是只读;发检查结果靠 App 私钥,不靠 GITHUB_TOKEN 的写权限;
  · 敲门的 aiwork-review-ping 什么权限都没有、不碰 secret。
"""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
GATE = ROOT / ".github" / "workflows" / "aiwork-gate.yml"
PING = ROOT / ".github" / "workflows" / "aiwork-review-ping.yml"


def _load(p: Path) -> dict:
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    # PyYAML 把键 `on` 读成 True
    doc["on"] = doc.pop(True, doc.get("on"))
    return doc


class GateWorkflow(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = _load(GATE)
        self.job = self.doc["jobs"]["gate"]

    def test_only_base_branch_triggers(self) -> None:
        self.assertEqual(set(self.doc["on"]), {"pull_request_target", "workflow_run"})
        self.assertEqual(set(self.doc["on"]["workflow_run"]["workflows"]), {"ci", "aiwork-review-ping"})

    def test_checks_out_default_branch_without_credentials(self) -> None:
        checkouts = [s for s in self.job["steps"] if str(s.get("uses", "")).startswith("actions/checkout")]
        self.assertEqual(len(checkouts), 1)
        w = checkouts[0].get("with") or {}
        self.assertEqual(w.get("ref"), "${{ github.event.repository.default_branch }}")
        self.assertIs(w.get("persist-credentials"), False)
        text = GATE.read_text(encoding="utf-8")
        for bad in ("pull_request.head", "head_sha }}", "refs/pull/"):
            self.assertNotIn(bad, text, f"关卡 workflow 里出现了 {bad!r},可能在检出或执行 PR 的代码")

    def test_key_only_from_main_only_environment(self) -> None:
        self.assertEqual(self.job.get("environment"), "aiwork-gate")
        step = next(s for s in self.job["steps"] if "main.mjs" in str(s.get("run", "")))
        self.assertEqual(step["env"]["AIWORK_GATE_PRIVATE_KEY"], "${{ secrets.AIWORK_GATE_PRIVATE_KEY }}")
        self.assertEqual(step["run"].strip(), "node .github/aiwork-gate/main.mjs")

    def test_read_only_token(self) -> None:
        perms = self.doc["permissions"]
        self.assertTrue(perms, "要显式写权限,不能吃仓库默认值")
        self.assertEqual({v for v in perms.values()}, {"read"})
        self.assertNotIn("permissions", self.job, "job 级别不许再放宽")

    def test_one_run_per_pr(self) -> None:
        conc = self.doc["concurrency"]
        self.assertIs(conc["cancel-in-progress"], True)
        self.assertIn("pull_request.number", conc["group"])
        self.assertIn("workflow_run.pull_requests[0].number", conc["group"])


class PingWorkflow(unittest.TestCase):
    def test_ping_has_no_power(self) -> None:
        doc = _load(PING)
        self.assertEqual(set(doc["on"]), {"pull_request_review"})
        self.assertEqual(doc["permissions"], {})
        text = PING.read_text(encoding="utf-8")
        self.assertNotIn("secrets.", text)
        self.assertNotIn("actions/checkout", text)
        self.assertEqual(doc["name"], "aiwork-review-ping", "关卡按这个名字监听它跑完")


if __name__ == "__main__":
    unittest.main()
