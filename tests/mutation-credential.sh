#!/usr/bin/env bash
# 红检 —— 证明 tests/test_credential.py 咬得动。
#
# 这一份格外重要:那些判据在实现存在之前红的是 **ModuleNotFoundError**,
# 那种红只证明"模块没了会响",**不证明"模块在但写错了会响"**(08-14 记过同款账)。
#
# 用法:tests/mutation-credential.sh   退出码:0 全咬住 / 1 有漏网
set -u
cd "$(dirname "$0")/.."
PY="${PY:-/root/.venvs/design-studio/bin/python}"
ORACLE=tests/test_credential.py
WORK="$(mktemp -d)"
SRCS=(bin/ds_credential.py bin/ds_shell_core.py)

declare -A BEFORE
for s in "${SRCS[@]}"; do
  BEFORE[$s]="$(sha256sum "$s" | cut -d' ' -f1)"
  cp "$s" "$WORK/$(basename "$s").orig"
done
restore() { for s in "${SRCS[@]}"; do cp "$WORK/$(basename "$s").orig" "$s"; done; }
trap 'restore; rm -rf "$WORK"' EXIT
pass=0; fail=0

mutate_and_expect() {
  local id="$1" target="$2" file="$3" old="$4" new="$5"
  local out="$WORK/mut-$id.txt"
  restore
  find bin tests -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null
  "$PY" - "$file" "$old" "$new" <<'PYEOF' || { echo "  [BAD]  $id 变异没打上去"; fail=$((fail+1)); return; }
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding="utf-8")
old, new = sys.argv[2], sys.argv[3]
if old not in s:
    sys.exit(f"变异锚点找不到: {old!r}")
p.write_text(s.replace(old, new, 1), encoding="utf-8")
PYEOF
  timeout 300 "$PY" -W ignore "$ORACLE" > "$out" 2>&1
  local rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "  [BAD]  $id -> 判据全绿:这条变异下它是瞎的(靶子 $target)"; fail=$((fail+1))
  elif grep -qE "^(FAIL|ERROR): $target" "$out"; then
    echo "  [OK]   $id -> 靶子 $target 如期红了"; pass=$((pass+1))
  else
    echo "  [BAD]  $id -> 红了,但**不是靶子** $target:"
    grep -E "^(FAIL|ERROR):" "$out" | head -3 | sed 's/^/         实际红的是:/'; fail=$((fail+1))
  fi
}

echo "== 红检开始 =="

# M1 把 key 原样塞进返回值 ⇒ 界面/日志/我的收据里都会出现它
mutate_and_expect M1 test_a2_nothing_the_api_returns_contains_the_key bin/ds_credential.py \
  '    out["env_var"] = var' \
  '    out["env_var"] = var; out["key"] = k'

# M2 把 key 写进配置(nanobot 的 settings API 就能这么干)⇒ 配置会进日志/截图/收据
mutate_and_expect M2 test_a3_the_config_never_holds_the_key bin/ds_credential.py \
  '    custom["apiKey"] = "${%s}" % var             # 只留引用形态,原文永不进配置' \
  '    custom["apiKey"] = k'

# M3 报错带上入参 ⇒ 坏路径把 key 回显出去(最容易被忽略的那一面)
mutate_and_expect M3 test_a4_the_failure_path_does_not_leak_it_either bin/ds_credential.py \
  '        raise CredentialError(f"配置读不出来:{cfg_path}({exc.__class__.__name__})") from None' \
  '        raise CredentialError(f"配置读不出来:{cfg_path} key={k} ({exc})") from None'

# M4 "提示"直接给原文 ⇒ 业主截个图就把 key 发出去了
mutate_and_expect M4 test_a5_the_hint_is_a_hint_not_the_key bin/ds_credential.py \
  '    return f"{k[:4]}…{k[-4:]}"' \
  '    return k'

# M5 变量名写死 ⇒ 两台 git-pull 机器上网关必死(规划双出 B 卷抓到的那条)
mutate_and_expect M5 test_c1_reads_whatever_variable_the_config_references bin/ds_credential.py \
  '    return m.group(1)' \
  '    return "DS_LLM_KEY"'

# M6 apiKey 不是 ${VAR} 时悄悄给个默认 ⇒ 静默走错(失败没有声音)
mutate_and_expect M6 test_c3_no_reference_is_an_error_not_a_silent_default bin/ds_credential.py \
  '        raise CredentialError("配置里的 apiKey 不是 ${变量} 形态,不知道该设哪个环境变量")' \
  '        return "DS_LLM_KEY"'

# M7 预设值在代码里另抄一份 ⇒ 与出货模板漂移(两边一起错也发现不了)
mutate_and_expect M7 test_b3_the_presets_come_from_the_shipped_template_not_a_second_copy bin/ds_credential.py \
  '    "mimo": {"label": "MiMo(小米)", **_template_presets()},' \
  '    "mimo": {"label": "MiMo(小米)", "apiBase": "https://抄错了/v1", "model": "mimo-v9"},'

# M8 缺 key 时连界面也不起 ⇒ 引导页永远没机会出现(退回本单要修的那个形状)
mutate_and_expect M8 test_d1_without_a_key_the_web_starts_and_the_gateway_waits bin/ds_shell_core.py \
  '    return {"start": ["ds-web"], "wait": ["网关"]}' \
  '    return {"start": [], "wait": ["ds-web", "网关"]}'

# M9 key.txt 里多写点别的 ⇒ "允许它在这个文件里"这条白名单会掩盖二次写入
mutate_and_expect M9 test_b1_key_file_is_one_clean_line bin/ds_credential.py \
  '        _atomic_write(key_path(home), k + "\n")' \
  '        _atomic_write(key_path(home), k + "\n# provider=" + provider + "\n")'

restore
echo
bad=0
for s in "${SRCS[@]}"; do
  now="$(sha256sum "$s" | cut -d' ' -f1)"
  [ "$now" = "${BEFORE[$s]}" ] || { echo "🔴 $s 没还原干净"; bad=1; }

# ── E 组(来源层 / writable):2026-08-16 对照 DSH 的 credentials seam 补的 ──────
# 这几条判据先行时红的是 **KeyError: 'source'**(字段不存在),那种红只证明
# "没有就会响" —— 下面才是"写错了会不会响"。

# N1 ~~空串当成有值~~ **等价变异,已撤**:去掉 `.strip() or None` 之后返回的是 `""`,
#    而下游全程用 truthiness(`env_key or key`、`if env_key else`)⇒ 空串照样被排除,
#    行为一字不差。**单点变异违反不了 e5**。
#    e5 因此咬不动 —— 但它不是废条:它防的是未来有人把下游改成 `is not None`
#    (那时空串就会冒充成一把配好的 key)。**红检咬不动 ≠ 判据没价值**,
#    同 T3 那两条等价变异的处理。

# N2 🔴 最该咬住的一条:报 key.txt 那把而不是真正生效的 env 那把
#    ⇒ 业主换完 key 看见"新的末四位",网关还在用旧的
mutate_and_expect N2 test_e4_when_both_exist_it_reports_the_one_that_actually_wins bin/ds_credential.py \
  '    live = env_key or key' \
  '    live = key or env_key'

# N3 来源层认反 ⇒ 界面把"环境变量供的"说成"文件供的"
# 🔴 第一版变异打偏了:`"file" if key else ("env" if env_key else None)` 在
#    「只有 env、没有 key.txt」时**结果一模一样**,红的是 e4 不是 e2。
#    脚本的"靶子核对"当场把它记成 [BAD] —— 那道核对是对的,不然我会以为 e2 有牙。
mutate_and_expect N3 test_e2_env_supplied_reports_its_layer bin/ds_credential.py \
  '            "source": "env" if env_key else ("file" if key else None),' \
  '            "source": "file" if env_key else ("file" if key else None),'

# N4 恒可写 ⇒ 被遮蔽那一格照样让业主填,白填一次
mutate_and_expect N4 test_e6_env_supplied_is_not_writable bin/ds_credential.py \
  '            "writable": env_key is None}' \
  '            "writable": True}'

# N5 拿掉遮蔽拒绝 ⇒ 写入"表面成功"(DSH 明确点名的那个病)
mutate_and_expect N5 test_e8_saving_while_shadowed_is_refused_and_says_which_variable bin/ds_credential.py \
  '    if _env_key(cfg):' \
  '    if False:'

# N6 configured 退回只看 key.txt ⇒ 装完就弹一张不该弹的卡
mutate_and_expect N6 test_e1_env_supplied_counts_as_configured bin/ds_credential.py \
  '    return {"configured": live is not None, "provider": provider,' \
  '    return {"configured": key is not None, "provider": provider,'

done
[ "$bad" -eq 0 ] && echo "被测文件原样还回(${#SRCS[@]} 个哈希一致)"
echo "== 红检结束:咬住 $pass 条,漏网 $fail 条 =="
[ "$fail" -eq 0 ] && [ "$bad" -eq 0 ] && exit 0 || exit 1
