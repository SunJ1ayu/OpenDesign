#!/usr/bin/env bash
# 红检 —— 证明 tests/e2e/update_notice.e2e.mjs 咬得动(track opendesign-in-app-update)。
#
# 🔴 为什么这一份要单独写:那条 e2e **写出来就是绿的**(它验的是已经做好的界面),
#    而"写出来就绿的判据"和"永远绿的判据"在屏幕上长得一模一样。第二轮的 t12 已经
#    栽过同一个形状 —— 值不值钱靠红检证明,不靠它自己说。
#
# 与 mutation-update-ui.sh 的区别:那份只改 web/src/update.ts 跑 node --test(秒级);
# 这份要改**渲染侧**(Sidebar.tsx / update.ts),而 e2e 跑的是 web/dist ——
# 所以每条变异都必须**重新 build**,否则改了源码而 e2e 跑的还是旧产物 = 假漏网。
# (dist 新鲜度那道闸治的就是这件事,这里是它的同一条道理。)
set -u
cd "$(dirname "$0")/.."
ORACLE=tests/e2e/update_notice.e2e.mjs
WORK="$(mktemp -d)"
cp -p web/src/update.ts "$WORK/update.ts.orig"
cp -p web/src/workspace/Sidebar.tsx "$WORK/Sidebar.tsx.orig"
cp -r web/dist "$WORK/dist.orig"
restore() {
  cp -p "$WORK/update.ts.orig" web/src/update.ts
  cp -p "$WORK/Sidebar.tsx.orig" web/src/workspace/Sidebar.tsx
  rm -rf web/dist && cp -r "$WORK/dist.orig" web/dist
}
trap 'restore; rm -rf "$WORK"' EXIT

bites=0; escapes=0
mutate_and_expect() {  # <id> <期望红的那一格(定长子串)> <文件> <old> <new>
  local id="$1" target="$2" file="$3" old="$4" new="$5"
  restore
  python3 - "$file" "$old" "$new" <<'PYEOF' || { echo "  [BAD]  $id 变异没打上去(靶子文本没匹配到)"; escapes=$((escapes+1)); return; }
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding="utf-8")
old, new = sys.argv[2], sys.argv[3]
if s.count(old) != 1:
    print(f"    锚点出现 {s.count(old)} 次,不是 1 次:{old!r}")
    sys.exit(1)
p.write_text(s.replace(old, new), encoding="utf-8")
PYEOF
  local out="$WORK/mut-$id.txt"
  ( cd web && npm run build ) > "$WORK/build-$id.txt" 2>&1 || {
    echo "  [BAD]  $id build 挂了(变异让它编译不过 ⇒ 这条变异问不出东西)"
    grep -E 'error TS|error:' "$WORK/build-$id.txt" | head -3 | sed 's/^/      /'
    escapes=$((escapes+1)); return; }
  node "$ORACLE" > "$out" 2>&1
  # 定长匹配:标签里有括号和引号,当正则会走样(mutation-update-ui.sh 那边实测踩过)
  if grep -F -- "$target" "$out" | grep -q '^  FAIL:'; then
    echo "  [咬住] $id → $target"; bites=$((bites+1))
  elif grep -q '^全部通过$' "$out"; then
    echo "  [漏网] $id e2e 全绿 —— $target 没咬住"; escapes=$((escapes+1))
  else
    echo "  [红在别处] $id 红了,但不是 $target"
    grep '^  FAIL:' "$out" | head -3 | sed 's/^/      实际红的:/'
    escapes=$((escapes+1))
  fi
}

echo "== 红检 tests/e2e/update_notice.e2e.mjs(每条都重新 build)=="

# e1 🔴 蓝点整个不画出来 —— 0.91 那次的形状:功能都对,就是没出现在业主眼前
mutate_and_expect e1 "设置那一行上有蓝点" web/src/update.ts \
  '  return !!info && info.update_available === true;' \
  '  return !!info && false;'

# e2 蓝点的悬停说明退回拼版本号(MR-2 修的那处)
# (靶子放在 badgeTitle 体内而不是 JSX 上:把 JSX 那处改掉会让 badgeTitle 的 import
#  变成未使用 ⇒ tsc 直接编译不过,那种变异什么也问不出来。)
mutate_and_expect e2 "蓝点的悬停说明印成" web/src/update.ts \
  '  return v ? `有新版 ${v}` : "有新版";' \
  '  return `有新版 ${v}`;'

# e3 下载行不再用 GitHub 给的地址(F1 那个 404 的老路)
# (闸把 GitHub 给的地址错杀 ⇒ 退回发布页常量:业主还是有地方可点,但点到的不是那一版。)
mutate_and_expect e3 "下载行指向 GitHub 给的发布页" web/src/update.ts \
  'const RELEASE_URL_RE = /^https:\/\/github\.com\/SunJ1ayu\/OpenDesign\/releases\//;' \
  'const RELEASE_URL_RE = /^https:\/\/never\.example\/releases\//;'

# e4 更新说明退回"取第一行"(标题会被当成正文印给业主)
mutate_and_expect e4 "说明取的是正文而不是" web/src/update.ts \
  '    if (isHeading) continue;' \
  '    if (isHeading && false) continue;'

restore
echo "== 咬住 $bites 条 / 漏网 $escapes 条"
[ "$escapes" -eq 0 ]
