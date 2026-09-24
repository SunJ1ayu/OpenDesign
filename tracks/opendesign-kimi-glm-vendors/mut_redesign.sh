#!/usr/bin/env bash
# 改设计后的变异自检:每个变异都必须让 test_vendor_one_door 红(rc≠0)。跑完还原。
set -u
cd "$(dirname "$0")/../.."
PY=/root/.venvs/design-studio/bin/python
survived=0
mut() {  # name file python-replace-old python-replace-new
  cp "$2" "$2.orig"
  if ! python3 - "$2" "$3" "$4" <<'P'
import sys; p,o,n=sys.argv[1:]; s=open(p,encoding='utf-8').read(); assert o in s,(p,o); open(p,'w',encoding='utf-8').write(s.replace(o,n,1))
P
  then echo "BROKEN   $1(原文找不到,变异没打上 —— 不许当成存活或被杀)"; survived=$((survived+1)); mv "$2.orig" "$2"; return; fi
  find bin -name __pycache__ -exec rm -rf {} + 2>/dev/null
  if $PY tests/test_vendor_one_door.py >/dev/null 2>&1; then echo "SURVIVED $1"; survived=$((survived+1)); else echo "killed   $1"; fi
  mv "$2.orig" "$2"
}
# (第 10 轮起按新代码重写 M1/M2:原文变了,旧写法会「没打上却显示存活」)
mut M1-no-steady-sweep bin/ds_credential.py '            if model in catalog:' '            if False:'
mut M2-keep-bare-name-as-is bin/ds_credential.py '                    _rename_preset(cfg, name, preset_name(here, model))
                    _apply_params(presets[preset_name(here, model)], here)' '                    pass'
mut M3-ignore-endpoint-change bin/ds_credential.py '_route_presets(cfg, endpoint_changed=endpoint_changed)' '_route_presets(cfg)'
mut M4-always-endpoint-change bin/ds_credential.py '_route_presets(cfg, endpoint_changed=endpoint_changed)' '_route_presets(cfg, endpoint_changed=True)'
mut M5-merge-template-into-foreign bin/ds_merge_config.py 'tpl["model_presets"] = {}' 'pass'
mut M6-merge-accepts-flags bin/ds_merge_config.py 'if args.api_base is not None or args.model is not None:' 'if False:'
# 第 10 轮修复清单
mut M7-rename-becomes-delete bin/ds_credential.py 'if here in PROVIDERS and model in PROVIDERS[here]["models"]:' 'if False:'
mut M8-save-always-resets-model bin/ds_credential.py '    if cur is None and not endpoint_changed:
        pass
    elif not (' '    if True:
        defaults["modelPreset"] = name
    elif not ('
mut M9-foreign-needs-own-presets bin/ds_merge_config.py 'foreign = bool(existing_base) and ds_credential' 'foreign = bool(existing_base) and bool(own_presets) and ds_credential'
mut M10-merge-skips-alignment bin/ds_merge_config.py '    ds_credential._route_presets(cfg)
    ds_credential._fallback_if_dangling(cfg)' '    pass'
mut M11-select-keeps-wrong-model bin/ds_credential.py 'existing["model"] = model' 'pass'
mut M12-save-overwrites-before-route bin/ds_credential.py '    _route_presets(cfg, endpoint_changed=endpoint_changed)
    ex = presets.get(name)' '    presets[name] = _custom_preset(provider, preset["model"])
    _route_presets(cfg, endpoint_changed=endpoint_changed)
    ex = presets.get(name)'
mut M13-keep-presets-on-a-gone-slot bin/ds_credential.py '        if prov != "custom" and not isinstance(providers.get(prov), dict):
            presets.pop(name)' '        if False:
            presets.pop(name)'
# 第 11 轮:DeepSeek 实测穿过全部判据的两个变异
mut M14-fallback-picks-whatever-is-first bin/ds_credential.py '        fallback = preset_name(primary, PROVIDERS[primary]["model"]) if primary else None' '        fallback = None'
mut M15-rename-skips-params bin/ds_credential.py '                    _rename_preset(cfg, name, preset_name(here, model))
                    _apply_params(presets[preset_name(here, model)], here)' '                    _rename_preset(cfg, name, preset_name(here, model))'
mut M16-merge-invents-current-on-foreign bin/ds_merge_config.py 'elif own_presets and (existing_preset or not foreign):' 'elif own_presets:'
mut M17-fallback-picks-first-on-foreign bin/ds_credential.py '        elif defaults.get("model") or not presets:
            defaults.pop("modelPreset")' '        elif not presets:
            defaults.pop("modelPreset")'
mut M18-model-field-brain-gets-overwritten bin/ds_credential.py '    if cur is None and not endpoint_changed:
        pass' '    if False:
        pass'
find bin -name __pycache__ -exec rm -rf {} + 2>/dev/null
echo "survived=$survived"; exit $survived
