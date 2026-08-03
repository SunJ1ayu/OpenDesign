#!/usr/bin/env bash
# MCP 契约闸的总跑开关(track opendesign-mcp-registry)。
#
# 存在的理由(2026-08-03):`pytest tests/` 用的 `python3` **没装 mcp** ⇒
# 工具表快照闸(`test_mcp_surface.py`)与入口契约闸的关键两条会**整块 SKIP**,
# 而汇总只会印一行漂亮的 "836 passed"。本单最重要的那条闸就这样在收货记录里
# 被当成"跑过了"。同一种病 `tests/e2e/run-all.sh` 已经治过一次:**SKIP 不算 PASS**。
#
# 所以这个脚本只做一件事:用**装了 mcp 的 python** 跑这几条闸,
# 而且**没装 mcp 就直接红**,不给"静默跳过"留门。
#
# 用法:
#   tests/mcp-gate.sh                     # 默认用 design-studio venv 的 python
#   PY=/path/to/python tests/mcp-gate.sh  # 指定解释器(Windows 真机用 Scripts\python.exe)
set -uo pipefail

cd "$(dirname "$0")/.."                   # 仓库根
PY="${PY:-/root/.venvs/design-studio/bin/python}"

if ! "$PY" -c "import mcp" 2>/dev/null; then
  echo "mcp-gate: FAIL —— \`$PY\` 没装 mcp 包。" >&2
  echo "  这几条闸查的正是 MCP 契约,没装 mcp 它们只会 SKIP,而 SKIP 不算 PASS。" >&2
  echo "  用装了 mcp 的解释器重跑:PY=<python> tests/mcp-gate.sh" >&2
  exit 2
fi

rc=0
for mod in test_mcp_surface test_mcp_entry_contract test_no_import_cycles; do
  echo "== $mod"
  "$PY" -m unittest discover -s tests -t tests -p "$mod.py" || rc=1
done

if [ $rc -eq 0 ]; then echo "mcp-gate: 全绿($PY)"; else echo "mcp-gate: 有红" >&2; fi
exit $rc
