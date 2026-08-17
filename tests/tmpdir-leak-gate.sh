#!/usr/bin/env bash
# 【临时目录泄漏闸】把一条命令跑在一块**空的临时台面**上,跑完数台面上还剩几个。
#
# 存在的理由(2026-08-17):业主报「磁盘满了」。50G 盘用到 94%,`/tmp` 里
# **205,666 个条目 / 6.5G**,几乎全是本仓库判据 `mkdtemp` 出来又没人收的空壳目录。
# 最早的 7-27、最新的就在排查当天 —— 不是历史遗留,是**水龙头一直开着**:
# 光那天一轮 `run-all.sh --with-gateway` 就新增约 1.7 万个。
#
# ── 为什么是"数台面"而不是"扫代码" ────────────────────────────────────
# 扫代码(grep mkdtemp 附近有没有 rmtree)这条路我先走过,**当场翻车两次**:
#   ① `test_ds_web_upload.py` 里有一堆 addCleanup,按文件判是"干净的" ——
#      而它的 `_mkdist()` 把目录当参数直接传进去,没人接、没人收,实测漏了 3678 个。
#   ② 反过来 31 个 `.mjs` 判据被判成"漏",实测每个只剩 1 个(上次跑崩的残渣),是干净的。
# 病根:**"文件里出现过清理代码" 回答不了 "这一处建的目录有没有被收"**。
# 所以这道闸只问一个能被机器直接量出来的问题:**跑完,台面上还剩几个?**
# 断言是行为断言,不是模式匹配 —— 想让它绿只有一条路:真把目录收干净。
#
# ── 底噪实测(2026-08-17,别改成"允许剩几个") ─────────────────────────
#   收干净的判据 `test_ds_organize`  跑完剩 **0** 个
#   漏的判据     `test_ds_web_api`   跑一次剩 **201** 个
# 底噪就是 0(unittest / node --test 自己不建临时目录),所以这里断言的是**剩 0**,
# 不留"允许少量残留"的余量 —— 留了余量,漏就能藏在余量里慢慢长。
#
# 用法:
#   tests/tmpdir-leak-gate.sh -- <命令...>              # 跑完必须剩 0,否则 rc=1
#   tests/tmpdir-leak-gate.sh --allow foo- -- <命令...> # 放行前缀 foo-(要写理由,见下)
#   tests/tmpdir-leak-gate.sh --keep -- <命令...>       # 红了保留台面供排查
#
# 退出码:0 = 命令绿且台面干净
#         9 = **命令绿了、但漏了目录**(这道闸自己的红)
#         其他 = 命令自己的 rc,原样透传
#
# ⚠️ 为什么漏目录用 9 而不是 1:1 是被测命令最常见的失败码,混用就**分不清
#    「判据挂了」和「判据漏目录了」** —— 而这两件事的修法完全不同,认错就修错方向。
#    本仓库四次栽在"退出码被吃掉/被盖掉造出假收据",这里不留这个模糊。
#
# ⚠️ `--allow` 是给**故意保留**用的(例:总跑红了留日志目录给人看),不是给"暂时先放过"用的。
#    每加一条都要在调用处写清楚为什么它该被留下 —— 放行清单一旦当垃圾桶用,这道闸就废了。
set -uo pipefail

allow=(); keep=0
while [ $# -gt 0 ]; do
  case "$1" in
    --allow) allow+=("$2"); shift 2 ;;
    --keep)  keep=1; shift ;;
    --) shift; break ;;
    -h|--help) sed -n '1,/^set -uo/p' "$0" | sed '$d'; exit 0 ;;
    *) echo "未知参数:$1(要跑的命令写在 -- 后面)" >&2; exit 2 ;;
  esac
done
[ $# -eq 0 ] && { echo "没给要跑的命令:tmpdir-leak-gate.sh [--allow 前缀]... -- <命令...>" >&2; exit 2; }

probe="$(mktemp -d -t ds-leakprobe-XXXXXX)"        # 台面本身建在外面的 TMPDIR 里
cleanup_probe() { [ "$keep" -eq 1 ] || rm -rf "$probe"; }

# 跑被测命令。**rc 必须原样接住** —— 本仓库栽过四次"管道吃掉退出码"造出假绿收据,
# 所以这里不接管道、不套 `; echo rc=$?`,直接赋值。
TMPDIR="$probe" TMP="$probe" TEMP="$probe" "$@"
cmd_rc=$?

# 数台面。用 -mindepth 1 -maxdepth 1:只数直接摆在台面上的,不递归进去。
mapfile -t left < <(find "$probe" -mindepth 1 -maxdepth 1 -printf '%f\n' 2>/dev/null | sort)

# 放行清单:前缀匹配
kept=()
for name in ${left[@]+"${left[@]}"}; do
  ok=0
  for a in ${allow[@]+"${allow[@]}"}; do case "$name" in "$a"*) ok=1; break ;; esac; done
  [ "$ok" -eq 0 ] && kept+=("$name")
done

n=${#kept[@]}
if [ "$n" -eq 0 ]; then
  cleanup_probe
  exit "$cmd_rc"                                   # 台面干净 —— 把命令自己的 rc 透传出去
fi

# 有残留:按前缀归并报出来,直接指向是谁漏的
echo >&2
kinds=$(printf '%s\n' "${kept[@]}" | sed -E 's/[^_-]*$//' | sort -u | wc -l)
echo "════ 临时目录泄漏闸:台面上剩了 ${n} 个(${kinds} 种前缀)════" >&2
printf '%s\n' "${kept[@]}" | sed -E 's/[^_-]*$//' | sort | uniq -c | sort -rn | head -40 >&2
# 前缀种类比列出来的多时说清楚,别让人以为报全了 —— 藏起来的那几种正是最容易漏改的。
[ "$kinds" -gt 40 ] && echo "  …还有 $((kinds - 40)) 种前缀没列出来" >&2
echo >&2
echo "  这些是判据建了又没收的东西。按前缀去 tests/ 里搜就能找到调用点。" >&2
echo "  ⚠️ 未必都是 mkdtemp 建的目录 —— 也可能是**直接落在 TMPDIR 上的文件**" >&2
echo "     (实例:test_ds_web.py 的逃逸诱饵 \`secret-*\`,搜 mkdtemp 永远找不到它)。" >&2
echo "  python:  self.addCleanup(shutil.rmtree, <目录>, ignore_errors=True)" >&2
echo "  node:    process.on(\"exit\", () => rmSync(<目录>, {recursive:true, force:true}))" >&2
echo "  shell:   trap 'rm -rf \"\$DIR\"' EXIT" >&2
[ "$keep" -eq 1 ] && echo "  台面留在:$probe" >&2
cleanup_probe

# 命令自己红了就报它的 rc(先修红的);命令绿但漏了 → 9(见文件头,不用 1)
[ "$cmd_rc" -ne 0 ] && exit "$cmd_rc"
exit 9
