#!/bin/bash
# 自攻 bt4:几种"看着差不多、其实错"的外层改法,每一种 bt4 都必须红。跑完无论如何恢复。
set -u
cd "$(git rev-parse --show-toplevel)"
f=tests/run-all.sh
git diff --quiet -- "$f" || { echo "拒跑:$f 有未提交改动"; exit 2; }
trap 'git checkout -- "$f"' EXIT
bad=0
mutate() {  # $1=名字 $2=python 替换表达式(对 s 操作)
  git checkout -- "$f"
  python3 - "$f" "$2" <<'PY'
import sys
p, expr = sys.argv[1], sys.argv[2]
s = open(p, encoding="utf-8").read(); t = eval(expr)
assert t != s, "变异没改到任何东西(锚点失效)"
open(p, "w", encoding="utf-8").write(t)
PY
  [ $? -eq 0 ] || { echo "🔴 [$1] 变异没打上"; bad=1; return; }
  if node --test --test-name-pattern='^bt4 ' tests/test_e2e_harness_guard.mjs >/dev/null 2>&1; then
    echo "🔴 [$1] bt4 仍然绿 ⇒ 问不住"; bad=1
  else
    echo "✅ [$1] bt4 红"
  fi
}
mutate "export 去掉(子进程拿不到路径)" 's.replace("export E2E_BROWSER_NOTES=\"$log_dir/e2e-browser-notes.txt\"", "E2E_BROWSER_NOTES=\"$log_dir/e2e-browser-notes.txt\"")'
mutate "回到 grep 日志数字" 's.replace("_bn_n=$(grep -c \x27\x27 \"$E2E_BROWSER_NOTES\")", "_bn_n=$(grep -c \x27浏览器没走正常关闭\x27 \"$_l\")")'
mutate "不合并重名(a a b)" 's.replace("sort | uniq -c", "awk \x27{print 1, $0}\x27")'
mutate "unset 挪到读之前" 's.replace("unset E2E_BROWSER_NOTES\n", "").replace("if [ -s \"$E2E_BROWSER_NOTES\" ]; then", "unset E2E_BROWSER_NOTES\nif [ -s \"${E2E_BROWSER_NOTES:-}\" ]; then")'
mutate "拼好了却没喂给 note_last" 's.replace("note_last \"${_sum:-见日志}\" \"$_skp\"", "_x=\"$_sum\"; note_last \"$(grep -m1 \x27^== 汇总:\x27 \"$_l\" | sed \x27s/^== 汇总://\x27)\" \"$_skp\"")'
git checkout -- "$f"; trap - EXIT
git diff --quiet -- "$f" && echo "== 已恢复($f 与 HEAD 一致,git 说的)"
exit $bad
