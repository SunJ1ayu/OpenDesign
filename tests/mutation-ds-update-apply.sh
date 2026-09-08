#!/usr/bin/env bash
# 红检 —— 证明 tests/test_ds_update_apply.py 那 30 条咬得动
# (track opendesign-in-app-update-install,第二刀"真去装")。
#
# 规矩同 tests/mutation-ds-update.sh:变异**被测对象**(bin/ds_update_apply.py),
# 每条指定靶子(**必须是它自己红**,红在别处不算红检过),跑完原样还回去并核哈希。
#
# 🔴 为什么另起一支、不塞进 mutation-ds-update.sh:那支按**测试名字**选靶子,
#    而这一批是新名字(t13~t18)。两批混在一起,靶子对不对得上全靠人眼。
#
# 🔴 这一批里最要紧的两条,是"看起来在工作"的路:
#    m1(digest 没给就跳过校验)—— 资产被换过也照装不误;
#    m8(装到活树上)—— 装到一半断电就是一半新一半旧,而 .nsi:92 说删不掉会悄悄跳过。
set -u
cd "$(dirname "$0")/.."
PY="${PY:-/root/.venvs/design-studio/bin/python}"

SRC=bin/ds_update_apply.py
# t20 咬的是**跨文件契约**,所以这支脚本管两个被测文件:python 这边发旗子,
# NSIS 那边认旗子。只变异其中一边,另一边的洞就永远照不出来。
NSI=installer/OpenDesign.nsi
ORACLE=tests.test_ds_update_apply
MUT_SRC="$SRC"              # 当前这条变异打在哪个文件上
WORK="$(mktemp -d)"
BEFORE="$(sha256sum "$SRC" | cut -d' ' -f1)"
BEFORE_NSI="$(sha256sum "$NSI" | cut -d' ' -f1)"
cp -p "$SRC" "$WORK/orig.py"
cp -p "$NSI" "$WORK/orig.nsi"
restore() {
  cp -p "$WORK/orig.py" "$SRC"
  cp -p "$WORK/orig.nsi" "$NSI"
  find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
}
trap 'restore; rm -rf "$WORK"' EXIT

bites=0; escapes=0

# mutate_and_expect <编号> <靶子测试名> <old> <new>
mutate_and_expect() {
  local id="$1" target="$2" old="$3" new="$4"
  restore
  "$PY" - "$MUT_SRC" "$old" "$new" <<'PYEOF' || { echo "  [BAD]  $id 变异没打上去(靶子文本没匹配到)"; escapes=$((escapes+1)); return; }
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding="utf-8")
old, new = sys.argv[2], sys.argv[3]
if s.count(old) != 1:
    print(f"    锚点出现 {s.count(old)} 次,不是 1 次:{old!r}")
    sys.exit(1)
p.write_text(s.replace(old, new), encoding="utf-8")
PYEOF
  local out="$WORK/mut-$id.txt"
  "$PY" -m unittest "$ORACLE" > "$out" 2>&1
  if grep -qE "^(FAIL|ERROR): $target" "$out"; then
    echo "  [咬住] $id → $target"
    bites=$((bites+1))
  elif grep -q "^OK" "$out"; then
    echo "  [漏网] $id 判据全绿 —— $target 没咬住这个变异"
    escapes=$((escapes+1))
  else
    echo "  [红在别处] $id 红了,但不是 $target(红在别处等于没红检过)"
    sed -n 's/^\(FAIL\|ERROR\): \(.*\)$/      实际红的:\2/p' "$out" | head -3
    escapes=$((escapes+1))
  fi
}

echo "== 红检 bin/ds_update_apply.py =="

# --- 信任根那一段 ---

# m1 🔴 没给 digest 就跳过校验 —— 一条"看起来在工作"的路
mutate_and_expect m1 test_t15a_missing_digest_is_a_failure_not_a_skip \
  '    digest = parse_digest(asset.get("digest"))
    if digest is None:' \
  '    digest = parse_digest(asset.get("digest"))
    if False:'

# m2 digest 形状放宽(长度不校验)
mutate_and_expect m2 test_t15b_malformed_digest_is_a_failure \
  '_SHA256_RE = re.compile(r"^sha256:([0-9a-f]{64})$", re.IGNORECASE)' \
  '_SHA256_RE = re.compile(r"^sha256:([0-9a-f]+)$", re.IGNORECASE)'

# m3 校验不过照装不误
mutate_and_expect m3 test_t4a_refuses \
  '    if got != digest:' \
  '    if False:'

# m4 🔴 拿版本号拼下载地址(第一刀 F1 那个坑:拼出来的 tag 点开 404)
mutate_and_expect m4 test_t14a_downloader_gets_the_exact_url_github_gave \
  '    url = asset.get("url")' \
  '    url = ("https://github.com/SunJ1ayu/OpenDesign/releases/download/win-installer-%s/%s" % (expect_version, asset.get("name")))'

# --- 活树与死线 ---

# m5 🔴 装到活树上(重拍前那个方案的形状)
mutate_and_expect m5 test_t16a_success_path_does_not_touch_the_live_tree \
  '        rc = install(dest, new_dir)' \
  '        rc = install(dest, paths["live"])'

# m6 校验失败留下半棵 .new(不是"当无事发生")
mutate_and_expect m6 test_t4c_new_dir_is_gone \
  '        _cleanup(dest, paths["new"])' \
  '        os.makedirs(paths["new"], exist_ok=True)'

# m7 新树不完整也交棒(不查哨兵)
mutate_and_expect m7 test_t5a_missing_sentinel_aborts \
  '    if not os.path.isfile(sentinel):' \
  '    if False:'

# m8 新树版本号不比对(装了个旧的也算成功)
mutate_and_expect m8 test_t5b_wrong_version_in_new_tree_aborts \
  '    if got != str(expect_version):' \
  '    if False:'

# m9 豁免写成通配符(design 里明写"不许用通配符糊过去")
mutate_and_expect m9 test_t13a_logs_exemption_is_a_named_dir_not_a_glob \
  'DATA_ROOT_EXEMPT_DIRS = ("Logs",)' \
  'DATA_ROOT_EXEMPT_DIRS = ("Logs*",)'

# m10 死线少守一层(UserData 掉出保护名单)
mutate_and_expect m10 test_t13b_protected_dirs_are_named \
  'DATA_ROOT_PROTECTED_DIRS = ("Data", "UserData")' \
  'DATA_ROOT_PROTECTED_DIRS = ("Data",)'

# m11 🔴 段① 往 UserData 里写(死线本身)
mutate_and_expect m11 test_t13c_stage_one_writes_nothing_under_data_root_but_logs \
  '    logs = os.path.join(root, DATA_ROOT_EXEMPT_DIRS[0])' \
  '    logs = os.path.join(root, "UserData")'

# --- 接力脚本的结构(行为归 Windows CI 的 e3/e4) ---

# m12 🔴 收摊闸挪到改名之后 —— 重拍后锚点搬家要钉的正是这件事
mutate_and_expect m12 test_t6a_teardown_gate_comes_before_any_rename \
  '    for i, step in enumerate(steps):' \
  '    steps = steps[1:] + steps[:1]
    for i, step in enumerate(steps):'

# m13 收摊失败不删 .new(留着半棵新树)
mutate_and_expect m13 test_t6b_failed_teardown_deletes_new_and_stops \
  '            "on_fail": ["delete_new", "abort"],' \
  '            "on_fail": ["abort"],'

# m14 渲染器悄悄丢掉最后一步
mutate_and_expect m14 test_t6c_renderer_keeps_every_step_and_their_order \
  '    for step in plan:
        out.append(step["marker"])' \
  '    for step in plan[:-1]:
        out.append(step["marker"])'

# m15 回滚步没了(换名中断就回不去)
mutate_and_expect m15 test_t17a_plan_has_a_rollback_that_puts_old_back \
  '            "kind": "rollback",' \
  '            "kind": "rollback_disabled",'

# --- 收口验收 ---

# m16 🔴 opener 用默认的 ⇒ 问 127.0.0.1 也跟着系统代理走(0.98.1 栽过)
mutate_and_expect m16 test_t18b_opener_bypasses_the_system_proxy \
  '    return urllib.request.build_opener(urllib.request.ProxyHandler({}))' \
  '    return urllib.request.build_opener()'

# m17 不看 nonce ⇒ 旧进程的应答也算"新版起来了"
mutate_and_expect m17 test_t18c_answer_without_the_nonce_is_not_accepted \
  '    if payload.get("nonce") != nonce:' \
  '    if False:'

# m18 不看版本号 ⇒ 换名没生效也算成功
mutate_and_expect m18 test_t18f_right_nonce_but_old_version_is_not_accepted \
  '    if str(payload.get("version") or "") != str(expect_version):' \
  '    if False:'

# --- 反误报对照组(方向与上面相反:改了不该红的地方,必须仍然全绿)---
restore
"$PY" - "$SRC" <<'PYEOF'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding="utf-8")
p.write_text(s.replace('SENTINEL_REL = os.path.join("ds", "bin", "ds_shell.py")',
                       '# 反误报对照:这行注释里写了 releases/download,闸不许因此变红\nSENTINEL_REL = os.path.join("ds", "bin", "ds_shell.py")'),
             encoding="utf-8")
PYEOF
if "$PY" -m unittest "$ORACLE" >"$WORK/mut-c1.txt" 2>&1 && grep -q "^OK" "$WORK/mut-c1.txt"; then
  echo "  [对照组] c1 只在注释里写 releases/download → 仍然全绿(没有误报)"
  bites=$((bites+1))
else
  echo "  [误报!] c1 注释里提一下就红了 —— 这道闸会逼人删掉解释才能过"
  escapes=$((escapes+1))
fi

# ── t20:/UPDATE 跨文件契约(python 发旗子 / NSIS 认旗子)──────────────────
#
# 🔴 这一组存在的全部理由:死线 t13 在 Linux 上用的是**替身安装器**,
#    走不到真 NSIS。契约的任何一边被悄悄改掉,t13 照样全绿。

MUT_SRC="$SRC"
# m19 python 这边改了旗子名(NSIS 那边照样只认老的)
#     ⚠️ 靶子一开始挑成了 t20a,红检报"红在别处" —— t20a 问的是"发出去的 argv 里
#        有没有这个常量",常量改名它当然还在。**该红的是跨文件那条(t20b)**,
#        它比对的是 python 的常量与 NSIS 真正解析的那一行。靶子搬到问得出的地方。
mutate_and_expect m19 test_t20b_the_nsi_parses_that_exact_flag \
  'INSTALL_UPDATE_FLAG = "/UPDATE"' \
  'INSTALL_UPDATE_FLAG = "/SILENTUPDATE"'

# m20 /D= 不再是最后一个参数(NSIS 的硬规矩,排错了这一位安装目录就不对)
mutate_and_expect m20 test_t20a_installer_is_invoked_with_the_update_flag \
  'cmd = [setup_path, "/S", INSTALL_UPDATE_FLAG, "/D=%s" % target_dir]' \
  'cmd = [setup_path, "/S", "/D=%s" % target_dir, INSTALL_UPDATE_FLAG]'

MUT_SRC="$NSI"
# m21 🔴 NSIS 那边把把守撤了 ⇒ 更新期照跑 provisioning ⇒ 死线破,而 t13 全绿
mutate_and_expect m21 test_t20c_provisioning_is_guarded_by_the_update_flag \
  '  ${If} $UpdateMode != "1"
    Call ProvisionConfig
  ${EndIf}' \
  '  Call ProvisionConfig'

# m22 把守还在,但守的是别的东西(把"看结构"和"看字面"分开:文件里仍然有 /UPDATE)
mutate_and_expect m22 test_t20c_provisioning_is_guarded_by_the_update_flag \
  '  ${If} $UpdateMode != "1"' \
  '  ${If} $R9 != "1"'

# m23 NSIS 那边不认这面旗子了(python 照发,没人接)
mutate_and_expect m23 test_t20b_the_nsi_parses_that_exact_flag \
  '  ${GetOptions} $R0 "/UPDATE" $R1' \
  '  ${GetOptions} $R0 "/UPD" $R1'

MUT_SRC="$SRC"

restore
AFTER="$(sha256sum "$SRC" | cut -d' ' -f1)"
AFTER_NSI="$(sha256sum "$NSI" | cut -d' ' -f1)"
if [ "$BEFORE" != "$AFTER" ]; then
  echo "🔴 还原失败:$SRC 的哈希对不上($BEFORE → $AFTER)"
  exit 2
fi
if [ "$BEFORE_NSI" != "$AFTER_NSI" ]; then
  echo "🔴 还原失败:$NSI 的哈希对不上($BEFORE_NSI → $AFTER_NSI)"
  exit 2
fi

echo "== 咬住 $bites / 漏网 $escapes =="
[ "$escapes" -eq 0 ] || exit 1
