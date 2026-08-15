#!/usr/bin/env bash
# 【总跑开关】一条命令跑完本仓库全部四套自动检查。改完东西、收货前跑这一条就够。
#
# 存在的理由(2026-08-06):在此之前本仓库有两个 runner(`tests/e2e/run-all.sh`、
# `tests/mcp-gate.sh`),**互不调用**,也都不跑 `node --test` 和 python 全量 ——
# 全靠人记得挨个跑。于是同一种病连犯三次:
#   08-02  30 个 e2e 没人跑,adoption.e2e.py 红了 6 天  → 建 tests/e2e/run-all.sh
#   08-03  MCP 契约闸整块 SKIP,汇总照印 "836 passed"   → 建 tests/mcp-gate.sh
#   08-05  发现 mcp-gate.sh 自己是个孤儿脚本,没有任何总跑调它,又烂了两天
# 病根不是缺哪一条检查,是**缺一个把它们全串起来的入口**。这就是那个入口。
#
# ── 假绿的两种已知形态,这个脚本专门冲它们来 ────────────────────────────
# ① SKIP 不是 PASS。「没跑」和「跑过且绿」是两件事,混进一个数字就是假绿。
#    本脚本把每段的 SKIP 单独列出来,并且**只要有一条没跑,汇总就不说"全绿"**
#    (退出码 3),不给"看着挺绿的"留门。
# ② 解释器缺包 ⇒ 整块闸静默跳过。08-05 实证:收货记录写着 "python 866/0",
#    而那是系统 `python3` 没装 mcp,工具表快照闸整块 SKIP、汇总照印 OK,
#    真相是它红了两天。所以这里的 python **解释器写死成 venv**,
#    不给系统 python3 留门;要换解释器只能显式 `PY=... tests/run-all.sh`。
#
# 用法:
#   tests/run-all.sh                 # 四段全跑(约 6 分钟);两条要活 gateway 的 e2e 记 SKIP
#   tests/run-all.sh --with-gateway  # 连那两条也跑(先按 tests/e2e/README.md 把 gateway 起起来)
#   PY=<python> tests/run-all.sh     # 换 python(Windows 真机:...\Scripts\python.exe)
#
# 退出码:0 = 四段全跑且全绿   1 = 有红   3 = 没红,但有没跑的(**不算通过**)
set -uo pipefail

cd "$(dirname "$0")/.."                   # 仓库根
PY="${PY:-/root/.venvs/design-studio/bin/python}"; export PY   # mcp-gate.sh 从环境里读
NODE="${NODE:-node}"

with_gateway=0
for a in "$@"; do
  case "$a" in
    --with-gateway) with_gateway=1 ;;
    -h|--help) sed -n '1,/^set -uo/p' "$0" | sed '$d'; exit 0 ;;
    *) echo "未知参数:$a(只认 --with-gateway)" >&2; exit 2 ;;
  esac
done

log_dir="$(mktemp -d -t ds-all-XXXXXX)"
names=(); rcs=(); notes=(); logs=()
n_fail=0; n_skip=0

# run_seg <显示名> <日志文件名> <命令...>
# 跑完不早退 —— 四段各自的结果一次看全,比"红在第一段就停"更有用。
# 跑完把这一段的 rc 和日志路径留在 LAST_RC / LAST_LOG 里,给下面的解析用。
run_seg() {
  local name="$1" slug="$2"; shift 2
  local log="$log_dir/$slug.log" t0=$SECONDS rc
  printf '\033[1m== %s\033[0m\n' "$name"
  "$@" >"$log" 2>&1; rc=$?
  names+=("$name"); rcs+=("$rc"); logs+=("$log")
  LAST_RC=$rc; LAST_LOG="$log"
  printf '   %s  %ds\n' "$([ $rc -eq 0 ] && printf '\033[32m完成\033[0m' || printf '\033[31m有红\033[0m')" $((SECONDS - t0))
  [ $rc -ne 0 ] && n_fail=$((n_fail + 1))
  return 0
}

# 每段跑完各自解析"这段有没有没跑的",结果记进 notes(与 names 同下标)。
note_last() { notes+=("$1"); [ -n "${2:-}" ] && n_skip=$((n_skip + $2)); return 0; }

# ── ① node 单测 ────────────────────────────────────────────────────────
run_seg "node 单测(tests/*.mjs)" node-unit $NODE --test tests/*.mjs
_l="$LAST_LOG"
_pass=$(grep -m1 '^# pass '    "$_l" | awk '{print $3}'); _pass="${_pass:-?}"
_skp=$(grep -m1 '^# skipped ' "$_l" | awk '{print $3}'); _skp="${_skp:-0}"
_todo=$(grep -m1 '^# todo '   "$_l" | awk '{print $3}'); _todo="${_todo:-0}"
note_last "${_pass} 通过 / ${_skp} 跳过 / ${_todo} todo" $((_skp + _todo))

# ── ② python 全量(解释器写死,见文件头形态②)────────────────────────
# python 全量 **走死断言闸的替身**(一次跑、两个信号,2026-08-07):
# 它在 sys.monitoring 下跑同一套判据,顺带记下"哪条断言从没被执行过" ——
# 那是判据最阴的一种失效(断言在那儿、却压根没被问出口,而每一层看到的都是绿的)。
# 单独当一段要多花 4 分半,而**慢到会被跳过的检查等于没有**,所以合并进这一段。
# `DS_SHELL_E2E=1`:S1b 给 `test_ds_shell_core.py` 加的两条**两腿真联跑**判据默认 skip
# (慢、要起 nanobot)。08-15 发现它们从 08-13 落地起就没被任何总跑叫起来过 ——
# 12 条断言一次没执行,而死断言闸每次都在喊,只是没人跑总跑所以没人听见。
# 这正是这个脚本文件头列的第 ③ 次复发:**默认关掉的检查等于没有检查**。
run_seg "python 全量 + 死断言闸($PY)" py-full env DS_SHELL_E2E=1 "$PY" tests/dead_assertions.py
_l="$LAST_LOG"
_ran=$(grep -oE '^Ran [0-9]+ test' "$_l" | tail -1 | awk '{print $2}'); _ran="${_ran:-?}"
_skp=$(grep -oE 'skipped=[0-9]+' "$_l" | tail -1 | cut -d= -f2); _skp="${_skp:-0}"
_dead=$(grep -oE '[0-9]+ 条断言一次都没执行过' "$_l" | head -1 | awk '{print $1}')
note_last "${_ran} 跑过 / ${_skp} 跳过${_dead:+ / ⚠️ ${_dead} 条死断言}" "$_skp"

# ── ③ MCP 契约闸(没装 mcp 直接红,不静默跳)──────────────────────────
run_seg "MCP 契约闸" mcp-gate tests/mcp-gate.sh
note_last "$([ "$LAST_RC" -eq 0 ] && echo '三条闸全绿' || echo '见日志')"

# ── ④ dist 新鲜度:入库的前端产物必须与源码同步 ────────────────────────
# 2026-08-06 两次被它咬:一次是 vite 产物按内容改名导致恢复不干净;
# 一次是我改完 api.ts 的错误文案**没重新 build**,而 e2e 恰好没断言那几句话 ——
# 入库的 dist 里根本没有新文案(是一条撞了额度上限、日志只写到一半的评审腿抓到的)。
# 本机铁律:**盘上和运行时对不上 = BLOCK**。这里就是那道闸:重新 build,
# 然后要求 git 对 web/dist 无话可说。
run_seg "dist 新鲜度(重新 build 后 git 应无差异)" dist-fresh \
  bash -c 'cd web && npm run build >/dev/null 2>&1 && cd .. && \
           test -z "$(git status --porcelain -- web/dist)"'
note_last "$([ "$LAST_RC" -eq 0 ] && echo "与源码同步" || echo "**入库的 dist 是旧的** —— 跑一次 npm run build 再提交")"

# ── ④ e2e 总跑 ─────────────────────────────────────────────────────────
e2e_args=(); [ "$with_gateway" -eq 1 ] && e2e_args+=(--with-gateway)
run_seg "e2e 总跑$([ "$with_gateway" -eq 1 ] && echo '(含 gateway)')" e2e tests/e2e/run-all.sh ${e2e_args[@]+"${e2e_args[@]}"}
_l="$LAST_LOG"
_sum=$(grep -m1 '^== 汇总:' "$_l" | sed 's/^== 汇总://')
_skp=$(printf '%s' "$_sum" | grep -oE '[0-9]+ SKIP' | awk '{print $1}'); _skp="${_skp:-0}"
note_last "${_sum:-见日志}" "$_skp"

# ── 汇总 ───────────────────────────────────────────────────────────────
echo
echo "════ 总跑汇总 ════"
for i in "${!names[@]}"; do
  if [ "${rcs[$i]}" -eq 0 ]; then mark=$'\033[32mPASS\033[0m'; else mark=$'\033[31mFAIL\033[0m'; fi
  printf '  %b  %-34s %s\n' "$mark" "${names[$i]}" "${notes[$i]}"
done
echo

if [ "$n_fail" -gt 0 ]; then
  echo "有 ${n_fail} 段红了,日志在 $log_dir"
  for i in "${!names[@]}"; do [ "${rcs[$i]}" -ne 0 ] && echo "   ${names[$i]} → ${logs[$i]}"; done
  exit 1
fi
if [ "$n_skip" -gt 0 ]; then
  # 这里**故意**不说"全绿":没跑的东西不许算通过(文件头形态①)。
  echo "没有红的,但有 ${n_skip} 条没跑 —— 不算通过。"
  echo "   要跑那两条 e2e:先按 tests/e2e/README.md 起 gateway,再 tests/run-all.sh --with-gateway"
  echo "   日志在 $log_dir"
  exit 3
fi
rm -rf "$log_dir"
echo "四段全跑,全绿。"
