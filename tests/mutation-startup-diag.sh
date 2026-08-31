#!/usr/bin/env bash
# 红检(变异测试)—— 证明启动可观测性那 19 条判据咬得动。
#
# 🔴 **它存在的真正理由**:2026-08-30 用"什么都不干的空壳"跑了一遍,
#    发现 **4 条断言在空实现下仍然绿**(s5b/s8b/s9/s12)。它们是**守卫型**的
#    (禁止某事发生),空实现当然满足 ⇒ **只能靠变异证明它们有用,否则就是摆设**。
#    我事先只预判到 3 条,实际 4 条 —— 那 4 条在下面是 M7/M12/M13/M15,
#    删掉任何一条,这个红检就退化成"看着挺全的"。
#
# 规矩同 tests/mutation-frame-late.sh:
#   1. 变异**被测对象**,不是判据本身;
#   2. 每条指定**靶子**:必须是那一条红,红在别处算漏网;
#   3. 跑完原样还回去(cp -p 保 mtime,别把 dist 新鲜度闸刷红)。
#
# 用法:tests/mutation-startup-diag.sh
# 退出码:0 = 每条都咬住靶子   1 = 有漏网   2 = 用法/现场问题

set -u
cd "$(dirname "$0")/.."
PY="${PY:-/root/.venvs/design-studio/bin/python}"

# 🔴 **每个被变异的文件都必须在这里**:2026-08-30 深夜漏了 probe_verdict.py,
#    于是它被改坏后再没还原 —— 后面每条变异都跑在一个已经残废的被测物上,
#    红检报"漏网 5 条",其中 4 条是**量具自己造出来的假象**。
#    这一条比它看起来重:漏掉的那个文件,它的变异结果**全部作废**。
#    2026-08-31 **又栽一次,同一个坑**:这一批加了变异 workflow 的 M65,而
#    `.github/workflows/*.yml` 不在这张清单里 ⇒ 它被改坏后再没还原,M66~M68 全跑在
#    残废的被测物上、红在别处。那三条的结果当场作废、重跑。
SOURCES=(bin/ds_diag.py bin/ds_shell.py bin/ds_web.py bin/probe_verdict.py \
         .github/scripts/windows-package-probe.ps1 \
         .github/workflows/windows-package-probe.yml)
WORK="$(mktemp -d)"
for f in "${SOURCES[@]}"; do cp -p "$f" "$WORK/$(echo "$f" | tr / _)"; done

restore() {
  for f in "${SOURCES[@]}"; do cp -p "$WORK/$(echo "$f" | tr / _)" "$f"; done
  find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
}
trap 'restore; rm -rf "$WORK"' EXIT

pass=0; fail=0
ORACLE=tests/test_startup_diag.py

mutate_and_expect() {
  local id="$1" src="$2" target="$3"; shift 3
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
  # 清 .pyc:同长度替换 + 同一秒 mtime 会让 CPython 复用旧字节码(2026-08-07 老账)
  find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
  timeout 300 "$PY" -W ignore "$ORACLE" > "$out" 2>&1
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

echo "== 红检开始(启动可观测性)=="

mutate_and_expect M1 bin/ds_shell.py test_s1_timestamp_carries_a_date \
  'stamp = time.strftime("%Y-%m-%d %H:%M:%S")' 'stamp = time.strftime("%H:%M:%S")'

mutate_and_expect M2 bin/ds_web.py test_s2_request_lines_carry_a_timestamp \
  'sys.stdout.write("%s %s - %s\n" % (stamp, self.address_string(), fmt % args))' \
  'sys.stdout.write("%s - %s\n" % (self.address_string(), fmt % args))'

mutate_and_expect M3 bin/ds_diag.py test_s3_each_startup_gets_its_own_id \
  'self.run_id = run_id or secrets.token_hex(3)' 'self.run_id = run_id or "aaaaaa"'

mutate_and_expect M4 bin/ds_diag.py test_s3_every_line_carries_the_run_id \
  'f"[启动] run={self.run_id} +{ms:.0f}ms {event}{tail}"' 'f"[启动] +{ms:.0f}ms {event}{tail}"'

mutate_and_expect M5 bin/ds_diag.py test_s4_elapsed_survives_a_wall_clock_jump_backwards \
  'self._clock = clock or time.monotonic' 'self._clock = clock or time.time'

mutate_and_expect M6 bin/ds_diag.py test_s5_manifest_names_the_app_and_the_webview2_version \
  'f"WebView2={webview2_version()}")' 'f"")'

# 🔴 守卫型①(空壳下这条是绿的):版本清单在非 Windows 上不许炸
mutate_and_expect M7 bin/ds_diag.py test_s5_manifest_does_not_explode_off_windows \
  '    except ImportError:
        return "不适用(非 Windows)"' \
  '    except ImportError:
        raise'

mutate_and_expect M8 bin/ds_diag.py test_s7_only_whitelisted_events_get_through \
  '        if event not in UI_EVENTS:
            return False' \
  '        if False:
            return False'

mutate_and_expect M9 bin/ds_diag.py test_s7_detail_is_length_capped \
  'self.mark(event, str(detail)[:DETAIL_CAP])' 'self.mark(event, str(detail))'

mutate_and_expect M10 bin/ds_diag.py test_s7_same_event_is_not_logged_twice \
  '            if event in self._ui_seen:
                return False' \
  '            if False:
                return False'

mutate_and_expect M11 bin/ds_diag.py test_s8_snapshot_when_the_frame_never_arrives \
  '        if not self._seen.wait(self._timeout):' '        if False:'

# 🔴 守卫型②(空壳下这条是绿的):首帧到了就一行都不许写(反误报)
mutate_and_expect M12 bin/ds_diag.py test_s8_absolutely_silent_when_the_frame_does_arrive \
  '        if not self._seen.wait(self._timeout):' \
  '        self._seen.wait(self._timeout)
        if True:'

# 🔴 守卫型③(空壳下这条是绿的):超时路径不许弹框 —— 阈值一旦承重就会天天误报
mutate_and_expect M13 bin/ds_diag.py test_s9_the_timeout_path_never_pops_a_dialog \
  '            try:
                self._on_timeout()' \
  '            try:
                alert("界面没出来")
                self._on_timeout()'

mutate_and_expect M14 bin/ds_diag.py test_s10_bundle_carries_only_the_whitelist \
  '            for name in BUNDLE_LOGS:
                p = app_dir / "Logs" / name' \
  '            for p in [q for q in app_dir.rglob("*") if q.is_file()]:
                name = p.name'

# 🔴 守卫型④(空壳下这条是绿的):观测层炸了不许拖垮启动
mutate_and_expect M15 bin/ds_diag.py test_s12_a_failing_emit_does_not_raise \
  '        try:
            self._emit(text)
        except Exception:
            pass' \
  '        self._emit(text)'

mutate_and_expect M16 bin/ds_shell.py test_s6_the_lying_literal_is_gone \
  'log(f"准备进入图形循环:{window_url(web)}")' 'log(f"窗口打开:{window_url(web)}")'

mutate_and_expect M17 bin/ds_shell.py test_s11_the_probe_is_actually_wired_in \
  '                            ready_probe=web_ready_probe,' '                            '

mutate_and_expect M18 bin/ds_shell.py test_s11_web_service_has_a_real_probe \
  '            return r.status == 200
    except Exception:
        return False' \
  '            return r.status == 200
    except Exception:
        return True'

# 🔴 四审孤腿 BLOCK 抓到的三条(2026-08-30 补)
# M19 退回 urlopen —— 就是那条"配了系统代理的机器上软件根本打不开"的病
mutate_and_expect M19 bin/ds_shell.py test_s13_probe_still_works_with_a_system_proxy_configured \
  '        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(
                f"http://127.0.0.1:{int(port)}/api/health", timeout=2) as r:' \
  '        with urllib.request.urlopen(
                f"http://127.0.0.1:{int(port)}/api/health", timeout=2) as r:'

# 🔴 守卫型⑤:拿掉幂等闸 ⇒ 托盘还原会再上一次膛 ⇒ 必然超时 ⇒ 假诊断
mutate_and_expect M20 bin/ds_shell.py test_s14_second_arm_does_not_start_a_second_watch \
  '        if self._frame_watch is not None:
            return' \
  '        if False:
            return'

# 🔴 守卫型⑥:接线断掉 ⇒ 前端报了首帧也解不了看门 ⇒ 每次都误报,而其余判据照绿
mutate_and_expect M21 bin/ds_shell.py test_s15_frame_submitted_disarms_the_watch \
  '        if event == "frontend.frame_submitted":
            self._shell.note_first_frame()' \
  '        if False:
            self._shell.note_first_frame()'

# M22 关掉涂抹 ⇒ 业主的项目名/文件名又会随诊断包走
mutate_and_expect M22 bin/ds_diag.py test_s16_request_lines_keep_the_endpoint_but_lose_the_names \
  '        kept = "/" + "/".join(parts[:2])' \
  '        kept = "/" + "/".join(parts)'

# ══ s18/s19:探针那道闸(2026-08-30 深夜整批重写)══════════════════════════
# 🔴 **为什么整批重写**:原来这里的 M23~M41 打的都是 `.ps1` 里那些"判定语句",
#    而判据是**静态读源码**的。那一晚外部评审自己动手变异 8 种改法逐条执行 ——
#    每一种静态判据都全绿。判定已搬进 `bin/probe_verdict.py`(纯函数),于是:
#      · 判定的变异打在 **python** 上,由 s19 的**行为判据**(喂事实、断言裁决)接住;
#      · `.ps1` 上只剩**接线**能被剪断,由 s18 的六条接线判据接住。
#    这不是"多补几条",是把够不着的那部分从字面搬到了行为。

# ── 判定本身(打 probe_verdict.py,靠 s19 行为判据咬)────────────────────
# M23 必须清单形同虚设 ⇒ 工作台.log 缺席也不红(该红不红)
mutate_and_expect M23 bin/probe_verdict.py test_s19_a_missing_required_log_is_a_FAIL \
  '            if name in REQUIRED_LOGS:' \
  '            if False:'

# M24 把豁免的网关.log 也算成必须 ⇒ **每一趟健康的 run 都假红**
mutate_and_expect M24 bin/probe_verdict.py test_s19_the_exempt_gateway_log_may_be_missing \
  'REQUIRED_LOGS = ("外壳.log", "工作台.log")' \
  'REQUIRED_LOGS = ("外壳.log", "工作台.log", "网关.log")'

# M25 "在不在"的极性翻转 ⇒ 在场的日志被当缺席
mutate_and_expect M25 bin/probe_verdict.py test_s19_all_logs_present_is_ok \
  '        if size is None:' \
  '        if size is not None:'

# M26 报错框的判定极性翻转 ⇒ 报错框被当成真窗口
mutate_and_expect M26 bin/probe_verdict.py test_s19_only_the_error_box_is_a_FAIL \
  '    boxes = [w for w in mine if w.get("cls") == DIALOG_CLASS]' \
  '    boxes = [w for w in mine if w.get("cls") != DIALOG_CLASS]'

# M27 真窗口集合把报错框也算进去 ⇒ "只有框"永远不成立
mutate_and_expect M27 bin/probe_verdict.py test_s19_only_the_error_box_is_a_FAIL \
  '    real = [w for w in mine if w.get("cls") != DIALOG_CLASS]' \
  '    real = list(mine)'

# M28 喂给判定的**值**被改坏(不改逻辑,改常量)
mutate_and_expect M28 bin/probe_verdict.py test_s19_only_the_error_box_is_a_FAIL \
  'DIALOG_CLASS = "#32770"' \
  'DIALOG_CLASS = "#00000"'

# M29 fail-open 从"枚举不到时兜底"扩成"永远兜底" ⇒ 什么窗口都没有也判过
mutate_and_expect M29 bin/probe_verdict.py test_s19_no_window_at_all_is_a_FAIL \
  '    if ours:' \
  '    if True:'

# M30 端口段判定退回"只认 8766" ⇒ 应用挪到 8767 就判它没活(健康假红)
mutate_and_expect M30 bin/probe_verdict.py test_s19_health_on_the_moved_port_is_ok \
  '    alive = {int(p): v for p, v in answers.items() if v}' \
  '    alive = {int(p): v for p, v in answers.items() if v and int(p) == 8766}'

# M31 "有没有应答"的极性翻转 ⇒ 应答了反而判死
# (2026-08-31 换靶子:不预填之后 answers 只装真答上来的,"一个都不应答"这一组
#  是空 dict —— 极性翻转在空 dict 上看不出来。改用"应用挪到 8767 健康启动"那一组。)
mutate_and_expect M31 bin/probe_verdict.py test_s19_health_on_the_moved_port_is_ok \
  '    alive = {int(p): v for p, v in answers.items() if v}' \
  '    alive = {int(p): v for p, v in answers.items() if not v}'

# M32 退回老口径时不说明 ⇒ 读数不诚实(看到 OK 的人不知道新口径其实没生效)
mutate_and_expect M32 bin/probe_verdict.py test_s19_enumeration_failure_falls_back_to_the_old_signal \
  "(EnumWindows 一个都没枚举到,退回老口径)" \
  "(一切正常)"

# ── 接线(打 .ps1,靠 s18 六条咬)──────────────────────────────────────
# M33 第 6 相不问判定器,自己说了算
mutate_and_expect M33 .github/scripts/windows-package-probe.ps1 test_s18_the_judge_is_asked_in_every_machine_decided_phase \
  "    \$v6 = Get-Verdict 'window' @{" \
  "    \$v6 = 'OK' ; \$null = @{"

# M34 第 8 相不问判定器
mutate_and_expect M34 .github/scripts/windows-package-probe.ps1 test_s18_the_judge_is_asked_in_every_machine_decided_phase \
  "Say-Verdict '8 收日志' (Get-Verdict 'logs' @{ present = \$present })" \
  "Say-Verdict '8 收日志' \"OK\""

# M35 判定器跑不成时不再 fail-closed(判不了却当过了)
mutate_and_expect M35 .github/scripts/windows-package-probe.ps1 test_s18_a_judge_that_does_not_run_is_a_FAIL_not_a_pass \
  '    if (-not $out) { return "FAIL - 判定器没有输出(rc=$rc,stderr:$errText)" }' \
  '    if (-not $out) { return "OK" }' \
  '    if (-not (Test-Path $judge)) { return "FAIL - 判定器不在:$judge" }' \
  '    if (-not (Test-Path $judge)) { return "OK" }'

# M36 改用装出来的那份判定器(版本对不上,可能是几个月前的)
mutate_and_expect M36 .github/scripts/windows-package-probe.ps1 test_s18_the_judge_is_the_repo_copy_not_the_installed_one \
  "    \$judge = Join-Path \$PSScriptRoot '..\\..\\bin\\probe_verdict.py'" \
  "    \$judge = \"\$InstallDir\\ds\\bin\\probe_verdict.py\""

# M37 第 5 相**轮询那一圈**退回写死一个端口(初始化那行不动 —— 改它不影响行为,
#     那种变异测的是断言不是代码,第一版就是这么写的,白占一条)
mutate_and_expect M37 .github/scripts/windows-package-probe.ps1 test_s18_the_health_phases_scan_a_span_not_one_hardcoded_port \
  '    foreach ($p in $PortSpan) {
        try {
            $h = Invoke-RestMethod' \
  '    foreach ($p in @(8766)) {
        try {
            $h = Invoke-RestMethod'

# M38 退出码闸:有相自报 FAIL 却不 exit 1 ⇒ 红的 run 绿着交差
mutate_and_expect M38 .github/scripts/windows-package-probe.ps1 test_s18_any_phase_saying_FAIL_makes_the_run_red \
  "\$failed = @(\$phases.GetEnumerator() | Where-Object { \$_.Value -match 'FAIL' } | ForEach-Object { \$_.Key })" \
  '$failed = @()'

# ── M39/M40:真跑(run 33321769218)抓到的假红 —— 中文键穿不过那条管道 ──────
# M39 JSON 不转纯 ASCII ⇒ 中文键被控制台代码页打坏 ⇒ 判定器一个都查不到 ⇒ 假红
mutate_and_expect M39 .github/scripts/windows-package-probe.ps1 test_s18_the_facts_reach_the_judge_as_pure_ascii \
  '        $json = $facts | ConvertTo-Json -Depth 6 -Compress -EscapeHandling EscapeNonAscii' \
  '        $json = $facts | ConvertTo-Json -Depth 6 -Compress'

# M40 判定器自己赌 locale ⇒ C locale 下 stdin 是 ASCII ⇒ 中文键全解不出来
mutate_and_expect M40 bin/probe_verdict.py test_s19_the_cli_reads_utf8_facts_under_any_locale \
  '    sys.stdin.reconfigure(encoding="utf-8", errors="replace")' \
  '    pass  # 不管 stdin 编码'

# ── M41~M45:第 2d 轮 subdeepseek 实测出来的四种"判据全绿而行为已坏" ──────
# 🔴 其中三种正好复活这两刀亲手修的三个洞。四条我都亲手复现过。

# M41 判定器的 kind 分发键改名 ⇒ rc=2 + 用法串走 stderr ⇒ 被当成裁决 ⇒ 第 6 相静默绿
mutate_and_expect M41 bin/probe_verdict.py test_s19_every_kind_is_reachable_from_the_cli \
  '    "window": lambda f: window_verdict(f.get("wins") or [], f.get("procs") or []),' \
  '    "win": lambda f: window_verdict(f.get("wins") or [], f.get("procs") or []),'

# M42 rc 守卫拆掉 ⇒ 判定器异常退出被当成裁决(fail-open)
mutate_and_expect M42 .github/scripts/windows-package-probe.ps1 test_s18_the_judge_failing_weirdly_is_a_FAIL_not_a_verdict \
  '    if ($rc -ne 0 -and $rc -ne 1) { return "FAIL - 判定器异常退出(rc=$rc):$out" }' \
  '    # rc 不管了'

# M43 **退场**(2026-08-31):它变异的是 `Get-AppWindows $appTitle` 的参数,而挑窗口
#     已经搬进判定器、这个函数不再带参数 ⇒ 变异对象不存在。
#     等价物:M56(枚举函数又长出过滤参数)、M59(判定器认的应用名被清空)。

# M44 端口段收窄成单端口(轮询那圈照样引用 $PortSpan)⇒ 写死 8766 的假红复活
mutate_and_expect M44 .github/scripts/windows-package-probe.ps1 test_s18_the_sampling_parameters_are_pinned_too \
  '$PortSpan   = 8766..8786' \
  '$PortSpan   = @(8766)'

# M45 第 10 相自己的健康检查不再旁路代理 ⇒ 它也走那条死代理 ⇒ 每趟假红
mutate_and_expect M45 .github/scripts/windows-package-probe.ps1 test_s18_the_sampling_parameters_are_pinned_too \
  '                     -TimeoutSec 2 -Proxy $null' \
  '                     -TimeoutSec 2'

# ── M46~M53:第 2e 轮 subdeepseek 实测的七种(采实层)+ stderr 当裁决那条 ─────
# 🔴 采实层住在 .ps1 里、本机跑不了 ⇒ 只能静态钉;所以每一条都必须有变异证明它咬得动。

# M46 stderr 并回裁决流 ⇒ 判定器语法错时 traceback 被当成裁决 ⇒ exit 0
mutate_and_expect M46 .github/scripts/windows-package-probe.ps1 test_s18_stderr_can_never_become_a_verdict \
  '        $out  = $json | & $py $judge $kind 2>$errLog' \
  '        $out  = $json | & $py $judge $kind 2>&1'

# M47 **退场**(2026-08-31):`$appTitle` 这个变量没了(挑窗口搬进了判定器)。
#     ⚠️ 它退场前最后一次跑是**假的**:.ps1 的新注释里照抄了 `$appTitle = 'OpenDesign'`
#     这句话讲这段历史,变异工具打到了**注释**上 ⇒ 报"红在别处"。
#     等价物:M59(判定器的 APP_TITLE 被清空)、M61(挑窗口那一步被整个去掉)。

# M48 **退场**(2026-08-31):枚举时不再按标题匹配(那件事搬进了判定器)。
#     等价物:M57(采集条件 `if ($t)` 被翻过来)、M61(判定器里挑窗口那一步被去掉)。

# M49 窗口类的**取参**错(拿 lParam)⇒ 类名恒空 ⇒ 报错框判成真窗口
mutate_and_expect M49 .github/scripts/windows-package-probe.ps1 test_s18_the_sampling_is_pinned_not_just_referenced \
  'Class = [W32]::Cls($h)' \
  'Class = [W32]::Cls($l)'

# M50 第 8 相"在不在"的**极性**翻转 ⇒ 健康趟每份都算缺席
mutate_and_expect M50 .github/scripts/windows-package-probe.ps1 test_s18_the_sampling_is_pinned_not_just_referenced \
  '        if (Test-Path $log) {' \
  '        if (-not (Test-Path $log)) {'

# M51 Say 不再落账 ⇒ 各相照样打印 FAIL,而闸读到的是空的 ⇒ 自报 FAIL 也 exit 0
mutate_and_expect M51 .github/scripts/windows-package-probe.ps1 test_s18_the_sampling_is_pinned_not_just_referenced \
  'function Say([string]$k, [string]$v) { $phases[$k] = $v; "PHASE $k : $v" }' \
  'function Say([string]$k, [string]$v) { "PHASE $k : $v" }'

# M52 轮询退出条件的**极性**翻转 ⇒ 健康时空转、坏时提早判红
# (2026-08-31:锚点随实现变了 —— 不预填之后 answers 只装真答上来的,条件是 .Count)
mutate_and_expect M52 .github/scripts/windows-package-probe.ps1 test_s18_the_sampling_is_pinned_not_just_referenced \
  '    if ($answers.Count) { break }' \
  '    if (-not $answers.Count) { break }'

# M53 事实映射取错**属性名** ⇒ 每个窗口的 cls 都是 null ⇒ 报错框全判成真窗口
mutate_and_expect M53 .github/scripts/windows-package-probe.ps1 test_s18_the_sampling_is_pinned_not_just_referenced \
  'cls = $_.Class' \
  'cls = $_.cls'

# ══ 第 2g 轮:判断搬出 PowerShell + 闸走双路(2026-08-31)══════════════
# 这一批钉的是**第六轮 panel 实测的那 8 条**在新形状下的等价物,外加新接线本身。
# ⚠️ 有两条**故意不在这里**:闸前重播空 $phases、Get-Verdict 洗掉 FAIL 字样 ——
#    它们废掉的是**运行时**那条路,本机静态判据结构上问不出。那两条的红收据只能
#    来自真跑一趟(见 verify.md 的注入实验)。写在这里只会造出"钉过了"的假象。

# M54 第 6 相不再落收据 ⇒ 路二对这一相是瞎的
mutate_and_expect M54 .github/scripts/windows-package-probe.ps1 test_s18_the_judge_is_asked_in_every_machine_decided_phase \
  "Say-Verdict '6 窗口在不在' \$v6" \
  "Say '6 窗口在不在' \$v6"

# M55 闸不再读收据 ⇒ 退回一条路
mutate_and_expect M55 .github/scripts/windows-package-probe.ps1 test_s20_the_gate_reads_the_receipt_too \
  '    $hard = @(Get-Content $VerdictLog | Where-Object { $_ -like "1`t*" })' \
  '    $hard = @()'

# M56 枚举函数又长出过滤参数 ⇒ 挑窗口偷偷搬回本机验不了的地方
mutate_and_expect M56 .github/scripts/windows-package-probe.ps1 test_s18_the_sampling_parameters_are_pinned_too \
  'function Get-AllWindows {' \
  "function Get-AllWindows([string]\$Match = 'OpenDesign') {"

# M57 采集条件翻转 ⇒ 采的全是无标题窗口 ⇒ mine 空 ⇒ 落进 fail-open ⇒ 只有报错框时假绿
mutate_and_expect M57 .github/scripts/windows-package-probe.ps1 test_s18_the_sampling_is_pinned_not_just_referenced \
  '            if ($t) {
                $script:appwins' \
  '            if (-not $t) {
                $script:appwins'

# M58 窗口类写死 + 留个诱饵调用(第六轮实测的原物)
mutate_and_expect M58 .github/scripts/windows-package-probe.ps1 test_s20_the_window_class_is_sampled_exactly_once \
  '                $script:appwins += [PSCustomObject]@{ Title = $t; Class = [W32]::Cls($h) }' \
  '                $null = [W32]::Cls($h)
                $script:appwins += [PSCustomObject]@{ Title = $t; Class = '"'"'WindowsForms10.Window.8'"'"' }'

# M59 判定器认的应用名被清空 ⇒ 任何窗口都算我们的(第六轮实测的原物,换了地方)
mutate_and_expect M59 bin/probe_verdict.py test_s19_the_app_title_is_the_one_ds_shell_actually_uses \
  'APP_TITLE = "OpenDesign"' \
  'APP_TITLE = ""'

# M60 health 放宽成 is not None ⇒ 空版本号也算活(第六轮实测的原物)
mutate_and_expect M60 bin/probe_verdict.py test_s19_a_port_that_answered_without_a_version_is_not_alive \
  'alive = {int(p): v for p, v in answers.items() if v}' \
  'alive = {int(p): v for p, v in answers.items() if v is not None}'

# M61 挑窗口那一步被去掉 ⇒ 别人的窗口顶替我们的
mutate_and_expect M61 bin/probe_verdict.py test_s19_a_window_that_is_not_ours_does_not_count \
  'mine = [w for w in wins if APP_TITLE in str(w.get("title") or "")]' \
  'mine = list(wins)'

# M62 老口径那一步被去掉 ⇒ 别人的进程顶替我们的(fail-open 恒真)
mutate_and_expect M62 bin/probe_verdict.py test_s19_the_fallback_only_counts_our_own_processes \
  'ours = [t for t in procs if APP_TITLE in str(t)]' \
  'ours = list(procs)'

# M63 端口段又从 answers 的键反推 ⇒ 预填造出来的东西又变成了证据
mutate_and_expect M63 bin/probe_verdict.py test_s19_the_span_that_was_tried_is_named_even_when_nothing_answered \
  'ports = sorted(int(p) for p in tried)' \
  'ports = sorted(int(p) for p in answers)'

# M64 第 5 相预填复活(第六轮实测的原物)
mutate_and_expect M64 .github/scripts/windows-package-probe.ps1 test_s20_the_health_phase_does_not_prefill_the_answers \
  '$answers = @{}
$tried   = @($PortSpan)' \
  '$answers = @{}
$tried   = @($PortSpan)
foreach ($p in $PortSpan) { $answers["$p"] = $null }'

# M65 workflow 那一步不再 if: always() ⇒ 探针 exit 0(正是被绕过的样子)时它不跑
mutate_and_expect M65 .github/workflows/windows-package-probe.yml test_s20_the_workflow_independently_fails_the_job_from_the_receipt \
  '      - name: 裁决收据独立复核
        if: always()' \
  '      - name: 裁决收据独立复核'

# M66 第 6 相的等待条件改回"枚举到东西了吗" ⇒ 全量枚举下恒真 ⇒ 一秒就走人
mutate_and_expect M66 .github/scripts/windows-package-probe.ps1 test_s18_the_sampling_parameters_are_pinned_too \
  '} while ($script:lastRc -ne 0 -and (Get-Date) -lt $deadline)' \
  '} while ($wins.Count -eq 0 -and (Get-Date) -lt $deadline)'

# M67 Get-Verdict 不再记退出码 ⇒ lastRc 恒为 1 ⇒ 收据每趟全红(假红)
mutate_and_expect M67 .github/scripts/windows-package-probe.ps1 test_s20_every_verdict_leaves_a_machine_receipt \
  '    $script:lastRc = $rc
    return' \
  '    return'

# M68 收据里记的是常量而不是退出码 ⇒ 路二永远看不到 FAIL
mutate_and_expect M68 .github/scripts/windows-package-probe.ps1 test_s20_every_verdict_leaves_a_machine_receipt \
  '    ("{0}`t{1}`t{2}" -f $script:lastRc, $k, ($v -replace "`t", '"'"' '"'"')) |' \
  '    ("{0}`t{1}`t{2}" -f 0, $k, ($v -replace "`t", '"'"' '"'"')) |'

# ── 自审(panel 之前我自己找的三条,当时都是 65 条全绿放过)────────────
# M69 Say-Verdict 被换成 Say 的别名(真的那个改名留在后面当诱饵)
mutate_and_expect M69 .github/scripts/windows-package-probe.ps1 test_s20_every_verdict_leaves_a_machine_receipt \
  'function Say-Verdict([string]$k, [string]$v) {' \
  'function Say-Verdict([string]$k, [string]$v) { Say $k $v ; return }
function Say-VerdictOld([string]$k, [string]$v) {'

# M70 收据文件名只在 .ps1 这一侧改 ⇒ workflow 那步找不到文件 ⇒ 每趟假红
mutate_and_expect M70 .github/scripts/windows-package-probe.ps1 test_s20_both_files_mean_the_same_receipt \
  "\$VerdictLog     = Join-Path \$OutDir 'verdicts.tsv'" \
  "\$VerdictLog     = Join-Path \$OutDir 'verdicts-old.tsv'"

# M71 tried 写死成单端口 ⇒ 读数里"我问过哪一段"是假话
mutate_and_expect M71 .github/scripts/windows-package-probe.ps1 test_s20_the_ports_we_tried_are_the_span_we_scanned \
  '$tried   = @($PortSpan)' \
  '$tried   = @(8766)'

echo
echo "== 红检结果:咬住 $pass 条,漏网 $fail 条 =="
[ "$fail" -eq 0 ] || exit 1
