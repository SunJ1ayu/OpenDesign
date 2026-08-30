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

SOURCES=(bin/ds_diag.py bin/ds_shell.py bin/ds_web.py)
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

echo
echo "== 红检结果:咬住 $pass 条,漏网 $fail 条 =="
[ "$fail" -eq 0 ] || exit 1
