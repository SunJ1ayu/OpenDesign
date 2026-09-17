#!/usr/bin/env bash
# track opendesign-auto-update-countdown 的后端变异红检(主 agent 亲写)。
# 判据 au* 在实现之前是红的(evidence/oracle-v3-red-python),那只证明"没有实现时红";
# 这里证明**实现错一点点**时它们也红 —— 攻题两轮里点名的几种"看着对、其实错"的写法逐个造出来。
# 每个变异:改 bin/ 下一个文件 → 跑 tests.test_ds_web_auto_update → 期望红在指定用例 → 恢复。
# 跑法:tests/mutation-auto-update-backend.sh(约 2 分钟;工作树 bin/ 要干净)。任何一行漏网 / 没落地 ⇒ 退出码 1。
set -u
cd "$(dirname "$0")/.."
PY="${PY:-/root/.venvs/design-studio/bin/python}"
if [ -n "$(git status --porcelain -- bin)" ]; then echo "bin/ 有没提交的改动,拒跑(跑完会 checkout 回去)"; exit 2; fi
bad=0
restore() { git checkout -q -- bin; }
trap restore EXIT
run() {
  local name="$1" file="$2" expect="$3" old="$4" new="$5"
  restore
  "$PY" - "$file" "$old" "$new" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding="utf-8")
if s.count(sys.argv[2]) != 1:
    print("MUTATION-ANCHOR-MISSING", s.count(sys.argv[2])); sys.exit(3)
p.write_text(s.replace(sys.argv[2], sys.argv[3]), encoding="utf-8")
PY
  [ $? -eq 0 ] || { echo "[$name] 锚点没找到,变异没落地"; bad=1; return; }
  out=$("$PY" -m unittest tests.test_ds_web_auto_update 2>&1)
  if echo "$out" | grep -E "^(FAIL|ERROR): $expect" >/dev/null; then
    echo "[$name] 咬住 ✅ —— $expect 红了"
  else
    echo "[$name] 漏网 ❌ —— $expect 没红"; bad=1
  fi
  echo "$out" | grep -E "^(FAIL|ERROR):|^Ran|^OK|^FAILED" | sed 's/ (tests.*//' | sed 's/^/    /'
}

run B1-record-after-apply bin/ds_web.py "test_au3_" \
'            ok, err = ds_auto_update.record_attempt(paths.get("data_root"), info.get("latest"))
            if not ok:
                return False, {"ok": False, "stage": "auto_unrecorded",
                               "error": err or "自动更新记录写不进去"}
        result = ds_update_apply.apply_update(info, paths)' \
'        result = ds_update_apply.apply_update(info, paths)
        if auto_request:
            ok, err = ds_auto_update.record_attempt(paths.get("data_root"), info.get("latest"))'

run B2-no-fsync bin/ds_auto_update.py "test_au13_" \
'                os.fsync(fh.fileno())' \
'                pass'

run B3-fsync-before-flush bin/ds_auto_update.py "test_au13_" \
'                fh.flush()
                os.fsync(fh.fileno())' \
'                os.fsync(fh.fileno())
                fh.flush()'

run B4-substring-version bin/ds_auto_update.py "test_au9c_" \
'    return attempts.get(version)' \
'    return next((t for k, t in attempts.items() if k in version), None)'

run B5-max-attempted-version bin/ds_auto_update.py "test_au9b_" \
'    return attempts.get(version)' \
'    import ds_update
    mine = ds_update.parse_version(version)
    older = [t for k, t in attempts.items() if ds_update.parse_version(k) and mine and ds_update.parse_version(k) >= mine]
    return max(older) if older else None'

run B6-global-last-attempt-time bin/ds_auto_update.py "test_au15b_" \
'    ts = attempted_at(data_root, version)
    if ts is None:
        return False' \
'    ts = attempted_at(data_root, version)
    if ts is None:
        return False
    ts = max(read_attempts(data_root).values())'

run B7-server-recheck-only-attempted bin/ds_web.py "test_au12c_" \
'        if auto_request:
            auto = _auto_update_status(info, paths)
            if not auto.get("eligible"):' \
'        if auto_request:
            auto = ({"eligible": False, "why_not": "attempted"}
                    if ds_auto_update.attempted_at(paths.get("data_root"), info.get("latest")) is not None
                    else {"eligible": True})
            if not auto.get("eligible"):'

run B8-disabled-before-attempted bin/ds_web.py "test_au14_" \
'        data_root = paths.get("data_root")
        if ds_auto_update.attempted_at(data_root, latest) is not None:' \
'        data_root = paths.get("data_root")
        if (os.environ.get("OPENDESIGN_AUTO_UPDATE") or "").strip().lower() == "off":
            return {"eligible": False, "why_not": "disabled", "recent_failure": False}
        if ds_auto_update.attempted_at(data_root, latest) is not None:'

run B9-get-starts-update bin/ds_web.py "test_au1_" \
'            info["auto_update"] = _auto_update_status(info, paths)' \
'            info["auto_update"] = _auto_update_status(info, paths)
            if info["auto_update"].get("eligible"):
                ds_update_apply.apply_update(info, paths)'

restore
echo "== 后端变异红检结束:$([ $bad -eq 0 ] && echo 全部咬住 || echo 有漏网或没落地)"
exit $bad
