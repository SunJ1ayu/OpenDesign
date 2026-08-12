#!/usr/bin/env bash
# 变异测试(track opendesign-cnum-zeropad):证明判据**咬得动**。
#
# 红检答的是"判据在问本轮改动吗",变异答的是另一件事:
# **实现里种一个真 bug,判据会不会照样绿。** 两个都要。
#
# 硬规矩(08-11 栽过三次,全是脚本自己坏了却报"判据没咬住"):
#   - 变异打不上去(替换串没命中)⇒ **硬失败**,不许当成"判据漏了";
#   - 每次跑前后清 __pycache__(08-07:同长度替换 + 同秒 mtime ⇒ CPython 复用旧 .pyc,
#     既能造假绿也能造假红);
#   - 开跑前先确认基线是绿的,否则整场没有意义。
set -uo pipefail
cd "$(dirname "$0")/../.."                    # 仓库根
PY="${PY:-/root/.venvs/design-studio/bin/python}"
ORACLE=($PY tests/test_ds_cnum.py)
IMPL=(bin/ds_tools.py bin/ds_todo.py)
BK="$(mktemp -d)"; trap 'restore; rm -rf "$BK"' EXIT

purge_pyc() { find bin tests -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null; true; }
save()    { for f in "${IMPL[@]}"; do cp "$f" "$BK/$(basename "$f")"; done; }
restore() { for f in "${IMPL[@]}"; do [ -f "$BK/$(basename "$f")" ] && cp "$BK/$(basename "$f")" "$f"; done; purge_pyc; }

bitten=0; escaped=0

# mutate <名字> <文件> <原串> <替换串>
mutate() {
  local name="$1" file="$2" from="$3" to="$4"
  restore
  FROM="$from" TO="$to" python3 - "$file" <<'PY' || { echo "🔴 变异脚本自己坏了(替换串没命中):$name"; exit 9; }
import os, sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
frm, to = os.environ["FROM"], os.environ["TO"]
if s.count(frm) != 1:
    print(f"命中 {s.count(frm)} 次(要求恰好 1 次)", file=sys.stderr)
    sys.exit(1)
open(p, "w", encoding="utf-8").write(s.replace(frm, to))
PY
  purge_pyc
  if "${ORACLE[@]}" >/dev/null 2>&1; then
    echo "  ❌ $name —— 判据没咬住(种了 bug 还是绿的)"; escaped=$((escaped+1))
  else
    echo "  ✅ $name —— 判据咬住了"; bitten=$((bitten+1))
  fi
  restore
}

save
purge_pyc
echo "== 基线检查:没变异时判据必须绿 =="
if ! "${ORACLE[@]}" >/dev/null 2>&1; then
  echo "🔴 基线就是红的,变异测试没有意义。先把判据跑绿。"; exit 1
fi
echo "  ✅ 基线绿"
echo
echo "== 开始变异 =="

# W1 备注命中行不再保前缀字节,改回"整行重写成规范形式"
#    —— 攻题 Q4 掰过来的那条(会同时撞坏 no-op 契约)。期望 A1/A1b/N6 红。
mutate "W1 备注行不保前缀字节" bin/ds_tools.py \
  'new_line = lines[k][:m.start(2)] + note' \
  'new_line = note_line'

# W2 删备注退回"按字符串前缀认" —— 前导零/全角数字的行就删不掉了。期望 A2/A1d/A5d 红。
mutate "W2 删备注退回字符串匹配" bin/ds_tools.py \
  'if ds_todo.history_note_line_cnum(lines[k]) == num:' \
  'if lines[k].startswith(f"- C{num} 备注"):'

# W3 截止日那处漏改(五处只改四处的典型形态)。期望 A3_due_date / A4c 红。
mutate "W3 set_due_date 漏改" bin/ds_tools.py \
  '        hits = [i for i, ln in enumerate(lines) if ds_todo.change_line_cnum(ln) == num]
        if len(hits) != 1:
            box["write"] = False
            return {"error": "change_not_found" if not hits else "ambiguous_change"}
        i = hits[0]
        _, cur_due = ds_common.split_due(lines[i])' \
  '        _lr = re.compile(rf"^(- \[)(?P<old>[^\]]*)(\]\s+C{num}\b)")
        hits = [i for i, ln in enumerate(lines) if _lr.match(ln)]
        if len(hits) != 1:
            box["write"] = False
            return {"error": "change_not_found" if not hits else "ambiguous_change"}
        i = hits[0]
        _, cur_due = ds_common.split_due(lines[i])'

# W4 入口不做整数归一(半吊子修法:只改锚点、不归一入参)。期望 A4/A4b/A4c 红。
mutate "W4 入口不归一(返回字符串)" bin/ds_tools.py \
  '    m = re.fullmatch(r"C?(\d+)", str(value).strip())
    if not m:
        return None
    return int(m.group(1))' \
  '    m = re.fullmatch(r"C?(\d+)", str(value).strip())
    if not m:
        return None
    return int(m.group(1).lstrip("0") or "0") if str(value).strip().lstrip("C").startswith("0") is False else int("9" + m.group(1))'

# W5 歧义检查被拆掉(fail closed 变成"取第一条")。期望 A4/A5c 红。
mutate "W5 歧义不再 fail closed" bin/ds_tools.py \
  '        hits = [i for i, ln in enumerate(lines) if _change_line_cnum_for_edit(ln) == num]
        if len(hits) != 1:' \
  '        hits = [i for i, ln in enumerate(lines) if _change_line_cnum_for_edit(ln) == num]
        hits = hits[:1] if hits else hits
        if len(hits) != 1:'

# W6 改状态时重拼整行(破 BLOCK-2 字节铁律:C03 被规范化成 C3)。期望 N4/A3_status 红。
mutate "W6 改状态时重拼主行" bin/ds_tools.py \
  '                lines[i] = _STATUS_PREFIX_RE.sub(rf"\g<1>{new_status}\g<3>", lines[i], count=1)
                changed = True
                changed_fields.add("status")' \
  '                _rest = _EDIT_PREFIX_RE.match(lines[i]).group("text")
                lines[i] = f"- [{new_status}] C{num} " + _rest
                changed = True
                changed_fields.add("status")'

# W7 读侧口径被"顺手收紧"(全角数字不再认)—— 这一单明令不许动读侧。期望 A5 组红。
mutate "W7 读侧改成 ASCII-only" bin/ds_todo.py \
  '    m = HISTORY_NOTE_RE.match(line)
    if not m:
        return None
    return int(m.group(1))' \
  '    m = HISTORY_NOTE_RE.match(line)
    if not m or not m.group(1).isascii():
        return None
    return int(m.group(1))'

echo
echo "=== 变异测试:${bitten} 处被咬住,${escaped} 处漏网 ==="
[ "$escaped" -eq 0 ]
