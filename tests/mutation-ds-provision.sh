#!/usr/bin/env bash
# 红检(变异测试)—— 证明 tests/test_ds_provision.py 这份判据咬得动。
#
# 规矩与 tests/mutation-ds-shell-core.sh 同一套(别再各写一份):
#   1. 变异的是**被测对象**(bin/ds_provision.py),不是判据本身。
#   2. 每条变异都指定**靶子**:必须是**那一条**红,不是"随便红了就算过"。
#   3. 跑完把文件原样还回去,并**机械核对**(哈希)还回去了。
#
# 用法:tests/mutation-ds-provision.sh
# 退出码:0 = 每条变异都咬住了靶子   1 = 有漏网   2 = 现场问题

set -u
cd "$(dirname "$0")/.."
PY="${PY:-/root/.venvs/design-studio/bin/python}"
SRC=bin/ds_provision.py
ORACLE=tests/test_ds_provision.py
WORK="$(mktemp -d)"
BEFORE="$(sha256sum "$SRC" | cut -d' ' -f1)"
cp "$SRC" "$WORK/原件.py"

restore() { cp "$WORK/原件.py" "$SRC"; }
trap 'restore; rm -rf "$WORK"' EXIT

pass=0; fail=0

mutate_and_expect() {
  local id="$1" target="$2"; shift 2
  local out="$WORK/mut-$id.txt"
  restore
  # 08-07 的账:同长度替换 + 同一秒 mtime ⇒ CPython 可能复用旧 .pyc,
  # 红检既造得出假绿也造得出假红。被测对象是脚本(不进缓存),但同目录的模块会 ——
  # 一句 find 换掉一整类没法解释的怪现象。
  find bin tests -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null
  "$PY" - "$SRC" "$@" <<'PYEOF' || { echo "  [BAD]  $id 变异没打上去"; fail=$((fail+1)); return; }
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding="utf-8")
args = sys.argv[2:]
if len(args) % 2:
    sys.exit("旧/新必须成对")
for old, new in zip(args[0::2], args[1::2]):
    if old not in s:
        sys.exit(f"变异锚点找不到: {old!r}")
    s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")
PYEOF
  timeout 600 "$PY" -W ignore "$ORACLE" > "$out" 2>&1
  local rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "  [BAD]  $id -> 判据全绿:这条变异下它是瞎的(靶子 $target)"
    fail=$((fail+1))
  elif grep -qE "^(FAIL|ERROR): $target" "$out"; then
    echo "  [OK]   $id -> 靶子 $target 如期红了"
    pass=$((pass+1))
  else
    echo "  [BAD]  $id -> 红了,但**不是靶子** $target:"
    grep -E "^(FAIL|ERROR):" "$out" | head -4 | sed 's/^/         实际红的是:/'
    fail=$((fail+1))
  fi
}

echo "== 红检开始(每条变异都要咬住指定的那一条)=="

# M1 口令字母表混进非 ASCII —— 界面全好、第一句话永远发不出去的那种坏法
mutate_and_expect M1 test_a3_token_is_latin1_safe \
  '_ALPHABET = "abcdefghjkmnpqrstuvwxyz' \
  '_ALPHABET = "中文abcdefghjkmnpqrstuvwxyz'

# M2 口令不写给业主看 —— 随机生成的口令没人知道 = 聊天永远登不进去
mutate_and_expect M2 test_a4_owner_can_find_the_token \
  '    note = home / ".openDesign" / "登录口令.txt"' \
  '    note = home / ".openDesign" / "别处.txt"'

# M3 幂等性拆掉:每次跑都换一把新口令 ⇒ 业主抄下来的那把第二天失效
mutate_and_expect M3 test_b1_second_run_keeps_the_token \
  '    elif existing:' \
  '    elif False:'

# M4 已有配置一律当"没有配置" ⇒ 业主用了一年的那份被悄悄覆盖
#    (M3 打的是口令来源,这条打的是"读不读已有配置",两处不同的防线)
mutate_and_expect M4 test_b2_owner_chosen_token_survives \
  '    if not cfg_path.exists():
        return None' \
  '    if True:
        return None'

# M5 坏 JSON 当成"没有配置" ⇒ 覆盖掉业主唯一的那份
mutate_and_expect M5 test_d2_leaves_a_corrupt_config_alone \
  '    except (OSError, ValueError) as exc:' \
  '    except (OSError,) as exc:'

# M6 包装坏了(模板没铺进去)不点名 ⇒ 业主拿到的是合并脚本甩出来的 Python 栈。
#    两处检查都得拆掉才算真的破坏了契约(前置扫一次、merge 前再扫一次)——
#    只拆一处本就不该红,那是防线冗余,不是判据瞎。锚点用单行,别跟多行转义较劲。
mutate_and_expect M6 test_d1_says_human_words_when_the_template_is_missing \
  '    if not (ds_root / "config" / TEMPLATE_NAME).is_file():' \
  '    if False:' \
  '    if not template.is_file():' \
  '    if False:'

# M7 写到业主自己的家里 ⇒ 把他现有那套 nanobot/openclaw 弄坏,而他不会知道是我干的
mutate_and_expect M7 test_c1_does_not_touch_the_machines_own_nanobot \
  '    cfg_path = home / ".nanobot" / "config.json"' \
  '    cfg_path = Path(os.path.expanduser("~")) / ".nanobot" / "config.json"'

# M8 凭据落进配置文件 ⇒ 配置是会进日志/截图/收据的东西
mutate_and_expect M8 test_a6_no_credential_lands_in_the_config \
  '    note = write_token_note(home, final)' \
  '    _leak = json.loads(cfg_path.read_text(encoding="utf-8"))
    _leak.setdefault("providers", {}).setdefault("custom", {})["apiKey"] = "sk-泄漏了"
    write_json(cfg_path, _leak)
    note = write_token_note(home, final)'

# M9 模板压根没合并 ⇒ 三个工具服务都不在,助手"什么都不会做"
mutate_and_expect M9 test_a5_mcp_servers_are_wired \
  '    r = subprocess.run([python_exe, str(merger), str(template), str(cfg_path)],' \
  '    return
    r = subprocess.run([python_exe, str(merger), str(template), str(cfg_path)],'

# M10 本地聊天通道没打开 ⇒ 外壳的 patch_config 会拒绝这份配置
mutate_and_expect M10 test_a2_the_shell_accepts_what_provision_produced \
  '    ws["enabled"] = True' \
  '    ws["enabled"] = False'

# M11 显式给的口令不过 latin-1 闸 ⇒ 中文口令被写进去,等到聊天才炸
mutate_and_expect M11 test_b4_refuses_a_token_the_browser_cannot_send \
  '        final = check_token(token)          # 显式给的:当场验,不合格立刻说' \
  '        final = token.strip()'

# M12 往数据目录之外写东西 ⇒ 安装器的"只碰自己那棵树"承诺破功
mutate_and_expect M12 test_c2_writes_nothing_outside_the_home \
  '    note = home / ".openDesign" / "登录口令.txt"' \
  '    note = home.parent / "别动我" / "登录口令.txt"'

# M13 形状检查拆掉 ⇒ {"channels": null} 直接 AttributeError,业主收到一个 Python 栈
mutate_and_expect M13 test_e1_null_channels_does_not_throw_a_stack_at_the_owner \
  '            if not isinstance(node, dict):' \
  '            if False:'

# M14 退回"先落盘再合并" ⇒ 合并失败时留下一份开了通道却没有工具服务的半成品配置
# ⚠️ 第一版变异把 staging 直接换成 cfg_path,结果 finally 把**正式配置**删了 ——
#    破坏的比契约多,红在别处。变异要精确地只还原"顺序"这一件事。
mutate_and_expect M14 test_e3_a_failing_merge_leaves_no_half_config_behind \
  '        write_json(staging, cfg)
        merge_template(python_exe, ds_root, staging)
        os.replace(staging, cfg_path)' \
  '        write_json(staging, cfg)
        os.replace(staging, cfg_path)
        merge_template(python_exe, ds_root, cfg_path)'

restore
AFTER="$(sha256sum "$SRC" | cut -d' ' -f1)"
echo
if [ "$BEFORE" != "$AFTER" ]; then
  echo "🔴 还原失败:$SRC 与开跑前不一致($BEFORE -> $AFTER)"
  exit 2
fi
echo "被测文件已原样还回(sha256 一致:${BEFORE:0:12}…)"
echo "== 红检结束:咬住 $pass 条,漏网 $fail 条 =="
[ "$fail" -eq 0 ] || exit 1
