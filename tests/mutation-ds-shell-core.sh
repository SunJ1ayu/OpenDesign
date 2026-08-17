#!/usr/bin/env bash
# 红检(变异测试)—— 证明 tests/test_ds_shell_core.py 这份判据咬得动。
#
# 规矩(与 spike/mutation-test.sh 同一套,别再各写一份):
#   1. 变异的是**被测对象**(bin/ds_shell_core.py),不是判据本身 ——
#      改判据让它变红只能证明它会打字。
#   2. 每条变异都指定**靶子**:必须是**那一条**红,不是"随便红了就算过"
#      (08-11 变异脚本三次把靶子指错,红在别处还自称通过)。
#   3. 跑完必须把文件原样还回去,并**机械核对**还回去了(哈希),
#      否则一次中断就会把变异留在仓库里。
#
# 用法:tests/mutation-ds-shell-core.sh
# 退出码:0 = 每条变异都咬住了靶子   1 = 有漏网   2 = 用法/现场问题

set -u
cd "$(dirname "$0")/.."
PY="${PY:-/root/.venvs/design-studio/bin/python}"
SRC=bin/ds_shell_core.py
# 判据入口是**一组模块**,不是一个文件:有的契约由行为判据和静态闸共同保证
# (2026-08-17 的"子进程不许弹黑窗口"就是 —— 行为那半在 test_ds_shell_core,
# "每个创建点都走唯一来源"那半在 test_no_console_window)。
# 只跑一个文件的话,静态闸永远没人证明它咬得动。
ORACLE_MODULES="tests.test_ds_shell_core tests.test_no_console_window"
WORK="$(mktemp -d)"
BEFORE="$(sha256sum "$SRC" | cut -d' ' -f1)"
cp "$SRC" "$WORK/原件.py"

restore() { cp "$WORK/原件.py" "$SRC"; }
trap 'restore; rm -rf "$WORK"' EXIT

pass=0; fail=0

# 打一条变异(可以是**多点**的),跑判据,要求**指定的那条**红。
#
# 为什么要支持多点:有的契约由两道防线共同保证(比如"起动失败必须收干净"),
# 只拆其中一道**本就不该红** —— 那样的变异漏网不是判据瞎,是变异没打在契约上。
# 2026-08-13 第一版就是这么误报了两条。
#
# 用法:mutate_and_expect <id> <靶子> <旧1> <新1> [<旧2> <新2> ...]
mutate_and_expect() {
  # 分两句写:`local a=$1 b=$a` 在 bash 里 **b 拿不到 a** —— local 先把名字全声明成
  # 未设,再逐个赋值,于是 set -u 下当场炸 "unbound variable"。
  local id="$1" target="$2"; shift 2
  local out="$WORK/mut-$id.txt"
  restore
  local -a pairs=("$@")
  PAIRS_N="${#pairs[@]}" "$PY" - "$SRC" "$@" <<'PYEOF' || { echo "  [BAD]  $id 变异没打上去"; fail=$((fail+1)); return; }
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
  timeout 600 "$PY" -W ignore -m unittest $ORACLE_MODULES > "$out" 2>&1
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

# M1 端口探测退回"用 connect 猜" —— 已 bind 未 listen 的占用会被看成空
mutate_and_expect M1 test_a5_a_bound_but_not_listening_port_counts_as_busy \
  '        s.bind((host, int(port)))
        return True' \
  '        s.connect((host, int(port)))
        return False'

# M2 成组分配退回"每个都独立挑" —— 两条腿会拿到同一个号
mutate_and_expect M2 test_a6_group_allocation_never_hands_out_the_same_port_twice \
  '            if port not in used and port_free(port):' \
  '            if port_free(port):'

# M3 并发裁决拆掉 —— 同时启动会两份都自认唯一
mutate_and_expect M3 test_b8_two_instances_racing_at_the_same_moment_still_yield_one \
  '            if self._someone_ahead_of(port):' \
  '            if False and self._someone_ahead_of(port):'

# M4 握手退回"只 recv 一次" —— 分片就认不出来
# 🔴 08-17:这条的锚点**过期了两个版本**(实现从 `_recv_line` 换成了 `_recv_frame`),
#    于是它一直报"变异没打上去" —— 而那条契约实际上早就没有红检覆盖了。
#    「变异脚本自己坏了」这件事已经是第四次;锚点尽量挑**不容易改的那一行**。
mutate_and_expect M4 test_b10_a_handshake_split_across_packets_is_still_recognised \
  '        while len(buf) < limit and buf.count(b"\n") < 2:' \
  '        for _only_once in range(1):'

# M5 每条连接单开线程退回同步处理 —— 哑巴客户端能把锁堵住
mutate_and_expect M5 test_b9_a_silent_client_cannot_wedge_the_lock \
  '            threading.Thread(target=self._handle, args=(conn,),
                             name="ds-shell-lock-conn", daemon=True).start()' \
  '            self._handle(conn)'

# M6 退回"只盯当前这条腿、且结束时不点名" —— 前面那条先就绪后崩掉照样绿。
# ⚠️ 只拆其中一道防线是**不该红**的(另一道仍然兜得住,契约没被破坏)——
# 变异要打在契约上,不是打在某一行上。第一版只拆了一道,漏网,不是判据的错。
mutate_and_expect M6 test_c11_a_leg_that_dies_while_the_next_one_boots_fails_the_whole_start \
  '            for other in self._children:' \
  '            for other in [child]:' \
  '            dead = self.poll_dead()
            if dead:' \
  '            dead = self.poll_dead()
            if False:'

# M7 收割看父进程死活 —— 父亲先走,孙子就没人收。
# 同 M6:TERM 和 KILL 两条路都得堵上才算真的破坏了契约。
mutate_and_expect M7 test_c13_grandchildren_are_reaped_even_if_the_parent_died_first \
  '        if os.name == "posix":
            if child.pgid:
                try:
                    os.killpg(child.pgid, signal.SIGTERM)' \
  '        if os.name == "posix":
            if child.pgid and child.proc.poll() is None:
                try:
                    os.killpg(child.pgid, signal.SIGTERM)' \
  '                if child.proc.poll() is None or child.pgid or child.job_handle:' \
  '                if child.proc.poll() is None:'

# M8 配置改写退回"所有 MCP 一起改" —— 把机主自己装的第三方工具改坏
mutate_and_expect M8 test_d3_a_third_party_mcp_is_left_completely_alone \
  '    for name in OUR_MCP:
        servers[name]["command"] = str(python_exe)' \
  '    for name in servers:
        servers[name]["command"] = str(python_exe)'

# M9 中文口令放行 —— 装完看着一切正常,第一句话永远发不出去
mutate_and_expect M9 test_d5_refuses_a_config_whose_channel_is_off \
  '        str(token).encode("latin-1")' \
  '        str(token).encode("utf-8")'

# M10 配置原地截断改写 —— 断电会留下半份 JSON
mutate_and_expect M10 test_d6_a_reader_never_sees_a_half_written_config \
  '        os.replace(tmp_name, cfg_path)' \
  '        os.unlink(cfg_path); os.replace(tmp_name, cfg_path); time.sleep(0.002)'

# M11 子进程环境只做加法 —— 业主机器上的旧 DS_LLM_KEY 会漏进去
mutate_and_expect M11 test_e4_inherited_ds_keys_are_wiped_not_inherited \
  '        if upper in {"PYTHONPATH", "PYTHONHOME"} or upper.startswith("DS_"):' \
  '        if upper in {"PYTHONPATH", "PYTHONHOME"}:'

# M12 HOME 不接管 —— 网关会去读业主原来那份 ~/.nanobot/config.json
mutate_and_expect M12 test_e5_home_points_at_our_own_data_dir \
  '            "HOME": str(user_home),' \
  '            "HOME": base_env.get("HOME", str(user_home)),'

# M13 退出不加锁 —— 三个线程一起点退出会收两遍
mutate_and_expect M13 test_f9_the_check_and_set_in_on_quit_is_not_two_steps \
  '        with self._lock:
            if self.exiting:
                return
            self.exiting = True
            self.visible = False
        self.on_stop()' \
  '        if self.exiting:
            return
        self.on_stop()
        self.exiting = True
        self.visible = False'

# M14 「谁死了」和「为什么死」退回分两眼看 —— 两眼之间业主存了 key 触发重启,
#     名册一变就是「名字有、原因空」:c20 刚消灭的没线索弹窗换个入口又长回来
mutate_and_expect M14 test_c21_who_died_and_why_come_from_one_look \
  '        out = []
        for child in list(self._children):
            code = child.proc.poll()
            if code is None:
                continue
            out.append((child.service.name,
                        self._failure_message(child.service, "", code, what="意外退出了")))
        return out' \
  '        names = [c.service.name for c in list(self._children) if c.proc.poll() is not None]
        said = [self._failure_message(c.service, "", c.proc.poll(), what="意外退出了")
                for c in list(self._children) if c.proc.poll() is not None]
        return list(zip(names, said))'

# M15 重启时**新**腿起不来,收尸退回只 terminate —— Windows 上 Job 不关,
#     那条腿的 3 个 MCP 孙子留在机器上(c18 只钉住了旧腿那一半)
mutate_and_expect M15 test_c22_a_new_leg_that_cannot_come_up_is_reaped_the_same_way \
  '                self._kill_tree(child)
                self._close_job(child)
                try:
                    child.log_file.close()
                except Exception:
                    pass
                self._children = [c for c in self._children if c is not child]' \
  '                self._terminate_tree(child)
                self._children = [c for c in self._children if c is not child]'

# ── 2026-08-17:子进程不许弹黑窗口(track opendesign-console-windows)──────────
# 业主真机撞的:开软件冒两个黑窗口,**关掉一个就杀掉一条腿**。

# M16 唯一来源里把"别开窗口"那一位摘掉 —— 真机上就是业主看见的那两个黑窗口
mutate_and_expect M16 test_c23_a_child_on_windows_never_pops_a_console_window \
  '        return {"creationflags": WINDOWS_SPAWN_FLAGS}' \
  '        return {"creationflags": CREATE_NEW_PROCESS_GROUP}'

# M17 收尸兜底的 taskkill 不走那个来源 —— 每收一次尸闪一个黑窗口
mutate_and_expect M17 test_c24_the_taskkill_fallback_never_pops_a_console_window \
  '                **spawn_kwargs("nt"),' \
  '                # 这一行被变异摘掉了'

# M18 `_spawn` 把平台参数取错了平台(refactor 时最容易犯的一种)
#     ⇒ POSIX 上 Popen 直接拒收 creationflags,起不来,c23b 当场红。
#
# 🔴 这条的第一版是「干脆不要平台参数」(`kwargs.update({})`),**它把判据进程自己杀了**:
#    没有 start_new_session,子进程就和判据进程同一个进程组,`_terminate_tree` 那下
#    `killpg` 连测试进程一起收 ⇒ 整轮没有任何 FAIL 行、rc 非零,报成"红在别处"。
#    变异要问的是"判据咬不咬得动",不是"能不能把跑判据的人干掉"。
mutate_and_expect M18 test_c23b_the_spawn_really_uses_that_one_source \
  '        kwargs.update(spawn_kwargs())' \
  '        kwargs.update(spawn_kwargs("nt"))'

# M19 `_spawn` 自己手拼一份平台参数(行为一模一样,只是绕开了唯一来源)——
#     **行为判据抓不到它**(POSIX 那半边完全等价),靶子必须是静态闸:
#     这正是"各写各的"这个病复发的样子,下一个人就是这么漏掉 Windows 那一位的
mutate_and_expect M19 test_every_spawn_site_goes_through_the_one_source \
  '        kwargs.update(spawn_kwargs())' \
  '        kwargs.update({"start_new_session": True} if os.name == "posix" else {})'

# M20 换一种写法起进程,让静态闸**看不见**这个调用点(闸① 的射程本身)。
#     选 `from subprocess import Popen` 而不是改掉现有调用:模块照常能 import、
#     其它判据一条不动 ⇒ 红的只会是"闸自己瞎了"这一条。
#     这条堵的失效方式和别的都不同:**闸不是报错,是安静地扫不到,表现为全绿。**
mutate_and_expect M20 test_the_gate_can_see_every_spawn_site \
  'import subprocess' \
  'import subprocess
from subprocess import Popen  # 变异:换个写法,扫描器就瞎了'

# M21 在**已经合规**的那个函数里再插一个裸调用(三条评审腿独立命中的那个洞)。
#     老闸问的是"这个 def 里出现过 spawn_kwargs 吗" ⇒ 第一个合法调用替它作保,
#     **这条变异在老闸下是全绿的**。新闸问"这次调用用了吗",才咬得住。
mutate_and_expect M21 test_every_spawn_site_goes_through_the_one_source \
  '            proc = subprocess.Popen([str(x) for x in svc.argv], **kwargs)' \
  '            subprocess.run(["cmd", "/c", "echo hi"])
            proc = subprocess.Popen([str(x) for x in svc.argv], **kwargs)'

restore
AFTER="$(sha256sum "$SRC" | cut -d' ' -f1)"
echo
if [ "$BEFORE" != "$AFTER" ]; then
  echo "🔴 还原失败:$SRC 和跑之前不一样了($BEFORE -> $AFTER)"
  exit 2
fi
echo "被测文件已原样还回(哈希一致 ${BEFORE:0:12})"
echo "== 红检结束:咬住 $pass 条 / 漏网 $fail 条 =="
[ "$fail" -eq 0 ]
