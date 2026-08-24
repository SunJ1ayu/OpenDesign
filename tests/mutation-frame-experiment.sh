#!/usr/bin/env bash
# 红检(变异测试)—— 证明 **0.94.0 那批"方案 B 必须收进开关"的判据**咬得动。
#
# 覆盖 tests/test_window_frame_experiment.py 的 f1~f9。
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
ORACLE=tests/test_window_frame_experiment.py

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

echo "== 红检开始(0.94.0:方案 B 收进默认关闭的开关)=="

# M1 默认变成"关" —— 业主装上还是没有动画,他为这件事等了四个版本
mutate_and_expect M1 bin/ds_shell.py "$ORACLE" \
  test_f2_default_is_on \
  '        return not (_app_dir() / DISABLE_FLAG).is_file()' \
  '        return False'

# M2 逃生门失灵(永远开)—— 万一它把窗口搞坏了,业主关不掉
mutate_and_expect M2 bin/ds_shell.py "$ORACLE" \
  test_f3_flag_file_turns_it_off \
  '        return not (_app_dir() / DISABLE_FLAG).is_file()' \
  '        return True'

# M3 读不到环境时倒向"开" —— 方向反了:业主会连界面都看不见
mutate_and_expect M3 bin/ds_shell.py "$ORACLE" \
  test_f4_unreadable_environment_is_off_not_on \
  '    except Exception:
        return False' \
  '    except Exception:
        return True'

# M4 接管挪到开关外面 —— 默认路径又开始动窗口的边框计算了
mutate_and_expect M4 bin/ds_shell.py "$ORACLE" \
  test_f5_wndproc_install_is_behind_the_switch \
  '            if frame_animation_on() and not self._frame_gave_up:
                # 方案 B 全套。**先接管非客户区,再贴位** —— 顺序见上面。
                self._install_wndproc(form)' \
  '            self._install_wndproc(form)
            if frame_animation_on() and not self._frame_gave_up:
                # 方案 B 全套。**先接管非客户区,再贴位** —— 顺序见上面。'

# M5 默认路径改去贴五个位(含 CAPTION|THICKFRAME)—— 0.93 的病根
mutate_and_expect M5 bin/ds_shell.py "$ORACLE" \
  test_f6_frame_style_bits_are_behind_the_switch \
  '                self._apply_safe_styles(form)' \
  '                self._apply_native_styles(form)'

# M6 真最大化脱离开关 —— 没有 NCCALCSIZE 接管时它会盖住任务栏
mutate_and_expect M6 bin/ds_shell.py "$ORACLE" \
  test_f7_default_path_uses_fake_maximize \
  '            if frame_animation_on():
                from System.Windows.Forms import FormWindowState' \
  '            if True:
                from System.Windows.Forms import FormWindowState'

# M7 开关写成否定式 —— f5~f7 会**反向放行**,闸还是绿的而产品是坏的
mutate_and_expect M7 bin/ds_shell.py "$ORACLE" \
  test_f8_switch_is_written_in_the_positive_form \
  '            if frame_animation_on() and not self._frame_gave_up:
                # 方案 B 全套' \
  '            if not frame_animation_on() and not self._frame_gave_up:
                # 方案 B 全套'

# M8 诊断没人叫 —— 开关打开也拿不到任何数字,又要多跑一趟真机
mutate_and_expect M8 bin/ds_shell.py "$ORACLE" \
  test_f9_experiment_path_leaves_diagnostics \
  '                info = self._log_frame_diagnostics(form)
' \
  '                info = None
'

# M9 诊断里不再枚举子窗口 —— WebView2 那块还在不在就查不出来了
#    🔴 这条专治"判据靠 docstring 绿":函数注释里写着 EnumChildWindows,
#       f9 第一版就是这么被骗过去的。
mutate_and_expect M9 bin/ds_shell.py "$ORACLE" \
  test_f9_experiment_path_leaves_diagnostics \
  '            user32.EnumChildWindows(hwnd, ENUMPROC(_each), 0)' \
  '            pass'

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
