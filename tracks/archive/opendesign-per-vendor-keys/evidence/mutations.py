"""定点变异(track opendesign-per-vendor-keys,主 agent 亲写):每个变异单独套在一份干净副本上,跑点名的判据,期望红。"""
import os, shutil, subprocess, sys, tempfile
REPO = "/root/.openclaw/workspace/projects/design-studio"
PY = "/root/.venvs/design-studio/bin/python"
MUTS = [
 ("M1 保存第二家时就往配置写条目", "bin/ds_credential.py",
  "                _atomic_write(_switch_marker_path(home), provider + \"\\n\")\n",
  "                _atomic_write(_switch_marker_path(home), provider + \"\\n\")\n                cfg.setdefault('providers', {})[extra_provider_name(provider)] = {'apiKey': '${%s}' % extra_var_name(provider), 'apiBase': PROVIDERS[provider]['apiBase']}\n                _atomic_write(cfg_path, json.dumps(cfg, ensure_ascii=False, indent=2) + \"\\n\")\n",
  ["tests.test_per_vendor_keys"]),
 ("M2 prepare_gateway 写了条目却不给 key", "bin/ds_credential.py",
  "    return _extra_env(home, cfg)\n\n\ndef _extra_env", "    return {}\n\n\ndef _extra_env",
  ["tests.test_per_vendor_keys", "tests.test_per_vendor_live"]),
 ("M3 child_env 丢掉额外 key", "bin/ds_shell_core.py",
  "        env[str(name)] = str(value)\n    return env", "        pass\n    return env",
  ["tests.test_per_vendor_keys", "tests.test_per_vendor_live"]),
 ("M4 额外 key 也给了 ds-web", "bin/ds_shell_core.py",
  '"ds-web": child_env(base_env, key=None, key_var=None, **common)',
  '"ds-web": child_env(base_env, key=None, key_var=None, extra_keys=extra_keys, **common)',
  ["tests.test_per_vendor_keys"]),
 ("M5 菜单按 key 文件列厂商(不看网关有没有)", "bin/ds_credential.py",
  "    for vendor in _extra_entries(cfg):\n        if vendor not in out:",
  "    import glob as _g\n    for vendor in [os.path.basename(p)[:-4] for p in _g.glob(os.path.join(os.environ.get('HOME',''), '*', '.openDesign', 'keys', '*.txt'))] + list(_extra_entries(cfg)):\n        if vendor in PROVIDERS and vendor not in out:",
  ["tests.test_per_vendor_keys"]),
 ("M8 标记从不兑现", "bin/ds_credential.py",
  "        if marker in wanted or (marker == primary and read_key(home)):",
  "        if False:", ["tests.test_per_vendor_keys"]),
 ("M9 key 不在也吃掉标记", "bin/ds_credential.py",
  "    if not wanted and not existing and marker is None:\n        return cfg, False",
  "    if not wanted and not existing and marker is None:\n        return cfg, False\n    if marker is not None and marker not in wanted:\n        return cfg, True",
  ["tests.test_per_vendor_keys"]),
 ("M10 只有主槽时也补齐预设(改老家配置)", "bin/ds_credential.py",
  "    if not wanted and not existing and marker is None:\n        return cfg, False", "    if False:\n        return cfg, False",
  ["tests.test_per_vendor_keys"]),
 ("M10b 主槽补齐不看有没有第二家", "bin/ds_credential.py",
  "    if primary is not None and wanted:", "    if primary is not None:",
  ["tests.test_per_vendor_keys"]),
 ("M10c 两道一起去掉(早退 + 主槽补齐的条件)", "bin/ds_credential.py",
  "    if not wanted and not existing and marker is None:\n        return cfg, False",
  "    if False:\n        return cfg, False\n    wanted = wanted or {'__combo__': 1}" ,
  ["tests.test_per_vendor_keys"]),
 ("M11 选网关没拿到 key 的厂商也放行", "bin/ds_credential.py",
  "        hits = [v for v in live if model in PROVIDERS[v][\"models\"]]",
  "        hits = [v for v in PROVIDERS if model in PROVIDERS[v][\"models\"]]",
  ["tests.test_per_vendor_keys"]),
 ("M12 multi 被忽略(永远单把)", "bin/ds_credential.py",
  "    if multi and isinstance(cfg, dict):", "    if False:",
  ["tests.test_per_vendor_keys", "tests.test_per_vendor_live"]),
 ("M13 外壳不调 prepare_gateway", "bin/ds_shell.py",
  "        extra_keys = ds_credential.prepare_gateway(str(home), str(cfg))", "        extra_keys = {}",
  ["tests.test_ds_shell_wiring"]),
 ("M14 key 没了条目照留、注入空串", "bin/ds_credential.py",
  "        if vendor not in wanted:\n            providers.pop(name, None)",
  "        if False:\n            providers.pop(name, None)",
  ["tests.test_per_vendor_keys"]),
 ("M15 额外槽预设仍指 custom(发往主槽端点)", "bin/ds_credential.py",
  "                p[\"provider\"] = name\n", "                pass\n",
  ["tests.test_per_vendor_keys"]),
]
MUTS = [m for m in MUTS if not m[0].startswith(("M5 ", "M10c"))]
MUTS += [
 ("M5b 菜单列目录里所有厂商(不看网关有没有 key)", "bin/ds_credential.py",
  "    for vendor in _extra_entries(cfg):\n        if vendor not in out:",
  "    for vendor in list(PROVIDERS):\n        if vendor not in out:",
  ["tests.test_per_vendor_keys"]),
]
MUTS += [
 ("M10d 早退与主槽补齐条件一起去掉(会改老家配置)", "bin/ds_credential.py",
  ["    if not wanted and not existing and marker is None:\n        return cfg, False", "    if primary is not None and wanted:"],
  ["    pass", "    if primary is not None:"], ["tests.test_per_vendor_keys"]),
 ("M-ui1 打勾不看厂商", "web/src/chat/modelPicker.ts",
  "active: g.provider === status.provider && m.id === status.current });", "active: m.id === status.current });",
  ["node:tests/test_per_vendor_ui.mjs"]),
 ("M-ui2 点了不带厂商", "web/src/chat/modelPicker.ts",
  "return item.provider ? { model: item.id, provider: item.provider } : { model: item.id };", "return { model: item.id };",
  ["node:tests/test_per_vendor_ui.mjs"]),
]
only = sys.argv[1:]
for label, rel, old, new, tests in MUTS:
    if only and not any(label.startswith(o) for o in only):
        continue
    work = tempfile.mkdtemp(prefix="pv-mut-")
    subprocess.run(f"git -C {REPO} archive HEAD | tar -x -C {work}", shell=True, check=True)
    path = os.path.join(work, rel)
    src = open(path, encoding="utf-8").read()
    olds, news = (old, new) if isinstance(old, list) else ([old], [new])
    if any(src.count(o) != 1 for o in olds):
        print(f"??  {label}: 变异锚点找不到/不唯一"); shutil.rmtree(work); continue
    for o, n in zip(olds, news):
        src = src.replace(o, n)
    open(path, "w", encoding="utf-8").write(src)
    if tests[0].startswith("node:"):
        r = subprocess.run(["node", "--test", tests[0][5:]], cwd=work, capture_output=True, text=True, timeout=600)
        tail = [l for l in r.stdout.splitlines() if l.startswith("not ok")]
    else:
        r = subprocess.run([PY, "-m", "unittest", *tests], cwd=work, capture_output=True, text=True, timeout=600)
        tail = [l for l in (r.stdout + r.stderr).splitlines() if l.startswith(("FAIL:", "ERROR:"))]
    verdict = "咬住" if r.returncode != 0 else "🔴 漏了"
    print(f"{verdict}  {label}  rc={r.returncode}  红 {len(tail)} 条: {'; '.join(t.split('(')[0].replace('FAIL: ','').replace('ERROR: ','') for t in tail[:4])}")
    shutil.rmtree(work, ignore_errors=True)
