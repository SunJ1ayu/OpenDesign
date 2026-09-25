#!/usr/bin/env bash
# 红检 —— 证明 track opendesign-chat-error-visible 的判据**咬得动实现**。
#
# 判据先行时单测红在「modelError.ts 不存在」上;那种红只证明"没有就会响",不证明"写错了会响"(08-14 的规矩)。
# 每条变异只弄坏一处,并核对**红在该红的那一问上**(光看退出码,超时、夹具炸也是非 0 —— 那是假的咬住)。
# M12 要重新构建前端再跑 e2e(变异必须编译得过 —— 前两版写成 `false ? (…)` / `m.modelError && false ? (…)`,tsc 都报 possibly undefined、构建挂了,
# e2e 根本没跑,记成了漏网;构建失败现在单独报出来);脚本退出时还原源码并**再构建一次**,web/dist 回到与源码一致。
#
# 用法:tests/mutation-chat-model-error.sh [变异号...]    退出码:0 全咬住 / 1 有漏网
set -u
cd "$(dirname "$0")/.."
WORK="$(mktemp -d)"
SRCS=(web/src/chat/modelError.ts web/src/chat/transcript.ts web/src/chat/ChatPage.tsx web/src/settings/modelSettings.ts)
for s in "${SRCS[@]}"; do cp "$s" "$WORK/$(basename "$s").orig"; done
restore() { for s in "${SRCS[@]}"; do cp "$WORK/$(basename "$s").orig" "$s"; done; }
rebuilt=0
cleanup() {
  restore
  if [ $rebuilt -eq 1 ]; then (cd web && npm run build >/dev/null 2>&1) && echo "(已按还原后的源码重新构建 web/dist)"; fi
  rm -rf "$WORK"; echo "(已还原源码)"
}
trap cleanup EXIT
pass=0; fail=0; only=("$@")

wanted() {
  [ ${#only[@]} -eq 0 ] && return 0
  for x in "${only[@]}"; do [ "$x" = "$1" ] && return 0; done
  return 1
}

# mutate <id> <文件> <老串> <新串> <判据命令> <该红在哪一问(输出里要出现的串)> <说明>
mutate() {
  local id="$1" file="$2" old="$3" new="$4" oracle="$5" marker="$6" why="$7"
  wanted "$id" || return 0
  restore
  python3 - "$file" "$old" "$new" <<'PY' || { echo "  [BAD]  $id 变异没打上去"; fail=$((fail+1)); return; }
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding="utf-8")
old, new = sys.argv[2], sys.argv[3]
n = s.count(old)
if n != 1:
    sys.exit(f"变异锚点出现 {n} 次(必须恰好 1 次): {old!r}")
p.write_text(s.replace(old, new), encoding="utf-8")
PY
  local out rc
  out="$(timeout 900 bash -c "$oracle" 2>&1)"; rc=$?
  if [ $rc -ne 0 ] && grep -qF -- "$marker" <<<"$out"; then
    echo "  [咬住] $id —— $why"
    pass=$((pass+1))
  else
    echo "  [漏网] $id —— $why(rc=$rc,没见到「$marker」)"
    tail -15 <<<"$out" | sed 's/^/        /'
    fail=$((fail+1))
  fi
}

UNIT="node --test tests/test_chat_model_error.mjs"

mutate M1 web/src/chat/transcript.ts \
  '      if (e.kind === undefined || e.kind === null) return appendNote(state, e);' \
  '      if (e.kind === undefined || e.kind === null) return state;' \
  "$UNIT" "not ok 14 - 实时:真帧序" \
  "没有 kind 的 message 照旧丢掉(就是这个 bug)"

mutate M2 web/src/chat/transcript.ts \
  '      ? assistantBubble(id, r.content)' \
  '      ? { id, role, content: r.content, streaming: false }' \
  "$UNIT" "not ok 22 - 回放" \
  "回放不过同一个函数 ⇒ 切走再回来冒英文原文"

mutate M3 web/src/chat/modelError.ts \
  '  ["quota", /insufficient' \
  '  ["auth", /insufficient' \
  "$UNIT" "not ok 2 - 额度" \
  "欠费说成 key 错(把人指去改一把没坏的 key)"

mutate M4 web/src/chat/modelError.ts \
  '  ["auth", /invalid[_ ]api[_ ]key|' \
  '  ["auth", /invalid_request_error|invalid[_ ]api[_ ]key|' \
  "$UNIT" "not ok 7 - Grok 反例:invalid_request_error" \
  "拿 invalid_request_error 当 key 错的依据(模型名错 / 图片被拒也会被说成 key 错)"

mutate M5 web/src/chat/modelError.ts \
  '  if (PY_EXC.test(content)) return "internal";' \
  '' \
  "$UNIT" "not ok 10 - Grok 反例:助手自己出错" \
  "助手自己崩了却按厂商报错分类"

mutate M6 web/src/chat/modelError.ts \
  'const PREFIX = /^(Error: ' \
  'const PREFIX = /(Error: ' \
  "$UNIT" "not ok 13 - 不是网关出错壳" \
  "正文中间引用一句报错也被改写成出错说明"

mutate M7 web/src/chat/modelError.ts \
  '(?:sk|tp|ak|pk|rk)-)' \
  '(?:zz)-)' \
  "$UNIT" "not ok 12 - 原文原样留着备查" \
  "原文小字不给 key 打码"

mutate M8 web/src/chat/transcript.ts \
  '  return { ...state, thinking: false, messages: [...state.messages, assistantBubble(id, e.text)] };' \
  '  return { ...state, messages: [...state.messages, assistantBubble(id, e.text)] };' \
  "$UNIT" "not ok 15 - 实时:出错说明一到就收掉" \
  "说明出来了思考动画还挂着"

mutate M9 web/src/chat/transcript.ts \
  '  if (state.messages.some((m) => m.id === id)) return state;' \
  '' \
  "$UNIT" "not ok 18 - 实时:同一帧收两次" \
  "同一帧收两次出两条"

mutate M10 web/src/chat/transcript.ts \
  '      if (e.kind !== "progress" && e.kind !== "tool_hint") return state;' \
  '      if (e.kind !== "progress" && e.kind !== "tool_hint") return appendNote(state, e);' \
  "$UNIT" "not ok 19 - 实时:空 text" \
  "不认识的 kind 也上屏(内部痕迹当成回复)"

mutate M11 web/src/chat/transcript.ts \
  '  return { ...state, thinking: false, messages: [...state.messages, assistantBubble(id, e.text)] };' \
  '  return { ...state, busy: false, thinking: false, messages: [...state.messages, assistantBubble(id, e.text)] };' \
  "$UNIT" "not ok 17 - 实时:没有 kind 的普通消息" \
  "一轮中途来一句话就把输入解锁"

if wanted M12; then rebuilt=1; fi
mutate M12 web/src/chat/ChatPage.tsx \
  '            ) : m.modelError ? (' \
  '            ) : m.modelError && m.id === "never" ? (' \
  "(cd web && npm run build >/dev/null 2>&1 || { echo 构建失败:变异没编译过; exit 99; }) && node tests/e2e/chat_model_error.e2e.mjs" "not ok - ① 发完一句" \
  "界面不按出错样式画(看不出是出错、没有原文小字)"

mutate M13 web/src/settings/modelSettings.ts \
  '把上面「未启用」旁边的开关打开' \
  '在上面打开「启用」后' \
  "node --test tests/test_llm_key.mjs" "not ok 17 - d7" \
  "设置页那句又说回开关上没有的「启用」"

echo "红检:咬住 $pass / 漏网 $fail"
[ $fail -eq 0 ]
