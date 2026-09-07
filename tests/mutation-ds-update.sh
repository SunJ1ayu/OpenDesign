#!/usr/bin/env bash
# 红检 —— 证明 tests/test_ds_update.py 那 18 条咬得动(track opendesign-in-app-update)。
#
# 规矩同 tests/mutation-e2e-port-preflight.sh:变异**被测对象**(bin/ds_update.py),
# 每条指定靶子(必须是**它自己**红,红在别处不算),跑完原样还回去并用哈希核对。
#
# 🔴 存在的理由:本单最要紧的那条判据(t1「预发布也算数」)防的是一条**恒绿路径** ——
#    功能永远查不到新版本却不报错。防恒绿的判据自己要是恒绿,那就什么都没防住。
set -u
cd "$(dirname "$0")/.."
PY="${PY:-/root/.venvs/design-studio/bin/python}"

SRC=bin/ds_update.py
ORACLE=tests.test_ds_update
WORK="$(mktemp -d)"
BEFORE="$(sha256sum "$SRC" | cut -d' ' -f1)"
cp -p "$SRC" "$WORK/orig.py"
restore() {
  cp -p "$WORK/orig.py" "$SRC"
  find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
}
trap 'restore; rm -rf "$WORK"' EXIT

bites=0; escapes=0

# mutate_and_expect <编号> <靶子测试名> <old> <new>
mutate_and_expect() {
  local id="$1" target="$2" old="$3" new="$4"
  restore
  "$PY" - "$SRC" "$old" "$new" <<'PYEOF' || { echo "  [BAD]  $id 变异没打上去(靶子文本没匹配到)"; escapes=$((escapes+1)); return; }
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding="utf-8")
old, new = sys.argv[2], sys.argv[3]
if s.count(old) != 1:
    print(f"    锚点出现 {s.count(old)} 次,不是 1 次:{old!r}")
    sys.exit(1)
p.write_text(s.replace(old, new), encoding="utf-8")
PYEOF
  local out="$WORK/mut-$id.txt"
  DS_SHELL_E2E=1 "$PY" -m unittest "$ORACLE" > "$out" 2>&1
  if grep -qE "^(FAIL|ERROR): $target" "$out"; then
    echo "  [咬住] $id → $target"
    bites=$((bites+1))
  elif grep -q "^OK" "$out"; then
    echo "  [漏网] $id 判据全绿 —— $target 没咬住这个变异"
    escapes=$((escapes+1))
  else
    echo "  [红在别处] $id 红了,但不是 $target(红在别处等于没红检过)"
    sed -n 's/^\(FAIL\|ERROR\): \(.*\)$/      实际红的:\2/p' "$out" | head -3
    escapes=$((escapes+1))
  fi
}

echo "== 红检 bin/ds_update.py =="

# m1 🔴 本单的命根子:把预发布过滤掉 = 功能永远查不到新版本
mutate_and_expect m1 test_t1_picks_the_newest_even_though_all_are_prerelease \
  'if not isinstance(rel, dict) or rel.get("draft"):' \
  'if not isinstance(rel, dict) or rel.get("draft") or rel.get("prerelease"):'

# m1b 结构闸:代码里真的去调那个接口
mutate_and_expect m1b test_t1b_code_must_not_call_the_latest_endpoint \
  'RELEASES_PATH = "/repos/{repo}/releases"' \
  'RELEASES_PATH = "/repos/{repo}/releases/latest"'

# m1c 注释里提到那个接口**不许**被咬(反误报对照组,方向与其它条相反)
restore
"$PY" - "$SRC" <<'PYEOF'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding="utf-8")
p.write_text(s.replace('TIMEOUT_S = 10',
                       '# 反误报对照:这一行注释里写了 releases/latest,闸不许因此变红\nTIMEOUT_S = 10'),
             encoding="utf-8")
PYEOF
if DS_SHELL_E2E=1 "$PY" -m unittest "$ORACLE" >"$WORK/mut-m1c.txt" 2>&1 && grep -q "^OK" "$WORK/mut-m1c.txt"; then
  echo "  [对照组] m1c 注释里提到那个接口 → 仍然全绿(没有误报)"
  bites=$((bites+1))
else
  echo "  [误报!] m1c 只在注释里提了一下就红了 —— 这道闸会逼人删掉解释才能过"
  escapes=$((escapes+1))
fi

# m2 版本按字符串比("0.98.10" < "0.98.9" 在字符串下成立)
# (锚点 2026-09-07 随 S1 改实现更新过一次 —— 变异锚点过期在本仓是老毛病,
#  所以脚本对"没匹配到"报 [BAD] 而不是当没事发生。)
mutate_and_expect m2 test_t2a_numeric_not_lexicographic \
  'parts = [int(n) for n in m.group(1).split(".")]' \
  'parts = [n for n in m.group(1).split(".")]'

# m3 相等也提示更新
mutate_and_expect m3 test_t3a_same_version_no_offer \
  'if there <= here:' \
  'if there < here:'

# m4 本地更新时也提示(往回装)
mutate_and_expect m4 test_t3b_local_newer_no_offer \
  'if there <= here:' \
  'if there == here:'

# m5 资产不认名字,抓到什么算什么
# 靶子从 t1c 改到 t1c2(2026-09-07):第一轮红检时 m5 **漏网**,查出来 t1c 结构上
# 就问不出这件事 —— 它把资产整个拿走,那时认不认名字都返回 None。
# 于是新加了 t1c2(资产名字不对也不算候选),靶子跟着搬到问得出的地方。
# ⚠️ 这不是"改考卷让自己及格":断言是**加强**了(多问一件原来没问的事),
#    而且搬完之后 m5 必须仍然红 —— 红不了就是真放水。
mutate_and_expect m5 test_t1c2_asset_with_a_wrong_name_is_not_an_installer \
  'if ASSET_RE.match(asset.get("name") or ""):' \
  'if True:'

# m6 草稿也算数
mutate_and_expect m6 test_t1d_draft_is_never_a_candidate \
  'if not isinstance(rel, dict) or rel.get("draft"):' \
  'if not isinstance(rel, dict):'

# m7 异常直接漏给业主
mutate_and_expect m7 test_t7d_never_raises_whatever_happens \
  '    except Exception as exc:  # noqa: BLE001 —— 故意兜底,判据 t7d 就是钉它' \
  '    except ValueError as exc:'

# m8 读不出版本号时抛,而不是返回 None
mutate_and_expect m8 test_t2e_garbage_returns_none_not_exception \
  '    if not isinstance(text, str):
        return None' \
  '    if not isinstance(text, str):
        raise TypeError(text)'

# m9 给出 API 地址而不是浏览器下载地址(下回来的会是一坨 JSON,不是 exe)
mutate_and_expect m9 test_t3c_local_older_offers_with_what_it_needs \
  '"url": asset.get("browser_download_url"),' \
  '"url": asset.get("url"),'

# m10 读不出本机版本号时照样提示更新
mutate_and_expect m10 test_t3d_unparsable_local_version_never_offers \
  '''    here = parse_version(current)
    if here is None:''' \
  '''    here = parse_version(current) or (0, 0, 0)
    if here is None:'''

# ── 缓存那一批 ────────────────────────────────────────────────────────────

# m11 🔴 失败也进缓存 = 一次断网把"查不到"钉死 6 小时
mutate_and_expect m11 test_t8d_failure_is_never_cached \
  '    if not result.get("error"):' \
  '    if True:'

# m12 缓存不按版本号分键 = 装完新版还拿旧答案提示更新
# (第一版的 m12 是**我自己的变异写错了**:只多写一个键,读那一侧仍然按版本查,
#  性质根本没被破坏 ⇒ 判据全绿是对的。已给实现抽出 _cache_key 接缝,
#  现在一行就能表达"不按版本分键"。)
mutate_and_expect m12 test_t8e_cache_is_keyed_by_current_version \
  '    return current' \
  '    return "same-for-everyone"'

# m13 业主点「检查更新」也给缓存
mutate_and_expect m13 test_t8c_force_bypasses_cache \
  '    if not force:' \
  '    if True:'

# m14 缓存永不过期
mutate_and_expect m14 test_t8b_expired_cache_refetches \
  '        if hit and t - hit[0] < ttl:' \
  '        if hit:'

# m15 压根不缓存(每次都真去问 ⇒ 限流)
mutate_and_expect m15 test_t8a_second_call_within_ttl_does_not_refetch \
  '        hit = _cache.get(_cache_key(current))' \
  '        hit = None'

# ── S1 那批(自审补的)──────────────────────────────────────────────

# m16 只认三段(回到自审前的样子)= 业主宣布 1.0 那天更新检查看不见它
# (靶子故意避开反斜杠:第一版写成完整正则,经 heredoc→shell→python 三层转义后对不上,
#  脚本报的是 [BAD] 变异没打上去,不是假绿。)
mutate_and_expect m16 test_t2f_two_segment_version_is_understood \
  '{1,3}"' \
  '{2,3}"'

# m17 不补零 ⇒ (0,98) < (0,98,0),0.98 会被当成比 0.98.0 旧
mutate_and_expect m17 test_t2g_padding_makes_the_short_form_compare_right \
  '            while len(parts) < 3:
                parts.append(0)' \
  '            while False:
                parts.append(0)'

# m18 版本号形状不再要求"整段吻合"(去掉尾锚)⇒ 0.98.x 被当成 0.98,坏版本号当好的用
mutate_and_expect m18 test_t2e_garbage_returns_none_not_exception \
  'BARE_RE = re.compile(rf"^({_NUM})$")' \
  'BARE_RE = re.compile(rf"^({_NUM})")'

restore
AFTER="$(sha256sum "$SRC" | cut -d' ' -f1)"
echo
if [ "$BEFORE" != "$AFTER" ]; then
  echo "🔴 被测文件没还原干净!before=$BEFORE after=$AFTER"
  exit 2
fi
echo "== 红检小结:咬住 $bites 条 / 漏网 $escapes 条(被测文件已逐字节还原)=="
[ "$escapes" -eq 0 ] || exit 1
