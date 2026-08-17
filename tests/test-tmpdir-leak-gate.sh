#!/usr/bin/env bash
# 【泄漏闸自己的判据】给 tests/tmpdir-leak-gate.sh 用的。
#
# 存在的理由:这道闸是拿来判别人的,那**它自己坏了谁来判**?本仓库栽过的两种形态:
#   ① 量具坏了却去改被测物(08-11);② 假报警和假绿一样坏(变异脚本三次自己坏了)。
# 所以这里把闸的六条行为钉死,尤其是**退出码透传** —— 本仓库四次栽在
# "管道/包装吃掉 rc" 造出假绿收据,这闸正好是个包装,是同一种病的高发处。
#
# 用法:tests/test-tmpdir-leak-gate.sh     退出码 0 = 六条全过
set -uo pipefail
cd "$(dirname "$0")/.."
G=tests/tmpdir-leak-gate.sh
fail=0

# check <编号> <说明> <期望rc> <命令...>
check() {
  local id="$1" desc="$2" want="$3"; shift 3
  "$@" >/dev/null 2>&1; local got=$?
  if [ "$got" -eq "$want" ]; then
    printf '  \033[32mPASS\033[0m  %s %s (rc=%s)\n' "$id" "$desc" "$got"
  else
    printf '  \033[31mFAIL\033[0m  %s %s —— 期望 rc=%s,实得 rc=%s\n' "$id" "$desc" "$want" "$got"
    fail=$((fail + 1))
  fi
}

echo "== 泄漏闸自测 =="

# 命令自己的 rc 要原样透传:命令红了就报命令的红,别被闸的 1 盖掉 ——
# 盖掉的话"判据挂了"会被误读成"判据漏目录",修错方向。
check ① "命令红了、没漏 → 透传命令 rc" 7 \
  $G -- bash -c 'exit 7'
check ② "命令绿了、漏了 → 闸红 rc=9" 9 \
  $G -- bash -c 'mktemp -d >/dev/null; exit 0'
check ③ "命令红了、也漏了 → 透传命令 rc(先修红的)" 7 \
  $G -- bash -c 'mktemp -d >/dev/null; exit 7'
# ⑧ 是 ② 和 ③ 之间那条界:被测命令**自己**返回 1 时,不许和"漏目录"撞码。
# 撞了的话总跑看到 1 分不清是"判据挂了"还是"判据漏目录",两件事的修法完全不同。
check ⑧ "命令自己 rc=1、没漏 → 透传 1,不许被闸的码盖掉" 1 \
  $G -- bash -c 'exit 1'
check ④ "--allow 放行指定前缀 → 绿" 0 \
  $G --allow keepme- -- bash -c 'mktemp -d -t keepme-XXXXXX >/dev/null; exit 0'
# 放行清单必须是**精确前缀**,不能顺手把别的也放过 —— 放行清单一旦变成垃圾桶,闸就废了。
check ⑤ "--allow 不放行别的前缀 → 红" 9 \
  $G --allow keepme- -- bash -c 'mktemp -d -t other-XXXXXX >/dev/null; exit 0'
check ⑥ "什么都没建 → 绿" 0 \
  $G -- true
# 参数用法错了要红,别默默当成"没东西要跑"就绿了
check ⑦ "没给命令 → rc=2" 2 $G --

echo
if [ "$fail" -eq 0 ]; then echo "泄漏闸自测:八条全过。"; exit 0; fi
echo "泄漏闸自测:${fail} 条红了。"; exit 1
