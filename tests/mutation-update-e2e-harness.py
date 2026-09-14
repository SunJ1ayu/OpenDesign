#!/usr/bin/env python3
"""红检:tests/test_update_e2e_harness.py 咬不咬得住(track opendesign-in-app-update-install §3)。

每条变异把考卷搭子(替身 / 证书脚本 / 判定器 / workflow / ps1 里的主机表)改坏一处,
只跑对应那组判据,必须红。**逃掉一条 = 那组判据是摆设** ⇒ 退出码 1。
每条跑完原样拷回;锚点不唯一算 SETUP ERROR(也是 1),不许静默跳过。

用法(仓根):python tests/mutation-update-e2e-harness.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = os.environ.get("PY") or sys.executable
BACKUP = os.path.join(tempfile.mkdtemp(), "backup")
muts = [
 ("M1 digest prefix", ".github/scripts/fake_github.py", '"digest": "sha256:" + sha256_file(setup_path)', '"digest": "sha1:" + sha256_file(setup_path)', "H1"),
 ("M2 drop github.com redirect", ".github/scripts/windows-update-e2e.ps1", "$RedirectHosts = @('api.github.com', 'github.com')", "$RedirectHosts = @('api.github.com')", "H2"),
 ("M3 SAN lacks github.com", ".github/scripts/make-e2e-certs.sh", "subjectAltName = DNS:api.github.com, DNS:github.com", "subjectAltName = DNS:api.github.com", "H3"),
 ("M4 skip lookalike dirs", ".github/scripts/fake_github.py", "if d not in MANIFEST_SKIP_DIRS", "if not d.startswith('__pycache__')", "H5"),
 ("M5 corrupt two bytes", ".github/scripts/fake_github.py", "data[mid + 1:]", "bytes([data[mid+1] ^ 0xFF]) + data[mid + 2:]", "H4"),
 ("M6 e1 no marker check", ".github/scripts/update_e2e_verdict.py", '    _markers(f, problems)\n    return _finish("e1"', '    return _finish("e1"', "VVerdict"),
 ("M7 e3 no relaunch check", ".github/scripts/update_e2e_verdict.py", 'if _version(relaunch.get("health")) != old:', 'if False:', "VVerdict"),
 ("M8 e5 no seen check", ".github/scripts/update_e2e_verdict.py", 'if not bad or bad not in (f.get("seen_versions") or []):', 'if False:', "VVerdict"),
 ("M9 nested ignored", ".github/scripts/update_e2e_verdict.py", 'if f.get("nested_old_exists"):', 'if False:', "VVerdict"),
 ("M10 injection ignored", ".github/scripts/update_e2e_verdict.py", 'if inject.get("landed") is not True:', 'if False:', "VVerdict"),
 ("M11 missing facts ok", ".github/scripts/update_e2e_verdict.py", 'if f.missing:', 'if False:', "VVerdict"),
 ("M12 CI new version not newer", ".github/workflows/windows-update-e2e.yml", 'NEW="0.98.900"', 'NEW="0.98.3"', "H1"),
 ("M13 workflow gate lists four", ".github/workflows/windows-update-e2e.yml", "foreach ($k in 'e1', 'e2', 'e3', 'e4', 'e5')", "foreach ($k in 'e1', 'e2', 'e3', 'e4')", "WWorkflow"),
 ("M14 non-ascii output", ".github/scripts/update_e2e_verdict.py", 'text.encode("ascii", "replace").decode("ascii")', 'text + "中"', "VVerdict"),
 ("M16 pointers not checked", ".github/scripts/update_e2e_verdict.py", 'def _pointers(f, problems):\n', 'def _pointers(f, problems):\n    return\n', "VVerdict"),
 ("M17 .new counts as inside live", ".github/scripts/update_e2e_verdict.py", 'under = live + "\\\\"', 'under = live', "VVerdict"),
 ("M18 no /D on reset", ".github/scripts/windows-update-e2e.ps1", '-ArgumentList "/S /D=$InstallDir"', "-ArgumentList '/S'", "ZReset"),
 ("M15 e2 health ignored", ".github/scripts/update_e2e_verdict.py", 'if _version(f.get("health_after")) != old:\n        problems.append("old app not answering after refusal', 'if False:\n        problems.append("old app not answering after refusal', "VVerdict"),
]
bad = 0
for name, path, old, new, sel in muts:
    src = open(path, encoding="utf-8").read()
    if src.count(old) != 1:
        print(f"{name}: SETUP ERROR anchor count={src.count(old)}")
        bad += 1
        continue
    shutil.copy(path, BACKUP)
    try:
        open(path, "w", encoding="utf-8").write(src.replace(old, new))
        r = subprocess.run([PY, "-m", "unittest", "-k", sel, "tests/test_update_e2e_harness.py"], capture_output=True, text=True, timeout=300)
        bites = r.returncode != 0
        bad += 0 if bites else 1
        print(f"{name}: {'BITES' if bites else 'ESCAPED'}")
    finally:
        shutil.copy(BACKUP, path)
print(f"{len(muts)} mutations, {len(muts) - bad} bite, {bad} escaped/setup-error")
sys.exit(1 if bad else 0)
