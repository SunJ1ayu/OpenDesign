#!/usr/bin/env bash
# 红检 —— 证明 T4 那三份判据**咬得动前端实现**(track opendesign-key-onboarding)。
#
# 为什么必须单独跑一轮:判据先行时它们红在"模块不存在"上,
# **那种红只证明"没有就会响",不证明"写错了会响"**(08-14 立的规矩)。
#
# 🔴 这一份和仓里其它 mutation-*.sh 有一个关键不同:**前端要重新 build 才作数**。
#    e2e 跑的是 web/dist,不是 web/src —— 变异了源码却不 build,等于什么都没变,
#    判据当然全绿,而脚本会报"判据瞎了"。**那是最坏的一种假报警。**
#
# 用法:tests/mutation-llm-key.sh [变异号...]    退出码:0 全咬住 / 1 有漏网
set -u
cd "$(dirname "$0")/.."
WORK="$(mktemp -d)"
SRCS=(web/src/llmKey.ts web/src/LlmKeyCard.tsx web/src/chat/connection.ts
      web/src/App.tsx web/src/workspace/Sidebar.tsx)

for s in "${SRCS[@]}"; do cp "$s" "$WORK/$(basename "$s").orig"; done
restore() {
  for s in "${SRCS[@]}"; do cp "$WORK/$(basename "$s").orig" "$s"; done
}
# 🔴 还原源码之后**必须再 build 一次**:e2e 跑的是 web/dist,
# 只还原 src 的话,跑完留在盘上的 dist 是最后一个变异体的产物 ——
# 那正是"盘上和运行时对不上"的老毛病,而且它会被下一次 dist 新鲜度闸抓成红。
trap 'restore; (cd web && npm run build) >/dev/null 2>&1; rm -rf "$WORK"; echo "(已还原源码并重新 build)"' EXIT
pass=0; fail=0; only=("$@")

wanted() {                      # 没给参数就全跑
  [ ${#only[@]} -eq 0 ] && return 0
  for x in "${only[@]}"; do [ "$x" = "$1" ] && return 0; done
  return 1
}

build_now() {
  (cd web && npm run build) >"$WORK/build.log" 2>&1
}

# mutate <id> <文件> <老串> <新串> <判据命令> <该红在哪一问> <说明>
#
# 🔴 为什么要"该红在哪一问":光看退出码,**超时也是非 0** —— 这台机器内存只有 1G,
#    e2e 撞上内存压力会超时,而那会被记成"判据咬住了"。那是假的咬住,
#    比漏网更坏:它会让我以为这套判据有牙。所以必须核对**红在正确的那一问上**。
mutate() {
  local id="$1" file="$2" old="$3" new="$4" oracle="$5" marker="$6" why="$7"
  wanted "$id" || return 0
  restore
  python3 - "$file" "$old" "$new" <<'PY' || { echo "  [BAD]  $id 变异没打上去"; fail=$((fail+1)); return; }
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding="utf-8")
old, new = sys.argv[2], sys.argv[3]
n = s.count(old)
if n == 0:
    sys.exit(f"变异锚点找不到: {old!r}")
# 锚点必须唯一 —— 打错位置会让判据"全绿",而脚本报的是"判据瞎了"。
# 假报警和假绿一样坏,而且更贵:它会指着一份好判据让我去改它。
if n > 1:
    sys.exit(f"变异锚点不唯一({n} 处): {old!r}")
p.write_text(s.replace(old, new), encoding="utf-8")
PY
  # 🔴 build 不过 = 这条红检不算数(判据根本没机会跑),不是"咬住了"
  if ! build_now; then
    echo "  [BAD]  $id build 没过 —— 这条不算数(见 $WORK/build.log)"
    fail=$((fail+1)); return
  fi
  if eval "$oracle" >"$WORK/mut-$id.txt" 2>&1; then
    echo "  [漏网] $id  $why"
    fail=$((fail+1))
  elif grep -qF "$marker" "$WORK/mut-$id.txt"; then
    echo "  [咬住] $id  $why"
    pass=$((pass+1))
  else
    # 红了,但不是红在该红的那一问上 —— 超时 / 环境炸 / 判据自己坏了都长这样。
    # **这种不算咬住**(08-14 的规矩:红在 TypeError 上等于没红检过)。
    echo "  [存疑] $id  红了但不是红在「$marker」上 —— 见 $WORK/mut-$id.txt"
    fail=$((fail+1))
  fi
}

E2E="timeout 180 node tests/e2e/llm_key.e2e.mjs"
UNIT="node --test tests/test_llm_key.mjs tests/test_llm_key_surface.mjs tests/test_chat_connection.mjs"

echo "== 红检:T4 前端(每条都要重新 build,慢是应该的)"

# ---- 逻辑层(纯 node 判据就能咬,不必 build)----------------------------
mutate M1 web/src/llmKey.ts \
  'method: "POST",' 'method: "GET",' \
  "$UNIT" \
  "a3 保存用 POST" "saveKey 改用 GET ⇒ a3 该红"
# 🔴 M3/M7 的第一版**变异体自己编译不过**(2026-08-16 首次全跑才暴露,被脚本正确地
#    记成 [BAD] 不算数)。教训是这一类脚本共有的:**最自然的那个变异往往编译不过**,
#    而 TS 的报错点还离锚点很远,容易误读成"实现坏了"。两种坑各踩了一次:
#      M3 `!== 999`   ⇒ status 被窄化成字面量 999,和后面第 91 行的 `=== 400` 无重叠;
#      M7 去掉 safeHint 的唯一调用 ⇒ noUnusedLocals 报 TS6133。
#    ⇒ 改成语义相同但编译得过的写法:M3 放宽比较(不产生字面量窄化),
#      M7 保留对 safeHint 的引用(短路到不可达分支)。
mutate M3 web/src/llmKey.ts \
  'if (res.status === 200) {' 'if (res.status >= 200) {' \
  "$UNIT" \
  "a5 后端拒绝" "400 也当成功 ⇒ a5/a7 该红"
mutate M4 web/src/llmKey.ts \
  '请手动重启 OpenDesign 后再继续使用。' '请稍后再试。' \
  "$UNIT" \
  "d1 manual" "manual 不提重启 ⇒ d1/d3 该红"
mutate M5 web/src/llmKey.ts \
  'if (restart === "requested") {' 'if (restart !== "manual") {' \
  "$UNIT" \
  "d3 没见过的 restart" "未知值倒向 requested ⇒ d3 该红(保守方向反了)"
mutate M7 web/src/llmKey.ts \
  'hint: safeHint(body.hint, key),' 'hint: key || safeHint(body.hint, key),' \
  "$UNIT" \
  "c1 保存成功后" "把入参 key 当 hint 端出去 ⇒ c1/c2 该红"
mutate M17 web/src/chat/connection.ts \
  'const pw = this.storage.getItem(PASSWORD_KEY);' \
  'const pw = this.storage.getItem(PASSWORD_KEY) ?? "undefined";' \
  "$UNIT" \
  "没口令 = 代签主路" "没口令时瞎编一个 Bearer ⇒ 代签断言该红"

# ---- 界面层(必须 build 之后跑 e2e)-------------------------------------
mutate M9 web/src/LlmKeyCard.tsx \
  'type="password"' 'type="text"' \
  "$E2E" \
  "FAIL - A3" "输入框改明文 ⇒ A3 该红"
mutate M10 web/src/LlmKeyCard.tsx \
  'autoComplete="off"' 'autoComplete="on"' \
  "$E2E" \
  "FAIL - A3" "去掉 autocomplete ⇒ A3 该红"
mutate M11 web/src/LlmKeyCard.tsx \
  'if (inputRef.current) inputRef.current.value = "";' \
  'if (inputRef.current) { /* 不清空 */ }' \
  "$E2E" \
  "FAIL - C10" "保存后不清空输入框 ⇒ C10 该红"
mutate M12 web/src/LlmKeyCard.tsx \
  'const outcome = await saveKey(fetch, provider, rawKey);' \
  'localStorage.setItem("ds-last-key", rawKey); const outcome = await saveKey(fetch, provider, rawKey);' \
  "$E2E" \
  "FAIL - C9" "顺手把 key 存进 localStorage ⇒ C9 该红"
mutate M13 web/src/LlmKeyCard.tsx \
  'if (inputRef.current) inputRef.current.value = "";' \
  'document.title = rawKey; if (inputRef.current) inputRef.current.value = "";' \
  "$E2E" \
  "FAIL - C1" "把 key 写进页面标题 ⇒ C1 该红"
mutate M14 web/src/App.tsx \
  'if (!st.configured) setLlmKeyOpen(true);' 'setLlmKeyOpen(true);' \
  "$E2E" \
  "FAIL - E1" "已配置时也自动弹 ⇒ E1 该红"
mutate M18 web/src/App.tsx \
  '<div className="connect-modal-mask" onClick={() => setLlmKeyOpen(false)}>' \
  '<div className="connect-modal-mask">' \
  "$E2E" \
  "FAIL - A5" "遮罩上的 onClick 没了 ⇒ 卡片关不掉,业主被锁在门外 ⇒ A5 该红"

# 🔴 M19 是 M18 的**加强版,也是 A6 存在的全部理由**:它造出"看起来关掉了、
#    其实遮罩还在吃点击"这个形态 —— 卡片确实不见了(A5 照样绿),但那层
#    position:fixed;inset:0 的遮罩留在 DOM 里继续拦截所有点击。
#    这正是 08-16 那次 29 条 e2e 一起红的真实形态。**M19 漏网 = A6 是 A5 的重复,
#    删了它不心疼;M19 咬住 = A6 问到了 A5 问不出的东西。**
mutate M19 web/src/App.tsx \
  '<div className="connect-modal-mask" onClick={() => setLlmKeyOpen(false)}>' \
  '<div className="connect-modal-mask" onClick={() => { const el = document.querySelector("[data-ui=\"llm-key-card\"]"); if (el) (el as HTMLElement).style.display = "none"; }}>' \
  "$E2E" \
  "FAIL - A6" "卡片藏起来但遮罩留着继续吃点击 ⇒ A5 绿而 A6 该红"

mutate M20 web/src/App.tsx \
  'if (!st.configured) setLlmKeyOpen(true);' \
  'if (!st.configured && !sessionStorage.getItem("ds-key-dismissed")) setLlmKeyOpen(true); sessionStorage.setItem("ds-key-dismissed", "1");' \
  "$E2E" \
  "FAIL - A7" "关掉一次就再也不提醒 ⇒ 业主永远填不上 key ⇒ A7 该红"

mutate M16 web/src/workspace/Sidebar.tsx \
  'title="设置大模型 API key"' \
  'title="切换模型:python bin/set_model.py <模型id>"' \
  "$E2E" \
  "FAIL - F3" "把教人敲命令行的提示放回去 ⇒ F3 该红"

echo
echo "== 红检小结:${pass} 咬住 / ${fail} 漏网"
[ "$fail" -eq 0 ]
