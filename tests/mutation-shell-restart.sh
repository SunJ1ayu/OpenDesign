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
# 🔴 **变异打到哪个文件,它就必须在这张表里** —— 这张表同时是备份表、还原表
#    和收尾的哈希核对表。2026-09-08 我加更新交棒那一组时漏了 ds_update_apply.py:
#    它会被变异、却永远不还原,变异一路累积留在仓库里,而收尾的哈希核对**看不见它**。
#    (那一轮还没跑到就被我掐了,但坑是真的。)量具弄脏被测仓,是本仓的老毛病。
SRCS=(bin/ds_shell_core.py bin/ds_web.py bin/ds_shell.py bin/ds_update_apply.py)

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
A=bin/ds_update_apply.py

echo "== 红检开始(T3 重启链路)=="

# ---- 锁:动词分派 ----

# M1 动词认不出来 ⇒ 退回今天的行为(只会唤醒窗口)
# ⚠️ M1~M3 的锚点 2026-09-08 搬过:动词分派从一行三元表达式改成了 if/elif/else
#    (加更新交棒动词时)。**语义一个字没变,只是打在新的行上** —— 是这支脚本
#    自己喊「变异没打上去」才发现的,不然三条会一直静静地不跑。
mutate_and_expect M1 test_b11_the_restart_verb_restarts_and_does_not_raise_the_window "$CORE" "$C" \
  '        elif is_restart:
            cb = self.on_restart' \
  '        elif is_restart:
            cb = self.on_show'

# M2 反向:什么都当成重启 ⇒ 双击图标会掐断他的对话
mutate_and_expect M2 test_b12_a_frame_without_a_verb_still_means_show "$CORE" "$C" \
  '        else:
            cb = self.on_show' \
  '        else:
            cb = self.on_restart'

# M3 前缀匹配代替精确匹配 ⇒ "RESTART" 这种近似词也会重启
mutate_and_expect M3 test_b13_an_unknown_verb_never_means_restart "$CORE" "$C" \
  '                is_restart = verb.strip() == self._RESTART.strip()' \
  '                is_restart = self._RESTART.strip().startswith(verb.strip())'

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
  '    return "requested" if reply == ds_shell_core.LOCK_OK_RESTART.strip() else "manual"' \
  '    return "requested"'

# M12 发错动词(SHOW)⇒ 窗口被弹到前台,key 却没生效
mutate_and_expect M12 test_k3_a_real_shell_gets_the_restart_verb_not_show "$CRED" "$W" \
  '            s.sendall(ds_shell_core.LOCK_HELLO + ds_shell_core.LOCK_RESTART)' \
  '            s.sendall(ds_shell_core.LOCK_HELLO + ds_shell_core.LOCK_SHOW)'

# M13 外壳不吭声时死等 ⇒ 业主点了保存,界面转圈,以为程序死了。
# 🔴 靶子锚在 **deadline** 上,不是 create_connection 的 timeout:那个只管连接建立,
# 读多久由 recv_line 的 deadline 说了算 —— 首跑我锚错了地方,变异等于没打。
# ⚠️ 锚点 2026-09-08 加宽:这一行现在在 ds_web.py 里出现两次(更新交棒那座桥
#    抄了同款帧收发)。只写这一行会被判「锚点不唯一」而整条空转 ——
#    **同一段代码被复制到第二个地方,连红检的锚点都会跟着失效。**
mutate_and_expect M13 test_k4_a_wedged_shell_does_not_hang_the_save "$CRED" "$W" \
  '            s.sendall(ds_shell_core.LOCK_HELLO + ds_shell_core.LOCK_RESTART)
            reply = ds_shell_core.recv_line(s, deadline=time.monotonic() + 3)' \
  '            s.sendall(ds_shell_core.LOCK_HELLO + ds_shell_core.LOCK_RESTART)
            reply = ds_shell_core.recv_line(s, deadline=time.monotonic() + 60)'

# ---- 外壳接线(静态闸的双向验:它到底会不会红)----

# M14 锁端口没传给 child_env ⇒ 整条链路空转,而 core/ds-web 两侧判据全绿
mutate_and_expect M14 test_w1_child_env_is_told_the_lock_port "$WIRE" "$S" \
  '            dsweb_port=web, ws_port=ws, key=key, key_var=key_var, lock_port=lock_port)' \
  '            dsweb_port=web, ws_port=ws, key=key, key_var=key_var)'

# M15 锁没接重启回调 ⇒ 重启帧到了也没人处理
#     ⚠️ 锚点 2026-09-08 搬过一次:那一行原来以 `)` 收尾,加了 on_update 之后
#     变成以 `,` 收尾。**是这支脚本报「变异没打上去」当场喊出来的** ——
#     它没有默默放过,这正是「锚点过期」在本仓栽过四次之后加的那个 [BAD] 分支的价值。
mutate_and_expect M15 test_w3_the_lock_carries_a_restart_callback "$WIRE" "$S" \
  '        on_restart=lambda: restart_holder and restart_holder[0](),' \
  '        '

restore
echo
# ---- J 组:key 只进网关那条腿(2026-08-16 四审 BLOCK 的第一条)----

# Q1 ds-web 那份也塞 key ⇒ 回到病态:装好的应用重启后,改 key 的卡片永久只读,
#    还让业主去清一个外壳自己注入、他从没设过的变量。
mutate_and_expect Q1 test_j2_ds_web_does_not "$CORE" "$C" \
  '        "ds-web": child_env(base_env, key=None, key_var=None, **common),' \
  '        "ds-web": child_env(base_env, key=key, key_var=key_var, **common),'

# Q2 接线层把网关那份交给 ds-web ⇒ 逻辑层四条全绿而真机照样锁死。
#    这条专门验 J5 那道接线闸(「接线测试证明不了接上了」)。
mutate_and_expect Q2 test_j5_the_shell_really_uses_it "$CORE" "$S" \
  '                + [web_service(envs["ds-web"])])' \
  '                + [web_service(envs["网关"])])'

# ─────────────────────────────────────────────────────────────────────────
# 更新交棒(track opendesign-in-app-update-install)—— 同样穿三层。
# 🔴 这一组里最要紧的是 U3:**顺序**。它反过来的后果不是"更新失败",
#    是业主看到"软件关了,没再打开",而且没有任何东西会去回滚。

WEBUPD=tests/test_ds_web_update.py
APPLY=tests/test_ds_update_apply.py

# U1 core:没接 on_update 也回一个"我认了" ⇒ 新 ds-web 会据此宣布更新已开始,
#    而外壳其实只把窗口闪了一下(最坏的那种撒谎)
mutate_and_expect U1 test_m4_no_update_callback_means_fall_back_to_show_not_crash "$CORE" "$C" \
  '                is_update = (verb.strip() == self._UPDATE.strip()
                             and self.on_update is not None)' \
  '                is_update = verb.strip() == self._UPDATE.strip()'

# U2 core:交棒动词被当成重启 ⇒ 只掐断聊天,软件不会关,接力脚本白等
mutate_and_expect U2 test_m1_the_update_verb_reaches_the_update_callback_only "$CORE" "$C" \
  '        if is_update:
            cb = self.on_update' \
  '        if False:
            cb = self.on_update'

# U3 🔴 web:先请外壳关停、再起接力脚本(顺序反过来)
mutate_and_expect U3 test_t22c_the_relay_is_launched_before_the_shell_is_told_to_quit "$WEBUPD" "$W" \
  '        if not ds_update_apply.handoff(result.get("relay")):' \
  '        _early = ds_shell_bridge_update()
        if not ds_update_apply.handoff(result.get("relay")):'

# U4 web:接力脚本没起来照样请外壳关停 ⇒ 关了没人接手
mutate_and_expect U4 test_t22d_a_failed_handoff_never_asks_the_shell_to_quit "$WEBUPD" "$W" \
  '            self._json(200, {"ok": False, "stage": "handoff",
                             "error": "接力脚本没能启动,更新取消(软件照常可用)"})
            return' \
  '            pass'

# U5 web:裸 OK 也当成功(老外壳 ⇒ 界面说"更新已开始"而什么都没发生)
#    ⚠️ 靶子 2026-09-08 搬过:原来指 t22e,而这条变异在它下面**全绿漏网** ——
#    t22e 把**整座桥换成了替身**,桥内部那句判定压根没被执行。
#    它问的是"端点尊不尊重裁决",问不到"裁决本身对不对"。
#    ⇒ 新加了直接考那个纯函数的 t22h/t22i/t22j/t22k,靶子搬到它们身上。
#    **这是加强不是放宽**:搬完之后这条变异一次咬红三条。
mutate_and_expect U5 test_t22h_a_bare_ok_is_not_started "$WEBUPD" "$W" \
  '    return "started" if reply == ds_shell_core.LOCK_OK_UPDATE.strip() else "manual"' \
  '    return "started" if reply else "manual"'

# U6 web:没新版也装一遍
mutate_and_expect U6 test_t22b_no_new_version_means_nothing_is_installed "$WEBUPD" "$W" \
  '        if not info.get("update_available"):' \
  '        if False:'

# U7 web:安装口开到 GET 上(装软件是本仓最重的副作用,GET 面必须只读)
mutate_and_expect U7 test_t22a_get_never_triggers_an_install "$WEBUPD" "$W" \
  '        elif path == "/api/update/check":
            self._update_check()' \
  '        elif path == "/api/update/check":
            self._update_check()
        elif path == UPDATE_APPLY_PATH:
            self._update_apply()'

# U8 apply:交棒时不检查脚本在不在 ⇒ 起一个不存在的东西也报"交棒成功"
mutate_and_expect U8 test_t21a_missing_script_is_never_reported_as_handed_off "$APPLY" "$A" \
  '    if not relay_path or not os.path.isfile(relay_path):
        return False' \
  '    if False:
        return False'

# U9 apply:起失败了也算交棒(下一步就把软件关了)
mutate_and_expect U9 test_t21d_a_launcher_that_blows_up_is_not_a_handoff "$APPLY" "$A" \
  '    except Exception:  # noqa: BLE001 —— 起不来是"没交棒",不是"甩栈给业主"
        return False' \
  '    except Exception:  # noqa: BLE001
        pass'

# U10 apply:.new 放进安装根里面 ⇒ 安装器把它一起覆盖掉
mutate_and_expect U10 test_t23b_new_and_old_are_siblings_of_the_live_tree "$APPLY" "$A" \
  '    paths = {"live": live, "new": live + ".new", "old": live + ".old",' \
  '    paths = {"live": live, "new": os.path.join(live, "new"), "old": live + ".old",'

# U11 shell:交棒只停后台、不退出 ⇒ 外壳自己还攥着 $INSTDIR 里的文件,改名必然失败
mutate_and_expect U11 test_w9_the_update_callback_actually_tears_the_backend_down "$WIRE" "$S" \
  '            shell_holder[0].state.on_quit()' \
  '            shell_holder[0].stop_backend()'

# U12 shell:锁根本没接交棒回调
mutate_and_expect U12 test_w8_the_lock_carries_an_update_callback "$WIRE" "$S" \
  '        on_update=update_handoff)' \
  ')'

# 🔴 先还原再核对。**这一句 2026-09-08 才补上** —— 在那之前,收尾核对跑在
#    最后一条变异还打在身上的时候,于是**每一轮都稳定地报一次「没还原干净」**
#    (最后一条正好打在 ds_shell.py 上)。一个永远响的报警器 = 一个没人看的报警器,
#    而它要报的那件事(量具弄脏被测仓)恰恰是本仓的老毛病。
restore
bad=0
for s in "${SRCS[@]}"; do
  now="$(sha256sum "$s" | cut -d' ' -f1)"
  [ "$now" = "${BEFORE[$s]}" ] || { echo "🔴 $s 没还原干净"; bad=1; }
done
[ "$bad" -eq 0 ] && echo "被测文件原样还回(${#SRCS[@]} 个哈希一致)"
echo "== 红检结束:咬住 $pass 条,漏网 $fail 条 =="
[ "$fail" -eq 0 ] && [ "$bad" -eq 0 ] && exit 0 || exit 1
