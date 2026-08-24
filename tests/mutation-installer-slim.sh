#!/usr/bin/env bash
# 红检(变异测试)—— 证明**安装包瘦身那批判据**咬得动。
#
# 覆盖 tests/test_installer_slim.py 的 g2~g5。
# 规矩同 tests/mutation-native-frame.sh:
#   1. 变异**被测对象**(build-package.sh),不是判据本身;
#   2. 每条指定**靶子**:必须是那一条红,红在别处算漏网;
#   3. 跑完原样还回去,哈希机械核对(`cp -p`,保 mtime)。
#
# 🔴 它存在的理由:这一单删的是**装到业主机器上的东西**,删错了他打不开软件 ——
#    0.93 已经让他遇到过一次"打开全是白的"。闸绿不绿说明不了什么,
#    **闸咬不咬得动**才说明问题。
#
# 用法:tests/mutation-installer-slim.sh
# 退出码:0 = 每条都咬住靶子   1 = 有漏网   2 = 用法/现场问题

set -u
cd "$(dirname "$0")/.."
PY="${PY:-/root/.venvs/design-studio/bin/python}"

TARGET=tracks/opendesign-windows-installer/spike/build-package.sh
SOURCES=("$TARGET")
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
ORACLE=tests/test_installer_slim.py

mutate_and_expect() {
  local id="$1" src="$2" oracle="$3" target="$4"; shift 4
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
  find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
  timeout 300 "$PY" -W ignore "$oracle" > "$out" 2>&1
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
    fail=$((fail+1))
  fi
}

echo "== 红检开始(安装包瘦身)=="

# S1 整个瘦身被拿掉 —— 业主的安装/卸载又变回两万多个文件
mutate_and_expect S1 "$TARGET" "$ORACLE" \
  test_g5_slim_drop_exists_and_is_an_explicit_array \
  'SLIM_DROP=(lark_oapi botocore boto3 s3transfer telegram)' \
  'SLIM_DROP_DISABLED=(lark_oapi)'

# S2 改成通配符 —— 看着省事,`lark*` 删错了**不会报错**,只会让功能悄悄消失
mutate_and_expect S2 "$TARGET" "$ORACLE" \
  test_g5_slim_drop_exists_and_is_an_explicit_array \
  'SLIM_DROP=(lark_oapi botocore boto3 s3transfer telegram)' \
  'SLIM_DROP=(lark* boto* telegram)'

# S3 把真在用的包写进清单 —— 业主装完之后某个功能没了
mutate_and_expect S3 "$TARGET" "$ORACLE" \
  test_g2_never_drop_something_we_actually_use \
  'SLIM_DROP=(lark_oapi botocore boto3 s3transfer telegram)' \
  'SLIM_DROP=(lark_oapi botocore boto3 s3transfer telegram PIL)'

# S4 dist-info 不再跟着删 —— 留下"说包还在、其实不在"的元数据
mutate_and_expect S4 "$TARGET" "$ORACLE" \
  test_g4_dist_info_is_dropped_together_with_the_package \
  'for info in sorted(sp.glob("*.dist-info")):' \
  'for info in []:  # 元数据不删了'

# S5 删掉一个 nanobot 启动时真要 import 的包 —— **业主打不开软件**
#    (靶子必须是 g3:它问的是"结果",g5/g2 那种形状闸看不出这个)
mutate_and_expect S5 "$TARGET" "$ORACLE" \
  test_g3_nanobot_startup_survives_the_prune \
  'SLIM_DROP=(lark_oapi botocore boto3 s3transfer telegram)' \
  'SLIM_DROP=(lark_oapi botocore boto3 s3transfer telegram rich)'

restore
echo
for f in "${SOURCES[@]}"; do
  now="$(sha256sum "$f" | cut -d' ' -f1)"
  if [ "$now" != "${BEFORE[$f]}" ]; then
    echo "🔴 $f 没还原干净(哈希对不上)"; exit 2
  fi
done
echo "== 红检结束:咬住 $pass 条,漏网 $fail 条(源文件已原样还原)=="
[ "$fail" -eq 0 ]
