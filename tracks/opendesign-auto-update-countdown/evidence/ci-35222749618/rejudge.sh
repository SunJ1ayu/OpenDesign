#!/usr/bin/env bash
# 用仓里当前的判定器重判 Windows 真机 run 35222749618 采回来的九份事实(事实原样拷自 CI 产物 update-e2e-out)。
set -u
cd "$(dirname "$0")/../../../.."
dir=tracks/opendesign-auto-update-countdown/evidence/ci-35222749618
rc=0
for k in e1 e2 e3 e4 e5 e6 e7 e8 e9; do
  python3 .github/scripts/update_e2e_verdict.py "$k" "$dir/facts-$k.json" || rc=1
done
exit $rc
