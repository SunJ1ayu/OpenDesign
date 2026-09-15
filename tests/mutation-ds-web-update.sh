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
  '        force = raw_force.strip().lower() in ("1", "true", "yes", "on")' \
  '        force = False'

# n3 本机版本号另写一份(抄第二份迟早对不上)
mutate_and_expect n3 test_t9a_endpoint_answers_with_the_shape_the_ui_needs \
  '        self._json(200, ds_update.check_cached(VERSION, force=force))' \
  '        r = ds_update.check_cached(VERSION, force=force); r["current"] = "0.0.0"
        self._json(200, r)'

# n4 把 GitHub 的原始响应往界面上漏
mutate_and_expect n4 test_t9a_endpoint_answers_with_the_shape_the_ui_needs \
  '        force = raw_force.strip().lower() in ("1", "true", "yes", "on")
        self._json(200, ds_update.check_cached(VERSION, force=force))' \
  '        force = raw_force.strip().lower() in ("1", "true", "yes", "on")
        r = dict(ds_update.check_cached(VERSION, force=force)); r["raw"] = "…整坨响应…"
        self._json(200, r)'

# n5 路由整条拆掉(端点不在了,判据必须全红 —— 靶子取其中一条)
mutate_and_expect n5 test_t9a_endpoint_answers_with_the_shape_the_ui_needs \
  '        elif path == "/api/update/check":
            self._update_check()' \
  '        elif path == "/api/update/check--gone":
            self._update_check()'

# w5 force 判定退回"非空且非 0"(第三轮评审 F6 原样重现:?force=false 也强制)
mutate_and_expect w5 "test_t9e_force_false_is_not_force" \
  '        force = raw_force.strip().lower() in ("1", "true", "yes", "on")' \
  '        force = raw_force not in ("", "0")'

# ── t19:更新收口的 nonce 回显(track opendesign-in-app-update-install)──────

# n6 🔴 压根不回显 ⇒ 客户端那半(t18)变成恒不成功 = 每次更新都判失败、都回滚
mutate_and_expect n6 test_t19a_health_echoes_the_nonce_i_asked_with \
  '            if nonce:
                health["nonce"] = nonce' \
  '            if False:
                health["nonce"] = nonce'

# n7 🔴 没问也回一个固定值 ⇒ 骗得过 t19a,却让 t18 的分辨力归零
#    (旧进程也会答出这个固定值 ⇒ "旧的还在答"永远认不出来)
mutate_and_expect n7 test_t19b_no_nonce_asked_no_nonce_echoed \
  '            nonce = parse_qs(urlsplit(self.path).query).get("nonce", [""])[0]' \
  '            nonce = parse_qs(urlsplit(self.path).query).get("nonce", ["ok"])[0] or "ok"'

# n8 为了塞 nonce 把 version 挤掉(收口判的是两件事,少一件都不算)
mutate_and_expect n8 test_t19c_version_is_still_there \
  '            health = {"ok": True, "version": VERSION,' \
  '            health = {"ok": True,'

# ── t31:同一时间只许一次更新(09-15 收口自审)──────
# n9 🔴 抢不到锁也照样往下走 ⇒ 两次更新并发
mutate_and_expect n9 test_t31a_a_second_apply_while_one_is_running_is_refused \
  '        if not lock.acquire(blocking=False):' \
  '        if not (lock.acquire(blocking=False) or True):'
# n10 失败路上不放锁 ⇒ 一次失败永远锁死(防修过头)
mutate_and_expect n10 test_t31b_a_failed_attempt_does_not_lock_out_the_next_one \
  '            if not keep:
                lock.release()' \
  '            if False:
                lock.release()'
# ── t35:接力脚本起来了就不放锁(09-15 收口外审)──────  (上面 n10 锚点随 started→keep 改名同步)
# n11 🔴 外壳没认动词也放锁 ⇒ 再点一次起第二份接力脚本
mutate_and_expect n11 test_t35a_once_the_relay_is_running_the_lock_is_kept \
  '            return True, {"ok": False, "stage": "shell",' \
  '            return False, {"ok": False, "stage": "shell",'
# n12 修过头:接力脚本根本没起来也留锁 ⇒ 业主再也点不了
mutate_and_expect n12 test_t35b_a_relay_that_never_started_does_not_keep_the_lock \
  '            return False, {"ok": False, "stage": "handoff",' \
  '            return True, {"ok": False, "stage": "handoff",'
# ── t41:先放锁、再回话(09-15 composer 最终总跑 t35b 红一次,探针坐实)──────  (n11/n12 锚点随"返回回包"同步)
# n13 🔴 回包又挪回持锁时写出 ⇒ 回包之后线程被调度走,紧跟着的第二次撞上还没放的锁
mutate_and_expect n13 test_t41b_handoff_failure_reply_means_the_lock_is_already_released \
  '            if not keep:
                lock.release()
        # 🔴 先放锁、再回话(t41)。失败的回包就是在告诉业主「可以再点」;
        #    原来回包在持锁时写出,写 socket 会让出 GIL ⇒ 满载时第二次先到、撞上还没放的锁。
        self._json(200, reply)' \
  '            if reply is not None:
                self._json(200, reply)
            if not keep:
                lock.release()'
# n14 与 n13 **是同一个变异体**(逐字节相同),只是换靶子看 t41a 也红 —— 不是独立的第 15 个变异(评审 r3 DeepSeek 指出)
mutate_and_expect n14 test_t41a_failure_reply_means_the_lock_is_already_released \
  '            if not keep:
                lock.release()
        # 🔴 先放锁、再回话(t41)。失败的回包就是在告诉业主「可以再点」;
        #    原来回包在持锁时写出,写 socket 会让出 GIL ⇒ 满载时第二次先到、撞上还没放的锁。
        self._json(200, reply)' \
  '            if reply is not None:
                self._json(200, reply)
            if not keep:
                lock.release()'

restore
AFTER="$(sha256sum "$SRC" | cut -d' ' -f1)"
echo
if [ "$BEFORE" != "$AFTER" ]; then
  echo "🔴 被测文件没还原干净!before=$BEFORE after=$AFTER"; exit 2
fi
echo "== 红检小结:咬住 $bites 条 / 漏网 $escapes 条(被测文件已逐字节还原)=="
[ "$escapes" -eq 0 ] || exit 1
