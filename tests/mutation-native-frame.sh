#!/usr/bin/env bash
# 红检(变异测试)—— 证明**方案 B 那批判据**咬得动。
#
# 覆盖 tests/test_window_native_frame.py 的 n1~n8。
# 规矩同 tests/mutation-window-chrome.sh:
#   1. 变异**被测对象**(bin/ds_shell.py),不是判据本身;
#   2. 每条指定**靶子**:必须是那一条红,红在别处算漏网;
#   3. 跑完原样还回去,哈希机械核对。
#
# 🔴 它存在的理由:0.92.0 那一单七条判据全绿、产品照样是坏的。
#    判据绿不绿说明不了什么,**判据咬不咬得动**才说明问题。
#    (n8 第一版就是在这儿被咬出来的:它扫文本,`if True:` 照样放行。)
#
# 用法:tests/mutation-native-frame.sh
# 退出码:0 = 每条都咬住靶子   1 = 有漏网   2 = 用法/现场问题

set -u
cd "$(dirname "$0")/.."
PY="${PY:-/root/.venvs/design-studio/bin/python}"

SOURCES=(bin/ds_shell.py)
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
ORACLE=tests/test_window_native_frame.py

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

echo "== 红检开始(方案 B:接回系统窗口框架)=="

# F1 常量抄错一位 —— 不报错,只是安静地设成别的位
mutate_and_expect F1 bin/ds_shell.py "$ORACLE" \
  test_n1_constants_match_winuser_h \
  'WS_CAPTION = 0x00C00000' 'WS_CAPTION = 0x00C00001'

# F2 把 CAPTION 砍回去 —— **这就是 0.92.0 那个被真机证伪的规格**
mutate_and_expect F2 bin/ds_shell.py "$ORACLE" \
  test_n2_style_bits_include_caption_and_thickframe \
  'needed = (WS_CAPTION | WS_THICKFRAME' 'needed = (WS_THICKFRAME' \
  'style | WS_CAPTION | WS_THICKFRAME' 'style | WS_THICKFRAME'

# F3 把 THICKFRAME 砍掉 —— 上游把它和 CAPTION 当不可分的一对
mutate_and_expect F3 bin/ds_shell.py "$ORACLE" \
  test_n2_style_bits_include_caption_and_thickframe \
  'needed = (WS_CAPTION | WS_THICKFRAME' 'needed = (WS_CAPTION' \
  'style | WS_CAPTION | WS_THICKFRAME' 'style | WS_CAPTION'

# F4 加了位却不装接管 —— 只做前半边 = 窗口长出一条真的标题栏。
#    (第一版这条是把 GWLP_WNDPROC 换成字面量 -4,那**根本没改变功能**,
#     判据绿是对的。变异本身要是没破坏行为,红检就在测一个假问题。)
mutate_and_expect F4 bin/ds_shell.py "$ORACLE" \
  test_n3_caption_requires_nccalcsize_takeover \
  '            self._install_wndproc(form)
            self._apply_native_styles(form)' '            self._apply_native_styles(form)'

# F5 NCCALCSIZE 分支不再吃掉非客户区
mutate_and_expect F5 bin/ds_shell.py "$ORACLE" \
  test_n4_nccalcsize_true_branch_returns_zero \
  '                    self._fit_maximized_to_work_area(hwnd, lparam)
                return 0' '                    self._fit_maximized_to_work_area(hwnd, lparam)
                return 1'

# F6 绕过 WinForms 那一层 —— 它负责的一堆行为会静默失效
mutate_and_expect F6 bin/ds_shell.py "$ORACLE" \
  test_n5_other_messages_go_back_to_the_original_proc \
  'return self._user32.CallWindowProcW(' 'return self._user32.DefWindowProcW('

# F7 回调对象存成局部变量 —— 被 GC 之后 Windows 回调进野内存
mutate_and_expect F7 bin/ds_shell.py "$ORACLE" \
  test_n6_wndproc_callback_is_kept_on_the_instance \
  'self._wndproc_hook = WNDPROC(self._wndproc)' 'local_hook = WNDPROC(self._wndproc)'

# F8 退回"假最大化" —— 业主点名的"放大动画"那一半就死在这里
mutate_and_expect F8 bin/ds_shell.py "$ORACLE" \
  test_n7_maximize_uses_window_state_not_bounds \
  '            form.WindowState = FormWindowState.Maximized
            return True' '            form.Bounds = form.Bounds
            return True'

# F9 还原判断改成恒真 —— **n8 第一版就是被这条咬出来的**(它当时照样绿)
mutate_and_expect F9 bin/ds_shell.py "$ORACLE" \
  test_n8_show_window_does_not_unmaximize \
  '        if minimized:' '        if True:'

# F10 改名漏改一处 —— **本单真犯过的那个 bug,原样做成变异**
#     (窗口一 shown 就 AttributeError,而全量回归 1299 项照样全绿)
mutate_and_expect F10 bin/ds_shell.py "$ORACLE" \
  test_n9_no_dangling_self_method_references \
  'self._on_ui(self._apply_native_styles_and_frame)' 'self._on_ui(self._setup_native_frame)'

# F11 幂等退化成"挂过就不再挂" —— 全屏切回来之后动画消失
mutate_and_expect F11 bin/ds_shell.py "$ORACLE" \
  test_n10_install_is_idempotent_per_handle \
  'if self._wndproc_hook is not None and self._hooked_hwnd == hwnd_now:' 'if self._wndproc_hook is not None:'

# F12 销毁前不解挂(panel P1 那条)—— 回调随对象走,而消息还在发
mutate_and_expect F12 bin/ds_shell.py "$ORACLE" \
  test_n11_wndproc_is_uninstalled_before_destroy \
  '            self.window_api.uninstall_wndproc()
            try:
                self.window.destroy()' '            try:
                self.window.destroy()'

restore
echo "== 还原核对 =="
bad=0
for f in "${SOURCES[@]}"; do
  now="$(sha256sum "$f" | cut -d' ' -f1)"
  if [ "$now" != "${BEFORE[$f]}" ]; then echo "  [BAD] $f 没还原干净"; bad=1; fi
done
[ "$bad" -eq 0 ] && echo "  [OK]   所有被变异的文件都按哈希还原了"

echo "== 红检结束:咬住 $pass 条,漏网 $fail 条 =="
[ "$fail" -eq 0 ] && [ "$bad" -eq 0 ] && exit 0 || exit 1
