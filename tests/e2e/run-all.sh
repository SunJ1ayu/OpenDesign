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
# 开跑之前先过一道**产物新鲜度闸**(check-dist-fresh.sh,约 3 秒):把当前前端源码
# build 一遍,与 web/dist 逐字节比对。对不上就中止 —— 那种情形下跑出来的绿是假的,
# 验的不是你改的那份代码。它只报告不修复,web/dist 一个字节都不碰。
#
# 退出码:有任何一条 FAIL 就非 0。**SKIP 永远不算 PASS**(见下方汇总)。
set -uo pipefail

cd "$(dirname "$0")/../.."          # 仓库根
PY="${PY:-python3}"
NODE="${NODE:-node}"

# 需要外部活 gateway 的场景:它们读 E2E_BASE 连一个别人起好的服务(口令不用给 ——
# T2 起 ds-web 替前端代签,见 helpers.waitConnected),
# 没有 gateway 时会红在"连不上"而不是真缺陷 —— 默认跳过,并在汇总里如实报数。
NEEDS_GATEWAY="new_chat.e2e.mjs project-thread.e2e.mjs"

with_gateway=0
filters=()
for a in "$@"; do
  case "$a" in
    --with-gateway) with_gateway=1 ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
    *) filters+=("$a") ;;
  esac
done

# ── 产物新鲜度闸(2026-08-24,track opendesign-dist-freshness-gate)────────────
# e2e 跑的是 `web/dist`,不是 `web/src`。两者对不上时,「你以为验了你改的代码,
# 其实没有」—— 而且全绿,从收据上看不出来。0.91→0.93 三个包就一直是这个状态。
#
# 这道闸**比产物**:把当前源码 build 到仓外临时目录,与 web/dist 逐字节对。
# 它替换掉的旧闸(原先只装在 llm_key.e2e.mjs 一个场景里)比的是 mtime ——
# 那个指标会误报(改注释/切分支/复制),更会**漏报**(src 改了而 dist mtime
# 因无关动作变新 ⇒ 闸绿而产物是旧的)。而且 37 个前端 e2e 里它只守了 1 个。
#
# ⚠️ 放在这里、放在场景循环**之前**,而且 rc 直接用 `if !` 接 ——
#    **不许 `;` 接、不许进管道**(那两种写法会吞掉退出码,这个项目栽过五次)。
if ! tests/e2e/check-dist-fresh.sh; then
  echo
  echo "== 总跑中止:前端产物与源码不一致,再往下跑出来的绿是假的。" >&2
  exit 1
fi

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
# 名字里带 -log- 是**故意的**:这个目录**红了**会被留下给人看(见文件尾),
# 是"故意保留",不是泄漏,所以泄漏闸放行它。而同目录下的 `ds-e2e-home-`(E2E_HOME)
# 是真漏、必须被闸咬住 —— 两者要是共用 `ds-e2e-` 前缀,放行一个就会连另一个一起放过,
# 那道闸就对 E2E_HOME 永远瞎了。改名的唯一目的就是让放行范围咬得准。
# ⚠️ 2026-08-18 这句话变过一次:原来写的是「红/**有跳过**时会留下」,而同一天
#    文件尾已经改成「只跳过就收掉」—— 孪生说明 tests/run-all.sh:141-147 改了、
#    这一份漏了,四审当场抓到「同页自相矛盾」。改行为就得回来改这句。
log_dir="$(mktemp -d -t ds-e2e-log-XXXXXX)"

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
# 收摊。2026-08-17:这个假家目录从来没人收,清理前 /tmp 里堆了 62 个。
# trap 紧贴 mktemp 而不是写在文件尾 —— 下面那个"接不上 chromium 缓存就 exit 2"
# 的早退路径也得收干净,写在尾巴上它就漏了。
#
# ⚠️ 看着危险其实不危险:下面会往 $E2E_HOME/.cache 里放一个**指向真实
#    ~/.cache/ms-playwright 的符号链接**。`rm -rf` 删的是链接本身,不会跟着链接
#    进去删掉那 641M 的真缓存(POSIX 语义:rm 不递归进符号链接)。
#    本机在这上面栽过一次(worktree 里的 node_modules 链接被 merge 带回主仓
#    **覆盖掉真目录**),所以这句话必须留在这儿,别让下一个人再验一遍。
trap 'rm -rf "$E2E_HOME"' EXIT
mkdir -p "$E2E_HOME/.openDesign" "$E2E_HOME/.cache"
printf 'sk-e2e-fixture-not-a-real-key\n' > "$E2E_HOME/.openDesign/key.txt"

# 🔴 chromium 缓存必须接回真实家目录,否则上面这个隔离**自己造出一场大面积假红**:
#    `helpers.chromiumPath()` 用 `os.homedir()` 找 `~/.cache/ms-playwright`,
#    换了 HOME 就是 ENOENT ⇒ 31 条 e2e 在 1 秒内全挂。
#    2026-08-16 实测,那份收据看起来极像"整个前端崩了"——**它第一次就骗到了我**。
#    (辨认特征:每条耗时都 <2s,而真跑一条要几十秒;用真实 HOME 的那两条却是绿的。)
ln -s "$HOME/.cache/ms-playwright" "$E2E_HOME/.cache/ms-playwright" 2>/dev/null || true
# 接不上就**当场喊停**,不许静默滑过去 —— 静默失败正是这次假红的形状
# (同族:`pip --platform` 静默丢依赖、`git add` 对被忽略的文件静默跳过)。
if [ ! -e "$E2E_HOME/.cache/ms-playwright" ]; then
  printf '\033[31m✗\033[0m 接不上 chromium 缓存(%s/.cache/ms-playwright)——\n' "$HOME" >&2
  printf '   照跑下去会是 31 条 e2e 秒挂的假红,不是真劣化。先装 playwright 浏览器。\n' >&2
  exit 2
fi

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
  # 日志目录收掉:一条红的都没有 ⇒ 里面没有要查的东西。
  # 2026-08-18 改。此前这里留着不收、**又不打印路径** —— 等于给 /tmp 添了一个
  # 谁也不知道在哪的目录;而在总跑里它还会被外层泄漏闸放行掉(--allow ds-e2e-log-),
  # 于是"故意留给人看"这句话在任何一条路径上都不成立。红的时候仍然留(见上面)。
  rm -rf "$log_dir"
  echo "   没有红的,但有 ${skip} 条没跑 —— 不算通过。"
  exit 0
fi
rm -rf "$log_dir"
echo "   全绿。"
