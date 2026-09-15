#!/usr/bin/env bash
# 红检 —— 证明 rl1~rl12 咬得动(track opendesign-update-check-rate-limit)。
# 每条变异:改一个被测文件的一处、跑对应判据、要求**指定的那一条**红;跑完逐字节还原并核哈希。
set -u
cd "$(dirname "$0")/.."
PY="${PY:-/root/.venvs/design-studio/bin/python}"

FILES=(bin/ds_update.py installer/make-update-manifest.py web/src/update.ts
       .github/scripts/fake_github.py .github/scripts/update_e2e_verdict.py)
WORK="$(mktemp -d)"
declare -A BEFORE
for f in "${FILES[@]}"; do
  BEFORE[$f]="$(sha256sum "$f" | cut -d' ' -f1)"
  mkdir -p "$WORK/orig/$(dirname "$f")"
  cp -p "$f" "$WORK/orig/$f"
done
restore() {
  for f in "${FILES[@]}"; do cp -p "$WORK/orig/$f" "$f"; done
  find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
}
trap 'restore; rm -rf "$WORK"' EXIT

bites=0; escapes=0
# mutate <id> <被测文件> <判据:py 模块 | node 文件> <靶子测试名子串> <旧> <新>
mutate() {
  local id="$1" file="$2" oracle="$3" target="$4" old="$5" new="$6"
  restore
  "$PY" - "$file" "$old" "$new" <<'PYEOF' || { echo "  [BAD]  $id 变异没打上去"; escapes=$((escapes+1)); return; }
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding="utf-8")
old, new = sys.argv[2], sys.argv[3]
if s.count(old) != 1:
    print(f"    锚点出现 {s.count(old)} 次,不是 1 次:{old!r}")
    sys.exit(1)
p.write_text(s.replace(old, new), encoding="utf-8")
PYEOF
  if [ -n "${MUTATE_ALSO_OLD:-}" ]; then
    "$PY" - "$file" "$MUTATE_ALSO_OLD" "$MUTATE_ALSO_NEW" <<'PYEOF' || { echo "  [BAD]  $id 第二处变异没打上去"; escapes=$((escapes+1)); return; }
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding="utf-8")
old, new = sys.argv[2], sys.argv[3]
if s.count(old) != 1:
    print(f"    锚点出现 {s.count(old)} 次,不是 1 次:{old!r}")
    sys.exit(1)
p.write_text(s.replace(old, new), encoding="utf-8")
PYEOF
  fi
  local out="$WORK/mut-$id.txt" red
  if [[ "$oracle" == *.mjs ]]; then
    node --test "$oracle" > "$out" 2>&1
    red="$(grep -E '^not ok [0-9]+ - ' "$out" | sed -E 's/^not ok [0-9]+ - //')"
    grep -qE '^# fail 0$' "$out" && red=""
  else
    "$PY" -m unittest "$oracle" > "$out" 2>&1
    red="$(grep -E '^(FAIL|ERROR): ' "$out")"
  fi
  if grep -qF -- "$target" <<<"$red"; then
    echo "  [咬住] $id → $target"; bites=$((bites+1))
  elif [ -z "$red" ]; then
    echo "  [漏网] $id 判据全绿 —— $target 没咬住"; escapes=$((escapes+1))
  else
    echo "  [红在别处] $id 红了,但不是 $target"
    head -3 <<<"$red" | sed 's/^/      实际红的:/'
    escapes=$((escapes+1))
  fi
}

SRC=tests.test_ds_update_source
echo "== ds_update 订阅源 / 清单 / 回落 / 人话 / 代理 =="
mutate r1 bin/ds_update.py $SRC test_rl2_the_highest_version_wins_not_the_first_entry \
  '        if ver is not None and (best_ver is None or ver > best_ver):' \
  '        if ver is not None and best_ver is None:'
mutate r2 bin/ds_update.py $SRC test_rl4_when_the_feed_works_the_api_is_never_asked \
  '        if result.get("error"):
            reasons.append("%s:%s" % (label, result["error"]))
            continue
        return result' \
  '        if result.get("error") or label == FEED_LABEL:
            reasons.append("%s:%s" % (label, result["error"]))
            continue
        return result'
mutate r3 bin/ds_update.py $SRC test_rl5a_feed_down_falls_back_to_the_api \
  '                           (API_LABEL, lambda: _via_releases(current, fetch_releases))):' \
  '                           ):'
mutate r4 bin/ds_update.py $SRC test_rl6_not_newer_means_up_to_date_without_fetching_a_manifest \
  '    if here is not None and best_ver <= here:' \
  '    if False:'
mutate r5 bin/ds_update.py $SRC test_rl3c_every_mismatch_is_refused \
  '    if not tag_m or m.get("tag") != tag:' \
  '    if not tag_m:'
mutate r6 bin/ds_update.py $SRC test_rl3c_every_mismatch_is_refused \
  '    if not isinstance(sha, str) or not _HEX64_RE.match(sha):' \
  '    if not isinstance(sha, str):'
mutate r7 bin/ds_update.py $SRC test_rl3b_tag_text_is_used_verbatim_in_the_url \
  '        "browser_download_url": "%s/%s/releases/download/%s/%s" % (WEB_BASE, repo, tag, name),' \
  '        "browser_download_url": "%s/%s/releases/download/%s/%s" % (WEB_BASE, repo, "win-installer-" + ".".join(str(n) for n in parse_version(tag)), name.replace(version, ".".join(str(n) for n in parse_version(tag)))),'
mutate r8 bin/ds_update.py $SRC test_rl7a_rate_limit_is_explained \
  '        if exc.code == 429 or (exc.code == 403 and "rate limit" in said):' \
  '        if False:'
mutate r9 bin/ds_update.py $SRC test_rl8a_api \
  '    return urllib.request.build_opener().open(req, timeout=timeout)' \
  '    return urllib.request.urlopen(req, timeout=timeout)'
mutate r10 bin/ds_update.py $SRC test_rl8e_manifest_is_asked_for_as_a_file_not_as_json \
  '    return _get_text(manifest_url(repo, tag), "application/octet-stream", timeout)' \
  '    return _get_text(manifest_url(repo, tag), "application/json", timeout)'
mutate r11 bin/ds_update.py $SRC test_rl9_injected_fetch_never_touches_the_feed \
  '    if fetch is not None:
        try:' \
  '    if False:
        try:'
mutate r12 bin/ds_update.py $SRC test_rl1b_other_tags_are_dropped \
  '            if m and TAG_RE.match(m.group(1)):' \
  '            if m:'
mutate r13 bin/ds_update.py $SRC test_rl5c_both_down_says_both_reasons_and_offers_nothing \
  '    return _failure(current, "查更新失败:" + ";".join(reasons))' \
  '    return _failure(current, "查更新失败:" + reasons[-1])'
mutate r14 bin/ds_update.py $SRC test_rl8b_feed \
  '    return _get_text(atom_url(repo), "application/atom+xml", timeout)' \
  '    return urllib.request.urlopen(urllib.request.Request(atom_url(repo)), timeout=timeout).read().decode("utf-8")'

mutate r15 bin/ds_update.py tests.test_ds_update_source test_rl7c_garbage_body_is_explained_not_dumped \
  '    elif isinstance(exc, (json.JSONDecodeError, UnicodeDecodeError)):' \
  '    elif False:'

echo "== 发版清单生成脚本 =="
mutate n1 installer/make-update-manifest.py tests.test_update_manifest test_rl10a_digest_and_size_come_from_the_file_itself \
  '        "asset": {"name": name, "size": size, "sha256": h.hexdigest()},' \
  '        "asset": {"name": name, "size": size, "sha256": hashlib.sha256(name.encode()).hexdigest()},'
# n2 两道都拆:脚本自己的"文件名与标签版本一致"检查,和写出前用产品 parse_manifest 的自核。
#    单拆任何一道,另一道照样拒 ⇒ 判据照绿(09-15 首跑 n2 只拆第一道、漏网,核实是冗余不是没钉住)。
MUTATE_ALSO_OLD='    try:
        ds_update.parse_manifest(text, args.tag)
    except ValueError as exc:' MUTATE_ALSO_NEW='    try:
        pass
    except ValueError as exc:' \
mutate n2 installer/make-update-manifest.py tests.test_update_manifest test_rl10b_tag_and_file_name_must_agree \
  '    if not name_m or not tag_m or name_m.group(1) != tag_m.group(1):' \
  '    if not name_m or not tag_m:'

echo "== 界面原因 =="
mutate u1 web/src/update.ts tests/test_update_ui.mjs "rl11b" \
  '  if (!s.info) return "软件后台没响应";' \
  '  if (!s.info) return "";'
mutate u2 web/src/update.ts tests/test_update_ui.mjs "rl11a" \
  '  return s.info.error ? s.info.error : "";' \
  '  return "";'

echo "== Windows e2e 替身 / 判定器 =="
H=tests.test_update_e2e_harness
mutate h1 .github/scripts/fake_github.py $H test_h6b_feed_mode_manifest_with_json_accept_is_404_like_real_github \
  '                if "json" in (self.headers.get("Accept") or "").lower():' \
  '                if False:'
mutate h2 .github/scripts/fake_github.py $H test_h6c_feed_mode_api_is_rate_limited \
  '                if src == "feed":
                    log({"kind": "releases"' \
  '                if False:
                    log({"kind": "releases"'
mutate h3 .github/scripts/update_e2e_verdict.py $H test_v2_every_break_fails \
  '        if "releases" in kinds:
            problems.append("feed path worked but the app still asked the rate-limited API")' \
  '        if False:
            problems.append("feed path worked but the app still asked the rate-limited API")'
mutate h4 .github/scripts/update_e2e_verdict.py $H test_v2_every_break_fails \
  '        if "releases" not in kinds:
            problems.append("fallback: app never asked the API after the feed failed")' \
  '        if False:
            problems.append("fallback: app never asked the API after the feed failed")'

restore
echo
dirty=0
for f in "${FILES[@]}"; do
  after="$(sha256sum "$f" | cut -d' ' -f1)"
  [ "${BEFORE[$f]}" = "$after" ] || { echo "🔴 $f 没还原干净"; dirty=1; }
done
[ "$dirty" -eq 0 ] || exit 2
echo "== 红检小结:咬住 $bites 条 / 漏网 $escapes 条(被测文件已逐字节还原)=="
[ "$escapes" -eq 0 ] || exit 1
