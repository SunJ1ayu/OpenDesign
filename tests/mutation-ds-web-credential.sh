#!/usr/bin/env bash
# 红检 —— 证明**接口层**那两份判据咬得动 bin/ds_web.py 的本单改动。
#
# 为什么单独一份(tests/mutation-credential.sh 不够):那一份只变异
# ds_credential.py / ds_shell_core.py,**一行 ds_web.py 都没碰** ⇒ 两个针孔、
# 来源检查、口令代签这三样从落地起一次红检都没跑过。
# 而 89ca1e7 刚**改强了** test_ds_web_proxy 的题面 —— 改题面就得重新红检,
# 否则"我把断言改强了"这句话只有我的自述在撑着。
#
# 用法:tests/mutation-ds-web-credential.sh   退出码:0 全咬住 / 1 有漏网
set -u
cd "$(dirname "$0")/.."
PY="${PY:-/root/.venvs/design-studio/bin/python}"
WORK="$(mktemp -d)"
SRCS=(bin/ds_web.py)

declare -A BEFORE
for s in "${SRCS[@]}"; do
  BEFORE[$s]="$(sha256sum "$s" | cut -d' ' -f1)"
  cp "$s" "$WORK/$(basename "$s").orig"
done
restore() { for s in "${SRCS[@]}"; do cp "$WORK/$(basename "$s").orig" "$s"; done; }
trap 'restore; rm -rf "$WORK"' EXIT
pass=0; fail=0

# 用法:mutate_and_expect <id> <靶子测试名> <判据文件> <老串> <新串>
mutate_and_expect() {
  local id="$1" target="$2" oracle="$3" file="bin/ds_web.py" old="$4" new="$5"
  local out="$WORK/mut-$id.txt"
  restore
  # 同长度替换 + 同一秒 mtime 会让 CPython 复用旧 .pyc(2026-08-07 的雷:
  # 既造过假绿也造过假红)⇒ 每条变异前把字节码缓存清干净。
  find bin tests -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null
  "$PY" - "$file" "$old" "$new" <<'PYEOF' || { echo "  [BAD]  $id 变异没打上去"; fail=$((fail+1)); return; }
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding="utf-8")
old, new = sys.argv[2], sys.argv[3]
if old not in s:
    sys.exit(f"变异锚点找不到: {old!r}")
p.write_text(s.replace(old, new, 1), encoding="utf-8")
PYEOF
  timeout 300 "$PY" -W ignore "$oracle" > "$out" 2>&1
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

CRED=tests/test_ds_web_credential.py
PROXY=tests/test_ds_web_proxy.py

echo "== 红检开始(接口层)=="

# ---- 来源检查:双向都要验(一个永远拒绝的闸和一个永远放行的闸一样没用)----

# M1 拆掉 Sec-Fetch-Site 这一道(Origin 白名单还在)
# 🔴 靶子不能写 i1/i2/i3:那三条**同时**带两个头,拆一道另一道就接住了 —— 首跑它们
# 真的全绿,而那不是"判据瞎",是**变异等价**。分离验证的 i7 才是这道防线的靶子。
mutate_and_expect M1 test_i7_a_cross_site_fetch_marker_alone_is_enough_to_refuse "$CRED" \
  '        if site and site not in ("same-origin", "same-site", "none"):' \
  '        if False:'

# M2 拆掉 Origin 白名单这一道(Sec-Fetch-Site 还在)⇒ 不发那个头的老浏览器就失守
mutate_and_expect M2 test_i6_a_cross_site_origin_alone_is_enough_to_refuse "$CRED" \
  '        port = self.server.server_address[1]' \
  '        return True
        port = self.server.server_address[1]'

# M3 反向:恒拒 ⇒ 误伤同源页面和我自己的 curl(判据 i4/i5 是这条的双向验)
mutate_and_expect M3 test_i5_a_plain_request_without_origin_still_works "$CRED" \
  '        origin = (self.headers.get("Origin") or "").strip()' \
  '        return False
        origin = (self.headers.get("Origin") or "").strip()'

# ---- 口令代签:签没签、签的是不是配置里那一个、会不会漏回浏览器 ----

# M4 不替前端签 ⇒ 退回"业主自己输口令"那个形状(本单要消灭的)
mutate_and_expect M4 test_j1_proxy_signs_with_the_configured_password "$CRED" \
  '            pw = _gateway_password()' \
  '            pw = None'

# M5 签的不是配置里那一个 ⇒ 这条专门验 89ca1e7 那次"把断言改强"到底值不值
mutate_and_expect M5 test_09_header_allowlist "$PROXY" \
  '                hdrs["Authorization"] = "Bearer " + pw' \
  '                hdrs["Authorization"] = "Bearer 随便签一个"'

# M6 口令跟着响应回浏览器 ⇒ 等于把长期凭据交出去
mutate_and_expect M6 test_j2_the_password_itself_never_comes_back "$CRED" \
  '        self._send(status, ctype, body)  # 状态码原样透传(含 401)' \
  '        self._send(status, ctype, body + (_gateway_password() or "").encode())'

# ---- key 不回显:好路径、坏路径、和"存完之后再读一次" ----

# M7 存完顺手把原文回给界面
mutate_and_expect M7 test_h2_saving_returns_no_key_and_says_what_happens_next "$CRED" \
  '        out.pop("env_var", None)          # 给外壳用的,不必给浏览器' \
  '        out["key"] = str(body.get("key") or "")'

# M8 坏路径把请求体回显(最容易被忽略的那一面)
mutate_and_expect M8 test_h3_a_bad_provider_is_refused_in_human_words "$CRED" \
  '            self._json(400, {"error": str(exc)})' \
  '            self._json(400, {"error": str(exc), "body": body})'

# M9 状态接口把原文一起回 ⇒ 界面刷新一次就把它印出来
mutate_and_expect M9 test_h4_the_key_never_shows_up_in_a_later_read "$CRED" \
  '        out = ds_credential.status(os.path.expanduser("~"), cfg)' \
  '        out = ds_credential.status(os.path.expanduser("~"), cfg)
        out["key"] = ds_credential.read_key(os.path.expanduser("~"))'

# M10 降级不诚实:通道没接通却回"已请求重启" ⇒ 业主等一个不会发生的事
# 🔴 首跑漏网:h2 只问"是那两个值之一",规格里的"不假装成功"没进判据 ⇒ 补了 h5。
mutate_and_expect M10 test_h5_without_a_shell_it_says_manual_instead_of_pretending "$CRED" \
  '    return "manual"' \
  '    return "requested"'

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
