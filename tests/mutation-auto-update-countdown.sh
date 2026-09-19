#!/usr/bin/env bash
# track opendesign-auto-update-countdown 的前端变异红检(主 agent 亲写)。
# 为什么要有:AC-B / AC-E / AC-F / AC-H 里"什么都不该发生"那几条在基线上**结构上红不了**(基线本来就什么都不发生),
# AC-A 还要挡住延迟更新与提前开放工作区。故意改坏实现,验证这些断言确实会失败。
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
run M1-manual-check-auto-applies "手动检查之后自己发了更新请求" \
  'if (startupAuto) handleStartupAutoCheck(d);' 'if (startupAuto || d) handleStartupAutoCheck(d);'
run M2-toggle-auto-applies "中途开启自动检查之后自己发了更新请求" \
  'if (previous !== autoCheck && autoCheck) checkUpdate(false, false);' \
  'if (previous !== autoCheck && autoCheck) checkUpdate(false, true);'
run M3-delayed-auto-update "查到新版后没有立即发起自动更新" \
  '      void applyUpdate(true);' '      window.setTimeout(() => { void applyUpdate(true); }, 10000);'
run M4-workspace-before-update "检查更新结束前工作区已经出现|更新完成前工作区曾被挂载" \
  '  if (startupPhase !== "ready") {' '  if (false && startupPhase !== "ready") {'
run M5-handoff-opens-old-workspace "接力程序刚启动就进入了旧版工作区|更新交棒后提前进入了旧版工作区" \
  '        if (!parsed.ok) setStartupPhase("ready");' '        setStartupPhase("ready");'

restore
echo "== 变异红检结束:$([ $bad -eq 0 ] && echo 全部咬住 || echo 有漏网或没落地)"
exit $bad
