#!/usr/bin/env bash
# 红检 —— 证明 e2e 端口预检那批判据咬得动(track opendesign-stage-timer-e2e-red)。
#
# 规矩同 tests/mutation-installer-slim.sh:变异**被测对象**、每条指定靶子、
# 跑完原样还回去并用哈希核对。
#
# 🔴 存在的理由:这道闸是"防止判据被环境骗"的闸。它自己要是瞎了,
#    下一个遗孤照样能把五天烧掉,而且这次连"有一道闸"的错觉都算进去了。
set -u
cd "$(dirname "$0")/.."
PY="${PY:-/root/.venvs/design-studio/bin/python}"

GATE=tests/e2e/check-ports.sh
RUNNER=tests/e2e/run-all.sh
SOURCES=("$GATE" "$RUNNER")
WORK="$(mktemp -d)"
declare -A BEFORE
for f in "${SOURCES[@]}"; do
  BEFORE["$f"]="$(sha256sum "$f" | cut -d' ' -f1)"
  cp -p "$f" "$WORK/$(echo "$f" | tr / _)"
done
restore() {
  for f in "${SOURCES[@]}"; do cp -p "$WORK/$(echo "$f" | tr / _)" "$f"; done
  find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
}
trap 'restore; rm -rf "$WORK"' EXIT

pass=0; fail=0
ORACLE=tests/test_e2e_port_preflight.py

mutate_and_expect() {
  local id="$1" src="$2" target="$3"; shift 3
  local out="$WORK/mut-$id.txt"
  restore
  if [ "$src" = "__RENAME__" ]; then
    mv "$GATE" "$WORK/gate-hidden.sh"
  else
    "$PY" - "$src" "$@" <<'PYEOF' || { echo "  [BAD]  $id 变异没打上去"; fail=$((fail+1)); return; }
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding="utf-8")
args = sys.argv[2:]
for old, new in zip(args[0::2], args[1::2]):
    if old not in s:
        sys.exit(f"变异锚点找不到: {old!r}")
    s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")
PYEOF
  fi
  find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
  timeout 120 "$PY" -W ignore "$ORACLE" > "$out" 2>&1
  local rc=$?
  [ "$src" = "__RENAME__" ] && mv "$WORK/gate-hidden.sh" "$GATE"
  if [ "$rc" -eq 0 ]; then
    echo "  [BAD]  $id -> 判据全绿:这条变异下它是瞎的(靶子 $target)"; fail=$((fail+1))
  elif grep -qE "^(FAIL|ERROR): $target" "$out"; then
    echo "  [OK]   $id -> 靶子 $target 如期红了"; pass=$((pass+1))
  else
    echo "  [BAD]  $id -> 红了,但**不是靶子** $target:"
    grep -E "^(FAIL|ERROR):" "$out" | head -4 | sed 's/^/         实际红的是:/'; fail=$((fail+1))
  fi
}

echo "== 红检开始(e2e 端口预检)=="

# M1 闸永远说"干净" —— 遗孤占着端口也放行,正是 08-30 那五天的状态
mutate_and_expect M1 "$GATE" test_p3_an_occupied_port_is_caught_and_named \
  'if [ "$busy" -gt 0 ]; then' 'if [ "$busy" -gt 999 ]; then'

# M2 闸乱报 —— 干净的端口也说被占。**误报和假绿一样坏**:
#    它会让人养成"绕开这道闸"的习惯,而绕法得写成谎话
mutate_and_expect M2 "$GATE" test_p2_clean_ports_pass \
  '  [ -z "$line" ] && continue' '  line="fake pid=1"'

# M3 闸不再说出是谁占的 —— 只说"有问题"查不动,遗孤照样能活八天
mutate_and_expect M3 "$GATE" test_p3_an_occupied_port_is_caught_and_named \
  'echo "🔴 端口 $p 被占着:pid=${pid:-?}  起于 ${started:-?}"' \
  'echo "🔴 有端口被占着"'

# M4 总跑不再叫它 —— 闸建好了没接线,等于没建
mutate_and_expect M4 "$RUNNER" test_p4_wired_into_the_e2e_runner \
  'if ! tests/e2e/check-ports.sh; then' 'if false; then  # 预检下线'

# M5 闸整个没了
mutate_and_expect M5 "__RENAME__" test_p1_preflight_exists_and_is_runnable

# M6 把 ss 的错误重新吞掉(= 2026-09-07 修之前的真实状态)——
#    ss 坏了就当"没人占",恒绿。三条腿里两条各自独立命中的就是这个。
mutate_and_expect M6 "$GATE" test_p5_no_ss_must_fail_closed \
  'if ! line="$("$SS_BIN" -lptnH "sport = :$p" 2>/dev/null)"; then' \
  'line=""; if false; then'

# M7 不再扫派生端口 —— button_roles 的 PORT+1(8825)又回到扫描范围之外
mutate_and_expect M7 "$GATE" test_p7_derived_ports_are_scanned_too \
  'grep -oP '"'"'PORT \+ \K[0-9]+'"'"' "$f" 2>/dev/null | sort -u | while read -r off; do' \
  'true | while read -r off; do'

# M8 试过又撤了,原因写在这儿,别让下一个人再试一遍:
#   我原本在这里加了一道 `command -v "$SS_BIN"` 的前置闸(没装 iproute2 就喊停)。
#   M8 变异它 ⇒ **判据全绿** ⇒ 说明那道闸不承重:每个端口那次
#   `if ! line="$("$SS_BIN" ...)"` 已经把"没装"和"坏了"两种都咬住了。
#   不承重的分支 = 死断言,而死断言正是本单在治的病 ⇒ **删掉它**,
#   而不是给它编一条能让它显得有用的判据。红检照出的是我自己的冗余代码。

restore
echo
for f in "${SOURCES[@]}"; do
  now="$(sha256sum "$f" | cut -d' ' -f1)"
  [ "$now" = "${BEFORE[$f]}" ] || { echo "🔴 $f 没还原干净(哈希对不上)"; exit 2; }
done
echo "== 红检结束:咬住 $pass 条,漏网 $fail 条(源文件已原样还原)=="
[ "$fail" -eq 0 ]
