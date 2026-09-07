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

# v4 已作废(2026-09-07):它咬的是 update.ts 里那条 VERSION_RE,
# 而评审 F1 之后**地址不再由我们拼**,那条正则连同 releasePageUrl 一起没了。
# 变异随被测对象消失而作废是正常的;留着它只会每轮报一次 [BAD]。
# 替代它的是下面 v8:验地址那一关能不能被拆掉。

# v5 🔴 开关关了也照样自动往外发
mutate_and_expect v5 "u10 🔴 显式关掉之后就不许再自动往外发请求" \
  '  return prefs[AUTO_CHECK_PREF] !== false;' \
  '  return true;'

# v6 更新说明不洗 markdown 记号(靶子 2026-09-07 从"剥标题记号"改到"剥粗体")
# 原靶子那一行已删:加了 isHeading 之后它是半死代码,而且它把 `#123` 这种 issue 编号
# 也剥了。v6 第一次漏网正是把这件事照出来的 —— 变异漏网不总是判据的错,
# 有时是被测对象里那一行本来就不该在。
mutate_and_expect v6 "u11 更新说明取第一句有意义的话,去掉 markdown 记号" \
  '      .replace(/\*\*|__|`/g, "")     // 粗体 / 行内代码' \
  '      .replace(/^$/g, "")     // 粗体 / 行内代码'

# v7 更新说明不截断(长文会把那一行撑爆)
mutate_and_expect v7 "u12 更新说明太长要截断,空的要给空串" \
  '    return line.length > max ? line.slice(0, max - 1) + "…" : line;' \
  '    return line;'

# v8 🔴 后端给什么就渲染什么(验地址那一关拆掉)
mutate_and_expect v8 "u7 别人给的地址一律不放行(界面上那个链接是要业主去点的)" \
  '  return RELEASE_URL_RE.test(url) ? url : null;' \
  '  return url;'

# v9 🔴 有新版却不在收起来的那一行上留记号(F2 原样重现)
mutate_and_expect v9 "u13 🔴 有新版时,设置那一行必须挂个记号(不然业主根本看不到)" \
  '  return !!info && info.update_available === true;' \
  '  return false;'

# v10 查完了没拿到东西,长得像"还没查过"(F3 原样重现)
mutate_and_expect v10 "u14 done + 空结果要说查不到,不许伪装成没查过" \
  '  if (s.state === "done" && !s.info) return "查不到更新";' \
  '  if (false) return "查不到更新";'

# v11 地址被闸掉时不给退路(F-C 原样重现:蓝点亮着,没地方可点)
mutate_and_expect v11 "u15 地址被闸掉时也得给业主一条路(F-C:仓库改名会让下载行静默消失)" \
  '  return safeReleaseUrl(url) ?? RELEASES_PAGE;' \
  '  return safeReleaseUrl(url) as string;'

# v12 有新版但没版本号时掉进"已是最新"(F-D 原样重现)
mutate_and_expect v12 "u16 有新版但没版本号时,不许说成「已是最新」(F-D)" \
  '  if (info.update_available) return "有新版 ›";' \
  '  if (false) return "有新版 ›";'

# v13 跳过标题的依据退回"按开头几个词"(submimo 补充 1 原样重现)
mutate_and_expect v13 "u17 正文以「这一版」开头时不许被当成标题跳掉(submimo 补充 1)" \
  '    const isHeading = /^\s*#+\s/.test(raw);' \
  '    const isHeading = /^这一版|^更新内容|^改了什么/.test(raw.replace(/^\s*#+\s*/, ""));'

# v14 蓝点的悬停说明退回拼版本号(MR-2 原样重现:latest 为 null 时印「有新版 null」)
mutate_and_expect v14 "u19 🔴 没版本号时,蓝点的说明不许把 null 印给业主" \
  '  return v ? `有新版 ${v}` : "有新版";' \
  '  return `有新版 ${v}`;'

restore
AFTER="$(sha256sum "$SRC" | cut -d' ' -f1)"
echo
if [ "$BEFORE" != "$AFTER" ]; then echo "🔴 被测文件没还原干净!"; exit 2; fi
echo "== 红检小结:咬住 $bites 条 / 漏网 $escapes 条(被测文件已逐字节还原)=="
[ "$escapes" -eq 0 ] || exit 1
