#!/usr/bin/env bash
# 红检 —— 证明 tests/test_ds_web_update.py 那 4 条咬得动(track opendesign-in-app-update)。
# 变异被测对象 bin/ds_web.py 的查更新处理函数,每条指定靶子,跑完哈希核对还原。
set -u
cd "$(dirname "$0")/.."
PY="${PY:-/root/.venvs/design-studio/bin/python}"

SRC=bin/ds_web.py
ORACLE=tests.test_ds_web_update
WORK="$(mktemp -d)"
BEFORE="$(sha256sum "$SRC" | cut -d' ' -f1)"
cp -p "$SRC" "$WORK/orig.py"
restore() {
  cp -p "$WORK/orig.py" "$SRC"
  find . -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
}
trap 'restore; rm -rf "$WORK"' EXIT

bites=0; escapes=0
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
    echo "  [咬住] $id → $target"; bites=$((bites+1))
  elif grep -q "^OK" "$out"; then
    echo "  [漏网] $id 判据全绿 —— $target 没咬住"; escapes=$((escapes+1))
  else
    echo "  [红在别处] $id 红了,但不是 $target"
    sed -n 's/^\(FAIL\|ERROR\): \(.*\)$/      实际红的:\2/p' "$out" | head -3
    escapes=$((escapes+1))
  fi
}

echo "== 红检 /api/update/check =="

# n1 🔴 查更新失败时甩 500 给前端(业主什么都没干就看见"出错了")
mutate_and_expect n1 test_t9b_network_failure_is_still_200 \
  '        self._json(200, ds_update.check_cached(VERSION, force=force))' \
  '        r = ds_update.check_cached(VERSION, force=force)
        self._json(500 if r.get("error") else 200, r)'

# n2 业主点「检查更新」也给缓存
mutate_and_expect n2 test_t9c_force_really_asks_again \
  '        force = parse_qs(urlsplit(self.path).query).get("force", ["0"])[0] not in ("", "0")' \
  '        force = False'

# n3 本机版本号另写一份(抄第二份迟早对不上)
mutate_and_expect n3 test_t9a_endpoint_answers_with_the_shape_the_ui_needs \
  '        self._json(200, ds_update.check_cached(VERSION, force=force))' \
  '        r = ds_update.check_cached(VERSION, force=force); r["current"] = "0.0.0"
        self._json(200, r)'

# n4 把 GitHub 的原始响应往界面上漏
mutate_and_expect n4 test_t9a_endpoint_answers_with_the_shape_the_ui_needs \
  '        force = parse_qs(urlsplit(self.path).query).get("force", ["0"])[0] not in ("", "0")
        self._json(200, ds_update.check_cached(VERSION, force=force))' \
  '        force = parse_qs(urlsplit(self.path).query).get("force", ["0"])[0] not in ("", "0")
        r = dict(ds_update.check_cached(VERSION, force=force)); r["raw"] = "…整坨响应…"
        self._json(200, r)'

# n5 路由整条拆掉(端点不在了,判据必须全红 —— 靶子取其中一条)
mutate_and_expect n5 test_t9a_endpoint_answers_with_the_shape_the_ui_needs \
  '        elif path == "/api/update/check":
            self._update_check()' \
  '        elif path == "/api/update/check--gone":
            self._update_check()'

restore
AFTER="$(sha256sum "$SRC" | cut -d' ' -f1)"
echo
if [ "$BEFORE" != "$AFTER" ]; then
  echo "🔴 被测文件没还原干净!before=$BEFORE after=$AFTER"; exit 2
fi
echo "== 红检小结:咬住 $bites 条 / 漏网 $escapes 条(被测文件已逐字节还原)=="
[ "$escapes" -eq 0 ] || exit 1
