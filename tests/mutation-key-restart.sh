#!/usr/bin/env bash
# 红检 —— 证明 track opendesign-key-restart 的判据**咬得动实现**。
#
# 判据先行时它们红在「函数 / 文件不存在」上;那种红只证明"没有就会响",不证明"写错了会响"(08-14 的规矩)。
# 每条变异只弄坏一处,并核对**红在该红的那一问上**(光看退出码,超时、夹具炸也是非 0 —— 那是假的咬住)。
#
# 用法:tests/mutation-key-restart.sh [变异号...]    退出码:0 全咬住 / 1 有漏网
set -u
cd "$(dirname "$0")/.."
PY=/root/.venvs/design-studio/bin/python
WORK="$(mktemp -d)"
SRCS=(bin/ds_shell_core.py bin/ds_gateway.py bin/ds_web.py bin/ds_credential.py bin/ds_shell.py
      web/src/settings/modelSettings.ts)
for s in "${SRCS[@]}"; do cp "$s" "$WORK/$(basename "$s").orig"; done
restore() { for s in "${SRCS[@]}"; do cp "$WORK/$(basename "$s").orig" "$s"; done; }
trap 'restore; rm -rf "$WORK"; echo "(已还原源码)"' EXIT
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
  if [ $rc -ne 0 ] && grep -qF -- "$marker" <<<"$out"; then
    echo "  [咬住] $id —— $why"
    pass=$((pass+1))
  else
    echo "  [漏网] $id —— $why(rc=$rc,没见到「$marker」)"
    tail -15 <<<"$out" | sed 's/^/        /'
    fail=$((fail+1))
  fi
}

LIVE="$PY tests/test_key_live.py"
RESTART="$PY tests/test_key_restart.py"

mutate M1 bin/ds_shell_core.py \
  'return [str(python_exe), os.path.join(str(ds_root), "bin", "ds_gateway.py")]' \
  'return [str(python_exe), "-m", "nanobot", "gateway"]' \
  "$LIVE LiveKey" "「主槽换了 key 之后」" \
  "网关退回直接 -m nanobot 起(没有钩子)⇒ 换了 key 下一句还带旧的"

mutate M2 bin/ds_gateway.py \
  '    loader._env_replace = _live_env_replace' \
  '    pass' \
  "$LIVE LauncherHook.test_g1_the_file_wins_over_the_start_time_env" "sk-start-time-env-0000" \
  "启动器不装钩子 ⇒ 解析出启动时的 env"

mutate M3 bin/ds_gateway.py \
  '        raise SystemExit(REFUSE)' \
  '        return' \
  "$LIVE LauncherHook.test_g4_the_launcher_refuses_to_run_when_the_hook_point_is_gone" "钩点不在了,启动器照样开跑" \
  "钩点没了照样开跑(静默退回只认 env)"

mutate M4 bin/ds_gateway.py \
  '        return value if value else orig(match)' \
  '        return value or ""' \
  "$LIVE LauncherHook.test_g3_neither_file_nor_env_still_raises_like_nanobot" "'error'" \
  "两边都没有却解析成空串(空 key 被当成配好了)"

mutate M5 bin/ds_shell_core.py \
  '            "stdin": subprocess.DEVNULL,' \
  '' \
  "$RESTART SupervisorStdinAndEnsure.test_s1_children_do_not_inherit_the_hosts_stdin" "子进程拿到的是管家的输入管道" \
  "子进程继承管家 stdin(Windows 卡死的根因)"

mutate M6 bin/ds_shell_core.py \
  '        todo = [s for s in services if s.name not in alive]' \
  '        todo = list(services)' \
  "$RESTART SupervisorStdinAndEnsure.test_s2_ensure_leaves_a_live_gateway_alone" "网关活着,ensure 却换了一个新进程" \
  "ensure 照样重启活着的网关"

mutate M7 bin/ds_shell_core.py \
  '        if todo:' \
  '        if False:' \
  "$RESTART SupervisorStdinAndEnsure.test_s2b_ensure_starts_a_gateway_that_was_never_started" "没在跑的网关没被起起来" \
  "ensure 什么都不起(全新装机第一次存 key 连不上)"

mutate M8 bin/ds_web.py \
  '        return "live"' \
  '        pass' \
  "$RESTART WorkbenchVerdict.test_w1_gateway_listening_means_live_and_no_frame" "!= 'live'" \
  "网关在跑还去请外壳"

mutate M9 bin/ds_credential.py \
  '                prepare_gateway(home, cfg_path)          # key 文件在先,条目在后(见 docstring)' \
  '' \
  "$RESTART KeyFilesAndConfigTogether.test_k1_saving_a_second_vendor_in_settings_adds_its_entry_right_away" "配置里还没有它的条目" \
  "设置页存第二家不当场补条目"

mutate M10 bin/ds_credential.py \
  '            prepare_gateway(home, cfg_path)              # 当场兑现「想换过去」:不会再有起网关那一下替它兑现' \
  '' \
  "$RESTART KeyFilesAndConfigTogether.test_k2_the_onboarding_switch_happens_right_away" "没当场兑现" \
  "引导页「存了想换过去」不当场兑现"

mutate M11 bin/ds_credential.py \
  '        with catalog_scope(home):
            prepare_gateway(home, cfg_path)
    return pid' \
  '        prepare_gateway(home, cfg_path)
    return pid' \
  "$RESTART KeyFilesAndConfigTogether.test_k3_a_custom_provider_with_a_key_is_usable_right_away" "配置里没有条目" \
  "沿用登记前的目录范围 ⇒ 新自定义供应商补不上条目"

mutate M12 bin/ds_shell.py \
  '            sup.ensure([gateway_service(fresh["网关"])])' \
  '            sup.restart([gateway_service(fresh["网关"])])' \
  "$RESTART ShellWiresEnsureAndLauncher.test_r1_the_lock_callback_ensures_instead_of_restarting" "锁帧回调没走 ensure" \
  "外壳收到帧照旧重启"

mutate M13 bin/ds_shell.py \
  'argv=core.gateway_argv(str(python_exe()), str(install_root() / "ds")),' \
  'argv=[str(python_exe()), "-m", "nanobot", "gateway"],' \
  "$RESTART ShellWiresEnsureAndLauncher.test_r2_the_gateway_is_started_through_the_live_key_launcher" "test_r2" \
  "外壳不经启动器起网关"

mutate M14 web/src/settings/modelSettings.ts \
  '    return "已保存,下一句对话起就用它。";' \
  '    return "已保存,正在自动重启后台服务,稍等片刻即可继续使用。";' \
  "node --test tests/test_llm_key.mjs" "not ok" \
  "live 却说在重启、叫他等"

echo "红检:咬住 $pass / 漏网 $fail"
[ $fail -eq 0 ]
