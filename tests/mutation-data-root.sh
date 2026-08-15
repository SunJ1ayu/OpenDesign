#!/usr/bin/env bash
# 红检(变异测试)—— 证明 tests/test_data_root.py 这份判据咬得动。
#
# 规矩与 tests/mutation-ds-provision.sh 同一套:
#   1. 变异的是**被测对象**(bin/*.py),不是判据本身。
#   2. 每条变异都指定**靶子**:必须是**那一条**红,不是"随便红了就算过"。
#   3. 跑完把文件原样还回去,并**机械核对**(哈希)还回去了。
#
# 与那份不同的一点:这一单的实现摊在 5 个文件里,所以变异带文件名。
#
# 用法:tests/mutation-data-root.sh
# 退出码:0 = 每条变异都咬住了靶子   1 = 有漏网   2 = 现场问题

set -u
cd "$(dirname "$0")/.."
PY="${PY:-/root/.venvs/design-studio/bin/python}"
ORACLE=tests/test_data_root.py
WORK="$(mktemp -d)"
SRCS=(bin/ds_common.py bin/ds_shell_core.py bin/ds_tools.py bin/ds_taxonomy.py bin/ds_refs.py)

declare -A BEFORE
for s in "${SRCS[@]}"; do
  BEFORE[$s]="$(sha256sum "$s" | cut -d' ' -f1)"
  cp "$s" "$WORK/$(basename "$s").orig"
done

restore() { for s in "${SRCS[@]}"; do cp "$WORK/$(basename "$s").orig" "$s"; done; }
trap 'restore; rm -rf "$WORK"' EXIT

pass=0; fail=0

# mutate_and_expect <编号> <靶子测试名> <文件> <旧串> <新串>
mutate_and_expect() {
  local id="$1" target="$2" file="$3" old="$4" new="$5"
  local out="$WORK/mut-$id.txt"
  restore
  # 08-07 的账:同长度替换 + 同一秒 mtime ⇒ CPython 可能复用旧 .pyc。
  find bin tests -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null
  "$PY" - "$file" "$old" "$new" <<'PYEOF' || { echo "  [BAD]  $id 变异没打上去"; fail=$((fail+1)); return; }
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding="utf-8")
old, new = sys.argv[2], sys.argv[3]
if old not in s:
    sys.exit(f"变异锚点找不到: {old!r}")
p.write_text(s.replace(old, new, 1), encoding="utf-8")
PYEOF
  timeout 600 "$PY" -W ignore "$ORACLE" > "$out" 2>&1
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

echo "== 红检开始(每条变异都要咬住指定的那一条)=="

# M1 env 直接不认 ⇒ 业主的东西照旧写进安装目录(本单要防的头号事故)
mutate_and_expect M1 test_a2_writes_do_not_touch_the_install_tree bin/ds_common.py \
  '    if DATA_ROOT_ENV not in os.environ:
        return ds_root' \
  '    if True:
        return ds_root'

# M2 空串当"没设" ⇒ 静默退回安装目录(缺席家族第四条)
mutate_and_expect M2 test_c5_an_empty_env_value_is_not_treated_as_unset bin/ds_common.py \
  '    if configured == "":' \
  '    if False:'

# M3 拆掉"不许放在会被删的地方" ⇒ 数据根设在 ds/ 里也照收
mutate_and_expect M3 test_c4_env_pointing_inside_the_install_dir_is_refused bin/ds_common.py \
  '        for danger in _deletable_roots(ds_root):' \
  '        for danger in []:'

# M4 危险区退回"上一级永远算" ⇒ 开发/台架误报(这正是 08-15 真发生过的那次)
mutate_and_expect M4 test_c7_a_dev_checkout_does_not_get_false_alarms bin/ds_common.py \
  '    if parent and parent != real and any(
            os.path.exists(os.path.join(parent, m)) for m in _INSTALL_MARKERS):' \
  '    if parent and parent != real:'

# M5 迁移只搬 projects ⇒ 图库和索引留在会被删的地方
mutate_and_expect M5 test_g1_legacy_data_moves_into_the_data_root bin/ds_common.py \
  '_LEGACY_DATA_DIRS = ("projects", "clients", "refs", "organize")' \
  '_LEGACY_DATA_DIRS = ("projects",)'

# M6 迁移覆盖同名 ⇒ 把业主已有的那份盖掉
mutate_and_expect M6 test_g2_never_overwrites_something_already_there bin/ds_common.py \
  '    if os.path.lexists(target):
        report["skipped"].append(rel)
        return' \
  '    if False:
        report["skipped"].append(rel)
        return'

# M7 unknown 不排除代码 ⇒ canary 淹在几千条 bin/*.py 里
mutate_and_expect M7 test_g4_the_unknown_report_is_not_drowned_in_code bin/ds_common.py \
  '    known_top = set(_LEGACY_DATA_DIRS) | set(_LEGACY_DATA_FILES) \
        | set(_CODE_TOP) | set(_CODE_FILES)' \
  '    known_top = set(_LEGACY_DATA_DIRS) | set(_LEGACY_DATA_FILES)'

# M8 外壳不把数据根传给子进程 ⇒ 三个 MCP 与 ds-web 全都回到老行为
mutate_and_expect M8 test_d1_child_env_carries_the_data_root bin/ds_shell_core.py \
  '            "DS_DATA_ROOT": os.path.join(
                os.path.dirname(os.path.realpath(user_home)), "Data"),' \
  ''

# M9 拆掉工作区重叠拦截 ⇒ 业主可以把项目夹设在会被删的地方
mutate_and_expect M9 test_e1_refuses_the_install_dir_itself bin/ds_tools.py \
  '        if ds_common.within(guarded, candidate) or ds_common.within(candidate, guarded):' \
  '        if False:'

# M10 用户分类表读回安装目录 ⇒ 业主手改的规则卸载即失(只读数据那一路)
mutate_and_expect M10 test_f4_a_hand_edited_taxonomy_is_read_from_the_data_root bin/ds_taxonomy.py \
  '    user_path = os.path.join(ds_common.data_root(ds_root), USER_TAXONOMY_REL)' \
  '    user_path = os.path.join(ds_root, USER_TAXONOMY_REL)'

# M11 图片搬走了、索引留下 ⇒ 卸载后"图还在但图库全空"
mutate_and_expect M11 test_f3_the_index_lands_next_to_the_images bin/ds_refs.py \
  '    return os.path.join(ds_common.data_root(ds_root), "refs-index.md")' \
  '    return os.path.join(ds_root, "refs-index.md")'

restore
echo
bad=0
for s in "${SRCS[@]}"; do
  now="$(sha256sum "$s" | cut -d' ' -f1)"
  [ "$now" = "${BEFORE[$s]}" ] || { echo "🔴 $s 没还原干净"; bad=1; }
done
[ "$bad" -eq 0 ] && echo "被测文件全部原样还回(5 个文件哈希一致)"
echo "== 红检结束:咬住 $pass 条,漏网 $fail 条 =="
[ "$fail" -eq 0 ] && [ "$bad" -eq 0 ] && exit 0 || exit 1
