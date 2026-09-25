#!/usr/bin/env bash
# 红检 —— 证明 track opendesign-composer-zcode 的判据**咬得动实现**(照 tests/mutation-chat-model-error.sh 的做法)。
#
# 判据先行时单测红在「composerSkills.ts 不存在」上;那种红只证明"没有就会响",不证明"写错了会响"(08-14 的规矩)。
# 每条变异只弄坏一处,并核对**红在该红的那一问上**(光看退出码,超时、夹具炸也是非 0 —— 那是假的咬住)。
# Z14 起要重新构建前端再跑 e2e(变异必须编译得过,构建失败单独报出来);脚本退出时还原源码并**再构建一次**。
# e2e 要一个带假 key 的家目录(同 tests/e2e/run-all.sh 的 E2E_HOME),否则一打开就被带去设置页。
#
# 用法:tests/mutation-composer-zcode.sh [变异号...]    退出码:0 全咬住 / 1 有漏网
set -u
cd "$(dirname "$0")/.."
WORK="$(mktemp -d)"
SRCS=(web/src/chat/modelError.ts web/src/chat/transcript.ts web/src/chat/ChatPage.tsx web/src/chat/composerSkills.ts web/src/chat/systemNote.ts web/src/chat/modelPicker.ts)
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
  # 单测按**测试名**认红(「not ok <任意编号> - c19」):中间插测试会让编号整体后移,按编号认会把咬住记成漏网(r1fix 第 1 遍就是)
  local hit=1
  if [[ "$marker" =~ ^not\ ok\ [0-9]+\ -\ (c[0-9]+)$ ]]; then
    grep -qE -- "^not ok [0-9]+ - ${BASH_REMATCH[1]} " <<<"$out" && hit=0
  else
    grep -qF -- "$marker" <<<"$out" && hit=0
  fi
  if [ $rc -ne 0 ] && [ $hit -eq 0 ]; then
    echo "  [咬住] $id —— $why"
    pass=$((pass+1))
  else
    echo "  [漏网] $id —— $why(rc=$rc,没见到「$marker」)"
    tail -15 <<<"$out" | sed 's/^/        /'
    fail=$((fail+1))
  fi
}

UNIT="node --test tests/test_composer_zcode.mjs"
E2E_HOME="$(mktemp -d -t ds-e2e-home-XXXXXX)"
mkdir -p "$E2E_HOME/.openDesign" "$E2E_HOME/.cache"
echo sk-e2e-fixture > "$E2E_HOME/.openDesign/key.txt"
ln -s "$HOME/.cache/ms-playwright" "$E2E_HOME/.cache/ms-playwright"
trap 'cleanup; rm -rf "$E2E_HOME"' EXIT
E2E="(cd web && npm run build >/dev/null 2>&1 || { echo 构建失败:变异没编译过; exit 99; }) && HOME=$E2E_HOME USERPROFILE=$E2E_HOME node tests/e2e/composer_zcode.e2e.mjs"

# ── 停止(④)的归约 ──
mutate Z1 web/src/chat/transcript.ts \
  '      if (e.status === "idle") return state.stopPending ? finishTurn(state) : state;' \
  '      if (e.status === "idle") return finishTurn(state);' \
  "$UNIT" "not ok 9 - c9" \
  "任何 idle 都解锁(业主会在回复中途插话 —— 4c C2)"

mutate Z2 web/src/chat/transcript.ts \
  '      if (e.status === "idle") return state.stopPending ? finishTurn(state) : state;' \
  '      if (e.status === "idle") return state;' \
  "$UNIT" "not ok 7 - c7" \
  "点了停止、网关回 idle 还卡在回复中(网关不发 turn_end)"

mutate Z3 web/src/chat/transcript.ts \
  '  return stopped ? finishTurn(next) : next;' \
  '  return next;' \
  "$UNIT" "not ok 8 - c8" \
  "回话先于 idle 到时不收尾"

mutate Z4 web/src/chat/transcript.ts \
  '  if (note) return { id, role: "assistant", content: note, streaming: false, systemNote: true };' \
  '' \
  "$UNIT" "not ok 7 - c7" \
  "停止回话照旧英文当助手回复(R1)"

mutate Z5 web/src/chat/systemNote.ts \
  '"已停止(已经开始的那一步可能已做完)"' \
  '"已停止"' \
  "$UNIT" "not ok 7 - c7" \
  "停在记账中间,不提醒那一步可能已经做了(QA Gemini)"

mutate Z6 web/src/chat/transcript.ts \
  '  return state.busy ? { ...state, stopPending: turnId } : state;' \
  '  return { ...state, stopPending: turnId };' \
  "$UNIT" "not ok 12 - c12" \
  "不在回复时也记停止标记"

# ── 技能表(①②)──
mutate Z7 web/src/chat/composerSkills.ts \
  'const SLASH = /^[/\u3001\uff0f]([^\s/\u3001\uff0f]*)$/;' \
  'const SLASH = /^[/]([^\s/]*)$/;' \
  "$UNIT" "not ok 3 - c3" \
  "只认半角 /(业主开着中文标点,按 / 打出「、」,永远弹不出)"

mutate Z8 web/src/chat/composerSkills.ts \
  '      rest = rest.slice(head.length + 1);' \
  '' \
  "$UNIT" "not ok 2 - c2" \
  "换技能时叠两个开头"

mutate Z9 web/src/chat/composerSkills.ts \
  '    [s.name, s.abbr, ...s.keywords]' \
  '    [s.name, s.abbr]' \
  "$UNIT" "not ok 4 - c4" \
  "关键词筛不到(打 /账本 找不到记一下)"

# (第一版改的是「中午好」那一行的下界 11 —— 永远走不到:前面「上午好」先返回了,是等价变异、不算漏网。改成挪上午的上界)
mutate Z10 web/src/chat/composerSkills.ts \
  '  if (h >= 9 && h < 12) return "上午好,今天想聊点什么?";' \
  '  if (h >= 9 && h < 13) return "上午好,今天想聊点什么?";' \
  "$UNIT" "not ok 17 - c17" \
  "问候语分界错一小时"

# ── 模型按钮(③)与欠账 Q3′ ──
mutate Z11 web/src/chat/modelPicker.ts \
  '  glm_plan: "GLM 套餐",' \
  '  glm_plan: "GLM",' \
  "$UNIT" "not ok 6 - c6" \
  "GLM 两家分不开(看不出扣哪家的钱)"

mutate Z12 web/src/chat/modelPicker.ts \
  '  return { short: VENDOR_SHORT[status.provider] ?? full, full };' \
  '  return { short: VENDOR_SHORT[status.provider] ?? full.replace(/[(（].*?[)）]/g, ""), full };' \
  "$UNIT" "not ok 6 - c6" \
  "自定义供应商名字也去括号(4c C5)"

mutate Z13 web/src/chat/modelError.ts \
  '  return { text: TEXT[kind], raw: maskKeys(t), rawLabel: FIXED[t] ? "聊天服务的说法" : "原文" };' \
  '  return { text: TEXT[kind], raw: maskKeys(t), rawLabel: "原文" };' \
  "$UNIT" "not ok 15 - c15" \
  "网关改写的英文仍标「原文」(Q3′)"

mutate Z19 web/src/chat/modelPicker.ts \
  '  if (!status.models.some((m) => m.id === status.current)) return null;' \
  '' \
  "$UNIT" "not ok 6 - c6" \
  "后台兜底报错了厂商,按钮照写(QA 执行第 1 步抓到的回归)"

# ── 第 1 轮评审修复(R1 / R2 / R3)──
mutate Z20 web/src/chat/transcript.ts \
  '  return withoutStop({ ...state, messages: [...state.messages, msg], busy: true, activity: [] });' \
  '  return { ...state, messages: [...state.messages, msg], busy: true, activity: [] };' \
  "$UNIT" "not ok 19 - c19" \
  "新一轮带着上一轮的停止标记(■ 一直灰,评审 R2)"

mutate Z21 web/src/chat/transcript.ts \
  '      return state.busy || state.stopPending ? withoutStop({ ...state, busy: false }) : state;' \
  '      return state.busy ? { ...state, busy: false } : state;' \
  "$UNIT" "not ok 19 - c19" \
  "出错收尾不清停止标记(评审 R2)"

mutate Z22 web/src/chat/transcript.ts \
  '  const stopped = !!(state.stopPending && bubble.systemNote && e.turn_id === state.stopPending);' \
  '  const stopped = !!(state.stopPending && bubble.systemNote);' \
  "$UNIT" "not ok 20 - c20" \
  "后台子任务回报也当停止回话,提前解锁(评审 R3)"

mutate Z23 web/src/chat/transcript.ts \
  '  return withoutStop({ ...state, busy: false, thinking: false, activity: [] });' \
  '  return { ...state, busy: false, thinking: false, activity: [] };' \
  "$UNIT" "not ok 19 - c19" \
  "断线后放掉这一轮不清停止标记(评审 R2)"

# ── 界面(要构建 + e2e)──
if wanted Z14 || wanted Z15 || wanted Z16 || wanted Z17 || wanted Z18 || wanted Z24 || [ ${#only[@]} -eq 0 ]; then rebuilt=1; fi
mutate Z14 web/src/chat/ChatPage.tsx \
  '    setTranscript((s) => requestStop(s, turnId));' \
  '    setTranscript((s) => requestStop(appendLocalUser(s, "/stop", `local-${turnId}`), turnId));' \
  "$E2E" "not ok - ④ 发送是 ↑ 图标" \
  "点停止上屏一条 /stop 用户气泡"

mutate Z15 web/src/chat/ChatPage.tsx \
  '              if ((e.key === "Enter" && !e.shiftKey) || e.key === "Tab") {' \
  '              if (e.key === "Tab") {' \
  "$E2E" "not ok - ② 打 / 弹同一份技能表" \
  "技能表开着按 Enter 把 /参考 发出去了"

mutate Z16 web/src/chat/ChatPage.tsx \
  '                {modelVendor && <span className="vendor">{modelVendor.short}</span>}' \
  '' \
  "$E2E" "not ok - ③ 模型按钮" \
  "按钮上没有厂商名"

mutate Z17 web/src/chat/ChatPage.tsx \
  '            ) : m.systemNote ? (' \
  '            ) : m.systemNote && m.id === "never" ? (' \
  "$E2E" "not ok - ④ 发送是 ↑ 图标" \
  "系统小字画成普通助手回复"

# (第一版把问候语换成死字 —— greetingFor 没人用了,tsc 报错、构建挂了,e2e 根本没跑。改成仍调用、但不看现在几点)
mutate Z18 web/src/chat/ChatPage.tsx \
  '            <div className="home-greet">{greetingFor(greetAt)}</div>' \
  '            <div className="home-greet">{greetingFor(new Date(2026, 0, 1, 10))}</div>' \
  "$E2E" "not ok - ⑤ 首页问候语" \
  "问候语不随时间"

mutate Z24 web/src/chat/ChatPage.tsx \
  '            if (m.event === "turn_end" || (m.event === "goal_status" && m.status === "idle")) onTurnEnd?.();' \
  '            if (m.event === "turn_end" || (m.event === "goal_status" && m.status === "idle" && m.never === 1)) onTurnEnd?.();' \
  "$E2E" "not ok - ④ 发送是 ↑ 图标" \
  "停下之后侧栏历史 / 项目数据不刷新(评审 R1)"

echo "红检:咬住 $pass / 漏网 $fail"
[ $fail -eq 0 ]
