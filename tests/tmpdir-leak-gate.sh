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
#   tests/tmpdir-leak-gate.sh -- <命令...>              # 跑完必须剩 0,否则 rc=9
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

# ── 量具开工前先量一次自己(2026-08-18,四审两腿各自独立指到这里)──────────
# 两条失败路径都会让这道闸**无声地永远绿**,而它守的正是"盘要满了"这种场景:
#   ① `mktemp -d` 失败(盘满 / TMPDIR 不可写)⇒ $probe 是空串 ⇒ TMPDIR="" 回落真 /tmp
#      ⇒ `find ""` 报错被 2>/dev/null 吞掉 ⇒ 数出 0 个 ⇒ 报"干净"。
#   ② 数台面用的 `find -printf`/`-mindepth` 是 GNU 扩展、`mapfile` 要 bash≥4。
#      换个用户态(BSD/macOS)它们直接报错,stderr 同样被吞 ⇒ 同样数出 0 个。
# 一道会无声瞎掉的闸比没有闸更坏 —— 它让每一次真泄漏都变成"看着挺绿的"。
# 所以:先放一个哨兵,确认这套数法真的数得出来,数不出来就**拒跑**(rc=2,不是绿)。
if [ -z "$probe" ] || [ ! -d "$probe" ]; then
  echo "✗ 泄漏闸:台面没建起来(mktemp 失败?盘满了?)—— 拒跑。" >&2
  echo "  '数不出来' 不等于 '干净',这道闸不许在瞎的时候放行。" >&2
  exit 2
fi
# mkdir 单独判:它失败是**另一种病**(台面建起来了但写不进去 —— 只读挂载、配额满、
# SELinux),和"数法不管用"的修法完全不同。混在下面那条里报,会把人支到 find/mapfile
# 那条死路上去查。(2026-08-18 四审 subkimi 6)
if ! mkdir -p "$probe/.ds-leak-sentinel" 2>/dev/null; then
  echo "✗ 泄漏闸:台面建起来了、却往里写不进东西($probe)—— 拒跑。" >&2
  echo "  只读挂载?配额满?这跟「数法不管用」是两种病,别去查 find/mapfile。" >&2
  rm -rf "$probe" 2>/dev/null
  exit 2
fi

# ⚠️ `_selfcheck=()` 这一行**不是多余的防御**,少了它这道闸会**报绿**。
# 2026-08-18 红检实测(判据 ⑭):`mapfile` 内建不在的时候 ——
#   ① mapfile 报 command not found,`_selfcheck` 从没被赋过值;
#   ② `${#_selfcheck[@]}` 在 set -u 下确实报 unbound variable,**但它长在 `if [ ]`
#      的条件里,没能让脚本停下**,只被当成"条件为假";
#   ③ 控制流于是穿过整个自检,落到下面正常流程的 `mapfile -t left`,
#      而那里的 `${left[@]+"${left[@]}"}` 守卫把"数不出来"安静地当成"台面上什么都没有";
#   ④ n=0 ⇒ 干净 ⇒ **rc=0**。
# 上一轮四审三腿一致说这个洞"堵上了" —— 堵住的只是 mktemp 那条,这条从没堵住过。
_selfcheck=()
mapfile -t _selfcheck < <(find "$probe" -mindepth 1 -maxdepth 1 -printf '%f\n' 2>/dev/null | sort)
if [ "${#_selfcheck[@]}" -ne 1 ] || [ "${_selfcheck[0]:-}" != ".ds-leak-sentinel" ]; then
  echo "✗ 泄漏闸自检没过:这台机器上数不出台面里的东西" >&2
  echo "  (find -printf / find -mindepth / mapfile —— 都是 GNU + bash≥4 才有的)。" >&2
  echo "  照跑下去它会对一切泄漏说「剩 0」—— 拒跑,rc=2。" >&2
  rm -rf "$probe"
  exit 2
fi
rmdir "$probe/.ds-leak-sentinel"

# 收台面 —— 但**被测命令红了就不收**。
# 2026-08-17 头一次真跑就栽在这:e2e 段红了两条,而它的详细日志正落在台面里
# (它自己故意在失败时保留日志给人看),台面一收,**排查线索当场没了**,
# 汇总里那两行日志路径全指向已经不存在的目录。
# 一道会毁掉现场的闸,比没有闸更坏 —— 它让每次真失败都变难查。
cleanup_probe() {
  [ "$keep" -eq 1 ] && return 0
  # 空台面一律收掉 —— 哪怕命令红了。留一个空目录只是给 /tmp 添新垃圾,
  # 而这道闸的全部意义就是别往 /tmp 添垃圾。
  if [ -z "$(ls -A "$probe" 2>/dev/null)" ]; then rm -rf "$probe"; return 0; fi
  if [ "${cmd_rc:-0}" -ne 0 ]; then
    echo "  (被测命令红了,台面留着供排查:$probe)" >&2
    return 0
  fi
  rm -rf "$probe"                                  # 命令绿了但漏了:上面已把前缀报全,不留现场
}

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
