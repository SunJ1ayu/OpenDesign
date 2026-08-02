#!/usr/bin/env bash
# e2e 总跑开关。
#
# 存在的理由(2026-08-02):`tests/e2e/` 下 30 个 e2e 谁都不归 `unittest discover` 管
# (文件名不匹配 `test_*.py`),全靠人记得手跑一遍 —— 于是 `adoption.e2e.py` 的三条
# 断言在 `38da0ac` 之后**红了 6 天没人发现**。修那三条只是止血,这个脚本才是根因。
#
# 用法:
#   tests/e2e/run-all.sh              # 跑全部可无人值守的场景(约 2.5 分钟)
#   tests/e2e/run-all.sh --with-gateway   # 连需要活 gateway 的两条也跑
#   tests/e2e/run-all.sh focus_ring todo  # 只跑名字含这些子串的
#
# 退出码:有任何一条 FAIL 就非 0。**SKIP 永远不算 PASS**(见下方汇总)。
set -uo pipefail

cd "$(dirname "$0")/../.."          # 仓库根
PY="${PY:-python3}"
NODE="${NODE:-node}"

# 需要外部活 gateway 的场景:它们读 E2E_BASE/E2E_PASSWORD 连一个别人起好的服务,
# 没有 gateway 时会红在"连不上"而不是真缺陷 —— 默认跳过,并在汇总里如实报数。
NEEDS_GATEWAY="new_chat.e2e.mjs project-thread.e2e.mjs"

with_gateway=0
filters=()
for a in "$@"; do
  case "$a" in
    --with-gateway) with_gateway=1 ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) filters+=("$a") ;;
  esac
done

matches_filter() {                   # 无 filter 时全收
  [ ${#filters[@]} -eq 0 ] && return 0
  for f in "${filters[@]}"; do [[ "$1" == *"$f"* ]] && return 0; done
  return 1
}

pass=0; fail=0; skip=0
failed_names=(); skipped_names=()
log_dir="$(mktemp -d -t ds-e2e-XXXXXX)"

run_one() {                          # $1=文件路径  $2=解释器
  local file="$1" runner="$2" name; name="$(basename "$file")"
  local log="$log_dir/$name.log" t0 t1
  t0=$SECONDS
  if "$runner" "$file" >"$log" 2>&1; then
    t1=$((SECONDS - t0)); printf '  \033[32mPASS\033[0m  %-34s %3ds\n' "$name" "$t1"
    pass=$((pass + 1))
  else
    t1=$((SECONDS - t0)); printf '  \033[31mFAIL\033[0m  %-34s %3ds   %s\n' "$name" "$t1" "$log"
    fail=$((fail + 1)); failed_names+=("$name")
  fi
}

echo "== e2e 总跑(仓库根 $(pwd))"
[ ${#filters[@]} -gt 0 ] && echo "   只跑名字含:${filters[*]}"
echo

for file in tests/e2e/*.e2e.py tests/e2e/*.e2e.mjs; do
  [ -e "$file" ] || continue         # glob 没命中时不要把字面量当文件
  name="$(basename "$file")"
  matches_filter "$name" || continue

  if [[ " $NEEDS_GATEWAY " == *" $name "* ]] && [ "$with_gateway" -eq 0 ]; then
    printf '  \033[33mSKIP\033[0m  %-34s       需要活 gateway,加 --with-gateway 才跑\n' "$name"
    skip=$((skip + 1)); skipped_names+=("$name"); continue
  fi

  case "$name" in
    *.py)  run_one "$file" "$PY" ;;
    *.mjs) run_one "$file" "$NODE" ;;
  esac
done

echo
echo "== 汇总:${pass} PASS / ${fail} FAIL / ${skip} SKIP"
# SKIP 单独列出来,不并进 PASS —— 「没跑」和「跑过且绿」是两件事,混在一起就是假绿。
if [ "$skip" -gt 0 ]; then
  echo "   未跑(不算通过):${skipped_names[*]}"
fi
if [ "$fail" -gt 0 ]; then
  echo "   红的:${failed_names[*]}"
  echo "   日志在 $log_dir"
  exit 1
fi
rm -rf "$log_dir"
echo "   全绿。"
