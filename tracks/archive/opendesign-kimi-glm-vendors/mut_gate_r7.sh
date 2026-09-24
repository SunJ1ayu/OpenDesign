#!/bin/bash
# 第 7 轮 MiMo 声称存活的两个闸变异(M3 只看额外槽 / M4 活厂商≥2):逐个套上,跑全部 set_model 相关判据;任何一个变异全绿 ⇒ 退出 1
set -u; PY=/root/.venvs/design-studio/bin/python; bak=$(mktemp); cp bin/set_model.py "$bak"; rc=0
for m in "ds_credential._extra_entries(cfg)" "len(ds_credential._live_vendors(cfg)) >= 2"; do
  sed -i "s/    if isinstance(cfg, dict) and ds_credential._live_vendors(cfg):/    if isinstance(cfg, dict) and $m:/" bin/set_model.py
  grep -q "and $m:" bin/set_model.py || { echo "变异没套上:$m"; rc=1; }
  if $PY tests/test_kimi_glm_vendors.py >/dev/null 2>&1 && $PY tests/test_set_model.py >/dev/null 2>&1; then echo "存活:$m"; rc=1
  else echo "被杀:$m ← $($PY tests/test_kimi_glm_vendors.py 2>&1 | grep -E '^FAIL:' | sed 's/ (.*//;s/FAIL: //' | sort -u | tr '\n' ' ')"; fi
  cp "$bak" bin/set_model.py
done
cmp -s "$bak" bin/set_model.py || { echo "没还原"; rc=1; }; rm -f "$bak"; exit $rc
