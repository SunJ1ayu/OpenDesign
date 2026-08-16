#!/usr/bin/env bash
# 红检 —— 证明「连接身份(slot)」那套判据咬得动(track opendesign-key-onboarding)。
#
# 为什么必须单独跑一轮:判据先行时它们红的是「每列都查不到连接」,那种红只证明
# **标签不存在会响**,不证明**标签打错了会响**。而"打错"恰恰是这次的真实风险:
# 待办列传的是 `variant="home"`,拿 variant 当身份就会和首页撞名(kimi 腿抓到)。
#
# 🔴 前端要重新 build 才作数:e2e 跑的是 web/dist,变异了 src 不 build 等于没变。
# 🔴 chat_reconnect 单跑需要夹具(隔离家目录 + chromium 缓存),否则秒挂 —— 见
#    tests/e2e/run-all.sh 里那两段注释。这里自己造一份,别依赖开发机的家目录。
#
# 用法:tests/mutation-slot.sh [变异号...]   退出码:0 全咬住 / 1 有漏网
set -u
cd "$(dirname "$0")/.."
WORK="$(mktemp -d)"
SRCS=(web/src/chat/connection.ts web/src/workspace/ChatColumn.tsx web/src/TodoRail.tsx)
for s in "${SRCS[@]}"; do cp "$s" "$WORK/$(basename "$s").orig"; done
restore() { for s in "${SRCS[@]}"; do cp "$WORK/$(basename "$s").orig" "$s"; done; }

# 夹具:隔离家目录 + 把 chromium 缓存接回去(接不上就没法跑,当场喊停)
E2E_HOME="$(mktemp -d -t ds-mut-home-XXXXXX)"
mkdir -p "$E2E_HOME/.openDesign" "$E2E_HOME/.cache"
printf 'sk-mutation-fixture\n' > "$E2E_HOME/.openDesign/key.txt"
ln -s "$HOME/.cache/ms-playwright" "$E2E_HOME/.cache/ms-playwright" 2>/dev/null || true
[ -e "$E2E_HOME/.cache/ms-playwright" ] || { echo "接不上 chromium 缓存,红检没法跑"; exit 2; }

trap 'restore; (cd web && npm run build) >/dev/null 2>&1; rm -rf "$WORK" "$E2E_HOME"; echo "(已还原源码并重新 build)"' EXIT
pass=0; fail=0; only=("$@")

wanted() { [ ${#only[@]} -eq 0 ] && return 0; for x in "${only[@]}"; do [ "$x" = "$1" ] && return 0; done; return 1; }

RC_E2E="env HOME=$E2E_HOME USERPROFILE=$E2E_HOME timeout 220 node tests/e2e/chat_reconnect.e2e.mjs"
UNIT="node --test tests/test_chat_connection.mjs"

# mutate <id> <文件> <老串> <新串> <判据命令> <该红在哪一问> <说明>
mutate() {
  local id="$1" file="$2" old="$3" new="$4" oracle="$5" marker="$6" why="$7"
  wanted "$id" || return 0
  restore
  python3 - "$file" "$old" "$new" <<'PY' || { echo "  [BAD]  $id 变异没打上去"; fail=$((fail+1)); return; }
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding="utf-8")
old, new = sys.argv[2], sys.argv[3]
n = s.count(old)
if n == 0: sys.exit(f"变异锚点找不到: {old!r}")
# 锚点不唯一 ⇒ 打错位置会让判据"全绿",而脚本报的是"判据瞎了"。假报警和假绿一样坏。
if n > 1: sys.exit(f"变异锚点不唯一({n} 处): {old!r}")
p.write_text(s.replace(old, new), encoding="utf-8")
PY
  if ! (cd web && npm run build) >"$WORK/build.log" 2>&1; then
    echo "  [BAD]  $id build 没过 —— 这条不算数(见 $WORK/build.log)"; fail=$((fail+1)); return
  fi
  if eval "$oracle" >"$WORK/mut-$id.txt" 2>&1; then
    echo "  [漏网] $id  $why"; fail=$((fail+1))
  elif grep -qF "$marker" "$WORK/mut-$id.txt"; then
    echo "  [咬住] $id  $why"; pass=$((pass+1))
  else
    # 红了但不在靶子上:超时/环境炸/判据自己坏了都长这样,**不算咬住**
    echo "  [存疑] $id  红了但不是红在「$marker」上 —— 见 $WORK/mut-$id.txt"; fail=$((fail+1))
  fi
}

echo "== 红检:连接身份(slot)"

# P1 标签根本不挂 ⇒ 判据回到"分不出哪一列"的老状态
mutate P1 web/src/chat/connection.ts \
  'if (slot) (socket as { __dsSlot?: string }).__dsSlot = slot;' \
  'if (false) (socket as { __dsSlot?: string }).__dsSlot = slot;' \
  "$RC_E2E" \
  "FAIL - 前置:首页那列恰好一条连接" "不挂标签 ⇒ 前置该红"

# 🔴 P2 是本份最该咬住的一条:**身份撞名**。
#    kimi 腿指出待办列传的也是 `variant="home"`,若拿 variant 当身份就会撞;
#    这条模拟工作区列错标成 home ⇒ 首页那列会数到 2。
#    P2 漏网 = 判据只会数"有没有",不会数"是不是这一列"。
mutate P2 web/src/workspace/ChatColumn.tsx \
  'slot="workspace"' 'slot="home"' \
  "$RC_E2E" \
  "FAIL - 前置:首页那列恰好一条连接" "工作区列错标成 home(撞名)⇒ 前置该红"

# P3 身份塞进 ws URL ⇒ 生产协议被测试污染(会原样打到真 gateway)
mutate P3 web/src/chat/connection.ts \
  '      client_id: this.randomId(),' \
  '      client_id: this.randomId(), slot: slot ?? "",' \
  "$UNIT" \
  "身份泄进了 ws URL" "把 slot 塞进 query ⇒ 单测该红"

echo
echo "== 红检小结:${pass} 咬住 / ${fail} 漏网"
[ "$fail" -eq 0 ]
