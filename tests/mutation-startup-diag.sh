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

SOURCES=(bin/ds_diag.py bin/ds_shell.py bin/ds_web.py \
         .github/scripts/windows-package-probe.ps1)
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

# ── s18:探针那道闸(08-30 第二轮外部评审报的两条,判据是静态的 ⇒ 更要证明咬得动)──
# 🔴 这四条变异改的是 **.ps1**,不是 python。本机没有 pwsh,判据只能读源码 ——
#    所以"判据是不是瞎的"这个问题在这里比别处更尖锐:把修复原样撤回去,它必须红。

# M23 撤掉"缺席=FAIL"那句文案 ⇒ 第 8 相又只剩 catch 里那个 FAIL ⇒ 现场是空的也绿
mutate_and_expect M23 .github/scripts/windows-package-probe.ps1 test_s18_a_missing_required_log_is_a_FAIL \
  'Say '"'"'8 收日志'"'"' "FAIL - 必须有的日志缺席:$($miss -join '"'"', '"'"') ⇒ 现场是空的。明细:$($got -join '"'"' | '"'"')"' \
  'Say '"'"'8 收日志'"'"' "必须有的日志缺席:$($miss -join '"'"', '"'"')。明细:$($got -join '"'"' | '"'"')"'

# M24 清空"必须有哪几份"的清单 ⇒ 缺谁都一样宽,FAIL 分支永远走不到
mutate_and_expect M24 .github/scripts/windows-package-probe.ps1 test_s18_the_required_logs_are_named \
  '    $required = @('"'"'外壳.log'"'"', '"'"'工作台.log'"'"')' \
  '    $required = @()'

# M25 把窗口类那一刀撤掉(只留注释里那句话)⇒ 报错框又算"窗口在"
#     ——这条同时也是在验判据自己滤掉了注释行;不滤的话它会在这条上瞎掉。
mutate_and_expect M25 .github/scripts/windows-package-probe.ps1 test_s18_the_window_phase_can_tell_a_message_box_from_the_app \
  '    $box  = @($wins | Where-Object { $_.Class -eq '"'"'#32770'"'"' })' \
  '    $box  = @()'

# M26 把"只有报错框"那条 FAIL 改回 OK ⇒ "软件根本打不开"整趟绿(评审报的正是这条路)
mutate_and_expect M26 .github/scripts/windows-package-probe.ps1 test_s18_a_screen_with_only_the_error_box_is_a_FAIL \
  '    Say '"'"'6 窗口在不在'"'"' "FAIL - 屏幕上只有报错框(窗口类 #32770),没有真窗口 ⇒ 软件根本打不开。框里写的:$txt"' \
  '    Say '"'"'6 窗口在不在'"'"' "OK - 有窗口(报错框也算)"'

# ── M27~M29:第 2b 轮外部评审报的两条判据洞(F1 守卫被阉割 / F2 极性翻转)──
# 🔴 三条我都亲手复现过:改之前**四条 s18 全绿**。它们是 M25 那类"字面满足不了判定"
#    的两个更狠的形态 —— 文案一个字没动,而机器事实再也够不到那条 FAIL。

# M27 把第 8 相的守卫改成常量假 ⇒ "现场是空的"永远走不到 FAIL(文案还在)
mutate_and_expect M27 .github/scripts/windows-package-probe.ps1 test_s18_a_missing_required_log_is_a_FAIL \
  '    if ($miss.Count) {' \
  '    if ($false) {'

# M28 把第 6 相的守卫改成常量真 ⇒ 这一相恒红(文案还在)
mutate_and_expect M28 .github/scripts/windows-package-probe.ps1 test_s18_a_screen_with_only_the_error_box_is_a_FAIL \
  'if ($box.Count -and -not $real.Count) {' \
  'if ($true) {'

# M29 极性:-eq 抄成 -ne ⇒ $box/$real 变成同一堆 ⇒ 只有报错框的屏幕走 $ours 判 OK(产品级假绿)
mutate_and_expect M29 .github/scripts/windows-package-probe.ps1 test_s18_the_window_phase_can_tell_a_message_box_from_the_app \
  "    \$box  = @(\$wins | Where-Object { \$_.Class -eq '#32770' })" \
  "    \$box  = @(\$wins | Where-Object { \$_.Class -ne '#32770' })"

# ── M30~M33:第 2b 轮 subkimi(超时前把报告写完了)报的三条,同一种病的第 3~5 个实例 ──
# 🔴 四条我都亲手复现过:改之前 s18 全绿。

# M30 攒 $miss 的依据被改成常量假 ⇒ 第 8 相的 FAIL 永远走不到(清单、文案、外层守卫都还在)
mutate_and_expect M30 .github/scripts/windows-package-probe.ps1 test_s18_the_required_logs_are_named \
  'if ($required -contains $n) { $miss += $n }' \
  'if ($false) { $miss += $n }'

# M31 把"必须"从清单换成全部 ⇒ 网关.log 合法缺席也算缺 ⇒ **每一趟健康的 run 都假红**
mutate_and_expect M31 .github/scripts/windows-package-probe.ps1 test_s18_the_required_logs_are_named \
  'if ($required -contains $n) { $miss += $n }' \
  'if ($names -contains $n) { $miss += $n }'

# M32 在场信号退回"任何带标题的窗口" ⇒ b99b603 修的"结构上不可能红"原样复活
mutate_and_expect M32 .github/scripts/windows-package-probe.ps1 test_s18_the_presence_signal_is_still_filtered_by_the_app_title \
  '    $ours = @($all | Where-Object { $_ -like "*$appTitle*" })' \
  '    $ours = @($all)'

# M33 把窗口类名那两行注释掉(代码没了、字还在)⇒ 验判据确实滤掉了注释
mutate_and_expect M33 .github/scripts/windows-package-probe.ps1 test_s18_the_window_phase_can_tell_a_message_box_from_the_app \
  '  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassNameW(IntPtr h, StringBuilder s, int n);' \
  '  // GetClassNameW 被注释掉了' \
  '    var sb = new StringBuilder(256); GetClassNameW(h, sb, 256); return sb.ToString();' \
  '    var sb = new StringBuilder(256); return sb.ToString();'

# ── M34~M37:第 2c 轮 subgemini 报的同一条数据流(第 7~10 个实例)──
# 🔴 前四条我都亲手复现过(M34/M35);M36/M37 是同一条链上剩下的两环,一并钉住。

# M34 真窗口集合把报错框也算进去 ⇒ "只有框"永远不成立 ⇒ 产品级假绿
mutate_and_expect M34 .github/scripts/windows-package-probe.ps1 test_s18_the_window_phase_can_tell_a_message_box_from_the_app \
  "    \$real = @(\$wins | Where-Object { \$_.Class -ne '#32770' })" \
  '    $real = @($wins)'

# M35 -contains → -notcontains:"$required" 三个字还在,而网关.log 变成永远缺席 ⇒ 趟趟假红
mutate_and_expect M35 .github/scripts/windows-package-probe.ps1 test_s18_the_required_logs_are_named \
  'if ($required -contains $n) { $miss += $n }' \
  'if ($required -notcontains $n) { $miss += $n }'

# M36 窗口清单不按应用标题取 ⇒ 同屏任何窗口都算"真窗口"
mutate_and_expect M36 .github/scripts/windows-package-probe.ps1 test_s18_the_window_phase_can_tell_a_message_box_from_the_app \
  '    $wins = @(Get-AppWindows $appTitle)' \
  "    \$wins = @(Get-AppWindows '')"

# M37 辅助函数不再取窗口类(段外那一环,第 6 相一个字不用改)
mutate_and_expect M37 .github/scripts/windows-package-probe.ps1 test_s18_the_window_lister_reports_title_and_class \
  '                $script:appwins += [PSCustomObject]@{ Title = $t; Class = [W32]::Cls($h) }' \
  '                $script:appwins += [PSCustomObject]@{ Title = $t; Class = "" }'

# ── M38~M41:第 2c 轮 submimo 报的(第 11~13 个实例)+ 退出码闸自己的判据 ──

# M38 在场信号算了但没人用(赋值还在,while 条件里删掉)
mutate_and_expect M38 .github/scripts/windows-package-probe.ps1 test_s18_the_presence_signal_is_still_filtered_by_the_app_title \
  '} while ($ours.Count -eq 0 -and $box.Count -eq 0 -and (Get-Date) -lt $deadline)' \
  '} while ($box.Count -eq 0 -and (Get-Date) -lt $deadline)'

# M39 辅助函数不问"窗口可见吗" ⇒ 看不见的窗口也算窗口在
# 🔴 锚点必须**唯一**:`IsWindowVisible` 在 Dump-Dialogs 里也有一份,而变异工具只换第一处
#    —— 第一版锚点就是这么打到了**另一个函数**上(判据当然不红,脚本判 BAD 是对的)。
mutate_and_expect M39 .github/scripts/windows-package-probe.ps1 test_s18_the_window_lister_reports_title_and_class \
  '        if ([W32]::IsWindowVisible($h)) {
            $t = [W32]::Text($h)
            if ($t -like "*$Match*") {
                $script:appwins' \
  '        if ($true) {
            $t = [W32]::Text($h)
            if ($t -like "*$Match*") {
                $script:appwins'

# M40 必须清单对、收集清单里却没有它 ⇒ 循环走不到 ⇒ 该红不红
mutate_and_expect M40 .github/scripts/windows-package-probe.ps1 test_s18_the_required_logs_are_named \
  "    \$names    = @('外壳.log', '工作台.log', '网关.log')" \
  "    \$names    = @('工作台.log', '网关.log')"

# M41 退出码闸:有相自报 FAIL 却不 exit 1 ⇒ 红的 run 绿着交差
mutate_and_expect M41 .github/scripts/windows-package-probe.ps1 test_s18_any_phase_saying_FAIL_makes_the_run_red \
  "\$failed = @(\$phases.GetEnumerator() | Where-Object { \$_.Value -match 'FAIL' } | ForEach-Object { \$_.Key })" \
  '$failed = @()'

echo
echo "== 红检结果:咬住 $pass 条,漏网 $fail 条 =="
[ "$fail" -eq 0 ] || exit 1
