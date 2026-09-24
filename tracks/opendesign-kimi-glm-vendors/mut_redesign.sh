#!/usr/bin/env bash
# 改设计后的变异自检:每个变异都必须让 test_vendor_one_door 红(rc≠0)。跑完还原。
set -u
cd "$(dirname "$0")/../.."
PY=/root/.venvs/design-studio/bin/python
survived=0
mut() {  # name file python-replace-old python-replace-new
  cp "$2" "$2.orig"
  python3 - "$2" "$3" "$4" <<'P'
import sys; p,o,n=sys.argv[1:]; s=open(p,encoding='utf-8').read(); assert o in s,(p,o); open(p,'w',encoding='utf-8').write(s.replace(o,n,1))
P
  find bin -name __pycache__ -exec rm -rf {} + 2>/dev/null
  if $PY tests/test_vendor_one_door.py >/dev/null 2>&1; then echo "SURVIVED $1"; survived=$((survived+1)); else echo "killed   $1"; fi
  mv "$2.orig" "$2"
}
mut M1-no-steady-sweep bin/ds_credential.py 'if p.get("model") in catalog or (prov == "custom" and endpoint_changed):' 'if prov == "custom" and endpoint_changed:'
mut M2-keep-bare-on-primary bin/ds_credential.py 'if p.get("model") in catalog or (prov == "custom" and endpoint_changed):' 'if (p.get("model") in catalog and p.get("model") not in (PROVIDERS[primary]["models"] if primary else [])) or (prov == "custom" and endpoint_changed):'
mut M3-ignore-endpoint-change bin/ds_credential.py '_route_presets(cfg, endpoint_changed=endpoint_changed)' '_route_presets(cfg)'
mut M4-always-endpoint-change bin/ds_credential.py '_route_presets(cfg, endpoint_changed=endpoint_changed)' '_route_presets(cfg, endpoint_changed=True)'
mut M5-merge-template-into-foreign bin/ds_merge_config.py 'tpl["model_presets"] = {}' 'pass'
mut M6-merge-accepts-flags bin/ds_merge_config.py 'if args.api_base is not None or args.model is not None:' 'if False:'
find bin -name __pycache__ -exec rm -rf {} + 2>/dev/null
echo "survived=$survived"; exit $survived
