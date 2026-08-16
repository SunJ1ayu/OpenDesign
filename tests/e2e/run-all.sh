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

# ── --with-gateway 的前置闸(2026-08-16,track opendesign-key-onboarding)──────
# 上面那个隔离家目录**救不了这两条**:它们连的是**别人起好的** ds_web,而决定
# 「弹不弹 key 卡片」的是**那个 ds_web 进程自己的 HOME**,不是这里 node 的 HOME。
# (其余场景自起 ds_web、子进程继承 HOME,所以夹具对它们有效。)
# ⇒ 起服务的人没给它一个「已配置 key」的家目录时,这两条会红在遮罩拦点击上,
#   而那和「聊天真坏了」在收据里长得一模一样 —— 我得从头再查一遍。
#   **环境没准备好要当场说清楚,不许混进判据结果里。**
if [ "$with_gateway" -eq 1 ]; then
  base="${E2E_BASE:-http://127.0.0.1:8768}"
  st="$("$PY" - "$base" <<'PY' 2>/dev/null || true
import json, sys, urllib.request
try:
    with urllib.request.urlopen(sys.argv[1] + "/api/llm/credential", timeout=5) as r:
        print("configured" if json.load(r).get("configured") else "unconfigured")
except Exception:
    print("unreachable")
PY
)"
  case "$st" in
    configured) ;;
    unreachable)
      printf '\033[31m✗\033[0m --with-gateway:连不上 %s 的 ds_web —— 先按 tests/e2e/README.md 起服务\n' "$base" >&2
      exit 2 ;;
    *)
      printf '\033[31m✗\033[0m --with-gateway:%s 那个 ds_web 处于「没配 key」状态\n' "$base" >&2
      printf '   ⇒ 它一开页面就自动弹 key 卡片,遮罩会吃掉这两条 e2e 的所有点击(不是聊天坏了)。\n' >&2
      printf '   修法:起 ds_web 时给它一个有 key 的家目录,例如\n' >&2
      printf '     H=$(mktemp -d); mkdir -p "$H/.openDesign"; echo sk-e2e-fixture > "$H/.openDesign/key.txt"\n' >&2
      printf '     env HOME="$H" USERPROFILE="$H" DS_WEB_PORT=8768 python3 bin/ds_web.py &\n' >&2
      exit 2 ;;
  esac
fi

matches_filter() {                   # 无 filter 时全收
  [ ${#filters[@]} -eq 0 ] && return 0
  for f in "${filters[@]}"; do [[ "$1" == *"$f"* ]] && return 0; done
  return 1
}

pass=0; fail=0; skip=0
failed_names=(); skipped_names=()
log_dir="$(mktemp -d -t ds-e2e-XXXXXX)"

# ── 隔离家目录(2026-08-16,track opendesign-key-onboarding)────────────────
# 起因:T4 起 ds-web 在「没配大模型 key」时会自动弹一张模态卡片,遮罩盖住整个界面。
# 那是给业主的**正确**行为(装完第一次打开就有得填),但这些场景测的是别的功能,
# 它们的点击会被遮罩拦下(`connect-modal-mask intercepts pointer events`),十几条一起红。
#
# 为什么以前没事:这些场景用 `...process.env` 继承**开发机的真实 HOME** ——
# 而开发机的 key 不在 `~/.openDesign/key.txt`(它走 mimocode 的 auth.json),
# 所以 ds-web 判定"没配"。业主机器不受影响(Windows 上 ds-nanobot.ps1 就是从
# key.txt 读的 ⇒ 判定"已配置")。
#
# ⇒ 给它们一个**隔离的家目录**并预置一把假 key,让它们回到"已配置"这个常态下测别的东西。
# 顺带修掉一个一直存在的隐患:这些场景本来就依赖开发机的家目录状态,不该那样。
# 🔴 单独跑某一条时不经过这里 ⇒ 会被卡片挡住。要单跑就自己带上:
#      HOME=$(mktemp -d) 且在里面放 .openDesign/key.txt
E2E_HOME="$(mktemp -d -t ds-e2e-home-XXXXXX)"
mkdir -p "$E2E_HOME/.openDesign"
printf 'sk-e2e-fixture-not-a-real-key\n' > "$E2E_HOME/.openDesign/key.txt"

run_one() {                          # $1=文件路径  $2=解释器  $3=1 表示要真实 HOME
  local file="$1" runner="$2" real_home="${3:-0}" name; name="$(basename "$file")"
  local log="$log_dir/$name.log" t0 t1
  t0=$SECONDS
  # 要活 gateway 的那两条连的是别人起好的真服务,得留在真实家目录里。
  if [ "$real_home" = "1" ]; then
    run_env=(env)
  else
    run_env=(env "HOME=$E2E_HOME" "USERPROFILE=$E2E_HOME")
  fi
  if "${run_env[@]}" "$runner" "$file" >"$log" 2>&1; then
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

  real_home=0
  [[ " $NEEDS_GATEWAY " == *" $name "* ]] && real_home=1
  case "$name" in
    *.py)  run_one "$file" "$PY" "$real_home" ;;
    *.mjs) run_one "$file" "$NODE" "$real_home" ;;
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
# 有 SKIP 时**不许**说"全绿" —— 上一行刚写完"不算通过",下一行又说全绿,
# 就是同页自相矛盾(08-06 修)。总跑 tests/run-all.sh 靠上面那行汇总数 SKIP。
if [ "$skip" -gt 0 ]; then
  echo "   没有红的,但有 ${skip} 条没跑 —— 不算通过。"
  exit 0
fi
rm -rf "$log_dir"
echo "   全绿。"
