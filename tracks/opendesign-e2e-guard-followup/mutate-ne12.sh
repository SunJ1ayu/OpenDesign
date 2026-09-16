#!/bin/bash
# ne12 的红靠变异证明:删掉 _no_egress.py 的回环检查块 ⇒ ne12 必须红;跑完无论如何恢复。
set -u
cd "$(git rev-parse --show-toplevel)"
f=tests/e2e/_no_egress.py
git diff --quiet -- "$f" || { echo "拒跑:$f 有未提交改动"; exit 2; }
trap 'git checkout -- "$f"' EXIT
python3 - "$f" <<'PY'
import sys
p = sys.argv[1]; s = open(p, encoding="utf-8").read()
a = s.index("    # 🔴 回环起不来要**响亮地红**"); b = s.index("    if _egress_open():")
open(p, "w", encoding="utf-8").write(s[:a] + s[b:])
PY
echo "== 变异:删掉 python 回环检查块($(git diff --numstat -- "$f" | awk '{print $2}') 行)"
node --test --test-name-pattern='^ne12 ' tests/test_e2e_harness_guard.mjs 2>&1 | grep -E -A2 '^(ok|not ok) |^# (pass|fail)|error:'
rc=${PIPESTATUS[0]}
git checkout -- "$f"; trap - EXIT
git diff --quiet -- "$f" && echo "== 已恢复($f 与 HEAD 一致,git 说的)"
[ "$rc" -ne 0 ] && { echo "✅ 变异下 ne12 红 ⇒ 它真的在问 python 回环检查"; exit 0; }
echo "🔴 变异下 ne12 仍然绿 ⇒ 这条判据问不住"; exit 1
