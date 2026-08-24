#!/usr/bin/env bash
# 产物新鲜度闸 —— 只答一个问题:**`web/dist` 是不是当前 `web/src` build 出来的产物?**
#
# 存在的理由:e2e 跑的是 `web/dist`,不是 `web/src`。两者对不上时,
# 「你以为验了你改的代码,其实没有」—— 而且全绿,看不出来。
#
# 为什么不比 mtime(旧闸的做法,2026-08-24 退场):时间戳是个脆指标。
#   改一行注释 / 切个分支 / 复制一次文件都会把它顶新 ⇒ **误报**;
#   反过来 src 真改了、而 dist 因某个无关动作 mtime 变新 ⇒ **漏报**,闸绿而产物是旧的。
#   **漏报才是致命的那一面**,而它恰恰是这道闸存在的全部理由。
# 为什么不比 src 的内容哈希:哈希把注释也算进去,改注释照样报警 —— 同一个毛病。
# ⇒ 唯一准确的答法是**比产物**:build 一次,逐字节对。实测 build 约 2.5s,付得起。
#
# 它**只报告,不修复**:`web/dist` 一个字节都不碰。「你欠一次 build」这个信号
# 必须留在工作树上被人看见,不能被工具悄悄抹平。
#
# 用法:check-dist-fresh.sh [--web-dir DIR]
# 退出码:0=产物一致;1=不一致 / build 失败 / 前提缺失;64=用法错误。

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WEB_DIR="$REPO/web"

while [ $# -gt 0 ]; do
  case "$1" in
    --web-dir)
      [ $# -ge 2 ] || { echo "--web-dir 后面要跟一个目录" >&2; exit 64; }
      WEB_DIR="$2"; shift 2 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "不认识的参数:$1" >&2; exit 64 ;;
  esac
done

DIST="$WEB_DIR/dist"

[ -d "$WEB_DIR" ] || { echo "🔴 前端目录不存在:$WEB_DIR" >&2; exit 1; }
if [ ! -d "$DIST" ]; then
  echo "🔴 没有 $DIST —— 前端还没 build 过。先:cd web && npm run build" >&2
  exit 1
fi

TMP="$(mktemp -d)" || { echo "🔴 建不了临时目录" >&2; exit 1; }
trap 'rm -rf "$TMP"' EXIT
OUT="$TMP/out"
LOG="$TMP/build.log"

# build 到**仓外**临时目录 —— 绝不碰 web/dist
if ! (cd "$WEB_DIR" && npx vite build --outDir "$OUT" --emptyOutDir) > "$LOG" 2>&1; then
  echo "🔴 前端 build 失败 —— 这一趟 e2e 的前提就不成立,不许当没事发生。" >&2
  echo "   (没装依赖的话:cd web && npm ci)" >&2
  echo "--- build 的最后 30 行 ---" >&2
  tail -30 "$LOG" >&2
  exit 1
fi

# 🔴 build 可能压根没建这个目录(例:配置成不写盘)。补上它,是为了让下面那条
#    「产物数」检查成为**明确的唯一判定** —— 否则 diff 会撞一个难懂的
#    「目录不存在」错误,把红的理由说成另一回事(2026-08-24 红检 M6 当场照出来的)。
mkdir -p "$OUT"
n=$(find "$OUT" -type f | wc -l)
if [ "$n" -eq 0 ]; then
  echo "🔴 build 报了成功,却一个文件都没产出。" >&2
  echo "   这条挡的是「两边都空 ⇒ 比对恒过」—— 那样这道闸会永远绿着、什么都不守。" >&2
  exit 1
fi

if diff -r "$DIST" "$OUT" > "$TMP/diff.txt" 2>&1; then
  echo "✅ 产物新鲜度:web/dist 就是当前源码 build 出来的($n 个文件逐字节一致)"
  exit 0
fi

echo "🔴 web/dist 不是当前源码 build 出来的 —— 这一趟 e2e 验的不是你改的那份代码。" >&2
echo "--- 差在哪(最多 40 行)---" >&2
head -40 "$TMP/diff.txt" >&2
echo "--- 怎么办 ---" >&2
echo "   cd web && npm run build   然后把 web/dist 一起提交。" >&2
echo "   (要是只改了注释,build 出来会逐字节一样,这道闸自己就绿了。)" >&2
exit 1
