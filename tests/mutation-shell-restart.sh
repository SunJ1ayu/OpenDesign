#!/usr/bin/env bash
# 红检 —— 证明 T3(填完 key 让网关重来一次)那一串判据咬得动。
#
# 覆盖三层,每层都单独变异:
#   ds_shell_core.py  锁的动词分派 / child_env / Supervisor.restart
#   ds_web.py         回请外壳的那座桥
#   ds_shell.py       外壳的接线(**它只有静态闸**,更需要证明那道闸不是摆设)
#
# 用法:tests/mutation-shell-restart.sh   退出码:0 全咬住 / 1 有漏网
set -u
cd "$(dirname "$0")/.."
PY="${PY:-/root/.venvs/design-studio/bin/python}"
WORK="$(mktemp -d)"
SRCS=(bin/ds_shell_core.py bin/ds_web.py bin/ds_shell.py)

declare -A BEFORE
for s in "${SRCS[@]}"; do
  BEFORE[$s]="$(sha256sum "$s" | cut -d' ' -f1)"
  cp "$s" "$WORK/$(basename "$s").orig"
done
restore() { for s in "${SRCS[@]}"; do cp "$WORK/$(basename "$s").orig" "$s"; done; }
trap 'restore; rm -rf "$WORK"' EXIT
pass=0; fail=0

# 用法:mutate_and_expect <id> <靶子测试名> <判据文件> <被改的源文件> <老串> <新串>
mutate_and_expect() {
  local id="$1" target="$2" oracle="$3" file="$4" old="$5" new="$6"
  local out="$WORK/mut-$id.txt"
  restore
  find bin tests -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null
  "$PY" - "$file" "$old" "$new" <<'PYEOF' || { echo "  [BAD]  $id 变异没打上去"; fail=$((fail+1)); return; }
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding="utf-8")
old, new = sys.argv[2], sys.argv[3]
n = s.count(old)
if n == 0:
    sys.exit(f"变异锚点找不到: {old!r}")
if n > 1:   # 锚点不唯一会打错位置,造出"判据瞎了"的假报警(08-15 栽过一次)
    sys.exit(f"变异锚点不唯一(出现 {n} 次): {old!r}")
p.write_text(s.replace(old, new, 1), encoding="utf-8")
PYEOF
  timeout 600 "$PY" -W ignore "$oracle" > "$out" 2>&1
  local rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "  [BAD]  $id -> 判据全绿:这条变异下它是瞎的(靶子 $target)"; fail=$((fail+1))
  elif grep -qE "^(FAIL|ERROR): $target" "$out"; then
    echo "  [OK]   $id -> 靶子 $target 如期红了"; pass=$((pass+1))
  else
    echo "  [BAD]  $id -> 红了,但**不是靶子** $target:"
    grep -E "^(FAIL|ERROR):" "$out" | head -3 | sed 's/^/         实际红的是:/'; fail=$((fail+1))
  fi
}

CORE=tests/test_ds_shell_core.py
CRED=tests/test_ds_web_credential.py
WIRE=tests/test_ds_shell_wiring.py
C=bin/ds_shell_core.py
W=bin/ds_web.py
S=bin/ds_shell.py

echo "== 红检开始(T3 重启链路)=="

# ---- 锁:动词分派 ----

# M1 动词认不出来 ⇒ 退回今天的行为(只会唤醒窗口)
mutate_and_expect M1 test_b11_the_restart_verb_restarts_and_does_not_raise_the_window "$CORE" "$C" \
  '        cb = self.on_restart if verb.strip() == self._RESTART.strip() else self.on_show' \
  '        cb = self.on_show'

# M2 反向:什么都当成重启 ⇒ 双击图标会掐断他的对话
mutate_and_expect M2 test_b12_a_frame_without_a_verb_still_means_show "$CORE" "$C" \
  '        cb = self.on_restart if verb.strip() == self._RESTART.strip() else self.on_show' \
  '        cb = self.on_restart'

# M3 前缀匹配代替精确匹配 ⇒ "RESTART" 这种近似词也会重启
mutate_and_expect M3 test_b13_an_unknown_verb_never_means_restart "$CORE" "$C" \
  '        cb = self.on_restart if verb.strip() == self._RESTART.strip() else self.on_show' \
  '        cb = self.on_restart if self._RESTART.strip().startswith(verb.strip()) else self.on_show'

# M4 只读一行就返回(退回改造前的 _recv_line 形态)⇒ 分片到达的动词被丢掉。
# 🔴 靶子不能写 b11:同包到达时缓冲里本来就有第二行,这条变异对它是**等价的** ——
# 首跑就是这么"漏网"的,而漏的其实是判据里没有分片动词那一条。补了 b14 才问得出来。
mutate_and_expect M4 test_b14_a_verb_in_a_second_packet_is_still_read "$CORE" "$C" \
  '        while len(buf) < limit and buf.count(b"\n") < 2:' \
  '        while len(buf) < limit and buf.count(b"\n") < 1:'

# ---- child_env ----

# M5 锁端口不进 env ⇒ ds-web 只会回 manual,整条自动重启空转
mutate_and_expect M5 test_e10_the_web_is_told_where_the_lock_is "$CORE" "$C" \
  '        env["DS_SHELL_LOCK_PORT"] = str(lock_port)' \
  '        pass'

# M6 忘了传变量名就悄悄用默认的 ⇒ 失败没有声音
mutate_and_expect M6 test_e9_forgetting_the_variable_name_is_loud "$CORE" "$C" \
  '            raise ValueError("有 key 却没说该设哪个环境变量(从配置的 apiKey 引用里读)")' \
  '            key_var = "DS_LLM_KEY"'

# M7 变量名写死 ⇒ 配置引用别的名字时,填了 key 也不能聊天
mutate_and_expect M7 test_e8_the_variable_name_comes_from_the_config_not_from_this_file "$CORE" "$C" \
  '        env[str(key_var)] = str(key)' \
  '        env["DS_LLM_KEY"] = str(key)'

# ---- Supervisor.restart ----

# M8 不点名,把所有腿都换掉 ⇒ 业主正看着的界面白掉
mutate_and_expect M8 test_c15_restart_replaces_only_the_named_leg "$CORE" "$C" \
  '        old = [c for c in self._children if c.service.name in names]' \
  '        old = list(self._children)'

# M9 旧进程不收就起新的 ⇒ 端口还被占着,重启"没反应"
mutate_and_expect M9 test_c15_restart_replaces_only_the_named_leg "$CORE" "$C" \
  '        for child in old:
            self._terminate_tree(child)' \
  '        for child in old:
            pass'

# M10 失败就连坐全停 ⇒ 界面陪葬,业主连"重启失败"都看不到
mutate_and_expect M10 test_c17_a_failed_restart_does_not_take_the_others_down "$CORE" "$C" \
  '                self._terminate_tree(child)
                self._children = [c for c in self._children if c is not child]
                raise' \
  '                self.shutdown()
                raise'

# ---- ds-web 那座桥 ----

# M11 不看应答就说"已安排" ⇒ 端口上随便是谁都被当成外壳
mutate_and_expect M11 test_k2_a_stranger_on_that_port_is_not_our_shell "$CRED" "$W" \
  '    return "requested" if reply == ds_shell_core.LOCK_OK.strip() else "manual"' \
  '    return "requested"'

# M12 发错动词(SHOW)⇒ 窗口被弹到前台,key 却没生效
mutate_and_expect M12 test_k3_a_real_shell_gets_the_restart_verb_not_show "$CRED" "$W" \
  '            s.sendall(ds_shell_core.LOCK_HELLO + ds_shell_core.LOCK_RESTART)' \
  '            s.sendall(ds_shell_core.LOCK_HELLO + ds_shell_core.LOCK_SHOW)'

# M13 外壳不吭声时死等 ⇒ 业主点了保存,界面转圈,以为程序死了。
# 🔴 靶子锚在 **deadline** 上,不是 create_connection 的 timeout:那个只管连接建立,
# 读多久由 recv_line 的 deadline 说了算 —— 首跑我锚错了地方,变异等于没打。
mutate_and_expect M13 test_k4_a_wedged_shell_does_not_hang_the_save "$CRED" "$W" \
  '            reply = ds_shell_core.recv_line(s, deadline=time.monotonic() + 3)' \
  '            reply = ds_shell_core.recv_line(s, deadline=time.monotonic() + 60)'

# ---- 外壳接线(静态闸的双向验:它到底会不会红)----

# M14 锁端口没传给 child_env ⇒ 整条链路空转,而 core/ds-web 两侧判据全绿
mutate_and_expect M14 test_w1_child_env_is_told_the_lock_port "$WIRE" "$S" \
  '            dsweb_port=web, ws_port=ws, key=key, key_var=key_var, lock_port=lock_port)' \
  '            dsweb_port=web, ws_port=ws, key=key, key_var=key_var)'

# M15 锁没接重启回调 ⇒ 重启帧到了也没人处理
mutate_and_expect M15 test_w3_the_lock_carries_a_restart_callback "$WIRE" "$S" \
  '        on_restart=lambda: restart_holder and restart_holder[0]())' \
  '        )'

restore
echo
bad=0
for s in "${SRCS[@]}"; do
  now="$(sha256sum "$s" | cut -d' ' -f1)"
  [ "$now" = "${BEFORE[$s]}" ] || { echo "🔴 $s 没还原干净"; bad=1; }
done
[ "$bad" -eq 0 ] && echo "被测文件原样还回(${#SRCS[@]} 个哈希一致)"
echo "== 红检结束:咬住 $pass 条,漏网 $fail 条 =="
[ "$fail" -eq 0 ] && [ "$bad" -eq 0 ] && exit 0 || exit 1
