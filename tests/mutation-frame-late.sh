#!/usr/bin/env bash
# 红检(变异测试)—— 证明 **0.94.0 那批"方案 B 必须收进开关"的判据**咬得动。
#
# 覆盖 tests/test_window_frame_late.py 的 h1~h6(0.95:方案 B 挪晚 + 自动撤销)。
# 规矩同 tests/mutation-native-frame.sh:
#   1. 变异**被测对象**(bin/ds_shell.py),不是判据本身;
#   2. 每条指定**靶子**:必须是那一条红,红在别处算漏网;
#   3. 跑完原样还回去,哈希机械核对。
#
# 🔴 它存在的理由:0.92 和 0.93 连着两版判据全绿、产品照样是坏的。
#    这一版的判据答不了"页面画不画得出来"(那只有 Windows 答得了),
#    它只保证"默认路径一个边框计算都不碰" —— 那就更要证明这个保证是真的。
#    (f9 第一版有这个洞:它扫 ast.unparse,把**docstring 里**写着的
#     EnumChildWindows 当成"代码用了它",靠注释就能绿。
#     **是我写 M9 时读出来的,不是红检先咬到的** —— 但随后用实验证实了:
#     把 f9 退回 ast.unparse 再跑 M9,结果是"判据全绿:这条变异下它是瞎的"。)
#
# 用法:tests/mutation-frame-experiment.sh
# 退出码:0 = 每条都咬住靶子   1 = 有漏网   2 = 用法/现场问题

set -u
cd "$(dirname "$0")/.."
PY="${PY:-/root/.venvs/design-studio/bin/python}"

SOURCES=(bin/ds_shell.py)
WORK="$(mktemp -d)"
declare -A BEFORE
for f in "${SOURCES[@]}"; do
  BEFORE["$f"]="$(sha256sum "$f" | cut -d' ' -f1)"
  cp -p "$f" "$WORK/$(echo "$f" | tr / _)"
done

restore() {
  # 🔴 cp -p:保住 mtime。不带 -p 的 cp 会把文件顶成"现在" ——
  #    dist 新鲜度闸就是这么被红检刷红的(08-24 的账),别再犯。
  for f in "${SOURCES[@]}"; do cp -p "$WORK/$(echo "$f" | tr / _)" "$f"; done
  find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
}
trap 'restore; rm -rf "$WORK"' EXIT

pass=0; fail=0
ORACLE=tests/test_window_frame_late.py

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
  #    那会同时造出假绿和假红(2026-08-07 的老账)。
  find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
  # 🔴 直接跑文件,别 `-m unittest tests/xxx.py` —— 那是路径不是模块名,
  #    unittest 会以 loader._FailedTest 整体报错,于是**每一条变异都"红在别处"**,
  #    红检看着像 9 条全漏网。第一版就是这么坏的(量具自己坏了,不是被测物)。
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

echo "== 红检开始(0.95:方案 B 挪到用的时候才装)=="

# T1 方案 B 挪回 shown —— 这就是 0.93 那个把业主窗口弄白的时机
mutate_and_expect T1 bin/ds_shell.py "$ORACLE" \
  test_h1_shown_path_does_not_touch_the_window_frame \
  '        self._on_ui(self._apply_safe_styles)' \
  '        self._on_ui(self._apply_native_styles_and_frame)'

# T2 shown 路上连安全位也不贴了 —— 0.92 修好的系统菜单/Win+方向键会丢
mutate_and_expect T2 bin/ds_shell.py "$ORACLE" \
  test_h1_shown_path_does_not_touch_the_window_frame \
  '        self._on_ui(self._apply_safe_styles)' \
  '        pass'

# T3 缩小时不再装框架 —— 挪晚了又不装 = 动画永远不会出现
mutate_and_expect T3 bin/ds_shell.py "$ORACLE" \
  test_h2_frame_is_applied_on_first_real_use \
  '            self._apply_native_styles_and_frame(form)
            form.WindowState = FormWindowState.Minimized' \
  '            form.WindowState = FormWindowState.Minimized'

# T4 装完不量了 —— 又回到"白了但我手上一个数字都没有"
mutate_and_expect T4 bin/ds_shell.py "$ORACLE" \
  test_h3_apply_is_immediately_followed_by_a_measurement \
  '                info = self._log_frame_diagnostics(form)
                if not self._frame_looks_sane(info):
                    self._revert_native_frame(form)' \
  '                info = None'

# T5 量了但不撤 —— 最坏情况又变回白屏,和 0.93 一样
mutate_and_expect T5 bin/ds_shell.py "$ORACLE" \
  test_h4_bad_measurement_triggers_an_automatic_revert \
  '                if not self._frame_looks_sane(info):
                    self._revert_native_frame(form)' \
  '                self._frame_looks_sane(info)'

# T6 撤销只解挂、不摘样式位 —— **比白屏更坏**:窗口会长出一条真的标题栏
mutate_and_expect T6 bin/ds_shell.py "$ORACLE" \
  test_h4_bad_measurement_triggers_an_automatic_revert \
  '            style = user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
            user32.SetWindowLongPtrW(hwnd, GWL_STYLE,
                                     style & ~(WS_CAPTION | WS_THICKFRAME))' \
  '            style = user32.GetWindowLongPtrW(hwnd, GWL_STYLE)'

# T7 撤销过了还接着试 —— 业主每点一次缩小就闪一下,日志也被刷满
mutate_and_expect T7 bin/ds_shell.py "$ORACLE" \
  test_h5_revert_is_remembered_so_it_does_not_retry_forever \
  '            if frame_experiment_on() and not self._frame_gave_up:' \
  '            if frame_experiment_on():'

# T8 量不出来就当成"坏了" —— 误撤没有任何好处,只有白闪一下 + 没动画
mutate_and_expect T8 bin/ds_shell.py "$ORACLE" \
  test_h6_the_measurement_never_breaks_the_window \
  "            log(f\"[诊断] 判断窗口是否正常时出错,按'正常'处理:{exc!r}\")
            return True" \
  "            log(f\"[诊断] 判断窗口是否正常时出错:{exc!r}\")
            return False"

restore
echo
for f in "${SOURCES[@]}"; do
  now="$(sha256sum "$f" | cut -d' ' -f1)"
  if [ "$now" != "${BEFORE[$f]}" ]; then
    echo "🔴 $f 没还原干净(哈希对不上)"; exit 2
  fi
done
echo "== 红检结束:咬住 $pass 条,漏网 $fail 条(源文件已原样还原)=="
[ "$fail" -eq 0 ]
