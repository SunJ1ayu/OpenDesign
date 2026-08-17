#!/usr/bin/env bash
# 一次性红检:证明「豁免」那两条新收紧的规则真的咬得动(2026-08-17,四审后)。
#
# 为什么不进 mutation-ds-shell-core.sh:那个脚本只变异 bin/ds_shell_core.py,
# 而豁免标记全在 ds_openfolder.py / ds_provision.py 里。**这是一次性证明,
# 不是常驻防线** —— 说清楚,免得下次有人把它当成"这块一直有人守着"。
#
# 用法:
#   tests/redcheck-exempt-window.sh                 # 用当前的闸跑,期望 2 咬 0 漏
#   tests/redcheck-exempt-window.sh --against 67780a7   # 换成那个 commit 的旧闸再跑
#
# 第二种用法是**证明这次收紧不是装饰**:同一份红检,旧闸 0 咬 2 漏、新闸 2 咬 0 漏。
# 没有这个对照,"新判据全红"也可能只是它本来就红在别处。
set -uo pipefail
cd /root/.openclaw/workspace/projects/design-studio
PY=/root/.venvs/design-studio/bin/python
SRC=bin/ds_openfolder.py
GATE=tests/test_no_console_window.py
AGAINST=""
[ "${1:-}" = "--against" ] && { AGAINST="${2:?--against 后面要跟 commit}"; }
if [ -n "$AGAINST" ]; then
  GATE_BAK="$(mktemp)"; cp "$GATE" "$GATE_BAK"
  git show "$AGAINST:$GATE" > "$GATE" || { echo "取不到 $AGAINST 的闸"; exit 64; }
  echo "⚠ 正在用 $AGAINST 的**旧闸**跑 —— 期望它漏,漏了才说明新闸有意义"
fi
# ⚠ 只能有**一个** EXIT trap:第二个 `trap ... EXIT` 会把第一个覆盖掉,
#   于是"跑完把闸换回来"会静静地不发生 —— 写这句时当场差点踩到。
gate_back() { [ -n "$AGAINST" ] && { cp "$GATE_BAK" "$GATE"; rm -f "$GATE_BAK"; }; return 0; }
WORK="$(mktemp -d)"
BEFORE="$(sha256sum "$SRC" | cut -d' ' -f1)"
cp "$SRC" "$WORK/原件.py"
restore() { cp "$WORK/原件.py" "$SRC"; }
trap 'restore; gate_back; rm -rf "$WORK"' EXIT

pass=0; fail=0
expect_red() {   # expect_red <名字> <python 改写脚本>
  local name="$1" script="$2"
  restore
  $PY - "$SRC" <<PYEOF || { echo "  [BAD]  $name:变异没打上去"; fail=$((fail+1)); return; }
$script
PYEOF
  if $PY -B -W ignore -m unittest tests.test_no_console_window > "$WORK/out.txt" 2>&1; then
    echo "  [BAD]  $name -> **判据全绿**,这条规则是摆设"
    fail=$((fail+1))
  else
    echo "  [OK]   $name -> 如期红了"
    pass=$((pass+1))
  fi
}

echo "== 一次性红检:豁免的两条新规则 =="

# ① 豁免理由空着 —— 旧实现会把下一行代码当成"理由"从而放行
expect_red "①理由空着" '
import sys,pathlib
p=pathlib.Path(sys.argv[1]); s=p.read_text(encoding="utf-8")
old="""    # no-console-exempt: os.startfile 不创建进程,它把请求交给 shell(ShellExecute),
    # 由资源管理器/关联程序自己以 GUI 形态打开 —— 没有控制台可弹。"""
new="""    # no-console-exempt:"""
assert old in s, "锚点找不到"
p.write_text(s.replace(old,new,1),encoding="utf-8")
'

# ② 豁免与调用点之间隔着一行代码 —— 旧实现的 3 行窗口照样够得着
expect_red "②中间隔了代码" '
import sys,pathlib
p=pathlib.Path(sys.argv[1]); s=p.read_text(encoding="utf-8")
old="""    # 由资源管理器/关联程序自己以 GUI 形态打开 —— 没有控制台可弹。
    os.startfile(path)"""
new="""    # 由资源管理器/关联程序自己以 GUI 形态打开 —— 没有控制台可弹。
    _ = 1
    os.startfile(path)"""
assert old in s, "锚点找不到"
p.write_text(s.replace(old,new,1),encoding="utf-8")
'

restore
AFTER="$(sha256sum "$SRC" | cut -d' ' -f1)"
echo
if [ "$BEFORE" != "$AFTER" ]; then
  echo "🔴 还原失败:$SRC 和跑之前不一样了"
  exit 2
fi
echo "被测文件已原样还回(哈希一致 ${BEFORE:0:12})"
echo "== 结束:咬住 $pass 条 / 漏网 $fail 条 =="
[ "$fail" -eq 0 ]
