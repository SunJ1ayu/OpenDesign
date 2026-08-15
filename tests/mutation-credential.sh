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
done
[ "$bad" -eq 0 ] && echo "被测文件原样还回(${#SRCS[@]} 个哈希一致)"
echo "== 红检结束:咬住 $pass 条,漏网 $fail 条 =="
[ "$fail" -eq 0 ] && [ "$bad" -eq 0 ] && exit 0 || exit 1
