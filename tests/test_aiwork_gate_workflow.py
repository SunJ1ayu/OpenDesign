#!/usr/bin/env python3
"""aiwork 放行关卡的 workflow 形状(M1;计划见 SunJ1ayu/aiwork 的 WORKFLOW-MIGRATION-PLAN.md)。

关卡的判定逻辑在 tests/test_aiwork_gate.mjs 里测;这里钉的是"判它的代码是谁的":
  · 只由 pull_request_target / workflow_run 触发 ⇒ 跑的永远是 main 上的 workflow 与 .github/aiwork-gate/;
    一旦混进 pull_request / push,PR 就能改掉正在判它的关卡;
  · 检出的是默认分支、不留凭据 ⇒ 不执行 PR 的代码;
  · 私钥只从 environment `aiwork-gate` 来(只许 main 用),仓库级 secret 同仓库分支的 PR 拿得到;
  · 顶层权限除了保险丝要的 statuses: write 全是只读;发检查结果靠 App 私钥,不靠 GITHUB_TOKEN 的写权限;
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
        # 步骤里(检出参数、脚本、环境变量)一律不许出现 PR 的提交 / 引用
        steps = yaml.safe_dump(self.job["steps"], allow_unicode=True)
        for bad in ("pull_request.head", "head_sha", "refs/pull/", "head_ref"):
            self.assertNotIn(bad, steps, f"关卡 workflow 的步骤里出现了 {bad!r},可能在检出或执行 PR 的代码")
        self.assertNotIn("env", self.doc, "顶层不放环境变量")

    def test_key_only_from_main_only_environment(self) -> None:
        self.assertEqual(self.job.get("environment"), "aiwork-gate")
        step = next(s for s in self.job["steps"] if "main.mjs" in str(s.get("run", "")))
        self.assertEqual(step["env"]["AIWORK_GATE_PRIVATE_KEY"], "${{ secrets.AIWORK_GATE_PRIVATE_KEY }}")
        self.assertEqual(step["run"].strip(), "node .github/aiwork-gate/main.mjs")

    def test_read_only_token(self) -> None:
        perms = self.doc["permissions"]
        self.assertTrue(perms, "要显式写权限,不能吃仓库默认值")
        writes = {k for k, v in perms.items() if v != "read"}
        self.assertEqual(writes, {"statuses"}, "除了保险丝要的 statuses: write,其余一律只读")
        self.assertEqual(perms["statuses"], "write")
        self.assertEqual(perms.get("issues"), "read", "读 PR 事件(最后一次改目标分支,G1)要 issues: read")
        self.assertNotIn("permissions", self.job, "job 级别不许再放宽")



class OneRunAtATime(unittest.TestCase):
    """aiwork-review 评审 5361260820 / 5361623557:并发组按事件分(PR 号、事件的提交),运行却写到 PR 当前的 head,
    几次运行同时算同一个提交 ⇒ 慢一步的旧运行能盖掉新结论;较新的运行 App 出错拨了 failure,较早的运行写完又拨回 success。
    根治:同一时间只有一次运行 —— 组名固定、不取消正在跑的,排队的只留最新一个;每次都重算全部开着的 PR,
    被顶掉的排队运行不会漏算。job 上不许再有按事件过滤的 if(被顶掉的要靠顶掉它的那次来算)。"""

    def setUp(self) -> None:
        self.doc = _load(GATE)
        self.job = self.doc["jobs"]["gate"]

    def test_single_fixed_group_never_cancels_running(self) -> None:
        conc = self.doc["concurrency"]
        self.assertNotIn("${{", str(conc["group"]), "组名随事件变,就又有几次运行同时在算")
        self.assertIs(conc["cancel-in-progress"], False, "取消正在跑的会留下只占了位的提交,还白算")
        self.assertNotIn("concurrency", self.job, "job 级别再分组,就有两层说法")

    def test_job_not_filtered_by_event(self) -> None:
        self.assertNotIn("if", self.job)


class PingWorkflow(unittest.TestCase):
    def test_ping_has_no_power(self) -> None:
        doc = _load(PING)
        self.assertEqual(set(doc["on"]), {"pull_request_review"})
        self.assertEqual(doc["permissions"], {})
        text = PING.read_text(encoding="utf-8")
        self.assertNotIn("secrets.", text)
        self.assertNotIn("actions/checkout", text)
        self.assertEqual(doc["name"], "aiwork-review-ping", "关卡按这个名字监听它跑完")


class GateReRunsOnEdit(unittest.TestCase):
    """GPT 评审(@ e604a31)R8:只改 PR 的目标分支时 head 不变、改动文件却变了 ⇒ 要订阅 edited 重算。"""

    def test_edited_triggers_recompute(self) -> None:
        types = set(_load(GATE)["on"]["pull_request_target"]["types"])
        self.assertTrue({"opened", "synchronize", "reopened", "labeled", "edited"} <= types, types)



class WorkflowScriptsParse(unittest.TestCase):
    """PR #10 上 aiwork-review-ping 的 ping 红过:`run: echo "PR #${{ … }}"` 里空格后的 `#` 被 YAML 当成注释,
    实际执行的只剩 `echo "PR`,引号不配对。这里把每个 workflow 里用 bash 跑的脚本按 YAML 解析后的样子取出来,
    `bash -n` 过一遍语法 —— 只看解析后的文本才抓得到这类错。"""

    def test_bash_steps_parse(self) -> None:
        import re
        import subprocess

        bad = []
        for wf in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
            doc = _load(wf)
            wf_shell = ((doc.get("defaults") or {}).get("run") or {}).get("shell")
            for job_id, job in (doc.get("jobs") or {}).items():
                job_shell = ((job.get("defaults") or {}).get("run") or {}).get("shell", wf_shell)
                for i, step in enumerate(job.get("steps") or []):
                    if "run" not in step:
                        continue
                    shell = step.get("shell", job_shell) or "bash"
                    if not str(shell).startswith("bash"):
                        continue
                    script = re.sub(r"\$\{\{.*?\}\}", "X", str(step["run"]))
                    r = subprocess.run(["bash", "-n"], input=script, capture_output=True, text=True)
                    if r.returncode:
                        bad.append(f"{wf.name} {job_id} 第 {i + 1} 步:{r.stderr.strip()}")
        self.assertEqual(bad, [])

    def test_ping_runs_whole_message(self) -> None:
        step = _load(PING)["jobs"]["ping"]["steps"][0]
        self.assertIn("aiwork-gate", step["run"], "echo 的整句都要在,不能被当成注释截掉")

if __name__ == "__main__":
    unittest.main()
