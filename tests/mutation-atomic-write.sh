#!/usr/bin/env bash
# 红检 —— 证明 tests/test_ds_atomic_write.py(aw1~aw17b)咬得动(track opendesign-atomic-archive-write)。
#
# 规矩同 tests/mutation-ds-update-apply.sh:变异**被测对象**(bin/ds_common.py、bin/ds_refs.py、bin/ds_tools.py),
# 每条指定靶子(**必须是它自己红**,红在别处不算红检过),跑完原样还回去并核哈希。
#
# 🔴 最要紧的是 m1 / m7 / m8:把"锁 + 临时文件 + 替换"退回**原地截断重写**。
#    那正是这单要修的病(强杀/盘满在截断之后 ⇒ 业主档案只剩空文件或半截),三处写口各一条。
# 🔴 aw2(真强杀)/ aw6(并发读者)是概率性的回归护栏,design.md 说好了**红检以 aw1 为准**,这里不拿它们当靶子。
# 🔴 aw12 只在 Windows 上真问(本机恒绿),由 .github/workflows/windows-atomic-probe.yml 跑,这里不变异。
set -u
cd "$(dirname "$0")/.."
PY="${PY:-/root/.venvs/design-studio/bin/python}"
ORACLE=tests.test_ds_atomic_write

FILES=(bin/ds_common.py bin/ds_refs.py bin/ds_tools.py)
WORK="$(mktemp -d)"
BEFORE="$(sha256sum "${FILES[@]}")"
for f in "${FILES[@]}"; do mkdir -p "$WORK/orig/bin"; cp -p "$f" "$WORK/orig/$f"; done
restore() {
  for f in "${FILES[@]}"; do cp -p "$WORK/orig/$f" "$f"; done
  find bin tests -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
}
trap 'restore; rm -rf "$WORK"' EXIT

bites=0; escapes=0

# mutate_and_expect <编号> <靶子测试名> <文件> <old> <new>
mutate_and_expect() {
  local id="$1" target="$2" file="$3" old="$4" new="$5"
  restore
  "$PY" - "$file" "$old" "$new" <<'PYEOF' || { echo "  [BAD]  $id 变异没打上去(靶子文本没匹配到)"; escapes=$((escapes+1)); return; }
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding="utf-8")
old, new = sys.argv[2], sys.argv[3]
if s.count(old) != 1:
    print(f"    锚点出现 {s.count(old)} 次,不是 1 次:{old!r}")
    sys.exit(1)
p.write_text(s.replace(old, new), encoding="utf-8")
PYEOF
  local out="$WORK/mut-$id.txt"
  timeout 600 "$PY" -m unittest "$ORACLE" > "$out" 2>&1
  if grep -E '^(FAIL|ERROR): ' "$out" | grep -qF -- "$target"; then
    echo "  [咬住] $id → $target"; bites=$((bites+1))
  elif grep -q "^OK" "$out"; then
    echo "  [漏网] $id 判据全绿 —— $target 没咬住这个变异"; escapes=$((escapes+1))
  else
    echo "  [红在别处] $id 红了,但不是 $target(红在别处等于没红检过)"
    sed -n 's/^\(FAIL\|ERROR\): \(.*\)$/      实际红的:\2/p' "$out" | head -3
    escapes=$((escapes+1))
  fi
}

echo "== 红检 档案原子写 =="

# m1 🔴 locked_rw 退回原地截断重写(三处写口里最热的那一个)
mutate_and_expect m1 test_aw1_a_write_that_dies_halfway_leaves_the_old_archive bin/ds_common.py \
  '        if box["write"]:
            atomic_write_text(path, "\n".join(box["lines"]))' \
  '        if box["write"]:
            with open(path, "w", encoding="utf-8") as _fh:
                _fh.write("\n".join(box["lines"]))'

# m2 失败路径不删临时文件
mutate_and_expect m2 test_aw3_no_tmp_litter_after_a_failed_or_a_successful_write bin/ds_common.py \
  '                os.unlink(tmp)' '                pass'

# m3 write=False 也照写
mutate_and_expect m3 test_aw4_write_false_changes_nothing bin/ds_common.py \
  '        if box["write"]:
            atomic_write_text(' \
  '        if True:
            atomic_write_text('

# m4 编码口径变了(带 BOM)⇒ 新旧产物字节不同
mutate_and_expect m4 test_aw7a_bytes_are_what_text_mode_would_have_written bin/ds_common.py \
  'tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory,' \
  'tempfile.NamedTemporaryFile(mode="w", encoding="utf-8-sig", dir=directory,'

# m5 不保留权限位 ⇒ 0644 被临时文件的 0600 悄悄收紧
mutate_and_expect m5 test_aw7b_permission_bits_are_kept bin/ds_common.py \
  '        os.chmod(tmp, mode)' '        pass'

# m6 不解符号链接 ⇒ 链接被换成普通文件
mutate_and_expect m6 test_aw8_the_link_survives_and_the_real_file_changes bin/ds_common.py \
  '    real = os.path.realpath(path)
    directory = os.path.dirname(real)' \
  '    real = path
    directory = os.path.dirname(real)'

# m7 🔴 add_style 退回原地截断重写
mutate_and_expect m7 test_aw9_add_style_dying_halfway_keeps_the_vocabulary bin/ds_refs.py \
  '        ds_common.atomic_write_text(path, text)' \
  '        with open(path, "w", encoding="utf-8") as _fh:
            _fh.write(text)'

# m8 🔴 rename_project 改标题退回原地截断重写
#    (首跑靶子是 aw10 ⇒ **漏网**:aw10 夹具首行不是「# 旧名」、故障先落在①,问不到④。补了 aw10b,见 d813814)
mutate_and_expect m8 test_aw10b_rename_dying_while_retitling_the_archive_keeps_it_whole bin/ds_tools.py \
  '            ds_common.atomic_write_text(old_path, body)' \
  '            with open(old_path, "w", encoding="utf-8") as _fh:
                _fh.write(body)'

# m9 锁形同虚设 ⇒ 两个进程各 +1 会丢更新
mutate_and_expect m9 test_aw5_two_processes_never_lose_an_increment bin/ds_common.py \
  '    with open(lock_path, "a+b") as lock_fh, ds_lock.exclusive(lock_fh):
        yield' \
  '    yield'

# m10 ds_tools 里又长出第二份 _replace_with_retry
mutate_and_expect m10 test_aw13_replace_with_retry_is_defined_once_in_ds_common bin/ds_tools.py \
  'def _write_workspace_json(cfg_path: str, obj: dict) -> None:' \
  'def _replace_with_retry(src, dst):
    os.replace(src, dst)


def _write_workspace_json(cfg_path: str, obj: dict) -> None:'

# m11 替换之前不刷盘(断电那一半,本机只能钉结构)
mutate_and_expect m11 test_aw14_fsync_happens_before_the_replace bin/ds_common.py \
  '            os.fsync(fh.fileno())' '            pass'

# m12 只读档案不再提前拒绝 ⇒ Linux(root)上硬写进去 / Windows 上空转 2 秒留只读残骸(评审 Kimi 那条)
mutate_and_expect m12 test_aw15_a_read_only_archive_is_refused_without_litter bin/ds_common.py \
  '    if archive_read_only(real):
        raise PermissionError(errno.EACCES, "档案是只读的,改不了", real)' \
  '    if False:
        raise PermissionError(errno.EACCES, "档案是只读的,改不了", real)'

# m13 改名提交点退回裸 os.replace(aw12c 的 Windows 行为本机照不出,这里咬结构钉 aw16)
mutate_and_expect m13 test_aw16_rename_project_commit_point_uses_replace_with_retry bin/ds_tools.py \
  '        ds_common.replace_with_retry(old_path, new_path, attempts=ds_common.ARCHIVE_REPLACE_ATTEMPTS)' \
  '        os.replace(old_path, new_path)'

# m14 闸前清单漏掉档案本体 ⇒ ①先提交、④再抛,链接指向新名、档案还叫旧名(评审 r2 DeepSeek 那条)
mutate_and_expect m14 test_aw17_renaming_a_read_only_archive_changes_nothing bin/ds_tools.py \
  '    out = [old_path]                                   # ④ 改名(可能连标题)一定动档案本体' \
  '    out = []                                           # ④ 改名(可能连标题)一定动档案本体'

# m15 闸前清单漏掉客户备忘 / 索引(①)⇒ 它们只读时照样改到一半(评审 r3 GLM 那条)
mutate_and_expect m15 test_aw17b_any_read_only_file_the_rename_would_rewrite_is_refused_up_front bin/ds_tools.py \
  '                if link_old in fh.read():
                    out.append(path)' \
  '                if False:
                    out.append(path)'

# m16 闸前清单漏掉 workspace.json(③)
mutate_and_expect m16 test_aw17b_any_read_only_file_the_rename_would_rewrite_is_refused_up_front bin/ds_tools.py \
  '    if isinstance(raw, dict) and isinstance(raw.get("projects"), dict) and old in raw["projects"]:
        out.append(cfg_path)' \
  '    if False:
        out.append(cfg_path)'

# 对照组:只加一行注释 ⇒ 必须仍然全绿(变异框架本身没有误报)
restore
"$PY" - bin/ds_common.py <<'PYEOF'
import pathlib
p = pathlib.Path("bin/ds_common.py"); s = p.read_text(encoding="utf-8")
anchor = 'def atomic_write_text(path: str, text: str,'
assert s.count(anchor) == 1
p.write_text(s.replace(anchor, "# 对照组:只是一行注释,open(path, \"w\")\n" + anchor), encoding="utf-8")
PYEOF
if timeout 600 "$PY" -m unittest "$ORACLE" > "$WORK/ctl.txt" 2>&1; then
  echo "  [对照组] c1 只加注释(含 open(path, \"w\") 字样)→ 仍然全绿(没有误报)"
else
  echo "  [对照组失败] c1 只加注释就红了 —— 判据有误报"; escapes=$((escapes+1))
  sed -n 's/^\(FAIL\|ERROR\): \(.*\)$/      实际红的:\2/p' "$WORK/ctl.txt" | head -3
fi

echo "== 咬住 $bites / 漏网 $escapes =="
restore
if [ "$(sha256sum "${FILES[@]}")" != "$BEFORE" ]; then
  echo "🔴 恢复失败:被测文件与开跑前对不上 —— 工作树需要人来收拾"
  exit 9
fi
echo "还原核对:3 个被测文件与开跑前逐字节一致"
[ "$escapes" -eq 0 ]
