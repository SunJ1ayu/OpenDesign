#!/usr/bin/env python3
"""两份关卡 workflow 必须和 aiwork templates/ 逐字节一样。

定义在 SunJ1ayu/aiwork 的 templates/。这里从那份检出读出来比对，不在 OpenDesign 再写一份形状。
aiwork 改了模板，这份测试会红，直到开一个同步 PR。
bash -n 仍扫本仓库全部 workflow：YAML 把 `#` 当注释截断脚本时，只看解析后的文本才抓得到。
"""
from __future__ import annotations

import os
import re
import subprocess
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _load(p: Path) -> dict:
    doc = yaml.safe_load(p.read_text(encoding="utf-8"))
    # PyYAML 把键 `on` 读成 True
    doc["on"] = doc.pop(True, doc.get("on"))
    return doc


def aiwork_checkout() -> Path:
    """模板和 matchAny 的定义在 aiwork 检出里。CI 经 AIWORK_CHECKOUT 传入；本地默认 /root/aiwork。拿不到就失败，不跳过。"""
    root = Path(os.environ.get("AIWORK_CHECKOUT") or "/root/aiwork")
    missing = [name for name in ("templates/aiwork-gate.yml", "templates/aiwork-review-ping.yml", "gate/decide.mjs") if not (root / name).is_file()]
    if missing:
        raise AssertionError(
            f"缺少 aiwork 检出（设 AIWORK_CHECKOUT，本地默认 /root/aiwork）: {root} 没有 {', '.join(missing)}"
        )
    sha = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    print(f"aiwork checkout {root} @ {sha}", flush=True)
    return root


class WorkflowsMatchAiworkTemplates(unittest.TestCase):
    def test_byte_identical_to_templates(self) -> None:
        root = aiwork_checkout()
        for name in ("aiwork-gate.yml", "aiwork-review-ping.yml"):
            got = (ROOT / ".github" / "workflows" / name).read_bytes()
            want = (root / "templates" / name).read_bytes()
            self.assertEqual(got, want, f"{name} 和 aiwork templates/{name} 不一致")


class WorkflowScriptsParse(unittest.TestCase):
    """PR #10 上 aiwork-review-ping 的 ping 红过:`run: echo "PR #${{ … }}"` 里空格后的 `#` 被 YAML 当成注释,
    实际执行的只剩 `echo "PR`,引号不配对。这里把每个 workflow 里用 bash 跑的脚本按 YAML 解析后的样子取出来,
    `bash -n` 过一遍语法 —— 只看解析后的文本才抓得到这类错。"""

    def test_bash_steps_parse(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
