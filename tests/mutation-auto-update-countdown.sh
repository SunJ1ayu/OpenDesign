#!/usr/bin/env bash
# track opendesign-auto-update-countdown 的前端变异红检(主 agent 亲写)。
# 为什么要有:AC-B / AC-E / AC-F / AC-H 里"什么都不该发生"那几条在基线上**结构上红不了**(基线本来就什么都不发生),
# AC-A 的 10 秒也只有在实现存在时才量得到。只有故意改坏实现、看它们咬不咬,才知道它们不是恒真。
# 每个变异:改 web/src/App.tsx → build 进 web/dist → 跑 e2e → 记结果 → 恢复(web/src 与 web/dist 都 checkout 回去)。
# 跑法:tests/mutation-auto-update-countdown.sh(约 9 分钟;会改写工作树里的 web/dist,跑完恢复;工作树要干净)
# 任何一行「漏网」或「没落地」⇒ 退出码 1。
set -u
cd "$(dirname "$0")/.."
if [ -n "$(git status --porcelain -- web/src web/dist)" ]; then echo "web/src 或 web/dist 有没提交的改动,拒跑(跑完会 checkout 回去)"; exit 2; fi
bad=0
restore() { git checkout -q -- web/src web/dist; git clean -qfd web/dist; }
trap restore EXIT
run() {
  local name="$1" expect="$2"; shift 2
  restore
  python3 - "$@" <<'PY'
import sys, pathlib
p = pathlib.Path("web/src/App.tsx"); s = p.read_text()
old, new = sys.argv[1], sys.argv[2]
if s.count(old) != 1:
    print("MUTATION-ANCHOR-MISSING", s.count(old)); sys.exit(3)
p.write_text(s.replace(old, new))
PY
  [ $? -eq 0 ] || { echo "[$name] 锚点没找到,变异没落地"; bad=1; return; }
  (cd web && npm run build >/dev/null 2>&1) || { echo "[$name] build 失败,不算数"; bad=1; return; }
  out=$(node tests/e2e/auto_update_countdown.e2e.mjs 2>&1)
  # 🔴 只认**失败行**里的那句断言原文(第一版 grep 段名 —— 段名在标题行里每次都出现,等于恒绿,09-17 自查抓到)。
  if echo "$out" | grep -E "FAIL: .*($expect)" >/dev/null; then
    echo "[$name] 咬住 ✅ —— 期望红在:$expect"
  else
    echo "[$name] 漏网 ❌ —— 没有红在:$expect"; bad=1
  fi
  echo "$out" | grep -E "FAIL|条没过|全部通过" | cut -c1-160 | sed 's/^/    /'
}
run M1-manual-check-counts-down "手动「检查更新」也弹了倒计时|手动「检查更新」之后自己发了 [1-9]" \
  'if (startupAuto) handleStartupAutoCheck(d);' 'if (startupAuto || d) handleStartupAutoCheck(d);'
run M2-toggle-counts-down "中途打开自动检查开关也弹了倒计时|中途打开开关之后自己发了 [1-9]" \
  '    checkUpdate(false, false);
  }, [autoCheck, checkUpdate]);' '    checkUpdate(false, true);
  }, [autoCheck, checkUpdate]);'
run M3-timer-3s "横幅出现到自动更新请求之间应当约 10 秒" \
  '}, AUTO_UPDATE_SECONDS * 1000);' '}, 3000);'
run M4-cancel-not-suppressing "点了取消,之后还是自动发了|取消之后发了|取消之后倒计时横幅又冒出来了" \
  '                autoSuppressedRef.current = true;
                clearAutoCountdown(true);
                setAutoBanner(null);' '                clearAutoCountdown(true);
                setAutoBanner(null);
                window.setTimeout(() => { const i = updateInfoRef.current; if (i) startAutoCountdown(i); }, 3000);'
run M5-manual-apply-keeps-countdown "业主已经手动开始更新了,横幅还在倒计时|应当只有手动那一次请求" \
  '    if (!isAuto) {
      autoSuppressedRef.current = true;
      clearAutoCountdown(true);
    } else {' '    if (!isAuto) {
      /* mutated */
    } else {'
restore
echo "== 变异红检结束:$([ $bad -eq 0 ] && echo 全部咬住 || echo 有漏网或没落地)"
exit $bad
