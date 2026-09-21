#!/usr/bin/env bash
# 跑全套红检,每个情景一份干净的仓外副本(变异不碰活仓),收据落 evidence/。
#   用法: probes/run-redchecks.sh <标签>          # 例:baseline-old-b8 / after-fix
set -u
cd "$(dirname "$0")/../../.."
LABEL="${1:?用法: run-redchecks.sh <标签>}"
PY="${PY:-/root/.venvs/design-studio/bin/python}"
OUT="tracks/opendesign-b8-race-forensics/evidence"
BASE="$(mktemp -d -p "${TMPDIR:-/tmp}" b8-redcheck-XXXXXX)"
trap 'rm -rf "$BASE"' EXIT
# 干净母本 = 当前**工作树**(不是 HEAD)——红检要问的是我现在手里这一版。
SRC="$(git stash create)"; SRC="${SRC:-HEAD}"
git archive "$SRC" | tar -x -C "$BASE"
rc_all=0
for c in r1 r2a r2b r2c r2c-lazy r3; do
  rep=1; [ "$c" = r3 ] && rep=3               # 正常树多跑几遍,竞态单次绿说明不了什么
  lazy=""; case="$c"
  if [ "$c" = r2c-lazy ]; then case=r2c; lazy="--lazy-probe"; fi
  work="$BASE/work-$c"; rm -rf "$work"; cp -r "$BASE" "$work" 2>/dev/null
  rm -rf "$work"/work-* 2>/dev/null
  f="$OUT/$LABEL-$c.txt"
  {
    echo "# 红检 $c  标签=$LABEL  commit=$(git rev-parse --short HEAD)  源=$SRC  改动文件数=$(git status --porcelain | grep -c .)"
    echo "# 跑于 $(date -u +%Y-%m-%dT%H:%M:%SZ)  副本=$work [仓外不承重]"
    timeout 600 "$PY" tracks/opendesign-b8-race-forensics/probes/redcheck.py \
        --repo "$work" --case "$case" $lazy --repeat "$rep" 2>&1
    echo "# rc=$?"
  } > "$f" 2>&1
  tail -2 "$f" | head -1
  grep -q "rc=0" "$f" || rc_all=1
done
echo "== 全套 rc=$rc_all (0=每条都符合预期)"
exit $rc_all
