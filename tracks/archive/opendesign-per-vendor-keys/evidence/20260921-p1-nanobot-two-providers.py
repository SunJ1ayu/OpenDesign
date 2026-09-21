import json, os, sys, tempfile
from pathlib import Path
from nanobot.providers.factory import load_provider_snapshot
cfg = {
  "providers": {
    "custom": {"apiKey": "${DS_LLM_KEY}", "apiBase": "https://token-plan-cn.xiaomimimo.com/v1"},
    "od_deepseek": {"apiKey": "${DS_LLM_KEY_DEEPSEEK}", "apiBase": "https://api.deepseek.com/v1"},
  },
  "model_presets": {
    "mimo-v2.5": {"label": "mimo-v2.5", "provider": "custom", "model": "mimo-v2.5"},
    "deepseek-v4-flash": {"label": "deepseek-v4-flash", "provider": "od_deepseek", "model": "deepseek-v4-flash"},
  },
  "agents": {"defaults": {"modelPreset": "mimo-v2.5"}},
}
p = Path(tempfile.mkdtemp()) / "config.json"
def run(preset, env):
    cfg["agents"]["defaults"]["modelPreset"] = preset
    p.write_text(json.dumps(cfg))
    for k in ("DS_LLM_KEY", "DS_LLM_KEY_DEEPSEEK"): os.environ.pop(k, None)
    os.environ.update(env)
    try:
        s = load_provider_snapshot(p)
        pr = s.provider
        print(f"{preset:20} -> model={s.model} base={getattr(pr,'api_base',None)} key={getattr(pr,'api_key',None)} cls={type(pr).__name__}")
    except Exception as e:
        print(f"{preset:20} -> ERROR {type(e).__name__}: {e}")
both = {"DS_LLM_KEY": "k-mimo", "DS_LLM_KEY_DEEPSEEK": "k-ds"}
run("mimo-v2.5", both)
run("deepseek-v4-flash", both)
run("mimo-v2.5", {"DS_LLM_KEY": "k-mimo"})            # deepseek var missing
run("deepseek-v4-flash", {"DS_LLM_KEY": "k-mimo", "DS_LLM_KEY_DEEPSEEK": ""})  # empty string
