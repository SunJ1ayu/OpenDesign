#!/usr/bin/env bash
# 红检 —— 证明 tests/test_update_ui.mjs 咬得动(track opendesign-in-app-update)。
# 变异被测对象 web/src/update.ts,每条指定靶子,跑完哈希核对还原。
set -u
cd "$(dirname "$0")/.."
SRC=web/src/update.ts
ORACLE=tests/test_update_ui.mjs
WORK="$(mktemp -d)"
BEFORE="$(sha256sum "$SRC" | cut -d' ' -f1)"
cp -p "$SRC" "$WORK/orig.ts"
restore() { cp -p "$WORK/orig.ts" "$SRC"; }
trap 'restore; rm -rf "$WORK"' EXIT

bites=0; escapes=0
mutate_and_expect() {
  local id="$1" target="$2" old="$3" new="$4"
  restore
  python3 - "$SRC" "$old" "$new" <<'PYEOF' || { echo "  [BAD]  $id 变异没打上去(靶子文本没匹配到)"; escapes=$((escapes+1)); return; }
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding="utf-8")
old, new = sys.argv[2], sys.argv[3]
if s.count(old) != 1:
    print(f"    锚点出现 {s.count(old)} 次,不是 1 次:{old!r}")
    sys.exit(1)
p.write_text(s.replace(old, new), encoding="utf-8")
PYEOF
  local out="$WORK/mut-$id.txt"
  node --test "$ORACLE" > "$out" 2>&1
  # 🔴 -F 定长匹配:靶子名里有括号,当正则会变成分组 ⇒ 真咬住的被报成"红在别处"
  #    (2026-09-07 实测踩了一次;本仓记忆里 panel-roster 那单也栽过同一种)。
  if grep -F -- "$target" "$out" | grep -qE '^not ok'; then
    echo "  [咬住] $id → $target"; bites=$((bites+1))
  elif grep -qE '^# fail 0$' "$out"; then
    echo "  [漏网] $id 判据全绿 —— $target 没咬住"; escapes=$((escapes+1))
  else
    echo "  [红在别处] $id 红了,但不是 $target"
    grep -E '^not ok ' "$out" | head -3 | sed 's/^/      实际红的:/'
    escapes=$((escapes+1))
  fi
}

echo "== 红检 web/src/update.ts =="

# v1 🔴 查不动时说"已是最新"(把失败伪装成成功)
mutate_and_expect v1 "u3 🔴 查不动的时候不许说「已是最新」" \
  '  if (info.error) return "查不到更新";' \
  '  if (false) return "查不到更新";'

# v2 点了没反应(这个按钮原来的病)
mutate_and_expect v2 "u4 点下去要有反应(这个按钮原来的病就是没反应)" \
  '  if (s.state === "checking") return "检查中…";' \
  '  if (false) return "检查中…";'

# v3 有新版却不说是哪一版
mutate_and_expect v3 "u1 有新版时,那句话里必须带着版本号" \
  '  if (info.update_available && info.latest) return `有新版 ${info.latest} ›`;' \
  '  if (info.update_available && info.latest) return "有新版 ›";'

# v4 版本口径放宽到单段(和 ds_update.py 不一致)
mutate_and_expect v4 "u8 发布页地址与版本解析口径一致(两段式认,坏形状不认)" \
  'const VERSION_RE = /^\d+(\.\d+){1,3}$/;' \
  'const VERSION_RE = /^\d+(\.\d+){0,3}$/;'

# v5 🔴 开关关了也照样自动往外发
mutate_and_expect v5 "u10 🔴 显式关掉之后就不许再自动往外发请求" \
  '  return prefs[AUTO_CHECK_PREF] !== false;' \
  '  return true;'

# v6 更新说明不洗 markdown 记号
mutate_and_expect v6 "u11 更新说明取第一句有意义的话,去掉 markdown 记号" \
  '      .replace(/^\s*#+\s*/, "")      // 标题记号' \
  '      .replace(/^\s*$/, "")      // 标题记号' 

# v7 更新说明不截断(长文会把那一行撑爆)
mutate_and_expect v7 "u12 更新说明太长要截断,空的要给空串" \
  '    return line.length > max ? line.slice(0, max - 1) + "…" : line;' \
  '    return line;'

restore
AFTER="$(sha256sum "$SRC" | cut -d' ' -f1)"
echo
if [ "$BEFORE" != "$AFTER" ]; then echo "🔴 被测文件没还原干净!"; exit 2; fi
echo "== 红检小结:咬住 $bites 条 / 漏网 $escapes 条(被测文件已逐字节还原)=="
[ "$escapes" -eq 0 ] || exit 1
