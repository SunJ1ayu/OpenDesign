#!/usr/bin/env bash
# 红检(变异测试)—— 证明**产物新鲜度闸**那批判据咬得动。
#
# 被测对象:tests/e2e/check-dist-fresh.sh + tests/e2e/run-all.sh 里的接线
# 判据:    tests/test_dist_freshness_gate.py
#
# 规矩与 tests/mutation-window-chrome.sh 同一套:
#   1. 变异**被测对象**,不是判据本身;
#   2. 每条指定**靶子**:必须是那一条红,红在别处算漏网;
#   3. 跑完原样还回去,并用哈希机械核对。
#
# 🔴 M3 是**新旧闸的对照组** —— 把闸退回"比 mtime"(旧闸的做法),
#    O2(只改注释)必须红。旧闸 0 咬 1 漏,新闸咬住,这一条才证明这次收紧有意义。
#    (「红检要跑对照组」:0.90.0 那单的教训。)
#
# 用法:tests/mutation-dist-gate.sh
# 退出码:0 = 每条都咬住靶子   1 = 有漏网   2 = 用法/现场问题

set -u
cd "$(dirname "$0")/.."
PY="${PY:-/root/.venvs/design-studio/bin/python}"
ORACLE=tests/test_dist_freshness_gate.py
ORACLE_MOD=tests.test_dist_freshness_gate   # -m unittest 要点分模块名,不是路径

SOURCES=(tests/e2e/check-dist-fresh.sh tests/e2e/run-all.sh)
WORK="$(mktemp -d)"
declare -A BEFORE
for f in "${SOURCES[@]}"; do
  BEFORE["$f"]="$(sha256sum "$f" | cut -d' ' -f1)"
  cp -p "$f" "$WORK/$(echo "$f" | tr / _)"
done

# 变异可能让闸往**真的** web/dist 写东西(M5 就是干这个的)。
# 只还原脚本不够 —— 2026-08-24 第一版正是这么把 judge-probe.txt 留在了仓库里,
# 它接着污染了下一轮变异,害得靶子红在别处、白查一轮。
find web/dist -type f | sort > "$WORK/dist-before.txt"

restore() {
  for f in "${SOURCES[@]}"; do cp -p "$WORK/$(echo "$f" | tr / _)" "$f"; done
  find web/dist -type f | sort > "$WORK/dist-now.txt"
  comm -13 "$WORK/dist-before.txt" "$WORK/dist-now.txt" | while read -r extra; do
    [ -n "$extra" ] && rm -f "$extra"
  done
}
trap 'restore; rm -rf "$WORK"' EXIT

pass=0; fail=0

# 用法:mutate_and_expect <id> <被变异文件> <靶子> <旧> <新>
mutate_and_expect() {
  local id="$1" src="$2" target="$3"; shift 3
  local out="$WORK/mut-$id.txt"
  restore
  "$PY" - "$src" "$@" <<'PYEOF' || { echo "  [BAD]  $id 变异没打上去"; fail=$((fail+1)); return; }
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding="utf-8")
args = sys.argv[2:]
if len(args) % 2:
    sys.exit("旧/新必须成对")
for old, new in zip(args[0::2], args[1::2]):
    if old not in s:
        sys.exit(f"变异锚点找不到: {old!r}")
    s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")
PYEOF
  chmod +x tests/e2e/check-dist-fresh.sh tests/e2e/run-all.sh
  timeout 900 "$PY" -W ignore -m unittest "$ORACLE_MOD" > "$out" 2>&1
  local rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "  [BAD]  $id -> 判据全绿:这条变异下它是瞎的(靶子 $target)"
    fail=$((fail+1))
  elif grep -qE "^(FAIL|ERROR): $target" "$out"; then
    echo "  [OK]   $id -> 靶子 $target 如期红了"
    pass=$((pass+1))
  else
    echo "  [BAD]  $id -> 红了,但**不是靶子** $target:"
    grep -E "^(FAIL|ERROR):" "$out" | head -4 | sed 's/^/         实际红的是:/'
    # 🔴 详情要当场吐进收据:trap 跑完就删 $WORK,不留的话下次只能整轮重跑才查得动
    #    (2026-08-24 查 M6 就吃了这个亏)。
    echo "         ---- 详情(前 40 行)----"
    head -40 "$out" | sed 's/^/         /'
    fail=$((fail+1))
  fi
}

echo "== 红检开始(产物新鲜度闸)=="

# M1 比对退回"只比文件名" —— js/css 带内容哈希所以名变了看得出来,
#    但 index.html **不带哈希**:改了内容名字一样 ⇒ 静默漏过。
mutate_and_expect M1 tests/e2e/check-dist-fresh.sh \
  test_o1b_index_html_change_is_caught \
  'if diff -r "$DIST" "$OUT" > "$TMP/diff.txt" 2>&1; then' \
  'if diff <(cd "$DIST" && find . -type f | sort) <(cd "$OUT" && find . -type f | sort) > "$TMP/diff.txt" 2>&1; then'

# M2 build 失败却报绿 —— 「返回成功≠事情发生了」最坏的一种:
#    所有 e2e 会在一个错误的前提上继续跑,而收据一片绿。
mutate_and_expect M2 tests/e2e/check-dist-fresh.sh \
  test_o3_build_failure_blocks_loudly \
  '  tail -30 "$LOG" >&2
  exit 1
fi' \
  '  tail -30 "$LOG" >&2
  exit 0
fi'

# M3 **对照组**:把闸退回旧做法(比 mtime)。只改注释的场景下它必红 ——
#    这正是 2026-08-24 那次事故的形状,也是这次收紧的全部意义。
mutate_and_expect M3 tests/e2e/check-dist-fresh.sh \
  test_o2_comment_only_change_is_not_flagged \
  'if diff -r "$DIST" "$OUT" > "$TMP/diff.txt" 2>&1; then' \
  'if [ -z "$(find "$WEB_DIR/src" -type f -newer "$DIST/index.html" 2>/dev/null | head -1)" ]; then'

# M4 run-all.sh 把闸的 rc 吃掉 —— 闸红了照样往下跑,收据照样绿。
#    这个项目栽过五次,所以单独打一枪。
mutate_and_expect M4 tests/e2e/run-all.sh \
  test_o6_runall_wiring \
  'if ! tests/e2e/check-dist-fresh.sh; then' \
  'tests/e2e/check-dist-fresh.sh; if false; then'

# M5 闸顺手改工作树 —— 「你欠一次 build」这个信号被工具悄悄抹平。
mutate_and_expect M5 tests/e2e/check-dist-fresh.sh \
  test_o4_does_not_touch_the_worktree \
  '  echo "✅ 产物新鲜度' \
  '  echo "闸到此一游" > "$DIST/judge-probe.txt"
  echo "✅ 产物新鲜度'

# M6 拆掉「产物数 > 0」那条 —— 两边都空时 diff 认为一致 ⇒ **恒绿**,
#    这道闸会永远绿着什么都不守,而收据上一切正常。
#    ⚠️ 第一轮这条**漏网**,而漏得有道理:那时 build 不写盘就连 $OUT 目录都不建,
#    diff 撞「目录不存在」替它红了 ⇒ 拆掉一条防线而行为没变 = **变异本身没意义**。
#    正确的处置不是把判据调过敏,是让实现把职责说清楚 —— 闸补了一行 `mkdir -p "$OUT"`,
#    「两边都空」这个真实场景才造得出来,这条变异也才真的咬得到东西。
mutate_and_expect M6 tests/e2e/check-dist-fresh.sh \
  test_o7_empty_build_output_is_not_treated_as_match \
  'if [ "$n" -eq 0 ]; then' \
  'if [ "$n" -lt 0 ]; then'

restore
echo
echo "== 机械核对:被变异的文件都还原了吗 =="
bad=0
for f in "${SOURCES[@]}"; do
  now="$(sha256sum "$f" | cut -d' ' -f1)"
  if [ "$now" != "${BEFORE[$f]}" ]; then echo "  🔴 $f 没还原!"; bad=1; fi
done
[ "$bad" -eq 0 ] && echo "  全部还原(sha256 逐个比过)"

echo
echo "== 红检结果:咬住 $pass 条 / 漏网 $fail 条 =="
if [ "$fail" -gt 0 ] || [ "$bad" -ne 0 ]; then exit 1; fi
exit 0
