#!/usr/bin/env bash
# 红检(变异测试)—— 证明**无边框窗口那一批判据**咬得动。
#
# 覆盖 2026-08-17 两轮四审落地的判据:
#   tests/test_shell_window_contract.py   x5 层序 / x6 结构 / x7 把手名单 / x8 stacking / x9 几何
#   tests/test_win_ctypes_decls.py        windll 调用点必须声明 argtypes
#   tests/test_ds_shell_wiring.py         w7 看门狗只看一眼
# (core 那边的 c21/c22 在 tests/mutation-ds-shell-core.sh 里,别在这儿重复一份。)
#
# 规矩与 mutation-ds-shell-core.sh 同一套:
#   1. 变异**被测对象**,不是判据本身;
#   2. 每条指定**靶子**:必须是那一条红,红在别处算漏网(08-11 栽过三次);
#   3. 跑完原样还回去,并用哈希机械核对。
#
# 🔴 它入库的理由(08-17 四审 subkimi F-3):第一版这批变异跑在
#    `/tmp/.../scratchpad/mutate.sh` 里 —— 收据上写着"7 咬住 0 漏网",
#    而那个脚本**没有任何人能从仓库复现**。按这个仓库自己的规矩,
#    没人跑得了的检查等于没有。
#
# 用法:tests/mutation-window-chrome.sh
# 退出码:0 = 每条都咬住靶子   1 = 有漏网   2 = 用法/现场问题

set -u
cd "$(dirname "$0")/.."
PY="${PY:-/root/.venvs/design-studio/bin/python}"

SOURCES=(bin/ds_shell.py web/src/app.css web/src/workspace/WindowChrome.tsx)
WORK="$(mktemp -d)"
declare -A BEFORE
for f in "${SOURCES[@]}"; do
  BEFORE["$f"]="$(sha256sum "$f" | cut -d' ' -f1)"
  cp "$f" "$WORK/$(echo "$f" | tr / _)"
done

restore() {
  for f in "${SOURCES[@]}"; do cp "$WORK/$(echo "$f" | tr / _)" "$f"; done
  find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
}
trap 'restore; rm -rf "$WORK"' EXIT

pass=0; fail=0

# 用法:mutate_and_expect <id> <被变异文件> <判据文件> <靶子> <旧> <新> [<旧2> <新2> ...]
mutate_and_expect() {
  local id="$1" src="$2" oracle="$3" target="$4"; shift 4
  local out="$WORK/mut-$id.txt"
  restore
  "$PY" - "$src" "$@" <<'PYEOF' || { echo "  [BAD]  $id 变异没打上去"; fail=$((fail+1)); return; }
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding="utf-8")
args = sys.argv[2:]
if len(args) % 2:
    sys.exit("旧/新必须成对")
for old, new in zip(args[0::2], args[1::2]):
    if old not in s:
        sys.exit(f"变异锚点找不到: {old!r}")
    s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")
PYEOF
  # 🔴 清 .pyc:同长度替换 + 同一秒 mtime 会让 CPython 复用旧字节码,
  #    那会同时造出假绿和假红(2026-08-07 redcheck-fooled-by-pyc-cache)。
  find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
  timeout 300 "$PY" -W ignore "$oracle" > "$out" 2>&1
  local rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "  [BAD]  $id -> 判据全绿:这条变异下它是瞎的(靶子 $target)"
    fail=$((fail+1))
  elif grep -qE "^(FAIL|ERROR): $target" "$out"; then
    echo "  [OK]   $id -> 靶子 $target 如期红了"
    pass=$((pass+1))
  else
    echo "  [BAD]  $id -> 红了,但**不是靶子** $target:"
    grep -E "^(FAIL|ERROR):" "$out" | head -4 | sed 's/^/         实际红的是:/'
    fail=$((fail+1))
  fi
}

CONTRACT=tests/test_shell_window_contract.py
CTYPES=tests/test_win_ctypes_decls.py
WIRING=tests/test_ds_shell_wiring.py

echo "== 红检开始(无边框窗口那一批)=="

# W1 窗口栏层号退回浮层之下 —— 填 key 的弹窗一出现,三个按钮全点不动
mutate_and_expect W1 web/src/app.css "$CONTRACT" \
  test_x5_nothing_is_allowed_to_cover_the_window_bar \
  'height: 30px; z-index: 200;' 'height: 30px; z-index: 60;'

# W2 按钮区塞回窗口栏里 —— 栏自己是 stacking context,里面的层号在根上下文不算数
#    (靶子是 x8;x6 咬同一件事的事件冒泡一面,由 W3 单独打)
mutate_and_expect W2 web/src/workspace/WindowChrome.tsx "$CONTRACT" \
  test_x8_the_grips_never_eat_the_buttons \
  '        onDoubleClick={toggle}
      />' \
  '        onDoubleClick={toggle}
      >'

# W3 同一处的另一面:按钮回到栏里 ⇒ 点按钮会冒泡成拖窗口、双击白送一次最大化
mutate_and_expect W3 web/src/workspace/WindowChrome.tsx "$CONTRACT" \
  test_x6_clicking_a_window_button_never_also_moves_the_window \
  '        onDoubleClick={toggle}
      />' \
  '        onDoubleClick={toggle}
      >'

# W4 少一个把手 —— 那条边拖了没反应
mutate_and_expect W4 web/src/app.css "$CONTRACT" \
  test_x7_the_css_grips_match_the_edge_list \
  '.win-grip-topleft     { top: 0; left: 0; width: 6px; height: 6px; }' \
  '.win-grip-NOPE        { top: 0; left: 0; width: 6px; height: 6px; }'

# W5 把手没贴住边(挪进屏幕里)—— 名字和层序都对,业主那边就是拖不动
mutate_and_expect W5 web/src/app.css "$CONTRACT" \
  test_x9_every_grip_actually_sits_on_its_edge \
  '.win-grip-top    { top: 0; left: 6px; right: 6px; height: 5px; }' \
  '.win-grip-top    { top: 40px; left: 6px; right: 6px; height: 5px; }'

# W6 把手厚度归零 —— 一条抓不住的线
mutate_and_expect W6 web/src/app.css "$CONTRACT" \
  test_x9_every_grip_actually_sits_on_its_edge \
  '.win-grip-left   { left: 0; top: 6px; bottom: 6px; width: 5px; }' \
  '.win-grip-left   { left: 0; top: 6px; bottom: 6px; width: 0px; }'

# W7 SendMessageW 不声明 argtypes —— 64 位 HWND 被静默截成 32 位
mutate_and_expect W7 bin/ds_shell.py "$CTYPES" \
  test_every_windll_call_declares_its_argtypes \
  '        user32.SendMessageW.argtypes = [wintypes.HWND, ctypes.c_uint,
                                        ctypes.c_size_t, ctypes.c_ssize_t]' \
  '        pass'

# W8 看门狗退回"问两遍" —— 两问之间名册一变就是「名字有、原因空」
mutate_and_expect W8 bin/ds_shell.py "$WIRING" \
  test_w7_the_watchdog_looks_once_not_twice \
  '                found = self.sup.take_dead()
                if found:
                    dead = [name for name, _ in found]
                    for _, report in found:' \
  '                dead = self.sup.poll_dead()
                if dead:
                    found = [(n, n) for n in dead]
                    for report in self.sup.dead_reports():'

restore
echo
bad=0
for f in "${SOURCES[@]}"; do
  after="$(sha256sum "$f" | cut -d' ' -f1)"
  if [ "${BEFORE[$f]}" != "$after" ]; then
    echo "🔴 还原失败:$f 和跑之前不一样了(${BEFORE[$f]} -> $after)"; bad=1
  fi
done
[ "$bad" -eq 0 ] || exit 2
echo "被变异的 ${#SOURCES[@]} 个文件都已原样还回(哈希一致)"
echo "== 红检结束:咬住 $pass 条 / 漏网 $fail 条 =="
[ "$fail" -eq 0 ]
