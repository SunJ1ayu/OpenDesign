#!/usr/bin/env python3
"""发版 workflow 的形状(规则 D1;计划见 SunJ1ayu/aiwork 的 WORKFLOW-MIGRATION-PLAN.md)。

业主是谁只在 `.aiwork/policy.json` 的 owner 一处定义,关卡(G7)和发版的审批人检查都读它。
以前发版 workflow 里另写了一份审批人,换业主账号时两处各说各的:关卡认新账号,
发版检查还在要求旧账号当 environment `release` 的审批人。
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RELEASE = ROOT / ".github" / "workflows" / "release.yml"
OWNER = json.loads((ROOT / ".aiwork" / "policy.json").read_text(encoding="utf-8"))["owner"]


class ReleaseApprover(unittest.TestCase):
    def setUp(self) -> None:
        self.text = RELEASE.read_text(encoding="utf-8")
        steps = yaml.safe_load(self.text)["jobs"]["check"]["steps"]
        self.names = [s.get("name") or s.get("uses") for s in steps]
        self.env_check = next(s for s in steps if s.get("name") == "environment release 的保护是齐的")
        self.env_check_at = steps.index(self.env_check)
        self.checkout_at = next(i for i, s in enumerate(steps) if str(s.get("uses", "")).startswith("actions/checkout@"))

    def test_approver_read_from_policy_owner(self) -> None:
        self.assertNotIn("APPROVER", self.env_check.get("env", {}), "审批人另写了一份,没从 policy 读")
        self.assertRegex(self.env_check["run"], r"APPROVER=\$\(jq -er '\.owner' \.aiwork/policy\.json\)")
        self.assertLess(self.checkout_at, self.env_check_at, "读 policy 之前要先检出(check 只在 main 上跑,读到的是 main 上那份)")

    def test_owner_login_not_written_elsewhere_in_workflow(self) -> None:
        # 注释里的仓库路径(SunJ1ayu/aiwork)不算;代码行里一律不许出现业主账号
        code = [ln for ln in self.text.splitlines() if not ln.lstrip().startswith("#")]
        hits = [ln.strip() for ln in code if re.search(rf"\b{re.escape(OWNER)}\b", ln)]
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
