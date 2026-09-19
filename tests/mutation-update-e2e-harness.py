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
 ("M6 e1 no marker check", ".github/scripts/update_e2e_verdict.py", '    _markers(f, problems)\n    return _finish(kind, f, problems, "updated', '    return _finish(kind, f, problems, "updated', "VVerdict"),
 ("M7 e3 no relaunch check", ".github/scripts/update_e2e_verdict.py", 'if _version(relaunch.get("health")) != old:', 'if False:', "VVerdict"),
 # M8 锚点带上 e5 自己的 _rolled_back 行:e9(track opendesign-auto-update-countdown)复用了同一句判断,只写那一句会命中两处(09-17 DeepSeek 评审抓到 SETUP ERROR)
 ("M8 e5 no seen check", ".github/scripts/update_e2e_verdict.py", 'if not bad or bad not in (f.get("seen_versions") or []):\n            problems.append("the unhealthy new version (%r) never answered, scenario untested" % (bad or None))\n        _reached_rollback(f, problems)\n        _rolled_back("e5"', 'if False:\n            problems.append("the unhealthy new version (%r) never answered, scenario untested" % (bad or None))\n        _reached_rollback(f, problems)\n        _rolled_back("e5"', "VVerdict"),
 ("M8b e9 no seen check", ".github/scripts/update_e2e_verdict.py", 'if not bad or bad not in (f.get("seen_versions") or []):\n            problems.append("the unhealthy new version (%r) never answered, scenario untested" % (bad or None))\n        _reached_rollback(f, problems)\n        _rolled_back("e9"', 'if False:\n            problems.append("the unhealthy new version (%r) never answered, scenario untested" % (bad or None))\n        _reached_rollback(f, problems)\n        _rolled_back("e9"', "VVerdict"),
 ("M9 nested ignored", ".github/scripts/update_e2e_verdict.py", 'if f.get("nested_old_exists"):', 'if False:', "VVerdict"),
 ("M10 injection ignored", ".github/scripts/update_e2e_verdict.py", 'if inject.get("landed") is not True:', 'if False:', "VVerdict"),
 ("M11 missing facts ok", ".github/scripts/update_e2e_verdict.py", 'if f.missing:', 'if False:', "VVerdict"),
 ("M12 CI new version not newer", ".github/workflows/windows-update-e2e.yml", 'NEW="0.98.900"', 'NEW="0.98.3"', "H1"),
 ("M13 workflow gate drops a scenario", ".github/workflows/windows-update-e2e.yml", "foreach ($k in 'e1', 'e2', 'e3', 'e4', 'e5', 'e6', 'e7', 'e8', 'e9')", "foreach ($k in 'e1', 'e2', 'e3', 'e4', 'e5', 'e6', 'e7', 'e8')", "WWorkflow"),
 ("M14 non-ascii output", ".github/scripts/update_e2e_verdict.py", 'text.encode("ascii", "replace").decode("ascii")', 'text + "中"', "VVerdict"),
 ("M16 pointers not checked", ".github/scripts/update_e2e_verdict.py", 'def _pointers(f, problems):\n', 'def _pointers(f, problems):\n    return\n', "VVerdict"),
 ("M17 .new counts as inside live", ".github/scripts/update_e2e_verdict.py", 'under = live + "\\\\"', 'under = live', "VVerdict"),
 ("M18 no /D on reset", ".github/scripts/windows-update-e2e.ps1", '-ArgumentList "/S /D=$InstallDir"', "-ArgumentList '/S'", "ZReset"),
 ("M19 rollback reach not checked", ".github/scripts/update_e2e_verdict.py", 'if (f.get("relay") or {}).get("old_seen") is not True:', 'if False:', "VVerdict"),
 ("M20 old_seen splits the if/elseif chain", ".github/scripts/windows-update-e2e.ps1", "        if (Test-Path -LiteralPath $OldDir) { $oldSeen = $true }\n        if ($running) { $seen = $true }\n", "        if ($running) { $seen = $true }\n        if (Test-Path -LiteralPath $OldDir) { $oldSeen = $true }\n", "ZWaitRelay"),
 ("M15 e2 health ignored", ".github/scripts/update_e2e_verdict.py", 'if _version(f.get("health_after")) != old:\n        problems.append("old app not answering after refusal', 'if False:\n        problems.append("old app not answering after refusal', "VVerdict"),
 # ── e6/e7 与收尾复查(09-15)──
 ("M21 e6 space not checked", ".github/scripts/update_e2e_verdict.py", '    if " " not in live:', '    if False:', "VVerdict"),
 ("M22 e7 rc not checked", ".github/scripts/update_e2e_verdict.py", '    if rc != 3:', '    if False:', "VVerdict"),
 ("M23 e7 .new ignored", ".github/scripts/update_e2e_verdict.py", '    if f.get("new_exists"):\n        problems.append(".new was created', '    if False:\n        problems.append(".new was created', "VVerdict"),
 ("M24 e7 any command line", ".github/scripts/update_e2e_verdict.py", '    if "/UPDATE" not in cmd or len(quoted) != 2 or " " not in quoted[1]:', '    if False:', "VVerdict"),
 ("M25 final health not checked", ".github/scripts/update_e2e_verdict.py", '        if _version(f.get("health_final")) != new:', '        if False:', "VVerdict"),
 ("M26 spaced scenarios not last", ".github/scripts/windows-update-e2e.ps1", "$Expected   = @('e2', 'e3', 'e4', 'e5', 'e1', 'e8', 'e9', 'e6', 'e7')", "$Expected   = @('e6', 'e7', 'e2', 'e3', 'e4', 'e5', 'e1', 'e8', 'e9')", "ZSpaced"),
 ("M27 spaced dir has no space", ".github/scripts/windows-update-e2e.ps1", r"$SpacedInstallDir = 'C:\OD e2e space\Programs\OpenDesign'", r"$SpacedInstallDir = 'C:\ODe2espace\Programs\OpenDesign'", "ZSpaced"),
 ("M28 e7 forgets to switch dir", ".github/scripts/windows-update-e2e.ps1", "function Run-e7 {\n    Use-SpacedInstallDir\n    $f = New-Facts", "function Run-e7 {\n    $f = New-Facts", "ZSpaced"),
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
